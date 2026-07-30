import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v243_identity_autoregressive_transformer import exact_top3_loss
from train_noodds_raw_v246_racer_sequence_ar import SequenceIdentityAutoregressiveTransformer


def make_model():
    return SequenceIdentityAutoregressiveTransformer(9, 5, [20, 4, 8, 8], [7, 5])


def test_empty_history_is_zero_but_real_history_is_encoded():
    torch.manual_seed(1)
    model = make_model()
    sequence = torch.randn(2, 6, 12, 13)
    empty = torch.zeros(2, 6, 12, dtype=torch.bool)
    full = torch.ones(2, 6, 12, dtype=torch.bool)
    assert torch.count_nonzero(model.encode_sequence(sequence, empty)) == 0
    assert torch.count_nonzero(model.encode_sequence(sequence, full)) > 0


def test_loss_masks_gradients_and_exact_probability_sum():
    torch.manual_seed(2)
    model = make_model()
    n = 3
    runner_num = torch.randn(n, 6, 9)
    runner_cat = torch.stack([torch.randint(0, card, (n, 6)) for card in [20, 4, 8, 8]], dim=2)
    race_num = torch.randn(n, 5)
    race_cat = torch.stack([torch.randint(0, card, (n,)) for card in [7, 5]], dim=1)
    sequence = torch.randn(n, 6, 12, 13)
    mask = torch.ones(n, 6, 12, dtype=torch.bool)
    targets = torch.tensor([[0, 1, 2], [1, 2, 3], [5, 4, 3]])
    hidden = model.encode(runner_num, runner_cat, race_num, race_cat, sequence, mask)
    assert hidden.shape == (n, 6, 64)
    assert torch.all(model.stage2(hidden, targets[:, 0]).gather(1, targets[:, :1]) < -1e8)
    assert torch.all(model.stage3(hidden, targets[:, 0], targets[:, 1]).gather(1, targets[:, :1]) < -1e8)
    loss = exact_top3_loss(model, hidden, targets)
    assert torch.isfinite(loss)
    loss.backward()
    assert model.sequence_gru.weight_ih_l0.grad is not None

    model.eval()
    with torch.no_grad():
        first = torch.softmax(model.stage1(hidden), dim=1)
        totals = []
        for row in range(n):
            total = 0.0
            for a in range(6):
                second = torch.softmax(model.stage2(hidden[row:row + 1], torch.tensor([a])), dim=1)[0]
                for b in range(6):
                    if b == a:
                        continue
                    third = torch.softmax(model.stage3(hidden[row:row + 1], torch.tensor([a]), torch.tensor([b])), dim=1)[0]
                    for c in range(6):
                        if c not in (a, b):
                            total += float(first[row, a] * second[b] * third[c])
            totals.append(total)
    np.testing.assert_allclose(totals, np.ones(n), atol=1e-5)
