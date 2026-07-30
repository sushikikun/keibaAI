from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research" / "equipment_generation_official_evidence_import_v1" / "equipment_generation_import_report_v1.md"


class ImportReportTest(unittest.TestCase):
    def test_report_contains_required_research_controls(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        for expected in [
            "47/48",
            "54",
            "46",
            "蒲郡",
            "桐生 boat",
            "planned_not_applied",
            "formal generation ID は0件",
            "既存 readiness は変更せず",
        ]:
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
