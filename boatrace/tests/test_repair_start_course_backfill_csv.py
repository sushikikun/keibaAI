from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from backfill_start_display_course_official import OUTPUT_FIELDS  # noqa: E402
from repair_start_course_backfill_csv import repair_bytes  # noqa: E402


def make_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def race_rows(key: str, lanes: range = range(1, 7)) -> list[dict]:
    result = []
    for lane in lanes:
        result.append(
            {
                "race_key": key,
                "db_race_key": key,
                "race_date": "2026-07-11",
                "venue_code": "01",
                "race_no": "1",
                "lane": str(lane),
                "start_display_course": str(lane),
                "start_display_st_text": f"0.{lane:02d}",
                "source_url": "https://example.test",
                "source_sha256": "abc",
                "fetched_at_utc": "2026-07-11T00:00:00+00:00",
            }
        )
    return result


class RepairStartCourseCsvTests(unittest.TestCase):
    def test_drops_incomplete_race_and_deduplicates_exact_lane(self) -> None:
        complete = race_rows("20260711_01_01")
        duplicate = dict(complete[0])
        duplicate["fetched_at_utc"] = "2026-07-11T00:01:00+00:00"
        incomplete = race_rows("20260711_02_01", range(1, 2))
        raw = make_csv(complete + [duplicate] + incomplete)
        raw = raw.replace(b"20260711_02_01", b"\x00\x0020260711_02_01")

        clean, report = repair_bytes(raw)
        self.assertEqual(report["accepted_races"], 1)
        self.assertEqual(report["accepted_rows"], 6)
        self.assertEqual(report["rejected_races"], 1)
        self.assertEqual(report["duplicate_rows_removed"], 1)
        self.assertEqual(report["nul_bytes_removed"], 4)
        self.assertNotIn(b"\x00", clean)

        rows = list(
            csv.DictReader(
                io.StringIO(clean.decode("utf-8-sig"), newline="")
            )
        )
        self.assertEqual(len(rows), 6)
        self.assertEqual({row["race_key"] for row in rows}, {"20260711_01_01"})


if __name__ == "__main__":
    unittest.main()
