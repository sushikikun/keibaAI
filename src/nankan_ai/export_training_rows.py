from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

import duckdb

from .basic_features import add_basic_features
from .schema import (
    BASIC_FEATURE_COLUMNS,
    DEFAULT_DB_PATH,
    DEFAULT_TRAINING_ROWS_PATH,
    PAST_RACE_ROWS_TABLE,
    REQUIRED_COLUMNS,
)


def export_training_rows(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path = DEFAULT_TRAINING_ROWS_PATH,
) -> int:
    db = Path(db_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db), read_only=True) as conn:
        rows = _fetch_training_source_rows(conn)

    fieldnames = list(REQUIRED_COLUMNS) + list(BASIC_FEATURE_COLUMNS)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(add_basic_features(row))

    return len(rows)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export training rows from DuckDB with MVP basic features."
    )
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="DuckDB input path")
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_TRAINING_ROWS_PATH),
        help="CSV output path",
    )
    args = parser.parse_args(argv)

    try:
        row_count = export_training_rows(db_path=args.db_path, output_path=args.output_path)
    except duckdb.CatalogException:
        print(f"NG: DuckDB table not found: {PAST_RACE_ROWS_TABLE}")
        return 1
    except duckdb.IOException as exc:
        print(f"NG: DuckDB could not be opened: {exc}")
        return 1

    print(f"OK: exported {row_count} rows to {args.output_path}")
    return 0


def _fetch_training_source_rows(conn: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    columns = ", ".join(_quote_identifier(column) for column in REQUIRED_COLUMNS)
    query = f"""
        SELECT {columns}
        FROM {PAST_RACE_ROWS_TABLE}
        WHERE UPPER(COALESCE({_quote_identifier("finish_position")}, '')) NOT IN ('SCR', 'EXC')
        ORDER BY
            {_quote_identifier("date")},
            {_quote_identifier("track")},
            TRY_CAST(NULLIF({_quote_identifier("race_no")}, '') AS INTEGER),
            TRY_CAST(NULLIF({_quote_identifier("horse_no")}, '') AS INTEGER)
    """
    records = conn.execute(query).fetchall()
    return [
        {column: "" if value is None else str(value) for column, value in zip(REQUIRED_COLUMNS, record)}
        for record in records
    ]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
