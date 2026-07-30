from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_noodds_v214_external import period_relation  # noqa: E402


class ExternalV214Tests(unittest.TestCase):
    def test_period_relation_blocks_same_day_as_forward(self) -> None:
        frozen = date(2026, 7, 11)
        self.assertEqual(
            period_relation(date(2026, 7, 2), date(2026, 7, 9), frozen),
            "pre_freeze_retrospective",
        )
        self.assertEqual(
            period_relation(date(2026, 7, 11), date(2026, 7, 11), frozen),
            "overlaps_freeze_date",
        )
        self.assertEqual(
            period_relation(date(2026, 7, 12), date(2026, 7, 12), frozen),
            "post_freeze_forward",
        )


if __name__ == "__main__":
    unittest.main()
