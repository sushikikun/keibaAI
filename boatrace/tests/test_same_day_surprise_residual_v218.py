import unittest

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_same_day_surprise_residual_v218 import (
    build_surprise_features,
    trifecta_marginals,
)


class SameDaySurpriseResidualTests(unittest.TestCase):
    def test_trifecta_marginals_have_expected_mass(self):
        probs = np.full((2, 120), 1.0 / 120.0)

        first, top3 = trifecta_marginals(probs)

        np.testing.assert_allclose(first.sum(axis=1), 1.0)
        np.testing.assert_allclose(top3.sum(axis=1), 3.0)
        np.testing.assert_allclose(first, 1.0 / 6.0)
        np.testing.assert_allclose(top3, 0.5)

    def test_current_result_cannot_change_current_features(self):
        probs = np.full((2, 120), 1.0 / 120.0)
        race_indices = np.asarray([0, 1], dtype=np.int32)
        meta = [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": "1"},
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": "2"},
        ]
        target_a = np.asarray([0, 1], dtype=np.int64)
        target_b = np.asarray([0, 119], dtype=np.int64)

        runner_a, race_a = build_surprise_features(
            probs, target_a, race_indices, meta
        )
        runner_b, race_b = build_surprise_features(
            probs, target_b, race_indices, meta
        )

        np.testing.assert_allclose(runner_a, runner_b)
        np.testing.assert_allclose(race_a, race_b)
        np.testing.assert_allclose(runner_a[0], 0.0)
        np.testing.assert_allclose(race_a[0], 0.0)
        self.assertGreater(float(np.abs(runner_a[1]).sum()), 0.0)
        self.assertGreater(float(np.abs(race_a[1]).sum()), 0.0)

        first_lane = int(A[target_a[0]])
        top3_lanes = {
            int(A[target_a[0]]),
            int(B[target_a[0]]),
            int(C[target_a[0]]),
        }
        self.assertIn(first_lane, top3_lanes)
