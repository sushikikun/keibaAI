from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_pc_kyotei_c4 import parse_c4_record


class PcKyoteiC4Tests(unittest.TestCase):
    def test_parses_fixed_width_c4_record(self):
        record = (
            b"C4"
            b"0"
            b"2026"
            b"0709"
            b"11"
            b"01"
            b"1"
            b"0000"
            b"3675"
            b"0583"
            b"0742"
            b"\r\n"
        )
        self.assertEqual(len(record), 34)
        row = parse_c4_record(
            record,
            "fixture.c4:1",
            "2026-07-11T00:00:00+00:00",
        )
        self.assertEqual(row["race_key"], "20260709_11_01")
        self.assertEqual(row["venue_name"], "biwako")
        self.assertIsNone(row["half_time"])
        self.assertEqual(row["lap_time"], 36.75)
        self.assertEqual(row["turn_time"], 5.83)
        self.assertEqual(row["straight_time"], 7.42)

    def test_rejects_wrong_record_length(self):
        with self.assertRaises(ValueError):
            parse_c4_record(
                b"C402026070911011367505830742",
                "bad.c4:1",
                "2026-07-11T00:00:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
