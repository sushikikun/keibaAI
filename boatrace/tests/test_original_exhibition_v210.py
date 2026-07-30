from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_live_feature_input import parse_start_display_official_html
from collect_original_exhibition_v210 import OUTPUT_COLUMNS, parse_table


class ExhibitionParsingTests(unittest.TestCase):
    def test_start_display_course_uses_html_block_order(self):
        blocks = []
        for lane, st in [(1, ".01"), (2, ".02"), (3, ".17"), (4, "F.06"), (6, ".05"), (5, ".04")]:
            blocks.append(
                "<div class=\"table1_boatImage1\">"
                f"<span class=\"table1_boatImage1Number is-type{lane}\">{lane}</span>"
                f"<span style=\"left: 50%\"></span>"
                f"<span class=\"table1_boatImage1Time\">{st}</span>"
                "</div>"
            )
        rows = parse_start_display_official_html("".join(blocks))
        self.assertEqual(rows[6]["start_display_course"], 5)
        self.assertEqual(rows[5]["start_display_course"], 6)
        self.assertEqual(rows[4]["start_display_st_text"], "F.06")

    def test_original_exhibition_parser_keeps_measured_columns_only(self):
        frame = pd.DataFrame(
            {
                "\u67a0": [1, 2, 3, 4, 5, 6],
                "ST": [".07", ".09", ".02", "F.01", "F.02", "F.01"],
                "\u5c55\u793a \u30bf\u30a4\u30e0": [6.86, 6.75, 6.93, 6.84, 6.82, 6.85],
                "\u4e00\u5468": [37.23, 36.83, 38.12, 37.43, 38.02, 37.73],
                "\u307e\u308f\u308a\u8db3": [6.70, 6.27, 6.68, 6.40, 6.32, 6.27],
                "\u76f4\u7dda": [7.25, 7.33, 7.50, 7.38, 7.30, 7.44],
                "\u30c1\u30eb\u30c8": [-0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )
        rows = parse_table(
            frame,
            date(2026, 5, 9),
            6,
            "https://example.invalid",
            "2026-07-11T00:00:00+00:00",
        )
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[3]["start_display_st"], -0.01)
        self.assertEqual(rows[1]["turn_time"], 6.27)
        self.assertFalse(any("odds" in column.lower() for column in OUTPUT_COLUMNS))


if __name__ == "__main__":
    unittest.main()
