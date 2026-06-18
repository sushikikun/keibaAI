from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .schema import DEFAULT_RAW_CSV_PATH, REQUIRED_COLUMNS

DEFAULT_REPORTS_DIR = Path("data/reports")
MISSING_RACES_FILENAME = "missing_win_odds_races.csv"
MISSING_ROWS_FILENAME = "missing_win_odds_rows.csv"

RACE_REPORT_COLUMNS = (
    "race_id",
    "date",
    "track",
    "race_no",
    "race_name",
    "distance",
    "field_size",
    "total_rows",
    "missing_rows",
    "missing_rate",
    "normal_missing_rows",
    "scr_missing_rows",
    "exc_missing_rows",
    "dnf_missing_rows",
)

ROW_REPORT_COLUMNS = (
    "race_id",
    "date",
    "track",
    "race_no",
    "race_name",
    "distance",
    "field_size",
    "horse_no",
    "gate_no",
    "horse_name",
    "finish_position",
    "start_type",
    "popularity",
    "win_odds_final",
)


@dataclass(frozen=True)
class MissingOddsReport:
    source: str
    reports_dir: Path
    lines: tuple[str, ...]

    def format(self) -> str:
        return "\n".join(self.lines)


def audit_missing_odds(
    *,
    csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
) -> MissingOddsReport:
    rows = _read_csv_rows(csv_path)
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)

    missing_rows = [row for row in rows if not _clean(row.get("win_odds_final"))]
    race_report_rows = _build_missing_race_rows(rows, missing_rows)
    row_report_rows = [_missing_row_report_row(row) for row in missing_rows]

    _write_csv(reports / MISSING_RACES_FILENAME, RACE_REPORT_COLUMNS, race_report_rows)
    _write_csv(reports / MISSING_ROWS_FILENAME, ROW_REPORT_COLUMNS, row_report_rows)

    lines = _build_report_lines(
        rows=rows,
        missing_rows=missing_rows,
        race_report_rows=race_report_rows,
        source=f"csv:{csv_path}",
        reports_dir=reports,
    )
    return MissingOddsReport(source=f"csv:{csv_path}", reports_dir=reports, lines=tuple(lines))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit missing win_odds_final values.")
    parser.add_argument("--csv-path", default=str(DEFAULT_RAW_CSV_PATH), help="Raw CSV input path")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Report output directory")
    args = parser.parse_args(argv)

    try:
        report = audit_missing_odds(csv_path=args.csv_path, reports_dir=args.reports_dir)
    except FileNotFoundError as exc:
        print(f"NG: {exc}")
        return 1

    print(report.format())
    return 0


