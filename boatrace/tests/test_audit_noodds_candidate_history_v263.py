from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_noodds_candidate_history_v263 import candidate_status, holm_adjust


class EvaluationProtocolV3Tests(unittest.TestCase):
    def test_holm_adjustment_is_monotone_and_controls_family(self):
        result = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.03})
        self.assertAlmostEqual(result["a"]["holm_adjusted_p"], 0.003)
        self.assertAlmostEqual(result["b"]["holm_adjusted_p"], 0.04)
        self.assertAlmostEqual(result["c"]["holm_adjusted_p"], 0.04)
        ordered = [
            result[name]["holm_adjusted_p"]
            for name in ("a", "b", "c")
        ]
        self.assertEqual(ordered, sorted(ordered))

    def test_promotion_requires_mean_ci_and_holm(self):
        self.assertEqual(
            candidate_status(-0.001, (-0.002, -0.0001), True),
            "promoted_development_challenger",
        )
        self.assertEqual(
            candidate_status(-0.001, (-0.002, 0.0001), True),
            "point_better_unconfirmed",
        )
        self.assertEqual(
            candidate_status(-0.001, (-0.002, -0.0001), False),
            "point_better_unconfirmed",
        )
        self.assertEqual(
            candidate_status(0.001, (0.0001, 0.002), False),
            "worse_than_champion",
        )


if __name__ == "__main__":
    unittest.main()
