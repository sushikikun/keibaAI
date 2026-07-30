from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_pc_kyotei_c3 import (
    OUTPUT_COLUMNS,
    parse_c3_record,
    race_completeness,
    update_database,
)


def make_record(
    lane: int, course: int, st: str = "016", symbol: str = " "
) -> bytes:
    record = (
        b"C3" b"0" b"2026" b"0709" b"11" b"01"
        + str(lane).encode("ascii")
        + b"4444" b"523" b"005" b"-05" b"6743" b"0"
        + b"00000000" b"202607081101"
        + str(course).encode("ascii")
        + st.encode("ascii")
        + symbol.encode("ascii")
        + b"\r\n"
    )
    assert len(record) == 61
    return record


class PcKyoteiC3Tests(unittest.TestCase):
    def test_parses_fixed_width_c3_record(self):
        row = parse_c3_record(
            make_record(1, 2, "006", "F"),
            "fixture.c3:1",
            "2026-07-11T00:00:00+00:00",
        )
        self.assertEqual(row["race_key"], "20260709_11_01")
        self.assertEqual(row["venue_name"], "biwako")
        self.assertEqual(row["body_weight"], 52.3)
        self.assertEqual(row["adjust_weight"], 0.5)
        self.assertEqual(row["tilt"], -0.5)
        self.assertEqual(row["exhibition_time"], 6.743)
        self.assertEqual(row["start_display_course"], 2)
        self.assertEqual(row["start_display_st"], 0.06)
        self.assertEqual(row["start_display_st_text"], "F.06")

    def test_detects_six_lane_course_permutation(self):
        rows = [
            parse_c3_record(
                make_record(lane, course), "fixture",
                "2026-07-11T00:00:00+00:00",
            )
            for lane, course in enumerate([1, 2, 3, 4, 6, 5], start=1)
        ]
        quality = race_completeness(
            pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
        ).iloc[0]
        self.assertEqual(quality["row_count"], 6)
        self.assertTrue(quality["course_complete"])
        self.assertTrue(quality["permutation"])

    def test_updates_existing_beforeinfo_rows(self):
        row = parse_c3_record(
            make_record(1, 2), "fixture", "2026-07-11T00:00:00+00:00"
        )
        frame = pd.DataFrame([row], columns=OUTPUT_COLUMNS)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as con:
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
                con.execute(
                    "INSERT INTO beforeinfo_entries VALUES (?, ?, ?)",
                    (row["race_key"], 1, ".15"),
                )
                con.commit()
            report = update_database(db_path, frame)
            with closing(sqlite3.connect(db_path)) as con:
                stored = con.execute(
                    """
                    SELECT start_display_course, start_display_st_text
                    FROM beforeinfo_entries
                    """
                ).fetchone()
            self.assertEqual(stored, (2, ".15"))
            self.assertEqual(report["db_course_rows_updated"], 1)

    def test_rejects_wrong_record_length(self):
        with self.assertRaises(ValueError):
            parse_c3_record(
                b"C302026070911011", "bad.c3:1",
                "2026-07-11T00:00:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