def _read_csv_rows(csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        return [
            {column: _clean(row.get(column)) for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def _build_missing_race_rows(
    rows: list[dict[str, str]],
    missing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    race_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    missing_by_race: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        race_rows[_clean(row.get("race_id"))].append(row)
    for row in missing_rows:
        missing_by_race[_clean(row.get("race_id"))].append(row)

    report_rows: list[dict[str, str]] = []
    for race_id, group in sorted(missing_by_race.items()):
        all_rows = race_rows[race_id]
        sample = all_rows[0]
        type_counts = Counter(_start_type(row) for row in group)
        total_rows = len(all_rows)
        missing_count = len(group)
        report_rows.append(
            {
                "race_id": race_id,
                "date": sample["date"],
                "track": sample["track"],
                "race_no": sample["race_no"],
                "race_name": sample["race_name"],
                "distance": sample["distance"],
                "field_size": sample["field_size"],
                "total_rows": str(total_rows),
                "missing_rows": str(missing_count),
                "missing_rate": _format_rate(missing_count, total_rows),
                "normal_missing_rows": str(type_counts["NORMAL"]),
                "scr_missing_rows": str(type_counts["SCR"]),
                "exc_missing_rows": str(type_counts["EXC"]),
                "dnf_missing_rows": str(type_counts["DNF"]),
            }
        )
    return report_rows


def _missing_row_report_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "race_id": row["race_id"],
        "date": row["date"],
        "track": row["track"],
        "race_no": row["race_no"],
        "race_name": row["race_name"],
        "distance": row["distance"],
        "field_size": row["field_size"],
        "horse_no": row["horse_no"],
        "gate_no": row["gate_no"],
        "horse_name": row["horse_name"],
        "finish_position": row["finish_position"],
        "start_type": _start_type(row),
        "popularity": row["popularity"],
        "win_odds_final": row["win_odds_final"],
    }


def _build_report_lines(
    *,
    rows: list[dict[str, str]],
    missing_rows: list[dict[str, str]],
    race_report_rows: list[dict[str, str]],
    source: str,
    reports_dir: Path,
) -> list[str]:
    race_ids = {_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}
    dates = sorted(_clean(row.get("date")) for row in rows if _clean(row.get("date")))
    missing_rate = _format_rate(len(missing_rows), len(rows))
    missing_race_ids = {row["race_id"] for row in missing_rows}

    lines = [
        "Win Odds Missing Audit",
        f"source: {source}",
        f"total_rows: {len(rows)}",
        f"race_count: {len(race_ids)}",
        f"date_min: {dates[0] if dates else '(none)'}",
        f"date_max: {dates[-1] if dates else '(none)'}",
        f"missing_win_odds_rows: {len(missing_rows)}",
        f"missing_win_odds_rate: {missing_rate}",
        f"missing_race_count: {len(missing_race_ids)}",
        "",
        "missing_by_date:",
    ]
    lines.extend(_counter_lines(Counter(row["date"] for row in missing_rows)))
    lines.extend(["", "missing_by_month:"])
    lines.extend(_counter_lines(Counter(row["date"][:7] for row in missing_rows)))
    lines.extend(["", "missing_by_race_no:"])
    lines.extend(_counter_lines(Counter(row["race_no"] for row in missing_rows), numeric_keys=True))
    lines.extend(["", "missing_by_field_size:"])
    lines.extend(_counter_lines(Counter(row["field_size"] for row in missing_rows), numeric_keys=True))
    lines.extend(["", "missing_by_finish_position:"])
    lines.extend(_counter_lines(Counter(row["finish_position"] for row in missing_rows)))
    lines.extend(["", "missing_by_start_type:"])
    lines.extend(_counter_lines(Counter(_start_type(row) for row in missing_rows)))
    lines.extend(["", "manual_check_candidate_races:"])
    lines.extend(_manual_check_candidate_lines(race_report_rows))
    lines.extend(
        [
            "",
            "output_files:",
            f"  {reports_dir / MISSING_RACES_FILENAME}",
            f"  {reports_dir / MISSING_ROWS_FILENAME}",
        ]
    )
    return lines


def _manual_check_candidate_lines(race_report_rows: list[dict[str, str]]) -> list[str]:
    candidates = [
        row for row in race_report_rows
        if _to_int(row["normal_missing_rows"]) > 0
    ]
    candidates.sort(
        key=lambda row: (
            -_to_int(row["normal_missing_rows"]),
            -_to_int(row["missing_rows"]),
            row["date"],
            _to_int(row["race_no"]),
        )
    )
    lines = []
    for row in candidates[:10]:
        lines.append(
            "  "
            f"{row['race_id']}: date={row['date']}, race_no={row['race_no']}, "
            f"missing_rows={row['missing_rows']}, normal_missing_rows={row['normal_missing_rows']}, "
            f"missing_rate={row['missing_rate']}, race_name={row['race_name']}"
        )
    return lines or ["  none"]


def _counter_lines(
    counter: Counter[str],
    *,
    numeric_keys: bool = False,
) -> list[str]:
    if numeric_keys:
        items = sorted(counter.items(), key=lambda item: _to_int(item[0]))
    else:
        items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [f"  {key or '(blank)'}: {value}" for key, value in items] or ["  none"]


def _start_type(row: dict[str, str]) -> str:
    finish = _clean(row.get("finish_position")).upper()
    if finish in {"SCR", "EXC", "DNF"}:
        return finish
    return "NORMAL"


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _format_rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{count / total * 100:.2f}%"


def _to_int(value: object) -> int:
    text = _clean(value)
    if not text or not text.lstrip("-").isdigit():
        return 0
    return int(text)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
