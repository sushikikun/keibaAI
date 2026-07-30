from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v231_start_course_pl import (
    aligned_probabilities,
    augment_matrix,
)


class NooddsRawV231StartCoursePlTests(unittest.TestCase):
    def test_augment_matrix_preserves_race_lane_order(self):
        base = np.arange(2 * 6 * 2, dtype=np.float32).reshape(12, 2)
        runner = np.zeros((2, 6, 1), dtype=np.float32)
        runner[0, :, 0] = np.arange(1, 7)
        runner[1, :, 0] = np.arange(11, 17)
        race = np.array([[100.0], [200.0]], dtype=np.float32)
        matrix = augment_matrix(base, runner, race)
        self.assertEqual(matrix.shape, (12, 4))
        np.testing.assert_array_equal(matrix[:6, 2], np.arange(1, 7))
        np.testing.assert_array_equal(matrix[6:, 2], np.arange(11, 17))
        np.testing.assert_array_equal(matrix[:6, 3], 100.0)
        np.testing.assert_array_equal(matrix[6:, 3], 200.0)

    def test_probability_alignment_uses_race_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fold.npz"
            probabilities = np.zeros((3, 120), dtype=np.float32)
            probabilities[:, 0] = [0.1, 0.2, 0.3]
            np.savez_compressed(
                path,
                race_indices=np.array([9, 3, 7], dtype=np.int32),
                ensemble=probabilities,
            )
            with np.load(path) as source:
                aligned = aligned_probabilities(
                    source,
                    np.array([7, 9], dtype=np.int32),
                    "ensemble",
                )
            np.testing.assert_allclose(aligned[:, 0], [0.3, 0.1])


if __name__ == "__main__":
    unittest.main()
