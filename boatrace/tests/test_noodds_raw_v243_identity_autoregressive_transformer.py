from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "<CODEX_HOME>_deps"))
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v243_identity_autoregressive_transformer import (
    IdentityAutoregressiveTransformer,
    exact_top3_loss,
    predict_distribution,
    safe_categories,
    set_seed,
)


class NooddsRawV243IdentityARTransformerTests(unittest.TestCase):
    def make_model(self):
        set_seed(24301, 1)
        return IdentityAutoregressiveTransformer(
            runner_numeric_width=5,
            race_numeric_width=3,
            runner_cards=[8, 5, 12, 12],
            race_cards=[25, 64],
        )

    def make_tensors(self, races=3):
        generator = torch.Generator().manual_seed(7)
        runner_num = torch.randn(races, 6, 5, generator=generator)
        runner_cat = torch.zeros(races, 6, 4, dtype=torch.long)
        race_num = torch.randn(races, 3, generator=generator)
        race_cat = torch.zeros(races, 2, dtype=torch.long)
        targets = torch.tensor([[0, 1, 2]] * races, dtype=torch.long)
        return runner_num, runner_cat, race_num, race_cat, targets

    def test_selected_lanes_are_masked(self):
        model = self.make_model()
        tensors = self.make_tensors(2)
        hidden = model.encode(*tensors[:4])
        first = torch.tensor([1, 4])
        second = torch.tensor([2, 0])
        stage2 = model.stage2(hidden, first)
        stage3 = model.stage3(hidden, first, second)
        self.assertTrue(torch.all(stage2[torch.arange(2), first] < -1e8))
        self.assertTrue(torch.all(stage3[torch.arange(2), first] < -1e8))
        self.assertTrue(torch.all(stage3[torch.arange(2), second] < -1e8))

    def test_distribution_is_finite_and_normalized(self):
        model = self.make_model()
        probs = predict_distribution(model, self.make_tensors(3), 2)
        self.assertEqual(probs.shape, (3, 120))
        self.assertTrue(np.isfinite(probs).all())
        self.assertTrue((probs > 0).all())
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-10)

    def test_loss_is_finite_and_backward_works(self):
        model = self.make_model()
        tensors = self.make_tensors(2)
        hidden = model.encode(*tensors[:4])
        loss = exact_top3_loss(model, hidden, tensors[4])
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertTrue(any(p.grad is not None for p in model.parameters()))

    def test_seed_reproduces_initial_predictions(self):
        tensors = self.make_tensors(2)
        first = predict_distribution(self.make_model(), tensors, 2)
        second = predict_distribution(self.make_model(), tensors, 2)
        np.testing.assert_array_equal(first, second)

    def test_safe_categories_reserves_zero_for_missing(self):
        values = np.array(
            [[[0.0, np.nan], [3.0, 8.0]]], dtype=np.float32
        )
        encoded = safe_categories(values, [5, 6])
        np.testing.assert_array_equal(encoded[0, 0], [1, 0])
        np.testing.assert_array_equal(encoded[0, 1], [4, 5])


if __name__ == "__main__":
    unittest.main()
