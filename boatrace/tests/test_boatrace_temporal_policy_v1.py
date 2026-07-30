from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"


def load_json(name: str):
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def load_csv(name: str):
    with (RESEARCH / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class TemporalPolicyV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (RESEARCH / "temporal_policy_manifest_v1.json").exists():
            raise unittest.SkipTest("temporal policy package has not been built")

    def test_manifest_hashes_and_validation(self) -> None:
        manifest = load_json("temporal_policy_manifest_v1.json")
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
        validation = load_json("temporal_policy_validation_v1.json")
        self.assertEqual(validation["status"], "pass", validation["errors"])
        self.assertEqual(validation["checks"]["protected_anchor_change_count"], 0)

    def test_unknown_equipment_boundaries_are_not_filled(self) -> None:
        rows = load_csv("equipment_generation_evidence_registry_v1.csv")
        self.assertEqual(len(rows), 3240)
        self.assertEqual({row["evidence_level"] for row in rows}, {"D"})
        self.assertTrue(all(not row["generation_start_date"] for row in rows))
        self.assertTrue(all(not row["generation_id_candidate"] for row in rows))
        self.assertTrue(all(row["generation_identity_usable"] == "false" for row in rows))
        self.assertEqual({row["equipment_type"] for row in rows}, {"motor", "boat"})
        self.assertEqual(len({row["venue_code"] for row in rows}), 24)

    def test_same_day_policy_closes_direct_result_join(self) -> None:
        policy = load_json("same_day_previous_result_policy_v1.json")
        required = set(policy["eligibility_predicates"])
        self.assertTrue(
            {
                "same_calendar_date",
                "same_venue_code",
                "same_racer_id",
                "prior_race_number_less_than_target_race_number",
                "prior_race_finish_before_semantic_availability",
                "previous_result_is_printed_in_target_race_official_beforeinfo",
                "semantic_available_at_no_later_than_target_prediction_cutoff",
            }.issubset(required)
        )
        self.assertIn(
            "direct_join_from_final_result_table_without_publication_time",
            policy["forbidden_paths"],
        )
        self.assertIn(
            "target_or_later_race_result",
            policy["forbidden_paths"],
        )

    def test_official_columns_and_subtitle_universe(self) -> None:
        windows = load_csv("official_stat_window_mapping_v1.csv")
        current = [row for row in windows if row["in_v0_1_snapshot"] == "true"]
        future_fl = [row for row in windows if row["official_stat_family"] == "flying_late"]
        self.assertEqual(len(current), 10)
        self.assertEqual(len(future_fl), 2)
        self.assertTrue(all(row["schema_mapping_confirmed"] == "true" for row in windows))
        self.assertTrue(all(row["snapshot_modified"] == "false" for row in windows))
        taxonomy = load_csv("race_stage_taxonomy_v1.csv")
        self.assertEqual(len(taxonomy), 595)
        self.assertTrue(all(row["normalized_stage"] for row in taxonomy))
        self.assertEqual(sum(row["raw_value_is_null"] == "true" for row in taxonomy), 1)
        self.assertTrue(
            all(
                row["review_status"] in {
                    "manual_seed_reviewed",
                    "auto_rule_unreviewed",
                    "unknown_unreviewed",
                }
                for row in taxonomy
            )
        )

    def test_allocation_is_provenance_only(self) -> None:
        rows = load_csv("allocation_process_regime_registry_v1.csv")
        self.assertTrue(rows)
        self.assertTrue(all(row["role"] == "provenance_only" for row in rows))
        self.assertTrue(all(row["prediction_feature_allowed"] == "false" for row in rows))
        per_venue = [row for row in rows if row["scope"] == "venue_status"]
        self.assertEqual(len(per_venue), 24)
        self.assertTrue(all(row["regime"] == "unknown" for row in per_venue))
        self.assertTrue(all(not row["effective_date"] for row in per_venue))

    def test_readiness_dimensions_have_reason_codes(self) -> None:
        document = load_json("readiness_dimensions_v2.json")
        expected = {
            "research_design_ready",
            "evaluation_contract_ready",
            "target_pipeline_ready",
            "data_collection_complete",
            "equipment_identity_ready",
            "meeting_temporal_semantics_ready",
            "same_day_feature_policy_ready",
            "official_window_provenance_ready",
            "formal_model_research_ready",
        }
        self.assertEqual(set(document["dimensions"]), expected)
        self.assertTrue(
            all(value["reason_codes"] for value in document["dimensions"].values())
        )
        self.assertFalse(
            document["dimensions"]["formal_model_research_ready"]["ready"]
        )


if __name__ == "__main__":
    unittest.main()
