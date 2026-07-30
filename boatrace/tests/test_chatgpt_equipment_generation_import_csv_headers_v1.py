from __future__ import annotations

import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "research" / "equipment_generation_official_evidence_import_v1" / "local_input_reconciliation_v1.csv"


class ImportCsvHeadersTest(unittest.TestCase):
    def test_local_input_reconciliation_has_unique_nonempty_headers(self) -> None:
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
        self.assertTrue(header)
        self.assertEqual(len(header), len(set(header)))
        self.assertNotIn("", header)
        self.assertEqual(header.count("status"), 1)


if __name__ == "__main__":
    unittest.main()
