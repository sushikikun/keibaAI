from __future__ import annotations

import json
from pathlib import Path

from nankan_ai.dataset_manifest import build_dataset_manifest, write_dataset_manifest
from nankan_ai.export_training_rows import export_training_rows
from nankan_ai.load_to_duckdb import load_csv_to_duckdb

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_build_dataset_manifest_from_fixture() -> None:
    output_dir = _test_output_dir() / "dataset-manifest"
    db_path = output_dir / "fixture.duckdb"
    training_path = output_dir / "training_rows.csv"
    manifest_path = output_dir / "dataset_manifest.json"

    load_csv_to_duckdb(FIXTURES_DIR / "nankan_past_races_valid.csv", db_path=db_path)
    export_training_rows(db_path=db_path, output_path=training_path)

    manifest = build_dataset_manifest(
        raw_csv_path=FIXTURES_DIR / "nankan_past_races_valid.csv",
        db_path=db_path,
        training_rows_path=training_path,
        label="fixture",
        pytest_result="fixture tests passed",
    )
    write_dataset_manifest(manifest, manifest_path)

    assert manifest["raw_row_count"] == 8
    assert manifest["snapshot_name"] == "kawasaki_fixture_races"
    assert manifest["label"] == "fixture"
    assert manifest["race_count"] == 2
    assert manifest["training_row_count"] == 6
    assert manifest["track_counts"]["races"] == {"kawasaki": 1, "oi": 1}
    assert manifest["finish_status_counts"] == {"EXC": 1, "SCR": 1, "DNF": 1}
    assert manifest["win_odds_final"]["missing_count"] == 2
    assert manifest["passing_order"]["all_missing"] is False
    assert manifest["field_size_mismatches"]["has_mismatches"] is False
    assert manifest["horse_no_duplicates"]["has_duplicates"] is False
    assert manifest["race_id_duplicates"]["has_duplicates"] is False
    assert len(manifest["files"]["raw_csv_sha256"]) == 64
    assert len(manifest["files"]["training_rows_csv_sha256"]) == 64

    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["pytest"]["result"] == "fixture tests passed"


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path
