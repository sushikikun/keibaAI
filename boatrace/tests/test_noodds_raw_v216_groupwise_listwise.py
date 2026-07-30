from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v216_groupwise_listwise import (  # noqa: E402
    append_groupwise_context,
    fixed_blend,
)


class GroupwiseListwiseV216Tests(unittest.TestCase):
    def test_context_columns_keep_absolute_lane_semantics(self) -> None:
        base = np.arange(12, dtype=np.float32).reshape(6, 2)
        context = np.arange(1, 7, dtype=np.float32).reshape(1, 6, 1)
        matrix, names = append_groupwise_context(
            base, context, ("ability",)
        )
        self.assertEqual(matrix.shape, (6, 14))
        self.assertEqual(len(names), 12)
        self.assertEqual(names[0], "ctx_lane1_ability")
        self.assertEqual(names[1], "ctx_candidate_minus_lane1_ability")
        self.assertEqual(names[-2], "ctx_lane6_ability")
        self.assertEqual(
            names[-1], "ctx_candidate_minus_lane6_ability"
        )

        candidate_lane3 = matrix[2, 2:]
        np.testing.assert_allclose(
            candidate_lane3,
            np.asarray(
                [1, 2, 2, 1, 3, 0, 4, -1, 5, -2, 6, -3],
                dtype=np.float32,
            ),
        )

    def test_fixed_blend_is_normalized(self) -> None:
        groupwise = np.zeros((1, 120), dtype=np.float64)
        groupwise[0, 0] = 1.0
        baseline = np.full((1, 120), 1.0 / 120.0)
        blended = fixed_blend(groupwise, baseline)
        self.assertAlmostEqual(float(blended.sum()), 1.0, places=12)
        self.assertGreater(blended[0, 0], baseline[0, 0])


if __name__ == "__main__":
    unittest.main()
