import unittest

import numpy as np

from train_same_day_surprise_residual_v218 import (
    build_surprise_features,
    candidate_features,
)


class SameDaySurpriseOnV270Tests(unittest.TestCase):
    def test_screen_selection_keeps_skipped_prior_race_history(self):
        probs = np.full((3, 120), 1.0 / 120.0)
        indices = np.asarray([0, 1, 2], dtype=np.int64)
        meta = [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": str(i)}
            for i in (1, 2, 3)
        ]
        target_a = np.asarray([0, 1, 2], dtype=np.int64)
        target_b = np.asarray([0, 119, 2], dtype=np.int64)

        runner_a, race_a = build_surprise_features(probs, target_a, indices, meta)
        runner_b, race_b = build_surprise_features(probs, target_b, indices, meta)
        screen_positions = np.asarray([0, 2], dtype=np.int64)
        screen_a = candidate_features(runner_a, race_a, screen_positions)
        screen_b = candidate_features(runner_b, race_b, screen_positions)

        np.testing.assert_allclose(screen_a[0], screen_b[0])
        self.assertGreater(float(np.abs(screen_a[1] - screen_b[1]).sum()), 0.0)

    def test_current_result_cannot_change_current_or_prior_features(self):
        probs = np.full((3, 120), 1.0 / 120.0)
        indices = np.asarray([0, 1, 2], dtype=np.int64)
        meta = [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": str(i)}
            for i in (1, 2, 3)
        ]
        target_a = np.asarray([0, 1, 2], dtype=np.int64)
        target_b = np.asarray([0, 119, 2], dtype=np.int64)

        runner_a, race_a = build_surprise_features(probs, target_a, indices, meta)
        runner_b, race_b = build_surprise_features(probs, target_b, indices, meta)

        np.testing.assert_allclose(runner_a[:2], runner_b[:2])
        np.testing.assert_allclose(race_a[:2], race_b[:2])


if __name__ == "__main__":
    unittest.main()
