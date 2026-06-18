from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from .schema import (
    DECIMAL_COLUMNS,
    FIELD_SIZE_MISMATCH_TOLERANCE,
    FINISH_STATUS_VALUES,
    INTEGER_COLUMNS,
    REQUIRED_COLUMNS,
    TRACKS,
)

RACE_ID_PATTERN = re.compile(r"^\d{8}_(kawasaki|oi|funabashi|urawa)_\d{1,2}$")
INTEGER_PATTERN = re.compile(r"^-?\d+$")


@dataclass(frozen=True)
class ValidationIssue:
    message: str
    row_number: int | None = None
    column: str | None = None
    race_id: str | None = None

    def format(self) -> str:
        parts: list[str] = []
        if self.row_number is not None:
            parts.append(f"row {self.row_number}")
        if self.race_id:
            parts.append(f"race_id={self.race_id}")
        if self.column:
            parts.append(f"column={self.column}")
        prefix = " ".join(parts)
        return f"{prefix}: {self.message}" if prefix else self.message


@dataclass
class ValidationResult:
    csv_path: Path
    row_count: int = 0
    race_count: int = 0
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_csv(
    csv_path: str | Path,
    *,
    field_size_tolerance: int = FIELD_SIZE_MISMATCH_TOLERANCE,
) -> ValidationResult:
    path = Path(csv_path)
    result = ValidationResult(csv_path=path)
    race_rows: dict[str, list[tuple[int, dict[str, str]]]] = {}
    race_field_sizes: dict[str, list[tuple[int, int]]] = {}
    seen_horse_numbers: dict[str, dict[str, int]] = {}

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                result.errors.append(ValidationIssue("CSV header is missing."))
                return result

            missing_columns = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
            if missing_columns:
                result.errors.append(
                    ValidationIssue(f"Required columns are missing: {', '.join(missing_columns)}")
                )
                return result

            for row_number, row in enumerate(reader, start=2):
                result.row_count += 1
                _validate_row(result, row_number, row)
                race_id = _clean(row.get("race_id"))
                if race_id:
                    race_rows.setdefault(race_id, []).append((row_number, row))
                    _record_field_size(race_field_sizes, race_id, row_number, row)
                    _record_horse_number(result, seen_horse_numbers, race_id, row_number, row)
    except FileNotFoundError:
        result.errors.append(ValidationIssue(f"CSV file not found: {path}"))
        return result
    except UnicodeDecodeError as exc:
        result.errors.append(ValidationIssue(f"CSV must be readable as UTF-8: {exc}"))
        return result
    except csv.Error as exc:
        result.errors.append(ValidationIssue(f"CSV parse error: {exc}"))
        return result

    result.race_count = len(race_rows)
    _validate_field_sizes(result, race_rows, race_field_sizes, field_size_tolerance)
    return result


def format_validation_result(result: ValidationResult) -> str:
    lines: list[str] = []
    if result.is_valid:
        lines.append(
            f"OK: {result.csv_path} ({result.row_count} rows, {result.race_count} races)"
        )
    else:
        lines.append(
            f"NG: {result.csv_path} ({len(result.errors)} errors, {result.row_count} rows)"
        )

    for issue in result.errors:
        lines.append(f"ERROR: {issue.format()}")
    for issue in result.warnings:
        lines.append(f"WARNING: {issue.format()}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Nankan past-race CSV.")
    parser.add_argument("csv_path", help="Path to data/raw/nankan_past_races.csv")
    args = parser.parse_args(argv)

    result = validate_csv(args.csv_path)
    print(format_validation_result(result))
    return 0 if result.is_valid else 1


