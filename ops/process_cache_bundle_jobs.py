from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nankan_ai.append_batch_log import file_sha256
from nankan_ai.build_append_from_cache import build_append_from_cache
from nankan_ai.import_cache_bundle import import_cache_bundle
from nankan_ai.merge_append_csv import merge_append_csv
from nankan_ai.validate_append_csv import format_append_validation_result, validate_append_csv


DEFAULT_JOBS = (
    "job_20260618_191957_p02",
    "job_20260618_191957_p03",
    "job_20260618_191957_p04",
    "job_20260618_191957_p05",
)
ROOT = Path(".")
RAW_CSV = ROOT / "data/raw/nankan_past_races.csv"
APPEND_CSV = ROOT / "data/incoming/nankan_past_races_append.csv"
BUNDLES_DIR = ROOT / "data/cache/bundles"
REPORTS_DIR = ROOT / "data/reports"


@dataclass
class JobSummary:
    job_id: str
    bundle_path: str
    imported: int
    skipped_existing_html: int
    append_rows: int
    append_races: int
    dry_run_status: str
    apply_status: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import cache bundles and process fetch jobs one by one. "
            "Default mode stops before raw apply."
        )
    )
    parser.add_argument("--jobs", nargs="+", default=list(DEFAULT_JOBS))
    parser.add_argument("--expected-start-raw-sha256", default="")
    parser.add_argument("--apply", action="store_true", help="Apply each job after successful dry-run.")
    parser.add_argument(
        "--continue-on-official-no-result",
        action="store_true",
        default=True,
        help="Continue when cached official error pages parse to zero rows.",
    )
    args = parser.parse_args()

    if args.expected_start_raw_sha256:
        actual = file_sha256(RAW_CSV)
        if actual.upper() != args.expected_start_raw_sha256.upper():
            print("NG: start raw SHA256 mismatch.")
            print(f"expected: {args.expected_start_raw_sha256.upper()}")
            print(f"actual:   {actual.upper()}")
            return 1

    summaries: list[JobSummary] = []
    started_at = datetime.now().strftime("%Y%m%d_%H%M%S")

    for job_id in args.jobs:
        print(f"\n=== {job_id} ===")
        job_csv = ROOT / f"data/jobs/fetch_job_{job_id}.csv"
        if not job_csv.exists():
            print(f"NG: fetch job CSV not found: {job_csv}")
            return 1

        try:
            bundle_path = resolve_bundle(job_id)
            import_result = import_cache_bundle(bundle_path)
            print(f"imported_html: {len(import_result.imported)}")
            print(f"skipped_existing_html: {len(import_result.skipped_existing)}")
            print(f"import_errors: {len(import_result.errors)}")
            if import_result.errors:
                for error in import_result.errors:
                    print(f"ERROR: {error}")
                return 1

            build_result = build_append_from_cache(
                fetch_plan_csv_path=job_csv,
                output_path=APPEND_CSV,
                exclude_existing=True,
            )
            print(f"append_rows: {build_result.row_count}")
            print(f"append_races: {build_result.race_count}")
            for warning in build_result.warnings:
                print(f"WARNING: {warning}")

            if build_result.row_count == 0:
                print("NG: append CSV has no rows. Stop before merge.")
                return 1

            validation = validate_append_csv(APPEND_CSV, raw_csv_path=RAW_CSV)
            print(format_append_validation_result(validation))
            if not validation.is_valid:
                print("NG: append validation failed. Stop before dry-run/apply.")
                return 1

            dry_code = merge_append_csv(APPEND_CSV, apply=False)
            if dry_code != 0:
                print("NG: merge dry-run failed. Stop before apply.")
                return dry_code

            apply_status = "not_requested"
            if args.apply:
                apply_code = merge_append_csv(APPEND_CSV, apply=True)
                if apply_code != 0:
                    print("NG: apply failed or was blocked.")
                    print_resume_guidance()
                    return apply_code
                apply_status = "applied"

            summaries.append(
                JobSummary(
                    job_id=job_id,
                    bundle_path=str(bundle_path),
                    imported=len(import_result.imported),
                    skipped_existing_html=len(import_result.skipped_existing),
                    append_rows=build_result.row_count,
                    append_races=build_result.race_count,
                    dry_run_status="passed",
                    apply_status=apply_status,
                )
            )
        except Exception as exc:  # noqa: BLE001 - print recovery guidance for operators.
            print(f"NG: {job_id} failed: {exc}")
            print_resume_guidance()
            write_summary(started_at, summaries)
            return 1

    report_path = write_summary(started_at, summaries)
    print(f"\nOK: wrote bulk job report to {report_path}")
    if not args.apply:
        print("raw apply was not run. Re-run with --apply after reviewing dry-run results.")
    return 0


def resolve_bundle(job_id: str) -> Path:
    direct = BUNDLES_DIR / f"cache_bundle_{job_id}.zip"
    if direct.exists():
        return direct

    downloaded = BUNDLES_DIR / f"cache_bundle_{job_id}_downloaded.zip"
    if downloaded.exists():
        extracted = extract_inner_bundle(downloaded, job_id, direct)
        if extracted.exists():
            return extracted
        return downloaded

    candidates = sorted(BUNDLES_DIR.glob(f"**/cache_bundle_{job_id}.zip"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"cache bundle not found for {job_id}. Expected {direct} or {downloaded}."
    )


def extract_inner_bundle(downloaded_zip: Path, job_id: str, target: Path) -> Path:
    with zipfile.ZipFile(downloaded_zip, "r") as archive:
        names = archive.namelist()
        inner_name = f"cache_bundle_{job_id}.zip"
        if inner_name not in names:
            return downloaded_zip
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(inner_name) as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)
    return target


def write_summary(started_at: str, summaries: list[JobSummary]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"bulk_cache_bundle_jobs_{started_at}.md"
    lines = [
        "# Bulk Cache Bundle Job Report",
        "",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- raw_sha256_now: `{file_sha256(RAW_CSV)}`",
        "",
        "| job_id | imported_html | skipped_existing_html | append_rows | append_races | dry_run | apply |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for summary in summaries:
        lines.append(
            "| {job_id} | {imported} | {skipped} | {rows} | {races} | {dry} | {apply} |".format(
                job_id=summary.job_id,
                imported=summary.imported,
                skipped=summary.skipped_existing_html,
                rows=summary.append_rows,
                races=summary.append_races,
                dry=summary.dry_run_status,
                apply=summary.apply_status,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def print_resume_guidance() -> None:
    states = sorted(REPORTS_DIR.glob("append_state_append_*.json"), key=lambda p: p.stat().st_mtime)
    if states:
        latest = states[-1]
        print(f"latest_append_state: {latest}")
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            print(f"completed_steps: {', '.join(payload.get('completed_steps', []))}")
            failed_step = payload.get("failed_step") or "(none recorded)"
            print(f"failed_step: {failed_step}")
        except json.JSONDecodeError:
            pass
        print("resume command:")
        print(f"  python -m nankan_ai.merge_append_csv --resume {latest}")
    else:
        print("No append_state file was found.")


def append_csv_counts(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows), len({row["race_id"] for row in rows})


if __name__ == "__main__":
    sys.exit(main())
