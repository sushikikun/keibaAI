from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .fetch_plan import DEFAULT_CACHE_HTML_DIR
from .parse_result_pages import parse_result_page_file
from .schema import DEFAULT_RAW_CSV_PATH, REQUIRED_COLUMNS
from .validate_append_csv import DEFAULT_APPEND_CSV_PATH, format_append_validation_result, validate_append_csv


@dataclass
class AppendBuildResult:
    output_path: Path
    row_count: int
    race_count: int
    warnings: list[str] = field(default_factory=list)
    validation_status: str = "not_run"


def build_append_from_cache(
    *,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    fetch_plan_csv_path: str | Path | None = None,
    output_path: str | Path = DEFAULT_APPEND_CSV_PATH,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    exclude_existing: bool = True,
    run_validation: bool = False,
) -> AppendBuildResult:
    raw_path = Path(raw_csv_path)
    output = Path(output_path)
    raw_header = _read_header(raw_path)
    if raw_header != list(REQUIRED_COLUMNS):
        raise ValueError("existing raw CSV header does not match the current required schema.")

    existing_race_ids = _load_existing_race_ids(raw_path) if exclude_existing else set()
    html_paths = _html_paths(fetch_plan_csv_path, cache_html_dir)
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    skipped_existing = 0
    for html_path in html_paths:
        parsed = parse_result_page_file(html_path)
        if exclude_existing and parsed.race_id in existing_race_ids:
            skipped_existing += 1
            continue
        rows.extend(parsed.rows)
        warnings.extend(f"{parsed.race_id}: {warning}" for warning in parsed.warnings)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=raw_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in raw_header} for row in rows)

    if skipped_existing:
        warnings.append(f"skipped_existing_races: {skipped_existing}")

    validation_status = "not_run"
    if run_validation:
        validation = validate_append_csv(output, raw_csv_path=raw_path)
        validation_status = "passed" if validation.is_valid else "failed"
        print(format_append_validation_result(validation))

    race_ids = {_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}
    return AppendBuildResult(
        output_path=output,
        row_count=len(rows),
        race_count=len(race_ids),
        warnings=warnings,
        validation_status=validation_status,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build data/incoming/nankan_past_races_append.csv from cached result HTML."
    )
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--fetch-plan-csv", default=None)
    parser.add_argument("--output-path", default=str(DEFAULT_APPEND_CSV_PATH))
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Do not skip race_id values already present in the current raw CSV.",
    )
    parser.add_argument("--validate", action="store_true", help="Run validate_append_csv after writing.")
    args = parser.parse_args(argv)

    result = build_append_from_cache(
        cache_html_dir=args.cache_html_dir,
        fetch_plan_csv_path=args.fetch_plan_csv,
        output_path=args.output_path,
        raw_csv_path=args.raw_csv_path,
        exclude_existing=not args.include_existing,
        run_validation=args.validate,
    )
    print(f"OK: wrote append CSV to {result.output_path}")
    print(f"rows: {result.row_count}")
    print(f"races: {result.race_count}")
    print(f"validation: {result.validation_status}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    return 0 if result.row_count > 0 else 1


def _html_paths(fetch_plan_csv_path: str | Path | None, cache_html_dir: str | Path) -> list[Path]:
    if fetch_plan_csv_path:
        with Path(fetch_plan_csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            paths = [
                Path(_clean(row.get("cache_html_path")) or Path(cache_html_dir) / f"{_clean(row.get('race_id'))}.html")
                for row in reader
            ]
        return [path for path in paths if path.exists()]
    return sorted(Path(cache_html_dir).glob("*.html"))


def _read_header(raw_csv_path: Path) -> list[str]:
    with raw_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _load_existing_race_ids(raw_csv_path: Path) -> set[str]:
    with raw_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            _clean(row.get("race_id"))
            for row in reader
            if _clean(row.get("race_id"))
        }


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = ["AppendBuildResult", "build_append_from_cache"]


if __name__ == "__main__":
    raise SystemExit(main())

