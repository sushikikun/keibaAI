from __future__ import annotations

import csv
import json
import math
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from boatrace_model_research.class_map import load_class_map
from boatrace_model_research.common import sha256_file
from boatrace_model_research.evaluation import (
    PROBABILITY_COLUMNS,
    assert_uniform_reference,
    evaluate_predictions,
    generate_uniform_predictions,
    validate_snapshot,
)
from boatrace_model_research.snapshot_runner import build_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _make_fake_corpus(root: Path) -> Path:
    contract = json.loads(
        (PROJECT_ROOT / "configs/boatrace_model_dataset_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )
    race_columns = contract["source_schema"]["race_facts_columns"]
    entry_columns = contract["source_schema"]["entry_facts_columns"]
    corpus = root / "corpus"
    batch_dir = corpus / "batches/20260101"
    batch_dir.mkdir(parents=True)

    race_definitions = [
        ("20260101_01_01", "1", "settled_standard_six_boat", [1, 2, 3, 4, 5, 6]),
        ("20260101_01_02", "2", "settled_standard_six_boat", [1, 2, 2, 4, 5, 6]),
        ("20260101_01_03", "3", "void", [1, 2, 3, 4, 5, 6]),
    ]
    race_rows: list[dict[str, object]] = []
    entry_rows: list[dict[str, object]] = []
    for race_key, race_no, result_status, finishes in race_definitions:
        race = {column: "" for column in race_columns}
        race.update(
            {
                "race_key": race_key,
                "race_date": "2026-01-01",
                "venue_code": "01",
                "race_no": race_no,
                "closed_at": f"2026-01-01 12:{int(race_no) * 10:02d}:00",
                "beforeinfo_time": "11:30",
                "distance": "1800",
                "grade_number": "3",
                "preview_air_temperature": "15.0",
                "preview_water_temperature": "12.0",
                "preview_wave_height": "1",
                "preview_weather": "晴",
                "preview_wind_direction_number": "2",
                "preview_wind_speed": "2",
                "subtitle": "一般",
                "title": "fixture",
                "result_status": result_status,
                "winning_technique_number": "1",
            }
        )
        race_rows.append(race)
        for lane, finish in enumerate(finishes, start=1):
            entry = {column: "" for column in entry_columns}
            entry.update(
                {
                    "race_key": race_key,
                    "race_date": "2026-01-01",
                    "venue_code": "01",
                    "race_no": race_no,
                    "lane": str(lane),
                    "racer_id": str(4000 + lane),
                    "racer_name": f"racer-{lane}",
                    "racer_age": str(30 + lane),
                    "racer_branch_number": "10",
                    "racer_class_number": "3",
                    "average_start_timing": "0.16",
                    "national_top_1_percent": "10.0",
                    "national_top_2_percent": "30.0",
                    "national_top_3_percent": "50.0",
                    "local_top_1_percent": "9.0",
                    "local_top_2_percent": "29.0",
                    "local_top_3_percent": "49.0",
                    "motor_no": str(10 + lane),
                    "motor_top_2_percent": "35.0",
                    "motor_top_3_percent": "52.0",
                    "boat_no": str(20 + lane),
                    "boat_top_2_percent": "33.0",
                    "boat_top_3_percent": "50.0",
                    "program_weight": "52.0",
                    "body_weight": "52.0",
                    "weight_adjustment": "0.0",
                    "exhibition_course": str(lane),
                    "exhibition_start_timing": "0.05",
                    "exhibition_time": "6.80",
                    "tilt": "0.0",
                    "propeller_new": "0",
                    "propeller_status": "none",
                    "parts_exchange_status": "none",
                    "actual_finish": str(finish),
                    "actual_course": str(lane),
                    "actual_start_timing": "0.15",
                }
            )
            entry_rows.append(entry)
    race_path = batch_dir / "race_facts.csv"
    entry_path = batch_dir / "entry_facts.csv"
    _write_csv(race_path, race_columns, race_rows)
    _write_csv(entry_path, entry_columns, entry_rows)
    manifest = {
        "promotion_status": "complete_verified",
        "complete_races": 3,
        "artifact_sha256": {
            "race_facts": sha256_file(race_path),
            "entry_facts": sha256_file(entry_path),
        },
    }
    manifest_path = batch_dir / "batch_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    registry_path = corpus / "integrity_registry.sqlite"
    connection = sqlite3.connect(registry_path)
    connection.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE batches (
            batch TEXT PRIMARY KEY,
            manifest_sha256 TEXT NOT NULL,
            integrity_status TEXT NOT NULL,
            hash_status TEXT NOT NULL,
            complete_races INTEGER NOT NULL,
            entry_rows INTEGER NOT NULL,
            odds_rows INTEGER NOT NULL,
            payout_rows INTEGER NOT NULL,
            errors_json TEXT NOT NULL,
            candidates INTEGER NOT NULL,
            excluded INTEGER NOT NULL,
            reasons_json TEXT NOT NULL
        );
        CREATE TABLE race_owners (
            race_key TEXT PRIMARY KEY,
            batch TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO metadata VALUES (?, ?)",
        ("last_full_audit_at", "2026-01-02T00:00:00+00:00"),
    )
    connection.execute(
        "INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "20260101",
            sha256_file(manifest_path),
            "passed",
            "verified",
            3,
            18,
            360,
            30,
            "[]",
            4,
            1,
            '{"fixture_source_excluded": 1}',
        ),
    )
    connection.executemany(
        "INSERT INTO race_owners VALUES (?, ?)",
        [(definition[0], "20260101") for definition in race_definitions],
    )
    connection.commit()
    connection.close()
    status = {
        "created_at": "2026-01-02T00:00:00+00:00",
        "complete_races": 3,
        "batch_count": 1,
        "candidate_races_audited": 4,
        "excluded_races": 1,
        "exclusion_reasons": {"fixture_source_excluded": 1},
    }
    (corpus / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return corpus


class BoatraceModelResearchV0Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="boatrace-research-v0-")
        cls.root = Path(cls.temporary.name)
        cls.corpus = _make_fake_corpus(cls.root)
        cls.build_result = build_snapshot(
            project_root=PROJECT_ROOT,
            corpus_root=cls.corpus,
            snapshots_root=cls.root / "snapshots",
            snapshot_id="fixture_v0",
            storage_format="csv",
        )
        cls.snapshot = Path(cls.build_result["snapshot_dir"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_class_map_is_frozen_and_round_trips(self) -> None:
        class_map = load_class_map(
            PROJECT_ROOT / "configs/trifecta_class_map_v1.json"
        )
        self.assertEqual(len(class_map.orders), 120)
        self.assertEqual(
            class_map.mapping_sha256,
            "e5b36e44602700d1c50cbd2c839a20328fcc317abc0c7de8388ed1b91d410f50",
        )
        for class_id in range(120):
            order = class_map.decode(class_id)
            self.assertEqual(class_map.encode(order), class_id)

    def test_snapshot_eligibility_and_forbidden_feature_contract(self) -> None:
        validation = validate_snapshot(
            project_root=PROJECT_ROOT,
            snapshot_dir=self.snapshot,
            verify_environment_hashes=True,
        )
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertEqual(validation["counts"]["canonical_races"], 3)
        self.assertEqual(validation["counts"]["prediction_input_eligible"], 3)
        self.assertEqual(validation["counts"]["main_evaluation_eligible"], 1)
        self.assertEqual(
            validation["counts"]["target_status_counts"],
            {"unique_order": 1, "tied": 1, "void": 1},
        )
        self.assertEqual(
            validation["counts"]["exclusion_reason_counts"],
            {"target_tied": 1, "target_void": 1},
        )
        profile = json.loads(
            (self.snapshot / "dataset_profile.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            profile["eligibility"]["target_status_counts"],
            {"unique_order": 1, "tied": 1, "void": 1},
        )
        for name in ("race_features.csv", "boat_features.csv"):
            with (self.snapshot / name).open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                columns = next(csv.reader(handle))
            forbidden = (
                "odds",
                "popular",
                "vote",
                "bet",
                "sales",
                "payout",
                "actual_finish",
                "actual_course",
                "actual_start_timing",
            )
            self.assertFalse(
                any(token in column.lower() for column in columns for token in forbidden)
            )

    def test_uniform_predictions_match_every_theoretical_metric(self) -> None:
        predictions = self.root / "uniform.csv.gz"
        generation = generate_uniform_predictions(
            project_root=PROJECT_ROOT,
            snapshot_dir=self.snapshot,
            output_path=predictions,
        )
        self.assertEqual(generation["race_count"], 3)
        report = evaluate_predictions(
            project_root=PROJECT_ROOT,
            snapshot_dir=self.snapshot,
            prediction_path=predictions,
        )
        contract = json.loads(
            (
                PROJECT_ROOT / "configs/boatrace_model_evaluation_v1_1.json"
            ).read_text(encoding="utf-8")
        )
        assert_uniform_reference(report, contract)
        self.assertEqual(report["qualification_status"], "passed")
        self.assertEqual(report["coverage"]["coverage"], 1.0)
        self.assertEqual(report["coverage"]["missing_races"], 0)
        expected = {
            "trifecta_log_loss": math.log(120),
            "winner_log_loss": math.log(6),
            "exacta_log_loss": math.log(30),
            "top3_set_log_loss": math.log(20),
            "second_given_first_log_loss": math.log(5),
            "third_given_first_second_log_loss": math.log(4),
            "trifecta_brier": 119 / 120,
        }
        for metric, value in expected.items():
            self.assertAlmostEqual(report["metrics"][metric], value, places=12)

    def test_invalid_or_missing_probabilities_are_disqualified(self) -> None:
        probability = 1.0 / 120.0
        bad_path = self.root / "bad.csv"
        with bad_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["race_key", *PROBABILITY_COLUMNS])
            values = [probability] * 120
            values[0] = -0.1
            values[1] += 0.1 + probability
            writer.writerow(["20260101_01_01", *values])
            writer.writerow(["20260101_01_02", *([probability] * 120)])
        report = evaluate_predictions(
            project_root=PROJECT_ROOT,
            snapshot_dir=self.snapshot,
            prediction_path=bad_path,
        )
        self.assertEqual(report["qualification_status"], "disqualified")
        self.assertTrue(any("outside [0,1]" in error for error in report["errors"]))
        self.assertTrue(any("missing prediction" in error for error in report["errors"]))

    def test_manifest_hash_tampering_is_detected(self) -> None:
        copied = self.root / "tampered"
        shutil.copytree(self.snapshot, copied)
        with (copied / "race_features.csv").open(
            "a", encoding="utf-8", newline=""
        ) as handle:
            handle.write("\n")
        manifest = json.loads(
            (copied / "dataset_manifest.json").read_text(encoding="utf-8")
        )
        manifest["snapshot_id"] = copied.name
        (copied / "dataset_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        validation = validate_snapshot(
            project_root=PROJECT_ROOT,
            snapshot_dir=copied,
            verify_environment_hashes=False,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(
            any("artifact SHA-256 mismatch" in error for error in validation["errors"])
        )


if __name__ == "__main__":
    unittest.main()
