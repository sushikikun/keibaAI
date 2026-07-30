from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
REHEARSAL = (
    ROOT
    / "results"
    / "boatrace_model_research"
    / "temporal_rehearsal"
    / "research_v0_1"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


class HypothesisRehearsalV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (REHEARSAL / "rehearsal_manifest.json").exists():
            raise unittest.SkipTest("rehearsal package has not been built")
        cls.report = json.loads(
            (REHEARSAL / "rehearsal_report.json").read_text(encoding="utf-8")
        )

    def test_manifest_and_protected_hashes(self) -> None:
        manifest = json.loads(
            (REHEARSAL / "rehearsal_manifest.json").read_text(encoding="utf-8")
        )
        errors = []
        for item in manifest["artifacts"]:
            path = ROOT / item["path"]
            if not path.exists():
                errors.append(f"missing {item['path']}")
            elif sha256(path) != item["sha256"]:
                errors.append(f"hash mismatch {item['path']}")
        for item in manifest["implementation_files"]:
            path = ROOT / item["path"]
            if sha256(path) != item["sha256"]:
                errors.append(f"implementation mismatch {item['path']}")
        self.assertEqual(errors, [])
        self.assertEqual(manifest["protected_inputs"]["changed_paths"], [])

    def test_all_hypotheses_and_core_blockers(self) -> None:
        records = list(rows(RESEARCH / "hypothesis_execution_readiness_v1.csv"))
        self.assertEqual(len(records), 33)
        self.assertEqual(len({item["hypothesis_id"] for item in records}), 33)
        core = [item for item in records if item["tier"] == "core_decision"]
        self.assertEqual(len(core), 25)
        self.assertTrue(all(item["blocker_ids"] for item in core))
        allowed = {
            "ready_after_final_snapshot",
            "ready_after_meeting_materialization",
            "blocked_by_equipment_generation",
            "blocked_by_external_data",
            "late_stage_optional",
            "not_applicable",
        }
        self.assertTrue(all(item["readiness_state"] in allowed for item in records))

    def test_feature_tiers_are_disjoint(self) -> None:
        document = json.loads(
            (RESEARCH / "feature_set_tiers_v1.json").read_text(encoding="utf-8")
        )
        ids = []
        for tier in document["tiers"]:
            ids.extend(item["feature_id"] for item in tier["features"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(document["validation"]["cross_tier_overlap_count"], 0)
        self.assertFalse(document["eligible_for_model_training"])

    def test_rehearsal_counts_and_metadata(self) -> None:
        expected = {
            "meeting_episode_candidates.csv": "meeting_episode_candidate_rows",
            "same_day_sequence.csv": "same_day_sequence_rows",
            "same_day_previous_result_candidates.csv": "same_day_previous_result_candidate_rows",
            "race_stage_materialized.csv": "race_stage_rows",
            "temporal_exceptions.csv": "temporal_exception_rows",
        }
        for filename, report_key in expected.items():
            count = 0
            for item in rows(REHEARSAL / filename):
                count += 1
                self.assertEqual(item["status"], "provisional")
                self.assertEqual(item["eligible_for_model_training"], "false")
                self.assertEqual(item["purpose"], "policy_execution_validation")
            self.assertEqual(count, self.report["row_counts"][report_key])
        self.assertEqual(self.report["row_counts"]["meeting_episode_candidate_rows"], 148956)
        self.assertEqual(self.report["row_counts"]["race_stage_rows"], 148956)

    def test_same_day_has_no_result_join_or_future_leak(self) -> None:
        for item in rows(REHEARSAL / "same_day_previous_result_candidates.csv"):
            self.assertEqual(item["source_actual_result_used"], "false")
            self.assertLess(int(item["prior_race_no"]), int(item["target_race_no"]))
            self.assertEqual(item["same_date"], "true")
            self.assertEqual(item["same_venue"], "true")
            self.assertEqual(item["same_racer_id"], "true")
        self.assertEqual(self.report["validation"]["same_day_future_leakage_count"], 0)

    def test_review_and_equipment_queues_are_complete(self) -> None:
        subtitles = list(rows(RESEARCH / "subtitle_review_queue_v1.csv"))
        equipment = list(rows(RESEARCH / "equipment_boundary_evidence_queue_v1.csv"))
        self.assertEqual(len(subtitles), 595)
        self.assertEqual(len(equipment), 3240)
        cumulative = [float(item["cumulative_race_coverage"]) for item in subtitles]
        self.assertEqual(cumulative, sorted(cumulative))
        self.assertAlmostEqual(cumulative[-1], 1.0, places=12)
        self.assertTrue(all(item["current_evidence_level"] == "D" for item in equipment))
        self.assertEqual(self.report["validation"]["equipment_generation_id_issued_count"], 0)
        self.assertEqual(self.report["validation"]["meeting_exception_without_reason_count"], 0)


if __name__ == "__main__":
    unittest.main()