def _validate_row(result: ValidationResult, row_number: int, row: dict[str, str]) -> None:
    race_id = _clean(row.get("race_id"))
    track = _clean(row.get("track"))
    race_date = _clean(row.get("date"))
    finish_position = _clean(row.get("finish_position")).upper()

    if not race_id or not RACE_ID_PATTERN.match(race_id):
        result.errors.append(
            ValidationIssue(
                "race_id must match YYYYMMDD_track_R.",
                row_number=row_number,
                column="race_id",
                race_id=race_id or None,
            )
        )

    if track not in TRACKS:
        result.errors.append(
            ValidationIssue(
                f"track must be one of: {', '.join(sorted(TRACKS))}.",
                row_number=row_number,
                column="track",
                race_id=race_id or None,
            )
        )

    if not _is_yyyy_mm_dd(race_date):
        result.errors.append(
            ValidationIssue(
                "date must be YYYY-MM-DD.",
                row_number=row_number,
                column="date",
                race_id=race_id or None,
            )
        )

    for column in sorted(INTEGER_COLUMNS):
        value = _clean(row.get(column))
        if value and not INTEGER_PATTERN.match(value):
            result.errors.append(
                ValidationIssue(
                    "value must be an integer.",
                    row_number=row_number,
                    column=column,
                    race_id=race_id or None,
                )
            )

    for column in sorted(DECIMAL_COLUMNS):
        value = _clean(row.get(column))
        if value and not _is_decimal(value):
            result.errors.append(
                ValidationIssue(
                    "value must be numeric.",
                    row_number=row_number,
                    column=column,
                    race_id=race_id or None,
                )
            )

    if finish_position and not (
        finish_position in FINISH_STATUS_VALUES
        or (finish_position.isdigit() and int(finish_position) > 0)
    ):
        result.errors.append(
            ValidationIssue(
                "finish_position must be a positive number, SCR, EXC, DNF, or blank.",
                row_number=row_number,
                column="finish_position",
                race_id=race_id or None,
            )
        )


def _record_field_size(
    race_field_sizes: dict[str, list[tuple[int, int]]],
    race_id: str,
    row_number: int,
    row: dict[str, str],
) -> None:
    field_size = _clean(row.get("field_size"))
    if field_size and INTEGER_PATTERN.match(field_size):
        race_field_sizes.setdefault(race_id, []).append((row_number, int(field_size)))


def _record_horse_number(
    result: ValidationResult,
    seen_horse_numbers: dict[str, dict[str, int]],
    race_id: str,
    row_number: int,
    row: dict[str, str],
) -> None:
    horse_no = _clean(row.get("horse_no"))
    if not horse_no or not INTEGER_PATTERN.match(horse_no):
        return

    race_seen = seen_horse_numbers.setdefault(race_id, {})
    first_seen_row = race_seen.get(horse_no)
    if first_seen_row is not None:
        result.errors.append(
            ValidationIssue(
                f"horse_no is duplicated in the same race; first seen at row {first_seen_row}.",
                row_number=row_number,
                column="horse_no",
                race_id=race_id,
            )
        )
        return

    race_seen[horse_no] = row_number


def _validate_field_sizes(
    result: ValidationResult,
    race_rows: dict[str, list[tuple[int, dict[str, str]]]],
    race_field_sizes: dict[str, list[tuple[int, int]]],
    field_size_tolerance: int,
) -> None:
    for race_id, rows in sorted(race_rows.items()):
        field_sizes = race_field_sizes.get(race_id, [])
        if not field_sizes:
            continue

        unique_sizes = {field_size for _, field_size in field_sizes}
        if len(unique_sizes) > 1:
            result.errors.append(
                ValidationIssue(
                    f"field_size has multiple values in one race: {sorted(unique_sizes)}.",
                    race_id=race_id,
                    column="field_size",
                )
            )
            continue

        declared_size = field_sizes[0][1]
        actual_rows = len(rows)
        if abs(declared_size - actual_rows) > field_size_tolerance:
            result.errors.append(
                ValidationIssue(
                    f"field_size={declared_size}, but CSV has {actual_rows} rows for this race.",
                    race_id=race_id,
                    column="field_size",
                )
            )


def _is_yyyy_mm_dd(value: str) -> bool:
    if len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
    except InvalidOperation:
        return False
    return True


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
