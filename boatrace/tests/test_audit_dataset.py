from __future__ import annotations

from pathlib import Path

from nankan_ai.audit_dataset import audit_dataset, build_audit_report
from nankan_ai.load_to_duckdb import load_csv_to_duckdb

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_audit_dataset_reads_csv_fixture() -> None:
    report = audit_dataset(csv_path=FIXTURES_DIR / "nankan_past_races_valid.csv")
    output = report.format()

    assert "total_rows: 8" in output
    assert "race_count: 2" in output
    assert "track_race_counts:" in output
    assert "finish_position_counts:" in output
    assert "basic_feature_counts:" in output
    assert "win_flag: 2" in output
    assert "second_flag: 1" in output
    assert "top3_flag: 4" in output
    assert "is_scratched: 2" in output
    assert "is_dnf: 1" in output


def test_audit_dataset_reads_duckdb_fixture() -> None:
    db_path = _test_output_dir() / "audit_fixture.duckdb"
    load_csv_to_duckdb(FIXTURES_DIR / "nankan_past_races_valid.csv", db_path=db_path)

    report = audit_dataset(db_path=db_path)
    output = report.format()

    assert "source: duckdb:" in output
    assert "total_rows: 8" in output
    assert "race_count: 2" in output


def test_build_audit_report_handles_empty_rows() -> None:
    report = build_audit_report([], source="test:empty")
    output = report.format()

    assert "total_rows: 0" in output
    assert "race_count: 0" in output
    assert "date_min: (none)" in output


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path
