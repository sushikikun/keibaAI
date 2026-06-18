from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb

from .basic_features import add_basic_features
from .schema import DEFAULT_DB_PATH, PAST_RACE_ROWS_TABLE, REQUIRED_COLUMNS


@dataclass(frozen=True)
class AuditReport:
    source: str
    lines: tuple[str, ...]

    def format(self) -> str:
        return "\n".join(self.lines)


def audit_dataset(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    csv_path: str | Path | None = None,
) -> AuditReport:
    if csv_path is not None:
        source = f"csv:{csv_path}"
        rows = _read_csv_rows(csv_path)
    else:
        source = f"duckdb:{db_path}:{PAST_RACE_ROWS_TABLE}"
        rows = _read_duckdb_rows(db_path)

    return build_audit_report(rows, source=source)


def build_audit_report(rows: list[dict[str, str]], *, source: str) -> AuditReport:
    race_ids = {_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}
    track_row_counts = Counter(_clean(row.get("track")) or "(blank)" for row in rows)
    track_race_ids: dict[str, set[str]] = defaultdict(set)
    finish_counts = Counter(_clean(row.get("finish_position")).upper() or "(blank)" for row in rows)

    for row in rows:
        track = _clean(row.get("track")) or "(blank)"
        race_id = _clean(row.get("race_id"))
        if race_id:
            track_race_ids[track].add(race_id)

    missing_counts = {
        column: sum(1 for row in rows if not _clean(row.get(column)))
        for column in REQUIRED_COLUMNS
    }
    top_missing = sorted(
        ((column, count) for column, count in missing_counts.items() if count > 0),
        key=lambda item: (-item[1], item[0]),
    )[:10]

    dates = sorted(_clean(row.get("date")) for row in rows if _clean(row.get("date")))
    field_size_lines = _field_size_mismatch_lines(rows)
    duplicate_lines = _horse_no_duplicate_lines(rows)
    race_no_gap_lines = _race_no_gap_lines(rows)
    feature_counts = _feature_counts(rows)

    lines: list[str] = [
        "Nankan Dataset Audit",
        f"source: {source}",
        f"total_rows: {len(rows)}",
        f"race_count: {len(race_ids)}",
        f"date_min: {dates[0] if dates else '(none)'}",
        f"date_max: {dates[-1] if dates else '(none)'}",
        "",
        "track_race_counts:",
    ]
    lines.extend(_counter_lines({track: len(ids) for track, ids in track_race_ids.items()}))
    lines.extend(["", "track_row_counts:"])
    lines.extend(_counter_lines(track_row_counts))
    lines.extend(["", "month_race_counts:"])
    lines.extend(_counter_lines(_month_race_counts(rows)))
    lines.extend(["", "top_missing_columns:"])
    lines.extend([f"  {column}: {count}" for column, count in top_missing] or ["  none"])
    lines.extend(["", "finish_position_counts:"])
    lines.extend(_counter_lines(finish_counts))
    lines.extend(["", "field_size_mismatches:"])
    lines.extend(field_size_lines or ["  none"])
    lines.extend(["", "horse_no_duplicates:"])
    lines.extend(duplicate_lines or ["  none"])
    lines.extend(["", "race_no_sequence_gaps:"])
    lines.extend(race_no_gap_lines or ["  none"])
    lines.extend(["", "basic_feature_counts:"])
    lines.extend([f"  {name}: {count}" for name, count in feature_counts.items()])

    return AuditReport(source=source, lines=tuple(lines))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Nankan past-race data quality.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="DuckDB input path")
    parser.add_argument("--csv-path", default=None, help="Audit a CSV directly instead of DuckDB")
    args = parser.parse_args(argv)

    try:
        report = audit_dataset(db_path=args.db_path, csv_path=args.csv_path)
    except FileNotFoundError as exc:
        print(f"NG: {exc}")
        return 1
    except duckdb.CatalogException:
        print(f"NG: DuckDB table not found: {PAST_RACE_ROWS_TABLE}")
        return 1
    except duckdb.IOException as exc:
        print(f"NG: DuckDB could not be opened: {exc}")
        return 1

    print(report.format())
    return 0


