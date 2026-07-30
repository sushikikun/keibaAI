from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_same_day_residual_v209_d9 import residual_scores  # noqa: E402


class FakeBooster:
    def predict(self, matrix: np.ndarray) -> np.ndarray:
        return np.arange(len(matrix), dtype=np.float64)


class SameDayV209D9Tests(unittest.TestCase):
    def test_residual_scores_are_centered_per_race(self) -> None:
        features = np.zeros((2, 120, 3), dtype=np.float32)
        values = residual_scores(FakeBooster(), features)
        self.assertEqual(values.shape, (2, 120))
        np.testing.assert_allclose(values.mean(axis=1), 0.0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
