from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v215_seed_ensemble import (  # noqa: E402
    LISTWISE_WEIGHT,
    align_rows,
    ensemble_probabilities,
    fixed_blend,
)


class SeedEnsembleV215Tests(unittest.TestCase):
    def test_align_rows_uses_race_indices(self) -> None:
        values = np.asarray([[10.0], [20.0], [30.0]])
        source = np.asarray([7, 2, 9])
        target = np.asarray([9, 7])
        np.testing.assert_array_equal(
            align_rows(values, source, target), np.asarray([[30.0], [10.0]])
        )

    def test_probability_ensemble_and_fixed_blend_are_normalized(self) -> None:
        first = np.asarray([[3.0, 2.0, 1.0, 0.0, -1.0, -2.0]])
        second = -first
        listwise = ensemble_probabilities([first, second])
        self.assertEqual(listwise.shape, (1, 120))
        self.assertAlmostEqual(float(listwise.sum()), 1.0, places=12)

        baseline = np.full((1, 120), 1.0 / 120.0)
        blended = fixed_blend(listwise, baseline)
        np.testing.assert_allclose(
            blended,
            LISTWISE_WEIGHT * listwise + (1.0 - LISTWISE_WEIGHT) * baseline,
        )
        self.assertAlmostEqual(float(blended.sum()), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
