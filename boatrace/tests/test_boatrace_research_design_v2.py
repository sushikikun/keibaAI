from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_boatrace_research_design_v2_package import (  # noqa: E402
    MODEL_SPECS,
    validate_package,
)


class ResearchDesignV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.research = ROOT / "research"
        if not cls.research.exists():
            raise unittest.SkipTest("research package has not been built")

    def test_machine_validation_and_hashes(self) -> None:
        result = validate_package(self.research)
        self.assertEqual(result["status"], "pass", result["errors"])
        self.assertEqual(result["manifest_hash_errors"], [])
        self.assertEqual(result["checks"]["hypothesis_id_duplicate_count"], 0)
        self.assertEqual(result["checks"]["orphan_hypothesis_count"], 0)
        self.assertEqual(result["checks"]["dependency_cycle_count"], 0)
        self.assertEqual(result["checks"]["immutable_anchor_change_count"], 0)
        self.assertEqual(result["checks"]["prohibited_inference_feature_count"], 0)

    def test_registry_contract(self) -> None:
        registry = json.loads(
            (self.research / "hypothesis_registry_v2.json").read_text(encoding="utf-8")
        )
        hypotheses = registry["hypotheses"]
        self.assertEqual(len(hypotheses), 33)
        self.assertEqual(
            sum(item["tier"] == "core_decision" for item in hypotheses), 25
        )
        self.assertTrue(all(item["primary_metric"].endswith("trifecta_log_loss") for item in hypotheses))
        self.assertTrue(
            all(item["rejection_condition"] for item in hypotheses if item["tier"] == "core_decision")
        )

    def test_core_experiments_isolate_one_hypothesis(self) -> None:
        document = json.loads(
            (self.research / "core_decision_experiments_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(document["experiments"]), 25)
        self.assertTrue(
            all(len(item["hypothesis_ids"]) == 1 for item in document["experiments"])
        )
        self.assertTrue(all(item["changed_dimension"] for item in document["experiments"]))

    def test_data_classes_and_current_future_separation(self) -> None:
        with (self.research / "data_gap_matrix_v1.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            gaps = list(csv.DictReader(handle))
        self.assertTrue(gaps)
        self.assertTrue(all(item["availability_class"] in "ABCDE" for item in gaps))
        with (self.research / "feature_research_map_v1.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            features = list(csv.DictReader(handle))
        current = [item for item in features if item["current_or_future"] == "current_v0_1"]
        future = [item for item in features if item["current_or_future"] == "future_as_of"]
        oracle = [item for item in features if item["current_or_future"] == "oracle_only"]
        self.assertEqual(len(current), 49)
        self.assertGreater(len(future), 20)
        self.assertEqual(len(oracle), 2)
        self.assertTrue(all(item["inference_allowed"] == "false" for item in oracle))

    def test_stage_gates_and_model_specs(self) -> None:
        gates = json.loads(
            (self.research / "research_stage_gates_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual([item["gate_id"] for item in gates["gates"]], [f"Gate{i}" for i in range(7)])
        self.assertEqual(gates["gates"][0]["current_status"], "active")
        self.assertTrue(all(item["current_status"] == "closed" for item in gates["gates"][1:]))
        actual_specs = {
            path.name for path in (self.research / "model_family_specs").glob("*.md")
        }
        self.assertEqual(actual_specs, set(MODEL_SPECS))

    def test_readiness_says_no_training(self) -> None:
        report = json.loads(
            (self.research / "pre_research_readiness_report_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["current_gate"], "Gate0")
        self.assertEqual(report["readiness_decision"], "NOT_READY_FOR_MODEL_RESEARCH")
        self.assertEqual(report["immutability_check"]["result"], "pass")
        self.assertEqual(report["official_window_change_proposal"]["snapshot_changes"], 0)


if __name__ == "__main__":
    unittest.main()
