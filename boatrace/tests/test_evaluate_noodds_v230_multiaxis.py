import unittest

import numpy as np

from evaluate_noodds_v230_multiaxis import (
    distribution_metrics,
    stage_probabilities,
)


class V230MultiaxisTests(unittest.TestCase):
    def test_stage_losses_reconstruct_trifecta_loss(self):
        rng = np.random.default_rng(2301)
        probs = rng.random((8, 120))
        probs /= probs.sum(axis=1, keepdims=True)
        target = np.arange(8, dtype=np.int64)

        result = stage_probabilities(probs, target)

        self.assertLess(
            result["reconstruction_error_vs_trifecta_nll"],
            1.0e-12,
        )

    def test_distribution_metrics_are_finite(self):
        probs = np.full((4, 120), 1.0 / 120.0)
        target = np.asarray([0, 1, 2, 3], dtype=np.int64)

        result = distribution_metrics(probs, target)

        self.assertAlmostEqual(result["log_loss"], np.log(120.0))
        self.assertAlmostEqual(result["mean_max_probability"], 1.0 / 120.0)
        self.assertAlmostEqual(result["mean_normalized_entropy"], 1.0)


if __name__ == "__main__":
    unittest.main()
