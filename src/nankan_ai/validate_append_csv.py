from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import DEFAULT_RAW_CSV_PATH, REQUIRED_COLUMNS, TRACKS
from .validate_csv import ValidationIssue, format_validation_result, validate_csv

DEFAULT_APPEND_CSV_PATH = Path("data/incoming/nankan_past_races_append.csv")
RACE_ID_TRACK_PATTERN = re.compile(r"^\d{8}_([a-z]+)_\d{1,2}$")
RACE_LEVEL_COLUMNS = (
    "date",
    "track",
    "race_no",
    "race_name",
    "distance",
    "surface",
    "weather",
    "track_condition",
    "class_name",
    "field_size",
)


@dataclass
class AppendValidationResult:
    append_csv_path: Path
    raw_csv_path: Path
    row_count: int = 0
    race_count: int = 0
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_append_csv(
    append_csv_path: str | Path = DEFAULT_APPEND_CSV_PATH,
    *,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    required_track: str | None = None,
) -> AppendValidationResult:
    append_path = Path(append_csv_path)
    raw_path = Path(raw_csv_path)
    result = AppendValidationResult(append_csv_path=append_path, raw_csv_path=raw_path)

    raw_header = _read_header(raw_path, result, label="existing raw")
    append_header = _read_header(append_path, result, label="append CSV")
    if raw_header is None or append_header is None:
        return result

    if append_header != raw_header:
        result.errors.append(
            ValidationIssue(
                "append CSV header must exactly match existing raw CSV header, including column order."
            )
        )
        return result

    if tuple(append_header) != REQUIRED_COLUMNS:
        result.errors.append(
            ValidationIssue(
                "CSV header does not match the current required Nankan schema exactly."
            )
        )
        return result

    base_validation = validate_csv(append_path, field_size_tolerance=0)
    result.row_count = base_validation.row_count
    result.race_count = base_validation.race_count
    result.errors.extend(base_validation.errors)
    result.warnings.extend(base_validation.warnings)

    append_rows = _read_rows(append_path)
    if not append_rows:
        result.errors.append(ValidationIssue("append CSV has no data rows."))
        return result

    existing_race_ids = _race_ids(_read_rows(raw_path))
    append_race_ids = _race_ids(append_rows)
    duplicated_existing = sorted(append_race_ids & existing_race_ids)
    for race_id in duplicated_existing[:50]:
        result.errors.append(
            ValidationIssue(
                "race_id already exists in the current raw CSV.",
                race_id=race_id,
                column="race_id",
            )
        )
    if len(duplicated_existing) > 50:
        result.errors.append(
            ValidationIssue(
                f"race_id already exists in current raw CSV for {len(duplicated_existing)} races; first 50 shown."
            )
        )

    _validate_append_track_scope(result, append_rows, required_track=required_track)
    _validate_race_metadata_conflicts(result, append_rows)
    return result


def format_append_validation_result(result: AppendValidationResult) -> str:
    status = "OK" if result.is_valid else "NG"
    lines = [
        (
            f"{status}: {result.append_csv_path} "
            f"({result.row_count} rows, {result.race_count} races, raw={result.raw_csv_path})"
        )
    ]
    for issue in result.errors:
        lines.append(f"ERROR: {issue.format()}")
    for issue in result.warnings:
        lines.append(f"WARNING: {issue.format()}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an incoming Nankan append CSV before merging it into raw data."
    )
    parser.add_argument(
        "append_csv_path",
        nargs="?",
        default=str(DEFAULT_APPEND_CSV_PATH),
        help="Path to data/incoming/nankan_past_races_append.csv",
    )
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument(
        "--required-track",
        default="",
        help="Optionally require one specific track. By default any single Nankan track is accepted.",
    )
    args = parser.parse_args(argv)

    result = validate_append_csv(
        args.append_csv_path,
        raw_csv_path=args.raw_csv_path,
        required_track=args.required_track or None,
    )
    print(format_append_validation_result(result))
    return 0 if result.is_valid else 1


def _read_header(
    csv_path: Path,
    result: AppendValidationResult,
    *,
    label: str,
) -> list[str] | None:
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                result.errors.append(ValidationIssue(f"{label} header is missing: {csv_path}"))
                return None
            return header
    except FileNotFoundError:
        result.errors.append(ValidationIssue(f"{label} file not found: {csv_path}"))
    except UnicodeDecodeError as exc:
        result.errors.append(ValidationIssue(f"{label} must be readable as UTF-8: {exc}"))
    except csv.Error as exc:
        result.errors.append(ValidationIssue(f"{label} parse error: {exc}"))
    return None


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {column: _clean(row.get(column)) for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def _race_ids(rows: list[dict[str, str]]) -> set[str]:
    return {_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}


def _validate_append_track_scope(
    result: AppendValidationResult,
    rows: list[dict[str, str]],
    *,
    required_track: str | None,
) -> None:
    tracks: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        track = _clean(row.get("track"))
        race_id = _clean(row.get("race_id"))
        if track:
            tracks.add(track)
        if track and track not in TRACKS:
            result.errors.append(
                ValidationIssue(
                    f"track must be one of: {', '.join(sorted(TRACKS))}.",
                    row_number=row_number,
                    column="track",
                    race_id=race_id or None,
                )
            )
        match = RACE_ID_TRACK_PATTERN.match(race_id)
        if match and track and track != match.group(1):
            result.errors.append(
                ValidationIssue(
                    f"track must match race_id track; found track={track}, race_id track={match.group(1)}.",
                    row_number=row_number,
                    column="track",
                    race_id=race_id,
                )
            )

    if len(tracks) > 1:
        result.errors.append(
            ValidationIssue(
                f"append CSV must contain exactly one track; found tracks={', '.join(sorted(tracks))}.",
                column="track",
            )
        )

    if required_track:
        for track in sorted(tracks):
            if track != required_track:
                result.errors.append(
                    ValidationIssue(
                        f"append CSV is limited to track={required_track}; found track={track or '(blank)'}.",
                        column="track",
                    )
                )

        if required_track not in TRACKS:
            result.errors.append(
                ValidationIssue(
                    f"required_track must be one of: {', '.join(sorted(TRACKS))}.",
                    column="track",
                )
            )


def _validate_race_metadata_conflicts(
    result: AppendValidationResult,
    rows: list[dict[str, str]],
) -> None:
    signatures: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        if not race_id:
            continue
        signatures[race_id].add(tuple(_clean(row.get(column)) for column in RACE_LEVEL_COLUMNS))

    for race_id, values in sorted(signatures.items()):
        if len(values) > 1:
            result.errors.append(
                ValidationIssue(
                    "race_id has conflicting race-level metadata inside append CSV.",
                    race_id=race_id,
                    column="race_id",
                )
            )


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "AppendValidationResult",
    "DEFAULT_APPEND_CSV_PATH",
    "format_append_validation_result",
    "validate_append_csv",
]


if __name__ == "__main__":
    raise SystemExit(main())
