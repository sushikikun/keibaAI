import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_v290_anchored_set_residual_on_v283 import (
    AnchoredSetResidual,
    anchored_probabilities,
    candidate_residual,
    fit_normalization,
    training_folds_for_target,
    transform_features,
)

ARCH = {
    "runner_projection_width": 8,
    "attention_heads": 2,
    "feedforward_width": 16,
    "dropout": 0.0,
    "transformer_layers": 1,
}


class AnchoredSetResidualTests(unittest.TestCase):
    def test_zero_initialized_heads_reproduce_parent(self):
        torch.manual_seed(1)
        model = AnchoredSetResidual(5, 3, ARCH).eval()
        runner = torch.randn(4, 6, 5)
        race = torch.randn(4, 3)
        parent = torch.softmax(torch.randn(4, 120), dim=1)
        with torch.no_grad():
            residual = candidate_residual(model(runner, race))
            actual = anchored_probabilities(parent, residual)
        self.assertTrue(torch.equal(residual, torch.zeros_like(residual)))
        self.assertTrue(torch.allclose(actual, parent, atol=1e-7, rtol=1e-6))

    def test_candidate_residual_has_120_centered_logits(self):
        residual = candidate_residual(torch.randn(3, 3, 6))
        self.assertEqual(tuple(residual.shape), (3, 120))
        self.assertTrue(torch.allclose(residual.mean(1), torch.zeros(3), atol=1e-6))

    def test_runner_storage_permutation_is_equivariant(self):
        torch.manual_seed(2)
        model = AnchoredSetResidual(4, 2, ARCH).eval()
        runner = torch.randn(2, 6, 4)
        race = torch.randn(2, 2)
        permutation = torch.tensor([2, 5, 1, 4, 0, 3])
        with torch.no_grad():
            original = model(runner, race)
            permuted = model(runner[:, permutation], race, permutation)
        self.assertTrue(torch.allclose(permuted, original[:, :, permutation], atol=1e-6))

    def test_normalization_is_fit_only_from_supplied_training_rows(self):
        train = [{
            "runner_numeric": np.full((2, 6, 2), 2.0, dtype=np.float32),
            "race_numeric": np.full((2, 1), 3.0, dtype=np.float32),
        }]
        stats = fit_normalization(train)
        self.assertTrue(np.array_equal(stats["runner_mean"], np.array([2.0, 2.0])))
        self.assertTrue(np.array_equal(stats["race_mean"], np.array([3.0])))

    def test_missing_values_are_zero_with_explicit_masks(self):
        fold = {
            "runner_numeric": np.array([[[np.nan, 2.0]] * 6], dtype=np.float32),
            "race_numeric": np.array([[np.nan, 4.0]], dtype=np.float32),
        }
        stats = {
            "runner_mean": np.array([0.0, 2.0], dtype=np.float32),
            "runner_std": np.ones(2, dtype=np.float32),
            "race_mean": np.array([0.0, 4.0], dtype=np.float32),
            "race_std": np.ones(2, dtype=np.float32),
        }
        runner, race = transform_features(fold, stats)
        self.assertTrue(np.all(runner[:, :, :2] == 0.0))
        self.assertTrue(np.all(runner[:, :, 2] == 1.0))
        self.assertTrue(np.all(runner[:, :, 3] == 0.0))
        self.assertTrue(np.array_equal(
            race, np.array([[0.0, 0.0, 1.0, 0.0]], dtype=np.float32)
        ))

    def test_training_history_is_strictly_chronological(self):
        self.assertEqual(training_folds_for_target("d6"), ())
        self.assertEqual(training_folds_for_target("d7"), ("d6",))
        self.assertEqual(training_folds_for_target("d8"), ("d6", "d7"))

    def test_anchored_probabilities_are_normalized(self):
        parent = torch.softmax(torch.randn(5, 120), dim=1)
        probability = anchored_probabilities(parent, torch.randn(5, 120))
        self.assertTrue(torch.all(probability > 0))
        self.assertTrue(torch.allclose(probability.sum(1), torch.ones(5), atol=1e-6))


if __name__ == "__main__":
    unittest.main()
