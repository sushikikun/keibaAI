from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from nankan_ai.export_training_rows import export_training_rows
from nankan_ai.load_to_duckdb import load_csv_to_duckdb
from nankan_ai.schema import PAST_RACE_ROWS_TABLE

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_duckdb_load_and_training_export() -> None:
    output_dir = _test_output_dir()
    db_path = output_dir / "pipeline_fixture.duckdb"
    output_path = output_dir / "training_rows.csv"
    csv_path = FIXTURES_DIR / "nankan_past_races_valid.csv"

    loaded_count = load_csv_to_duckdb(csv_path, db_path=db_path)
    exported_count = export_training_rows(db_path=db_path, output_path=output_path)

    assert loaded_count == 8
    assert exported_count == 6
    assert db_path.exists()
    assert output_path.exists()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        table_count = conn.execute(f"SELECT COUNT(*) FROM {PAST_RACE_ROWS_TABLE}").fetchone()[0]
    assert table_count == 8

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    positions = {row["horse_name"]: row for row in rows}
    assert "Fixture Horse D" not in positions
    assert "Fixture Horse F" not in positions

    assert positions["Fixture Horse A"]["win_flag"] == "1"
    assert positions["Fixture Horse A"]["second_flag"] == "0"
    assert positions["Fixture Horse A"]["top3_flag"] == "1"

    assert positions["Fixture Horse B"]["win_flag"] == "0"
    assert positions["Fixture Horse B"]["second_flag"] == "1"
    assert positions["Fixture Horse B"]["top3_flag"] == "1"

    assert positions["Fixture Horse C"]["win_flag"] == "0"
    assert positions["Fixture Horse C"]["second_flag"] == "0"
    assert positions["Fixture Horse C"]["top3_flag"] == "1"

    assert positions["Fixture Horse E"]["finish_position"] == "DNF"
    assert positions["Fixture Horse E"]["is_dnf"] == "1"
    assert positions["Fixture Horse E"]["is_scratched"] == "0"


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path
