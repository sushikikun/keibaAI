from __future__ import annotations

import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research" / "gate0_unresolved_reduction_v1"
BUILDER = ROOT / "scripts" / "build_boatrace_gate0_unresolved_reduction_v1.py"


def rows(name: str) -> list[dict[str, str]]:
    with (PACKAGE / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Gate0UnresolvedReductionV1Test(unittest.TestCase):
    def test_required_population_counts_and_metadata(self) -> None:
        expected = {
            "subtitle_p0_review_v1.csv": 53,
            "meeting_unresolved_resolution_v1.csv": 2268,
            "same_day_candidate_reconciliation_v1.csv": 32022,
        }
        for name, count in expected.items():
            value = rows(name)
            self.assertEqual(len(value), count, name)
            self.assertTrue(all(row["status"] == "provisional" for row in value), name)
            self.assertTrue(all(row["eligible_for_model_training"] == "false" for row in value), name)
            self.assertTrue(all(row["purpose"] == "policy_execution_validation" for row in value), name)

    def test_meeting_and_same_day_are_fail_closed(self) -> None:
        meeting = rows("meeting_unresolved_resolution_v1.csv")
        self.assertTrue(all(row["prediction_time_feature_eligibility"] == "false" for row in meeting))
        self.assertTrue(all(row["future_schedule_used_for_identity"] == "false" for row in meeting))
        same_day = rows("same_day_candidate_reconciliation_v1.csv")
        self.assertTrue(all(int(row["prior_race_no"]) < int(row["target_race_no"]) for row in same_day))
        self.assertTrue(all(row["source_actual_result_used_for_feature"] == "false" for row in same_day))

    def test_no_generation_id_and_manifest_validation(self) -> None:
        equipment = rows("equipment_evidence_batch_queue_v1.csv")
        self.assertTrue(equipment)
        self.assertTrue(all(row["generation_id_issued"] == "false" for row in equipment))
        self.assertTrue(all(row["potential_generation_count"] == "unknown_not_issued" for row in equipment))
        completed = subprocess.run(
            [sys.executable, str(BUILDER), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["valid"])
        self.assertEqual(result["protected_anchor_mismatch_count"], 0)
        self.assertEqual(result["artifact_hash_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