def _read_csv_rows(csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {column: _clean(row.get(column)) for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def _read_duckdb_rows(db_path: str | Path) -> list[dict[str, str]]:
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db}")

    columns = ", ".join(_quote_identifier(column) for column in REQUIRED_COLUMNS)
    with duckdb.connect(str(db), read_only=True) as conn:
        records = conn.execute(
            f"SELECT {columns} FROM {PAST_RACE_ROWS_TABLE}"
        ).fetchall()

    return [
        {column: "" if value is None else str(value) for column, value in zip(REQUIRED_COLUMNS, record)}
        for record in records
    ]


def _field_size_mismatch_lines(rows: list[dict[str, str]]) -> list[str]:
    race_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        if race_id:
            race_rows[race_id].append(row)

    lines: list[str] = []
    for race_id, group in sorted(race_rows.items()):
        sizes = sorted({_to_int(row.get("field_size")) for row in group if _to_int(row.get("field_size")) is not None})
        actual = len(group)
        if not sizes:
            lines.append(f"  {race_id}: field_size missing, actual_rows={actual}")
            continue
        if len(sizes) > 1:
            lines.append(f"  {race_id}: multiple field_size values={sizes}, actual_rows={actual}")
            continue
        declared = sizes[0]
        if declared != actual:
            lines.append(f"  {race_id}: field_size={declared}, actual_rows={actual}, diff={declared - actual}")
    return lines


def _horse_no_duplicate_lines(rows: list[dict[str, str]]) -> list[str]:
    seen: dict[str, dict[str, int]] = defaultdict(dict)
    duplicates: list[str] = []
    for index, row in enumerate(rows, start=2):
        race_id = _clean(row.get("race_id"))
        horse_no = _clean(row.get("horse_no"))
        if not race_id or not horse_no:
            continue
        first_row = seen[race_id].get(horse_no)
        if first_row is not None:
            duplicates.append(
                f"  {race_id}: horse_no={horse_no} duplicate at row {index}, first row {first_row}"
            )
        else:
            seen[race_id][horse_no] = index
    return duplicates


def _month_race_counts(rows: list[dict[str, str]]) -> Counter[str]:
    month_races: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        race_id = _clean(row.get("race_id"))
        race_date = _clean(row.get("date"))
        if race_id and len(race_date) >= 7:
            month_races[race_date[:7]].add(race_id)
    return Counter({month: len(race_ids) for month, race_ids in month_races.items()})


def _race_no_gap_lines(rows: list[dict[str, str]]) -> list[str]:
    race_numbers: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in rows:
        race_date = _clean(row.get("date"))
        track = _clean(row.get("track"))
        race_no = _to_int(row.get("race_no"))
        if race_date and track and race_no is not None:
            race_numbers[(race_date, track)].add(race_no)

    lines: list[str] = []
    for (race_date, track), numbers in sorted(race_numbers.items()):
        if not numbers:
            continue
        expected = set(range(min(numbers), max(numbers) + 1))
        missing = sorted(expected - numbers)
        if missing:
            missing_text = ",".join(str(number) for number in missing)
            present_text = ",".join(str(number) for number in sorted(numbers))
            lines.append(
                f"  {race_date} {track}: missing_race_no={missing_text}, present={present_text}"
            )
    return lines


def _feature_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "win_flag": 0,
        "second_flag": 0,
        "top3_flag": 0,
        "is_scratched": 0,
        "is_dnf": 0,
    }
    for row in rows:
        featured = add_basic_features(row)
        for name in counts:
            counts[name] += int(featured[name])
    return counts


def _counter_lines(counter: Counter[str] | dict[str, int]) -> list[str]:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [f"  {key}: {value}" for key, value in items] or ["  none"]


def _to_int(value: object) -> int | None:
    text = _clean(value)
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
