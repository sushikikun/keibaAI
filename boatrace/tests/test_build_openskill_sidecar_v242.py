from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_openskill_sidecar_v242 import (
    FEATURE_NAMES,
    build_skill_features,
    ranks_for_finish,
    relative_features,
)


class BuildOpenSkillSidecarV242Tests(unittest.TestCase):
    def test_complete_and_partial_rank_policy(self):
        ranks, complete = ranks_for_finish(
            np.array([1, 2, 3, 4, 5, 6])
        )
        self.assertTrue(complete)
        self.assertEqual(ranks, [1, 2, 3, 4, 5, 6])
        ranks, complete = ranks_for_finish(
            np.array([1, 2, 3, 0, 0, 0])
        )
        self.assertFalse(complete)
        self.assertEqual(ranks, [1, 2, 3, 4, 4, 4])

    def test_partial_rank_requires_unique_top_three(self):
        with self.assertRaisesRegex(ValueError, "unique top three"):
            ranks_for_finish(np.array([1, 2, 0, 0, 0, 0]))

    def test_relative_features_center_and_rank(self):
        difference, z, rank = relative_features(
            np.array([6, 5, 4, 3, 2, 1], dtype=float)
        )
        self.assertAlmostEqual(float(difference.mean()), 0.0)
        self.assertAlmostEqual(float(z.mean()), 0.0)
        np.testing.assert_allclose(
            rank,
            np.arange(1, 7, dtype=float) / 6.0,
        )

    def test_relative_ties_receive_average_rank(self):
        _difference, _z, rank = relative_features(
            np.ones(6, dtype=float)
        )
        np.testing.assert_allclose(
            rank, np.full(6, 3.5 / 6.0)
        )
    def test_same_day_results_do_not_change_same_day_features(self):
        racers = np.array(
            [
                ["a", "b", "c", "d", "e", "f"],
                ["a", "b", "c", "d", "e", "f"],
                ["a", "b", "c", "d", "e", "f"],
            ],
            dtype=object,
        )
        finishes = np.array(
            [
                [1, 2, 3, 4, 5, 6],
                [1, 2, 3, 4, 5, 6],
                [1, 2, 3, 4, 5, 6],
            ],
            dtype=np.int8,
        )
        dates = np.array([1, 1, 2], dtype=np.int32)
        features, summary = build_skill_features(
            racers, finishes, dates
        )
        self.assertEqual(features.shape, (3, 6, len(FEATURE_NAMES)))
        np.testing.assert_allclose(features[0], features[1])
        mu_index = FEATURE_NAMES.index("openskill_mu")
        ordinal_index = FEATURE_NAMES.index("openskill_ordinal")
        self.assertGreater(
            features[2, 0, mu_index], features[2, 5, mu_index]
        )
        self.assertGreater(
            features[2, 0, ordinal_index],
            features[2, 5, ordinal_index],
        )
        self.assertEqual(summary["complete_order_updates"], 3)
        self.assertEqual(summary["partial_top3_tied_bottom_updates"], 0)


if __name__ == "__main__":
    unittest.main()
