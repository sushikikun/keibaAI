from __future__ import annotations

import csv
import json
import math
import unittest
from pathlib import Path

from boatrace_model_research.class_map import load_class_map
from boatrace_model_research.outcome_audit_v0_1 import (
    KNOWN_RACE_KEYS,
    classify_outcome,
    theoretical_uniform_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = (
    PROJECT_ROOT / "results/boatrace_model_research/audits/research_v0_1"
)
V0_SNAPSHOT = (
    PROJECT_ROOT
    / "results/boatrace_model_research/snapshots/research_v0_136183_55f32b3538a9"
)


def _result(places: list[int], combinations: list[str]) -> dict:
    return {
        "boats": [
            {
                "racer_boat_number": lane,
                "racer_place_number": place,
            }
            for lane, place in enumerate(places, start=1)
        ],
        "payouts": {
            "trifecta": [
                {"combination": combination, "amount": 1000}
                for combination in combinations
            ]
        },
    }


class OutcomeClassificationTest(unittest.TestCase):
    def test_standard_unique_order(self) -> None:
        outcome, finishes, top3, payouts = classify_outcome(
            _result([1, 2, 3, 4, 5, 6], ["1-2-3"])
        )
        self.assertEqual(outcome, "unique_order")
        self.assertEqual(finishes, ("1", "2", "3", "4", "5", "6"))
        self.assertEqual(top3, (1, 2, 3))
        self.assertEqual(payouts, ("1-2-3",))

    def test_unique_top3_with_abnormal_lower_finish(self) -> None:
        outcome, _, top3, payouts = classify_outcome(
            _result([14, 1, 5, 2, 4, 3], ["2-4-6"])
        )
        self.assertEqual(outcome, "unique_top3_abnormal")
        self.assertEqual(top3, (2, 4, 6))
        self.assertEqual(payouts, ("2-4-6",))

    def test_tied_retains_multiple_winning_combinations(self) -> None:
        outcome, _, top3, payouts = classify_outcome(
            _result([6, 1, 5, 2, 2, 4], ["2-4-5", "2-5-4"])
        )
        self.assertEqual(outcome, "tied")
        self.assertIsNone(top3)
        self.assertEqual(payouts, ("2-4-5", "2-5-4"))

    def test_uniform_theory(self) -> None:
        metrics = theoretical_uniform_metrics()
        expected = {
            "trifecta_log_loss": math.log(120),
            "winner_log_loss": math.log(6),
            "exacta_log_loss": math.log(30),
            "top3_set_log_loss": math.log(20),
            "second_given_first_log_loss": math.log(5),
            "third_given_first_second_log_loss": math.log(4),
            "trifecta_brier": 119 / 120,
        }
        for name, value in expected.items():
            self.assertAlmostEqual(metrics[name], value, places=14)

    def test_class_map_round_trip_all_120(self) -> None:
        class_map = load_class_map(
            PROJECT_ROOT / "configs/trifecta_class_map_v1.json"
        )
        self.assertEqual(len(class_map.orders), 120)
        for class_id in range(120):
            self.assertEqual(class_map.encode(class_map.decode(class_id)), class_id)


@unittest.skipUnless(AUDIT_DIR.is_dir(), "real-data v0.1 audit has not been built")
class RealDataAuditSanityTest(unittest.TestCase):
    def test_known_six_trace(self) -> None:
        with (AUDIT_DIR / "known_outcome_trace.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = {row["race_key"]: row for row in csv.DictReader(handle)}
        self.assertEqual(set(rows), set(KNOWN_RACE_KEYS))
        for race_key in KNOWN_RACE_KEYS:
            self.assertEqual(rows[race_key]["raw_result_exists"], "true")
            self.assertEqual(rows[race_key]["audit_candidate_exists"], "true")
            self.assertEqual(rows[race_key]["research_v0_snapshot_exists"], "false")
            self.assertEqual(rows[race_key]["prediction_input_eligible"], "true")
        for race_key in KNOWN_RACE_KEYS[:5]:
            self.assertEqual(rows[race_key]["outcome_type"], "tied")
            self.assertEqual(rows[race_key]["main_one_hot_scorable"], "false")
        abnormal = rows[KNOWN_RACE_KEYS[5]]
        self.assertEqual(abnormal["outcome_type"], "unique_top3_abnormal")
        self.assertEqual(abnormal["main_one_hot_scorable"], "true")
        self.assertEqual(abnormal["trifecta_winning_combinations"], "2-4-6")

    def test_population_and_coverage(self) -> None:
        coverage = json.loads(
            (AUDIT_DIR / "coverage_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(coverage["counts"]["candidate_universe"], 148956)
        self.assertEqual(coverage["counts"]["prediction_eligible"], 144961)
        self.assertEqual(coverage["counts"]["scorable"], 144611)
        self.assertAlmostEqual(
            coverage["coverage"]["scorable_to_prediction_artifact_rate"],
            1.0,
            places=15,
        )
        self.assertEqual(
            coverage["missing"]["prediction_eligible_missing_from_v0_1_artifact"],
            [],
        )

    def test_no_target_mismatches(self) -> None:
        with (AUDIT_DIR / "target_mismatches.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows, [])

    def test_uniform_and_oracle(self) -> None:
        uniform = json.loads(
            (AUDIT_DIR / "uniform_sanity_report.json").read_text(encoding="utf-8")
        )
        oracle = json.loads(
            (AUDIT_DIR / "oracle_sanity_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(uniform["qualification_status"], "passed")
        self.assertTrue(uniform["all_within_tolerance"])
        self.assertEqual(oracle["qualification_status"], "passed")
        self.assertEqual(oracle["metrics"]["trifecta_log_loss"], 0.0)
        self.assertEqual(oracle["metrics"]["trifecta_brier_score"], 0.0)
        self.assertEqual(oracle["metrics"]["hit_at_1"], 1.0)
        self.assertEqual(oracle["metrics"]["actual_combo_rank"], 1.0)

    def test_v0_immutable_hash_attestation(self) -> None:
        manifest = json.loads(
            (AUDIT_DIR / "audit_manifest.json").read_text(encoding="utf-8")
        )
        attestation = manifest["v0_immutability"]
        self.assertTrue(attestation["verified_unchanged"])
        self.assertEqual(attestation["files_before"], attestation["files_after"])
        current = {
            path.relative_to(V0_SNAPSHOT).as_posix()
            for path in V0_SNAPSHOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(current, set(attestation["files_after"]))


if __name__ == "__main__":
    unittest.main()
