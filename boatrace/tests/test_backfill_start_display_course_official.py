from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from backfill_start_display_course_official import (
    Target,
    normalized_target,
    validate_start_rows,
)


class StartCourseBackfillTests(unittest.TestCase):
    def test_normalizes_unpadded_db_date(self):
        target = normalized_target(
            "2024129_02_01", "2024-12-9", "2", 1
        )
        self.assertEqual(target.race_key, "20241209_02_01")
        self.assertEqual(target.race_date, date(2024, 12, 9))
        self.assertEqual(target.db_race_key, "2024129_02_01")

    def test_accepts_complete_course_permutation(self):
        target = Target(
            "20260709_24_01",
            "20260709_24_01",
            date(2026, 7, 9),
            "24",
            1,
        )
        parsed = {
            lane: {
                "start_display_course": course,
                "start_display_st_text": ".10",
            }
            for lane, course in enumerate([1, 2, 3, 4, 6, 5], start=1)
        }
        status, rows, message = validate_start_rows(
            target, parsed, "https://example.test", "now", "abc"
        )
        self.assertEqual(status, "ok")
        self.assertEqual(len(rows), 6)
        self.assertEqual(message, "")

    def test_rejects_duplicate_course(self):
        target = Target(
            "20260709_24_01",
            "20260709_24_01",
            date(2026, 7, 9),
            "24",
            1,
        )
        parsed = {
            lane: {
                "start_display_course": course,
                "start_display_st_text": ".10",
            }
            for lane, course in enumerate([1, 2, 3, 4, 5, 5], start=1)
        }
        status, rows, _message = validate_start_rows(
            target, parsed, "https://example.test", "now", "abc"
        )
        self.assertEqual(status, "invalid_course_permutation")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
