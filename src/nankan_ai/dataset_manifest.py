from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .append_batch_log import DEFAULT_BATCH_LOG_PATH, read_batch_log
from .schema import (
    DEFAULT_DB_PATH,
    DEFAULT_RAW_CSV_PATH,
    DEFAULT_TRAINING_ROWS_PATH,
    REQUIRED_COLUMNS,
)

DEFAULT_MANIFEST_PATH = Path("data/reports/dataset_manifest_500.json")


def build_dataset_manifest(
    *,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
    training_rows_path: str | Path = DEFAULT_TRAINING_ROWS_PATH,
    batch_log_path: str | Path = DEFAULT_BATCH_LOG_PATH,
    label: str | None = None,
    pytest_result: str | None = None,
) -> dict[str, object]:
    raw_path = Path(raw_csv_path)
    db = Path(db_path)
    training_path = Path(training_rows_path)
    batch_log = Path(batch_log_path)
    rows = _read_csv_rows(raw_path)
    training_row_count = _csv_data_row_count(training_path)

    raw_row_count = len(rows)
    race_ids = {_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}
    dates = sorted(_clean(row.get("date")) for row in rows if _clean(row.get("date")))
    finish_counts = Counter(_clean(row.get("finish_position")).upper() or "(blank)" for row in rows)
    track_row_counts = Counter(_clean(row.get("track")) or "(blank)" for row in rows)
    track_race_ids: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        track = _clean(row.get("track")) or "(blank)"
        race_id = _clean(row.get("race_id"))
        if race_id:
            track_race_ids[track].add(race_id)

    missing_counts = {
        column: sum(1 for row in rows if not _clean(row.get(column)))
        for column in REQUIRED_COLUMNS
    }
    win_odds_missing = missing_counts.get("win_odds_final", 0)
    passing_order_missing = missing_counts.get("passing_order", 0)

    return {
        "manifest_version": 1,
        "snapshot_name": f"kawasaki_{label}_races" if label else "kawasaki_dataset",
        "label": label,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Data-layer snapshot before prediction modeling.",
        "paths": {
            "raw_csv": _path_string(raw_path),
            "duckdb": _path_string(db),
            "training_rows_csv": _path_string(training_path),
            "batch_log_csv": _path_string(batch_log),
        },
        "files": {
            "raw_csv_sha256": _sha256(raw_path),
            "duckdb_exists": db.exists(),
            "training_rows_csv_sha256": _sha256(training_path),
        },
        "row_grain": "one row per horse per race",
        "raw_row_count": raw_row_count,
        "race_count": len(race_ids),
        "training_row_count": training_row_count,
        "track_counts": {
            "rows": _sorted_counter_dict(track_row_counts),
            "races": _sorted_counter_dict(
                {track: len(ids) for track, ids in track_race_ids.items()}
            ),
        },
        "month_race_counts": _sorted_key_dict(_month_race_counts(rows)),
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
        "finish_status_counts": {
            "EXC": finish_counts.get("EXC", 0),
            "SCR": finish_counts.get("SCR", 0),
            "DNF": finish_counts.get("DNF", 0),
        },
        "top_missing_columns": _top_missing_columns(missing_counts, raw_row_count),
        "win_odds_final": {
            "missing_count": win_odds_missing,
            "missing_rate_percent": _percent(win_odds_missing, raw_row_count),
        },
        "passing_order": {
            "missing_count": passing_order_missing,
            "missing_rate_percent": _percent(passing_order_missing, raw_row_count),
            "all_missing": raw_row_count > 0 and passing_order_missing == raw_row_count,
        },
        "field_size_mismatches": _field_size_mismatch_summary(rows),
        "horse_no_duplicates": _horse_no_duplicate_summary(rows),
        "race_id_duplicates": _race_id_duplicate_summary(rows),
        "race_no_sequence_gaps": _race_no_sequence_gap_summary(rows),
        "batch_summary": _batch_summary(batch_log),
        "pytest": {
            "command": "python -m pytest",
            "result": pytest_result or "not_recorded",
        },
        "notes": [
            "No prediction model is included in this snapshot.",
            "Raw CSV values are not corrected or backfilled by this manifest.",
            "win_odds_final remains blank when the source value is unavailable.",
        ],
    }


def write_dataset_manifest(
    manifest: dict[str, object],
    output_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write a reproducible dataset manifest for the Nankan data layer."
    )
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--training-rows-path", default=str(DEFAULT_TRAINING_ROWS_PATH))
    parser.add_argument("--batch-log-path", default=str(DEFAULT_BATCH_LOG_PATH))
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--label",
        default=None,
        help="Snapshot label, for example 500 or 1000. Also controls the default output filename.",
    )
    parser.add_argument(
        "--pytest-result",
        default=None,
        help="Optional pytest result string to record after tests have run.",
    )
    args = parser.parse_args(argv)

    manifest = build_dataset_manifest(
        raw_csv_path=args.raw_csv_path,
        db_path=args.db_path,
        training_rows_path=args.training_rows_path,
        batch_log_path=args.batch_log_path,
        label=args.label,
        pytest_result=args.pytest_result,
    )
    output_path = write_dataset_manifest(manifest, args.output_path or _default_manifest_path(args.label))

    print(f"OK: wrote dataset manifest to {output_path}")
    print(f"raw_row_count: {manifest['raw_row_count']}")
    print(f"race_count: {manifest['race_count']}")
    print(f"training_row_count: {manifest['training_row_count']}")
    return 0


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{column: _clean(row.get(column)) for column in REQUIRED_COLUMNS} for row in reader]


