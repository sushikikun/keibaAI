import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v200 import A, B, C
from train_noodds_raw_v243_identity_autoregressive_transformer import exact_top3_loss
from train_noodds_raw_v249_pairwise_relational_ar import PairwiseRelationalAutoregressiveTransformer


def make_model():
    return PairwiseRelationalAutoregressiveTransformer(9, 5, [20, 4, 8, 8], [7, 5])


def test_pair_messages_exclude_self_and_keep_runner_shape():
    torch.manual_seed(1)
    model = make_model()
    raw = torch.randn(3, 6, 64)
    messages = model.pair_messages(raw)
    assert messages.shape == (3, 6, 64)
    assert torch.isfinite(messages).all()


def test_pair_network_receives_gradient_and_probabilities_sum_to_one():
    torch.manual_seed(2)
    model = make_model()
    model.eval()
    n = 3
    runner_num = torch.randn(n, 6, 9)
    runner_cat = torch.stack(
        [torch.randint(0, card, (n, 6)) for card in [20, 4, 8, 8]], dim=2
    )
    race_num = torch.randn(n, 5)
    race_cat = torch.stack(
        [torch.randint(0, card, (n,)) for card in [7, 5]], dim=1
    )
    targets = torch.tensor([[0, 1, 2], [1, 2, 3], [5, 4, 3]])
    hidden = model.encode(runner_num, runner_cat, race_num, race_cat)
    loss = exact_top3_loss(model, hidden, targets)
    loss.backward()
    assert model.pair_mlp[0].weight.grad is not None
    assert torch.isfinite(model.pair_mlp[0].weight.grad).all()

    with torch.no_grad():
        p1 = torch.softmax(model.stage1(hidden), dim=1)
        totals = []
        for row in range(n):
            total = 0.0
            for a, b, c in zip(A, B, C):
                first = torch.tensor([int(a)])
                second = torch.tensor([int(b)])
                p2 = torch.softmax(model.stage2(hidden[row:row + 1], first), dim=1)[0, b]
                p3 = torch.softmax(model.stage3(hidden[row:row + 1], first, second), dim=1)[0, c]
                total += float(p1[row, a] * p2 * p3)
            totals.append(total)
    np.testing.assert_allclose(totals, np.ones(n), atol=1e-5)
