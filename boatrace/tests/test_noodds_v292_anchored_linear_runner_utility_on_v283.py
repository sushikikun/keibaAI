import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_v290_anchored_set_residual_on_v283 import (
    anchored_probabilities,
    candidate_residual,
)
from train_noodds_v292_anchored_linear_runner_utility_on_v283 import (
    LinearRunnerUtility,
    fit_stats,
    training_folds_for_target,
    transform,
)


class AnchoredLinearRunnerUtilityTests(unittest.TestCase):
    def test_zero_initialization_reproduces_parent(self):
        model = LinearRunnerUtility(12).eval()
        runner = torch.randn(5, 6, 12)
        parent = torch.softmax(torch.randn(5, 120), dim=1)
        with torch.no_grad():
            residual = candidate_residual(model(runner))
            actual = anchored_probabilities(parent, residual)
        self.assertTrue(torch.equal(residual, torch.zeros_like(residual)))
        self.assertTrue(torch.allclose(actual, parent, atol=1e-7, rtol=1e-6))

    def test_model_has_only_linear_head_parameters(self):
        model = LinearRunnerUtility(12)
        self.assertEqual(set(dict(model.named_parameters())), {"weight", "lane_bias"})
        self.assertEqual(tuple(model.weight.shape), (3, 12))
        self.assertEqual(tuple(model.lane_bias.shape), (3, 6))

    def test_fit_stats_uses_only_supplied_training_folds(self):
        fold = {"numeric": np.full((2, 6, 3), [1.0, 2.0, 3.0], dtype=np.float32)}
        mean, std = fit_stats([fold])
        self.assertTrue(np.array_equal(mean, np.array([1.0, 2.0, 3.0], dtype=np.float32)))
        self.assertTrue(np.array_equal(std, np.ones(3, dtype=np.float32)))

    def test_transform_adds_missing_masks_and_lane_identity(self):
        numeric = np.zeros((1, 6, 2), dtype=np.float32)
        numeric[0, 2, 0] = np.nan
        fold = {"numeric": numeric}
        value = transform(fold, (np.zeros(2, dtype=np.float32), np.ones(2, dtype=np.float32)))
        self.assertEqual(tuple(value.shape), (1, 6, 10))
        self.assertEqual(value[0, 2, 0], 0.0)
        self.assertEqual(value[0, 2, 2], 1.0)
        self.assertTrue(np.array_equal(value[0, :, -6:], np.eye(6, dtype=np.float32)))

    def test_candidate_residual_has_120_centered_logits(self):
        residual = candidate_residual(torch.randn(4, 3, 6))
        self.assertEqual(tuple(residual.shape), (4, 120))
        self.assertTrue(torch.allclose(residual.mean(1), torch.zeros(4), atol=1e-6))

    def test_training_history_is_strictly_chronological(self):
        self.assertEqual(training_folds_for_target("d6"), ())
        self.assertEqual(training_folds_for_target("d7"), ("d6",))
        self.assertEqual(training_folds_for_target("d8"), ("d6", "d7"))

    def test_anchored_probabilities_are_normalized(self):
        parent = torch.softmax(torch.randn(5, 120), dim=1)
        residual = torch.randn(5, 120)
        actual = anchored_probabilities(parent, residual)
        self.assertTrue(torch.all(actual > 0))
        self.assertTrue(torch.allclose(actual.sum(1), torch.ones(5), atol=1e-6))


if __name__ == "__main__":
    unittest.main()