def _csv_data_row_count(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _top_missing_columns(
    missing_counts: dict[str, int],
    total_rows: int,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    items = sorted(
        ((column, count) for column, count in missing_counts.items() if count > 0),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        {
            "column": column,
            "missing_count": count,
            "missing_rate_percent": _percent(count, total_rows),
        }
        for column, count in items[:limit]
    ]


def _field_size_mismatch_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    race_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        if race_id:
            race_rows[race_id].append(row)

    mismatches: list[dict[str, object]] = []
    for race_id, group in sorted(race_rows.items()):
        declared_values = sorted(
            {_to_int(row.get("field_size")) for row in group if _to_int(row.get("field_size")) is not None}
        )
        actual_rows = len(group)
        if not declared_values:
            mismatches.append(
                {"race_id": race_id, "reason": "field_size_missing", "actual_rows": actual_rows}
            )
        elif len(declared_values) > 1:
            mismatches.append(
                {
                    "race_id": race_id,
                    "reason": "multiple_field_size_values",
                    "field_size_values": declared_values,
                    "actual_rows": actual_rows,
                }
            )
        elif declared_values[0] != actual_rows:
            mismatches.append(
                {
                    "race_id": race_id,
                    "field_size": declared_values[0],
                    "actual_rows": actual_rows,
                    "diff": declared_values[0] - actual_rows,
                }
            )

    return {
        "has_mismatches": bool(mismatches),
        "mismatch_count": len(mismatches),
        "examples": mismatches[:20],
    }


def _horse_no_duplicate_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=2):
        race_id = _clean(row.get("race_id"))
        horse_no = _clean(row.get("horse_no"))
        if not race_id or not horse_no:
            continue
        key = (race_id, horse_no)
        first_row = seen.get(key)
        if first_row is None:
            seen[key] = index
        else:
            duplicates.append(
                {
                    "race_id": race_id,
                    "horse_no": horse_no,
                    "first_csv_row": first_row,
                    "duplicate_csv_row": index,
                }
            )

    return {
        "has_duplicates": bool(duplicates),
        "duplicate_count": len(duplicates),
        "examples": duplicates[:20],
    }


def _race_id_duplicate_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    race_level_columns = (
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
    signatures: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        if not race_id:
            continue
        signatures[race_id].add(tuple(_clean(row.get(column)) for column in race_level_columns))

    conflicts = [
        {"race_id": race_id, "signature_count": len(values)}
        for race_id, values in sorted(signatures.items())
        if len(values) > 1
    ]
    return {
        "definition": "Flags race_id values with conflicting race-level metadata. Multiple horse rows per race_id are expected.",
        "has_duplicates": bool(conflicts),
        "duplicate_count": len(conflicts),
        "examples": conflicts[:20],
    }


def _month_race_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    month_races: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        race_date = _clean(row.get("date"))
        if race_id and len(race_date) >= 7:
            month_races[race_date[:7]].add(race_id)
    return {month: len(race_ids) for month, race_ids in month_races.items()}


def _race_no_sequence_gap_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    race_numbers: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in rows:
        race_date = _clean(row.get("date"))
        track = _clean(row.get("track"))
        race_no = _to_int(row.get("race_no"))
        if race_date and track and race_no is not None:
            race_numbers[(race_date, track)].add(race_no)

    gaps: list[dict[str, object]] = []
    for (race_date, track), numbers in sorted(race_numbers.items()):
        expected = set(range(min(numbers), max(numbers) + 1))
        missing = sorted(expected - numbers)
        if missing:
            gaps.append(
                {
                    "date": race_date,
                    "track": track,
                    "missing_race_no": missing,
                    "present_race_no": sorted(numbers),
                }
            )

    return {
        "has_gaps": bool(gaps),
        "gap_count": len(gaps),
        "examples": gaps[:50],
    }


def _batch_summary(batch_log_path: Path) -> dict[str, object]:
    rows = read_batch_log(batch_log_path)
    mode_counts = Counter(row.get("mode", "") or "(blank)" for row in rows)
    validation_counts = Counter(row.get("validation_status", "") or "(blank)" for row in rows)
    applied_rows = [row for row in rows if row.get("mode") == "applied" and row.get("validation_status") == "passed"]
    return {
        "batch_log_path": _path_string(batch_log_path),
        "batch_count": len(rows),
        "mode_counts": _sorted_counter_dict(mode_counts),
        "validation_status_counts": _sorted_counter_dict(validation_counts),
        "applied_added_rows": sum(_to_int(row.get("added_rows")) or 0 for row in applied_rows),
        "applied_added_races": sum(_to_int(row.get("added_races")) or 0 for row in applied_rows),
        "latest_batches": rows[-10:],
    }


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sorted_counter_dict(counter: Counter[str] | dict[str, int]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    }


def _sorted_key_dict(values: dict[str, int]) -> dict[str, int]:
    return {key: values[key] for key in sorted(values)}


def _percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total * 100, 2)


def _to_int(value: object) -> int | None:
    text = _clean(value)
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


def _default_manifest_path(label: str | None) -> Path:
    if label:
        safe_label = "".join(ch for ch in label if ch.isalnum() or ch in {"-", "_"})
        return Path(f"data/reports/dataset_manifest_{safe_label}.json")
    return DEFAULT_MANIFEST_PATH


if __name__ == "__main__":
    raise SystemExit(main())
