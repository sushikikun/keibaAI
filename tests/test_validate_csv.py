from __future__ import annotations

import csv
from pathlib import Path

from nankan_ai.schema import REQUIRED_COLUMNS
from nankan_ai.validate_csv import validate_csv

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_validate_csv_accepts_valid_fixture() -> None:
    csv_path = FIXTURES_DIR / "nankan_past_races_valid.csv"

    result = validate_csv(csv_path)

    assert result.is_valid, [error.format() for error in result.errors]
    assert result.row_count == 8
    assert result.race_count == 2


def test_validate_csv_rejects_invalid_fixture() -> None:
    csv_path = FIXTURES_DIR / "nankan_past_races_invalid.csv"

    result = validate_csv(csv_path)

    messages = "\n".join(error.format() for error in result.errors)
    assert not result.is_valid
    assert "race_id must match" in messages
    assert "date must be YYYY-MM-DD" in messages
    assert "track must be one of" in messages
    assert "column=distance" in messages
    assert "finish_position must be" in messages


def test_validate_csv_reports_missing_required_columns() -> None:
    csv_path = _test_output_dir() / "missing.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["race_id"])
        writer.writeheader()

    result = validate_csv(csv_path)

    assert not result.is_valid
    assert "Required columns are missing" in result.errors[0].message


def test_validate_csv_reports_duplicate_horse_no_in_same_race() -> None:
    csv_path = _write_csv(
        "duplicate_horse_no.csv",
        [
            _row(horse_no="7"),
            _row(horse_no="7"),
        ],
    )

    result = validate_csv(csv_path)

    assert not result.is_valid
    assert any("horse_no is duplicated" in error.message for error in result.errors)


def test_validate_csv_reports_large_field_size_mismatch() -> None:
    csv_path = _write_csv(
        "field_size_mismatch.csv",
        [
            _row(field_size="8", horse_no="1"),
            _row(field_size="8", horse_no="2"),
        ],
    )

    result = validate_csv(csv_path)

    assert not result.is_valid
    assert any("field_size=8" in error.message for error in result.errors)


def _write_csv(filename: str, rows: list[dict[str, str]]) -> Path:
    csv_path = _test_output_dir() / filename
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _row(**overrides: str) -> dict[str, str]:
    row = {column: "" for column in REQUIRED_COLUMNS}
    row.update(
        {
            "race_id": "20260616_kawasaki_10",
            "date": "2026-06-16",
            "track": "kawasaki",
            "race_no": "10",
            "race_name": "Fixture Race",
            "distance": "1600",
            "surface": "dirt",
            "weather": "fine",
            "track_condition": "standard",
            "class_name": "fixture",
            "field_size": "3",
            "horse_no": "1",
            "gate_no": "1",
            "horse_name": "Fixture Horse",
            "sex": "M",
            "age": "4",
            "carried_weight": "56.0",
            "jockey_name": "Fixture Jockey",
            "trainer_name": "Fixture Trainer",
            "body_weight": "500",
            "body_weight_diff": "2",
            "finish_position": "1",
            "finish_time": "1:38.0",
            "margin": "",
            "passing_order": "1-1-1",
            "last_3f": "38.1",
            "popularity": "1",
            "win_odds_final": "2.4",
        }
    )
    row.update(overrides)
    return row
