from __future__ import annotations

import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage_start_display_course_db_v213 import (
    apply_rows,
    load_validated_rows,
)


FIELDS = [
    "race_key",
    "db_race_key",
    "race_date",
    "venue_code",
    "race_no",
    "lane",
    "start_display_course",
    "start_display_st_text",
    "source_url",
    "source_sha256",
    "fetched_at_utc",
]


def rows_for_race():
    return [
        {
            "race_key": "20260709_24_01",
            "db_race_key": "202679_24_01",
            "race_date": "2026-07-09",
            "venue_code": "24",
            "race_no": "1",
            "lane": str(lane),
            "start_display_course": str(course),
            "start_display_st_text": ".10",
            "source_url": "https://example.test",
            "source_sha256": "abc",
            "fetched_at_utc": "now",
        }
        for lane, course in enumerate([1, 2, 3, 4, 6, 5], start=1)
    ]


class StageStartCourseDbV213Tests(unittest.TestCase):
    def test_validates_complete_permutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "courses.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows_for_race())
            rows, report = load_validated_rows(
                path, require_all_venues=False
            )
            self.assertEqual(len(rows), 6)
            self.assertEqual(report["races"], 1)
            self.assertEqual(report["venues"], {"24": 1})

    def test_applies_only_to_staging_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "staging.db"
            con = sqlite3.connect(db_path)
            try:
                con.execute(
                    """
                    CREATE TABLE beforeinfo_entries (
                        race_key TEXT NOT NULL,
                        lane INTEGER NOT NULL,
                        start_display_st_text TEXT,
                        PRIMARY KEY (race_key, lane)
                    )
                    """
                )
                con.executemany(
                    "INSERT INTO beforeinfo_entries VALUES (?, ?, ?)",
                    [
                        ("202679_24_01", lane, ".10")
                        for lane in range(1, 7)
                    ],
                )
                con.commit()
            finally:
                con.close()
            report = apply_rows(db_path, rows_for_race())
            self.assertEqual(report["rows_matched"], 6)
            con = sqlite3.connect(db_path)
            try:
                values = [
                    row[0]
                    for row in con.execute(
                        """
                        SELECT start_display_course
                          FROM beforeinfo_entries
                         ORDER BY lane
                        """
                    )
                ]
            finally:
                con.close()
            self.assertEqual(values, [1, 2, 3, 4, 6, 5])


if __name__ == "__main__":
    unittest.main()
