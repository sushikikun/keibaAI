from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from .append_batch_log import file_sha256
from .export_fetch_job import DEFAULT_JOBS_DIR, ExportFetchJobResult, export_fetch_job
from .fetch_plan import DEFAULT_CACHE_HTML_DIR, FetchPlanRow, build_fetch_plan
from .schema import DEFAULT_RAW_CSV_PATH, TRACKS

DEFAULT_REPORTS_DIR = Path("data/reports")
BULK_JOB_PLAN_COLUMNS = (
    "wave_id",
    "part_number",
    "job_id",
    "date_from",
    "date_to",
    "candidate_races",
    "cache_skipped_races",
    "race_id_first",
    "race_id_last",
    "job_csv_path",
    "job_json_path",
)


@dataclass(frozen=True)
class DateWindow:
    part_number: int
    date_from: str
    date_to: str


@dataclass(frozen=True)
class PlannedBulkJob:
    job_id: str
    wave_id: str
    part_number: int
    date_from: str
    date_to: str
    rows: list[FetchPlanRow]
    cache_skipped_races: int
    csv_path: Path
    json_path: Path

    @property
    def candidate_races(self) -> int:
        return len(self.rows)

    @property
    def race_id_first(self) -> str:
        return self.rows[0].race_id if self.rows else ""

    @property
    def race_id_last(self) -> str:
        return self.rows[-1].race_id if self.rows else ""

    def as_report_row(self) -> dict[str, str]:
        return {
            "wave_id": self.wave_id,
            "part_number": str(self.part_number),
            "job_id": self.job_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "candidate_races": str(self.candidate_races),
            "cache_skipped_races": str(self.cache_skipped_races),
            "race_id_first": self.race_id_first,
            "race_id_last": self.race_id_last,
            "job_csv_path": _path_string(self.csv_path),
            "job_json_path": _path_string(self.json_path),
        }


@dataclass(frozen=True)
class BulkJobPlanResult:
    track: str
    windows: int
    jobs: list[PlannedBulkJob]
    raw_sha256_at_export: str
    dry_run: bool
    csv_report_path: Path | None
    md_report_path: Path | None

    @property
    def jobs_created(self) -> int:
        return len(self.jobs)

    @property
    def total_candidate_races(self) -> int:
        return sum(job.candidate_races for job in self.jobs)

    @property
    def date_min(self) -> str:
        return min((job.date_from for job in self.jobs), default="")

    @property
    def date_max(self) -> str:
        return max((job.date_to for job in self.jobs), default="")


def plan_bulk_jobs(
    *,
    track: str,
    anchor_date: str,
    window_days: int,
    windows: int,
    race_no_from: int,
    race_no_to: int,
    jobs_per_wave: int,
    job_prefix: str,
    jobs_dir: str | Path = DEFAULT_JOBS_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    dry_run: bool = False,
    now: datetime | None = None,
) -> BulkJobPlanResult:
    normalized_track = track.strip().lower()
    _validate_inputs(
        track=normalized_track,
        window_days=window_days,
        windows=windows,
        race_no_from=race_no_from,
        race_no_to=race_no_to,
        jobs_per_wave=jobs_per_wave,
        job_prefix=job_prefix,
    )

    jobs_root = Path(jobs_dir)
    report_root = Path(reports_dir)
    raw_sha256 = file_sha256(raw_csv_path)
    job_windows = build_date_windows(anchor_date, window_days=window_days, windows=windows)
    planned_jobs: list[PlannedBulkJob] = []
    for window in job_windows:
        job_id = make_bulk_job_id(job_prefix, window.part_number, jobs_per_wave)
        wave_id = make_wave_id(window.part_number, jobs_per_wave)
        csv_path = jobs_root / f"fetch_job_{job_id}.csv"
        json_path = jobs_root / f"fetch_job_{job_id}.json"
        rows_before_cache = build_fetch_plan(
            track=normalized_track,
            date_from=window.date_from,
            date_to=window.date_to,
            race_no_from=race_no_from,
            race_no_to=race_no_to,
            raw_csv_path=raw_csv_path,
            cache_html_dir=cache_html_dir,
            exclude_existing=True,
            date_order="desc",
        )
        rows = [row for row in rows_before_cache if not Path(row.cache_html_path).exists()]
        planned_jobs.append(
            PlannedBulkJob(
                job_id=job_id,
                wave_id=wave_id,
                part_number=window.part_number,
                date_from=window.date_from,
                date_to=window.date_to,
                rows=rows,
                cache_skipped_races=len(rows_before_cache) - len(rows),
                csv_path=csv_path,
                json_path=json_path,
            )
        )

    _assert_no_existing_job_files(planned_jobs)
    if dry_run:
        return BulkJobPlanResult(
            track=normalized_track,
            windows=windows,
            jobs=planned_jobs,
            raw_sha256_at_export=raw_sha256,
            dry_run=True,
            csv_report_path=None,
            md_report_path=None,
        )

    created_at = now or datetime.now()
    for job in planned_jobs:
        _export_planned_job(
            job,
            track=normalized_track,
            raw_csv_path=raw_csv_path,
            jobs_dir=jobs_root,
            cache_html_dir=cache_html_dir,
            now=created_at,
        )

    csv_report, md_report = write_bulk_job_reports(
        planned_jobs,
        track=normalized_track,
        windows=windows,
        raw_sha256_at_export=raw_sha256,
        reports_dir=report_root,
        now=created_at,
    )
    return BulkJobPlanResult(
        track=normalized_track,
        windows=windows,
        jobs=planned_jobs,
        raw_sha256_at_export=raw_sha256,
        dry_run=False,
        csv_report_path=csv_report,
        md_report_path=md_report,
    )


