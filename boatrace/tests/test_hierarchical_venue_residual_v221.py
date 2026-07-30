import unittest

import numpy as np

from train_hierarchical_venue_residual_v221 import (
    build_hierarchical_features,
)


class HierarchicalVenueResidualTests(unittest.TestCase):
    def test_same_day_results_are_blocked_but_prior_day_is_visible(self):
        probs = np.full((3, 120), 1.0 / 120.0)
        target_a = np.asarray([0, 1, 2], dtype=np.int64)
        target_b = np.asarray([119, 1, 2], dtype=np.int64)
        race_indices = np.asarray([0, 1, 2], dtype=np.int32)
        meta = [
            {
                "race_date": "2026-01-01",
                "venue_code": "1",
                "race_no": "1",
            },
            {
                "race_date": "2026-01-01",
                "venue_code": "1",
                "race_no": "2",
            },
            {
                "race_date": "2026-01-02",
                "venue_code": "1",
                "race_no": "1",
            },
        ]

        features_a = build_hierarchical_features(
            probs, target_a, race_indices, meta
        )
        features_b = build_hierarchical_features(
            probs, target_b, race_indices, meta
        )

        np.testing.assert_allclose(features_a[:2], 0.0)
        np.testing.assert_allclose(features_b[:2], 0.0)
        self.assertGreater(float(np.abs(features_a[2]).sum()), 0.0)
        self.assertGreater(
            float(np.abs(features_a[2] - features_b[2]).sum()),
            0.0,
        )

    def test_other_venue_does_not_share_residual_state(self):
        probs = np.full((2, 120), 1.0 / 120.0)
        target = np.asarray([0, 1], dtype=np.int64)
        race_indices = np.asarray([0, 1], dtype=np.int32)
        meta = [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": "1"},
            {"race_date": "2026-01-02", "venue_code": "2", "race_no": "1"},
        ]

        features = build_hierarchical_features(
            probs, target, race_indices, meta
        )

        np.testing.assert_allclose(features, 0.0)


if __name__ == "__main__":
    unittest.main()
