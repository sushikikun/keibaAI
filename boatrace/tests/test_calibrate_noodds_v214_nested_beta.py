from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from calibrate_noodds_v214_nested_beta import (
    IDENTITY,
    beta_transform,
)


class NestedBetaCalibrationV214Tests(unittest.TestCase):
    def test_identity_preserves_distribution(self):
        probs = np.asarray(
            [[0.6, 0.3, 0.1], [0.02, 0.18, 0.8]],
            dtype=np.float64,
        )
        np.testing.assert_allclose(
            beta_transform(probs, IDENTITY),
            probs,
            atol=1e-12,
        )

    def test_transform_preserves_order_and_normalizes(self):
        probs = np.asarray([[0.7, 0.2, 0.1]], dtype=np.float64)
        transformed = beta_transform(
            probs, np.asarray([1.2, -0.8, 0.1])
        )
        np.testing.assert_allclose(transformed.sum(axis=1), 1.0)
        self.assertEqual(
            transformed[0].argsort().tolist(),
            probs[0].argsort().tolist(),
        )


if __name__ == "__main__":
    unittest.main()
