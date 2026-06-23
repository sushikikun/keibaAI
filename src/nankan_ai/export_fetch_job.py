from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .append_batch_log import file_sha256
from .fetch_plan import (
    DEFAULT_CACHE_HTML_DIR,
    FETCH_PLAN_COLUMNS,
    FetchPlanRow,
    build_fetch_plan,
)
from .schema import DEFAULT_RAW_CSV_PATH, TRACKS

DEFAULT_JOBS_DIR = Path("data/jobs")
FETCH_JOB_SOURCE = "keiba.go.jp official result page"


@dataclass(frozen=True)
class ExportFetchJobResult:
    job_id: str
    csv_path: Path
    json_path: Path
    race_count: int
    raw_sha256_at_export: str


def export_fetch_job(
    *,
    track: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    race_no_from: int | None = None,
    race_no_to: int | None = None,
    fetch_plan_csv_path: str | Path | None = None,
    fetch_plan_rows: list[FetchPlanRow | dict[str, str]] | None = None,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    jobs_dir: str | Path = DEFAULT_JOBS_DIR,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    job_id: str | None = None,
    now: datetime | None = None,
) -> ExportFetchJobResult:
    created_at = (now or datetime.now()).astimezone().isoformat(timespec="seconds")
    resolved_job_id = job_id or make_job_id(now)
    rows = _job_rows(
        track=track,
        date_from=date_from,
        date_to=date_to,
        race_no_from=race_no_from,
        race_no_to=race_no_to,
        fetch_plan_csv_path=fetch_plan_csv_path,
        fetch_plan_rows=fetch_plan_rows,
        raw_csv_path=raw_csv_path,
        cache_html_dir=cache_html_dir,
    )
    raw_sha256 = file_sha256(raw_csv_path)
    jobs = Path(jobs_dir)
    jobs.mkdir(parents=True, exist_ok=True)
    csv_path = jobs / f"fetch_job_{resolved_job_id}.csv"
    json_path = jobs / f"fetch_job_{resolved_job_id}.json"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FETCH_PLAN_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row for row in rows)

    dates = sorted({row["date"] for row in rows if row.get("date")})
    tracks = sorted({row["track"] for row in rows if row.get("track")})
    metadata = {
        "job_id": resolved_job_id,
        "created_at": created_at,
        "track": tracks[0] if len(tracks) == 1 else ";".join(tracks),
        "date_from": date_from or (dates[0] if dates else ""),
        "date_to": date_to or (dates[-1] if dates else ""),
        "race_count": len(rows),
        "race_ids": [row["race_id"] for row in rows],
        "source": FETCH_JOB_SOURCE,
        "raw_sha256_at_export": raw_sha256,
        "fetch_job_csv": _path_string(csv_path),
    }
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return ExportFetchJobResult(
        job_id=resolved_job_id,
        csv_path=csv_path,
        json_path=json_path,
        race_count=len(rows),
        raw_sha256_at_export=raw_sha256,
    )


def make_job_id(now: datetime | None = None) -> str:
    value = now or datetime.now()
    return f"job_{value.strftime('%Y%m%d_%H%M%S')}"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export an external HTML-fetch job from a fetch plan or range."
    )
    parser.add_argument("--track", choices=sorted(TRACKS), default=None)
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--race-no-from", type=int, default=None)
    parser.add_argument("--race-no-to", type=int, default=None)
    parser.add_argument("--fetch-plan-csv", default=None)
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--job-id", default=None)
    args = parser.parse_args(argv)

    result = export_fetch_job(
        track=args.track,
        date_from=args.date_from,
        date_to=args.date_to,
        race_no_from=args.race_no_from,
        race_no_to=args.race_no_to,
        fetch_plan_csv_path=args.fetch_plan_csv,
        raw_csv_path=args.raw_csv_path,
        jobs_dir=args.jobs_dir,
        cache_html_dir=args.cache_html_dir,
        job_id=args.job_id,
    )
    print(f"OK: wrote fetch job {result.job_id}")
    print(f"csv: {result.csv_path}")
    print(f"json: {result.json_path}")
    print(f"race_count: {result.race_count}")
    print(f"raw_sha256_at_export: {result.raw_sha256_at_export}")
    return 0


def _job_rows(
    *,
    track: str | None,
    date_from: str | None,
    date_to: str | None,
    race_no_from: int | None,
    race_no_to: int | None,
    fetch_plan_csv_path: str | Path | None,
    fetch_plan_rows: list[FetchPlanRow | dict[str, str]] | None,
    raw_csv_path: str | Path,
    cache_html_dir: str | Path,
) -> list[dict[str, str]]:
    if fetch_plan_rows is not None and fetch_plan_csv_path:
        raise ValueError("Provide only one of fetch_plan_rows or fetch_plan_csv_path.")
    if fetch_plan_rows is not None:
        rows = [
            row.as_csv_row() if isinstance(row, FetchPlanRow) else dict(row)
            for row in fetch_plan_rows
        ]
    elif fetch_plan_csv_path:
        rows = _read_fetch_plan_rows(fetch_plan_csv_path)
    else:
        if not all([track, date_from, date_to, race_no_from, race_no_to]):
            raise ValueError(
                "Provide fetch_plan_rows, --fetch-plan-csv, or all of --track, --date-from, --date-to, --race-no-from, --race-no-to."
            )
        plan_rows = build_fetch_plan(
            track=str(track),
            date_from=str(date_from),
            date_to=str(date_to),
            race_no_from=int(race_no_from),
            race_no_to=int(race_no_to),
            raw_csv_path=raw_csv_path,
            cache_html_dir=cache_html_dir,
            exclude_existing=True,
        )
        rows = [row.as_csv_row() for row in plan_rows]

    existing_race_ids = _existing_race_ids(raw_csv_path)
    return [
        {column: str(row.get(column, "")).strip() for column in FETCH_PLAN_COLUMNS}
        for row in rows
        if str(row.get("race_id", "")).strip() and str(row.get("race_id", "")).strip() not in existing_race_ids
    ]


def _read_fetch_plan_rows(fetch_plan_csv_path: str | Path) -> list[dict[str, str]]:
    with Path(fetch_plan_csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in FETCH_PLAN_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"fetch plan is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def _existing_race_ids(raw_csv_path: str | Path) -> set[str]:
    path = Path(raw_csv_path)
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            str(row.get("race_id", "")).strip()
            for row in reader
            if str(row.get("race_id", "")).strip()
        }


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "DEFAULT_JOBS_DIR",
    "FETCH_JOB_SOURCE",
    "ExportFetchJobResult",
    "export_fetch_job",
    "make_job_id",
]


if __name__ == "__main__":
    raise SystemExit(main())
