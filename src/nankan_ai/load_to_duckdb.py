from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import duckdb

from .schema import DEFAULT_DB_PATH, PAST_RACE_ROWS_TABLE, REQUIRED_COLUMNS
from .validate_csv import format_validation_result, validate_csv


def load_csv_to_duckdb(
    csv_path: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    validation = validate_csv(csv_path)
    if not validation.is_valid:
        raise ValueError(format_validation_result(validation))

    csv = Path(csv_path)
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db)) as conn:
        row_count = _replace_past_race_rows_table(conn, csv)

    return row_count


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load a validated Nankan CSV into DuckDB.")
    parser.add_argument("csv_path", help="Path to data/raw/nankan_past_races.csv")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="DuckDB output path")
    args = parser.parse_args(argv)

    try:
        row_count = load_csv_to_duckdb(args.csv_path, db_path=args.db_path)
    except ValueError as exc:
        print(exc)
        return 1

    print(f"OK: loaded {row_count} rows into {args.db_path}:{PAST_RACE_ROWS_TABLE}")
    return 0


def _replace_past_race_rows_table(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
) -> int:
    conn.execute(f"DROP TABLE IF EXISTS {PAST_RACE_ROWS_TABLE}")
    select_columns = ", ".join(
        f"COALESCE({_quote_identifier(column)}::VARCHAR, '') AS {_quote_identifier(column)}"
        for column in REQUIRED_COLUMNS
    )
    conn.execute(
        f"""
        CREATE TABLE {PAST_RACE_ROWS_TABLE} AS
        SELECT {select_columns}
        FROM read_csv_auto(?, header=true, all_varchar=true)
        """,
        [str(csv_path)],
    )
    return int(conn.execute(f"SELECT COUNT(*) FROM {PAST_RACE_ROWS_TABLE}").fetchone()[0])


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
