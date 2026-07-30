import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_v279_conditional_order_residual_on_v270 import (
    compose_conditionals,
    parent_conditionals,
)
from train_noodds_v291_nested_conditional_calibration_on_v283 import (
    calibrate_probability,
    fit_stage,
    stage_training_view,
    training_folds_for_target,
)


def random_parent(rows=12, seed=3):
    rng = np.random.default_rng(seed)
    probability = rng.gamma(1.5, 1.0, size=(rows, 120))
    return probability / probability.sum(axis=1, keepdims=True)


class NestedConditionalCalibrationTests(unittest.TestCase):
    def test_parent_factorization_reconstructs_all_120(self):
        parent = random_parent()
        actual = compose_conditionals(*parent_conditionals(parent))
        self.assertTrue(np.allclose(actual, parent, atol=1e-12, rtol=1e-10))

    def test_identity_parameters_reproduce_parent(self):
        parent = random_parent()
        identity = [{"alpha": 1.0, "bias": [0.0] * 6}] * 3
        actual = calibrate_probability(parent, identity)
        self.assertTrue(np.allclose(actual, parent, atol=1e-12, rtol=1e-10))

    def test_stage_masks_keep_true_context_and_expected_choices(self):
        parent = random_parent(120)
        target = np.arange(120, dtype=np.int64)
        expected = (6, 5, 4)
        for stage, choices in enumerate(expected):
            _, mask, lane = stage_training_view(parent, target, stage)
            self.assertTrue(np.all(mask[np.arange(len(target)), lane]))
            self.assertTrue(np.all(mask.sum(axis=1) == choices))

    def test_fitted_lane_bias_is_centered(self):
        parent = random_parent(120)
        target = np.arange(120, dtype=np.int64)
        cfg = {
            "probability_floor": 1e-15,
            "threads": 1,
            "seed": 29101,
            "max_iterations": 5,
            "history_size": 5,
            "line_search": "strong_wolfe",
            "tolerance_grad": 1e-9,
            "tolerance_change": 1e-11,
            "l2_alpha_toward_one": 0.01,
            "l2_lane_bias_toward_zero": 0.01,
        }
        result = fit_stage(parent, target, 0, cfg)
        self.assertTrue(np.isfinite(result["alpha"]))
        self.assertAlmostEqual(float(np.mean(result["bias"])), 0.0, places=12)

    def test_training_history_is_strictly_chronological(self):
        self.assertEqual(training_folds_for_target("d6"), ())
        self.assertEqual(training_folds_for_target("d7"), ("d6",))
        self.assertEqual(training_folds_for_target("d8"), ("d6", "d7"))

    def test_calibrated_probabilities_are_normalized(self):
        parent = random_parent()
        params = [
            {"alpha": 0.9, "bias": [-0.05, -0.03, -0.01, 0.01, 0.03, 0.05]},
            {"alpha": 1.1, "bias": [0.02, -0.02, 0.01, -0.01, 0.03, -0.03]},
            {"alpha": 1.0, "bias": [0.0] * 6},
        ]
        actual = calibrate_probability(parent, params)
        self.assertTrue(np.all(actual > 0))
        self.assertTrue(np.allclose(actual.sum(axis=1), 1.0, atol=1e-12))


if __name__ == "__main__":
    unittest.main()
