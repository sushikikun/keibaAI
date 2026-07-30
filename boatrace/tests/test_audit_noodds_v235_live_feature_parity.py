from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_noodds_v235_live_feature_parity import (
    align_reference_rows,
    compare_matrices,
    ordered_schema_hash,
)


class AuditNooddsV235LiveFeatureParityTests(unittest.TestCase):
    def test_aligns_six_rows_per_race_in_candidate_order(self):
        reference = np.arange(4 * 6 * 2).reshape(24, 2)
        aligned = align_reference_rows(
            reference,
            ["a", "b", "c", "d"],
            ["c", "a"],
        )
        np.testing.assert_array_equal(aligned[:6], reference[12:18])
        np.testing.assert_array_equal(aligned[6:], reference[:6])

    def test_matrix_comparison_requires_exact_nan_mask(self):
        reference = np.array([[1.0, np.nan]], dtype=np.float32)
        candidate = np.array([[1.0, 0.0]], dtype=np.float32)
        result = compare_matrices(reference, candidate, 1.0e-6)
        self.assertFalse(result["nan_mask_exact"])
        self.assertFalse(result["passed"])

    def test_matrix_comparison_honors_tolerance(self):
        reference = np.array([[1.0, 2.0]], dtype=np.float32)
        candidate = np.array([[1.0, 2.0 + 5.0e-7]], dtype=np.float32)
        result = compare_matrices(reference, candidate, 1.0e-6)
        self.assertTrue(result["passed"])
        candidate[0, 1] += 2.0e-6
        result = compare_matrices(reference, candidate, 1.0e-6)
        self.assertFalse(result["passed"])

    def test_schema_hash_changes_with_order(self):
        first = ordered_schema_hash(["a", "b"], [0])
        second = ordered_schema_hash(["b", "a"], [0])
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
