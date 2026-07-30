import unittest

import numpy as np

from train_noodds_v268_hierarchical_venue_on_v242 import (
    build_complete_hierarchical_features,
    candidate_features,
)


class HierarchicalVenueOnV242Tests(unittest.TestCase):
    def make_complete(self):
        return {
            "probability": np.full((3, 120), 1.0 / 120.0),
            "target": np.asarray([0, 1, 2], dtype=np.int64),
            "indices": np.asarray([0, 1, 2], dtype=np.int64),
        }

    def make_meta(self):
        return [
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": "1"},
            {"race_date": "2026-01-01", "venue_code": "1", "race_no": "2"},
            {"race_date": "2026-01-02", "venue_code": "1", "race_no": "1"},
        ]

    def test_screen_selection_keeps_skipped_prior_history(self):
        complete = self.make_complete()
        full = build_complete_hierarchical_features(complete, self.make_meta())
        selected = candidate_features(full, np.asarray([2], dtype=np.int64))

        np.testing.assert_allclose(full[:2], 0.0)
        self.assertGreater(float(np.abs(selected).sum()), 0.0)

        subset = {
            "probability": complete["probability"][[2]],
            "target": complete["target"][[2]],
            "indices": complete["indices"][[2]],
        }
        subset_only = build_complete_hierarchical_features(subset, self.make_meta())
        np.testing.assert_allclose(subset_only, 0.0)


if __name__ == "__main__":
    unittest.main()