def build_date_windows(anchor_date: str, *, window_days: int, windows: int) -> list[DateWindow]:
    if window_days < 1:
        raise ValueError("window_days must be positive.")
    if windows < 1:
        raise ValueError("windows must be positive.")

    anchor = date.fromisoformat(anchor_date)
    results: list[DateWindow] = []
    for index in range(windows):
        part_number = index + 1
        date_to = anchor - timedelta(days=index * window_days)
        date_from = date_to - timedelta(days=window_days - 1)
        results.append(
            DateWindow(
                part_number=part_number,
                date_from=date_from.isoformat(),
                date_to=date_to.isoformat(),
            )
        )
    return results


def make_wave_id(part_number: int, jobs_per_wave: int) -> str:
    if jobs_per_wave < 1:
        raise ValueError("jobs_per_wave must be positive.")
    return f"w{((part_number - 1) // jobs_per_wave) + 1:02d}"


def make_bulk_job_id(job_prefix: str, part_number: int, jobs_per_wave: int) -> str:
    return f"{job_prefix}_{make_wave_id(part_number, jobs_per_wave)}_p{part_number:02d}"


def write_bulk_job_reports(
    jobs: list[PlannedBulkJob],
    *,
    track: str,
    windows: int,
    raw_sha256_at_export: str,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    report_root = Path(reports_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    csv_path = report_root / f"bulk_job_plan_{track}_{timestamp}.csv"
    md_path = report_root / f"bulk_job_plan_{track}_{timestamp}.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BULK_JOB_PLAN_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(job.as_report_row() for job in jobs)

    md_path.write_text(
        _format_markdown_report(
            jobs,
            track=track,
            windows=windows,
            raw_sha256_at_export=raw_sha256_at_export,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return csv_path, md_path


def format_summary(result: BulkJobPlanResult) -> str:
    lines = [
        "DRY-RUN: no files were written." if result.dry_run else "OK: wrote bulk fetch jobs.",
        f"track: {result.track}",
        f"windows: {result.windows}",
        f"jobs_created: {result.jobs_created}",
        f"total_candidate_races: {result.total_candidate_races}",
        f"date_min: {result.date_min}",
        f"date_max: {result.date_max}",
        f"raw_sha256_at_export: {result.raw_sha256_at_export}",
    ]
    if result.csv_report_path:
        lines.append(f"csv_report: {result.csv_report_path}")
    if result.md_report_path:
        lines.append(f"md_report: {result.md_report_path}")
    lines.extend(_format_wave_summary_lines(result.jobs))
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan many official result-page fetch jobs in date windows."
    )
    parser.add_argument("--track", required=True, choices=sorted(TRACKS))
    parser.add_argument("--anchor-date", required=True)
    parser.add_argument("--window-days", required=True, type=int)
    parser.add_argument("--windows", required=True, type=int)
    parser.add_argument("--race-no-from", required=True, type=int)
    parser.add_argument("--race-no-to", required=True, type=int)
    parser.add_argument("--jobs-per-wave", required=True, type=int)
    parser.add_argument("--job-prefix", required=True)
    parser.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = plan_bulk_jobs(
        track=args.track,
        anchor_date=args.anchor_date,
        window_days=args.window_days,
        windows=args.windows,
        race_no_from=args.race_no_from,
        race_no_to=args.race_no_to,
        jobs_per_wave=args.jobs_per_wave,
        job_prefix=args.job_prefix,
        jobs_dir=args.jobs_dir,
        reports_dir=args.reports_dir,
        raw_csv_path=args.raw_csv_path,
        cache_html_dir=args.cache_html_dir,
        dry_run=args.dry_run,
    )
    print(format_summary(result))
    return 0


def _export_planned_job(
    job: PlannedBulkJob,
    *,
    track: str,
    raw_csv_path: str | Path,
    jobs_dir: str | Path,
    cache_html_dir: str | Path,
    now: datetime,
) -> ExportFetchJobResult:
    return export_fetch_job(
        track=track,
        date_from=job.date_from,
        date_to=job.date_to,
        fetch_plan_rows=job.rows,
        raw_csv_path=raw_csv_path,
        jobs_dir=jobs_dir,
        cache_html_dir=cache_html_dir,
        job_id=job.job_id,
        now=now,
    )


def _format_markdown_report(
    jobs: list[PlannedBulkJob],
    *,
    track: str,
    windows: int,
    raw_sha256_at_export: str,
) -> str:
    lines = [
        "# Bulk Job Plan",
        "",
        f"- track: {track}",
        f"- windows: {windows}",
        f"- jobs_created: {len(jobs)}",
        f"- total_candidate_races: {sum(job.candidate_races for job in jobs)}",
        f"- date_min: {min((job.date_from for job in jobs), default='')}",
        f"- date_max: {max((job.date_to for job in jobs), default='')}",
        f"- raw_sha256_at_export: `{raw_sha256_at_export}`",
        "",
        "## Waves",
        "",
    ]
    lines.extend(_format_wave_summary_lines(jobs))
    lines.extend(
        [
            "",
            "## Jobs",
            "",
            "| wave | part | job_id | date_from | date_to | candidate_races | cache_skipped | race_id_first | race_id_last |",
            "|---|---:|---|---|---|---:|---:|---|---|",
        ]
    )
    for job in jobs:
        lines.append(
            "| "
            + " | ".join(
                [
                    job.wave_id,
                    str(job.part_number),
                    job.job_id,
                    job.date_from,
                    job.date_to,
                    str(job.candidate_races),
                    str(job.cache_skipped_races),
                    job.race_id_first,
                    job.race_id_last,
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _format_wave_summary_lines(jobs: list[PlannedBulkJob]) -> list[str]:
    lines: list[str] = []
    wave_ids = sorted({job.wave_id for job in jobs})
    for wave_id in wave_ids:
        wave_jobs = [job for job in jobs if job.wave_id == wave_id]
        job_ids = ", ".join(job.job_id for job in wave_jobs)
        wave_total = sum(job.candidate_races for job in wave_jobs)
        lines.append(f"{wave_id}: {job_ids} ({wave_total} candidate races)")
    return lines


def _assert_no_existing_job_files(jobs: list[PlannedBulkJob]) -> None:
    existing = [
        path
        for job in jobs
        for path in (job.csv_path, job.json_path)
        if path.exists()
    ]
    if existing:
        raise FileExistsError(
            "fetch job file already exists; refusing to overwrite: "
            + ", ".join(_path_string(path) for path in existing)
        )


def _validate_inputs(
    *,
    track: str,
    window_days: int,
    windows: int,
    race_no_from: int,
    race_no_to: int,
    jobs_per_wave: int,
    job_prefix: str,
) -> None:
    if track not in TRACKS:
        raise ValueError(f"track must be one of: {', '.join(sorted(TRACKS))}")
    if window_days < 1:
        raise ValueError("window_days must be positive.")
    if windows < 1:
        raise ValueError("windows must be positive.")
    if race_no_from < 1 or race_no_to < race_no_from:
        raise ValueError("race_no_from/race_no_to must be a positive inclusive range.")
    if jobs_per_wave < 1:
        raise ValueError("jobs_per_wave must be positive.")
    if not job_prefix.strip():
        raise ValueError("job_prefix is required.")


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "BULK_JOB_PLAN_COLUMNS",
    "BulkJobPlanResult",
    "DateWindow",
    "PlannedBulkJob",
    "build_date_windows",
    "format_summary",
    "make_bulk_job_id",
    "make_wave_id",
    "plan_bulk_jobs",
    "write_bulk_job_reports",
]


if __name__ == "__main__":
    raise SystemExit(main())
