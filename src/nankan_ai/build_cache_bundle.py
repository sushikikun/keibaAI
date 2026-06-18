from __future__ import annotations

import argparse
import csv
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .append_batch_log import file_sha256
from .export_fetch_job import DEFAULT_JOBS_DIR, FETCH_JOB_SOURCE
from .fetch_plan import DEFAULT_CACHE_HTML_DIR
from .fetch_result_pages import DEFAULT_FETCH_LOG_PATH

DEFAULT_BUNDLES_DIR = Path("data/cache/bundles")


@dataclass(frozen=True)
class CacheBundleBuildResult:
    bundle_path: Path
    job_id: str
    html_count: int
    warnings: tuple[str, ...] = ()


def build_cache_bundle(
    *,
    job_id: str,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    bundles_dir: str | Path = DEFAULT_BUNDLES_DIR,
    job_csv_path: str | Path | None = None,
    job_json_path: str | Path | None = None,
    fetch_log_path: str | Path = DEFAULT_FETCH_LOG_PATH,
    output_path: str | Path | None = None,
    now: datetime | None = None,
) -> CacheBundleBuildResult:
    created_at = (now or datetime.now()).astimezone().isoformat(timespec="seconds")
    cache_dir = Path(cache_html_dir)
    resolved_job_csv = Path(job_csv_path) if job_csv_path else Path(DEFAULT_JOBS_DIR) / f"fetch_job_{job_id}.csv"
    resolved_job_json = Path(job_json_path) if job_json_path else Path(DEFAULT_JOBS_DIR) / f"fetch_job_{job_id}.json"
    race_ids = _race_ids_from_job(resolved_job_csv, resolved_job_json)
    html_paths, missing_html = _html_paths_for_bundle(cache_dir, race_ids)
    if not html_paths:
        raise ValueError("No HTML files found for this cache bundle.")

    bundle_path = Path(output_path) if output_path else Path(bundles_dir) / f"cache_bundle_{job_id}.zip"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    html_entries = [
        {
            "race_id": path.stem,
            "path": f"html/{path.name}",
            "sha256": file_sha256(path),
            "byte_size": path.stat().st_size,
        }
        for path in html_paths
    ]
    manifest = {
        "manifest_version": 1,
        "job_id": job_id,
        "created_at": created_at,
        "source": FETCH_JOB_SOURCE,
        "html_count": len(html_entries),
        "html_files": html_entries,
        "missing_html": missing_html,
    }

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in html_paths:
            bundle.write(path, arcname=f"html/{path.name}")
        bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        if Path(fetch_log_path).exists():
            bundle.write(fetch_log_path, arcname="fetch_log.csv")
        if resolved_job_csv.exists():
            bundle.write(resolved_job_csv, arcname=f"jobs/{resolved_job_csv.name}")
        if resolved_job_json.exists():
            bundle.write(resolved_job_json, arcname=f"jobs/{resolved_job_json.name}")

    return CacheBundleBuildResult(
        bundle_path=bundle_path,
        job_id=job_id,
        html_count=len(html_entries),
        warnings=tuple(f"missing_html: {race_id}" for race_id in missing_html),
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a portable cache bundle ZIP from cached official result HTML files."
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--bundles-dir", default=str(DEFAULT_BUNDLES_DIR))
    parser.add_argument("--job-csv-path", default=None)
    parser.add_argument("--job-json-path", default=None)
    parser.add_argument("--fetch-log-path", default=str(DEFAULT_FETCH_LOG_PATH))
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args(argv)

    result = build_cache_bundle(
        job_id=args.job_id,
        cache_html_dir=args.cache_html_dir,
        bundles_dir=args.bundles_dir,
        job_csv_path=args.job_csv_path,
        job_json_path=args.job_json_path,
        fetch_log_path=args.fetch_log_path,
        output_path=args.output_path,
    )
    print(f"OK: wrote cache bundle to {result.bundle_path}")
    print(f"job_id: {result.job_id}")
    print(f"html_count: {result.html_count}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    return 0


def _race_ids_from_job(job_csv_path: Path, job_json_path: Path) -> list[str]:
    if job_csv_path.exists():
        with job_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [
                str(row.get("race_id", "")).strip()
                for row in csv.DictReader(handle)
                if str(row.get("race_id", "")).strip()
            ]
    if job_json_path.exists():
        with job_json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return [str(race_id).strip() for race_id in payload.get("race_ids", []) if str(race_id).strip()]
    return []


def _html_paths_for_bundle(cache_html_dir: Path, race_ids: list[str]) -> tuple[list[Path], list[str]]:
    if race_ids:
        paths: list[Path] = []
        missing: list[str] = []
        for race_id in race_ids:
            path = cache_html_dir / f"{race_id}.html"
            if path.exists():
                paths.append(path)
            else:
                missing.append(race_id)
        return paths, missing
    return sorted(cache_html_dir.glob("*.html")), []


__all__ = [
    "DEFAULT_BUNDLES_DIR",
    "CacheBundleBuildResult",
    "build_cache_bundle",
]


if __name__ == "__main__":
    raise SystemExit(main())

