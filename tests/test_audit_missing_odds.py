from __future__ import annotations

import csv
from pathlib import Path

from nankan_ai.audit_missing_odds import (
    MISSING_RACES_FILENAME,
    MISSING_ROWS_FILENAME,
    audit_missing_odds,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_audit_missing_odds_writes_reports_from_fixture() -> None:
    reports_dir = _test_output_dir() / "missing-odds"
    report = audit_missing_odds(
        csv_path=FIXTURES_DIR / "nankan_past_races_valid.csv",
        reports_dir=reports_dir,
    )

    output = report.format()

    assert "missing_win_odds_rows: 2" in output
    assert "missing_race_count: 2" in output
    assert "EXC: 1" in output
    assert "SCR: 1" in output

    rows_path = reports_dir / MISSING_ROWS_FILENAME
    races_path = reports_dir / MISSING_RACES_FILENAME

    assert rows_path.exists()
    assert races_path.exists()

    with rows_path.open(encoding="utf-8", newline="") as handle:
        missing_rows = list(csv.DictReader(handle))
    with races_path.open(encoding="utf-8", newline="") as handle:
        missing_races = list(csv.DictReader(handle))

    assert len(missing_rows) == 2
    assert {row["start_type"] for row in missing_rows} == {"SCR", "EXC"}
    assert len(missing_races) == 2
    assert {row["race_id"] for row in missing_races} == {
        "20260616_kawasaki_10",
        "20260616_oi_08",
    }


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path
