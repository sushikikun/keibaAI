from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from nankan_ai.append_batch_log import file_sha256
from nankan_ai.bulk_job_planner import (
    build_date_windows,
    make_bulk_job_id,
    plan_bulk_jobs,
)
from nankan_ai.schema import REQUIRED_COLUMNS


def test_build_date_windows_are_contiguous_without_overlap() -> None:
    windows = build_date_windows("2026-06-22", window_days=84, windows=20)

    assert len(windows) == 20
    assert (windows[0].date_from, windows[0].date_to) == ("2026-03-31", "2026-06-22")
    assert (windows[1].date_from, windows[1].date_to) == ("2026-01-06", "2026-03-30")
    assert (windows[2].date_from, windows[2].date_to) == ("2025-10-14", "2026-01-05")

    for previous, current in zip(windows, windows[1:]):
        previous_start = date.fromisoformat(previous.date_from)
        current_end = date.fromisoformat(current.date_to)
        assert current_end == previous_start - timedelta(days=1)
        assert date.fromisoformat(current.date_to) < date.fromisoformat(previous.date_from)


def test_make_bulk_job_id_is_stable_by_wave_and_part() -> None:
    prefix = "job_20260623_funabashi"

    assert make_bulk_job_id(prefix, 1, 5) == "job_20260623_funabashi_w01_p01"
    assert make_bulk_job_id(prefix, 5, 5) == "job_20260623_funabashi_w01_p05"
    assert make_bulk_job_id(prefix, 6, 5) == "job_20260623_funabashi_w02_p06"
    assert make_bulk_job_id(prefix, 20, 5) == "job_20260623_funabashi_w04_p20"


def test_plan_bulk_jobs_writes_funabashi_jobs_and_reports(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    jobs_dir = tmp_path / "jobs"
    reports_dir = tmp_path / "reports"
    cache_dir = tmp_path / "cache" / "html"
    _write_raw(raw_path, ["20260622_funabashi_1"])
    _write_cache(cache_dir, "20260621_funabashi_1")

    result = plan_bulk_jobs(
        track="funabashi",
        anchor_date="2026-06-22",
        window_days=1,
        windows=2,
        race_no_from=1,
        race_no_to=2,
        jobs_per_wave=1,
        job_prefix="job_20260623_funabashi",
        jobs_dir=jobs_dir,
        reports_dir=reports_dir,
        raw_csv_path=raw_path,
        cache_html_dir=cache_dir,
        now=datetime(2026, 6, 23, 12, 0, 0),
    )

    assert result.jobs_created == 2
    assert result.total_candidate_races == 2
    assert result.raw_sha256_at_export == file_sha256(raw_path)
    assert result.csv_report_path == reports_dir / "bulk_job_plan_funabashi_20260623_120000.csv"
    assert result.md_report_path == reports_dir / "bulk_job_plan_funabashi_20260623_120000.md"

    first_job = jobs_dir / "fetch_job_job_20260623_funabashi_w01_p01.csv"
    second_json = jobs_dir / "fetch_job_job_20260623_funabashi_w02_p02.json"
    assert first_job.exists()
    assert second_json.exists()

    first_rows = _read_csv(first_job)
    assert [row["race_id"] for row in first_rows] == ["20260622_funabashi_2"]

    payload = json.loads(second_json.read_text(encoding="utf-8"))
    assert payload["job_id"] == "job_20260623_funabashi_w02_p02"
    assert payload["track"] == "funabashi"
    assert payload["race_ids"] == ["20260621_funabashi_2"]
    assert payload["raw_sha256_at_export"] == file_sha256(raw_path)

    report_rows = _read_csv(result.csv_report_path)
    assert [row["candidate_races"] for row in report_rows] == ["1", "1"]
    assert [row["cache_skipped_races"] for row in report_rows] == ["0", "1"]


def test_plan_bulk_jobs_refuses_to_overwrite_existing_job_file(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    jobs_dir = tmp_path / "jobs"
    _write_raw(raw_path, [])
    jobs_dir.mkdir()
    (jobs_dir / "fetch_job_job_20260623_funabashi_w01_p01.csv").write_text(
        "existing\n",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError):
        plan_bulk_jobs(
            track="funabashi",
            anchor_date="2026-06-22",
            window_days=1,
            windows=1,
            race_no_from=1,
            race_no_to=1,
            jobs_per_wave=5,
            job_prefix="job_20260623_funabashi",
            jobs_dir=jobs_dir,
            reports_dir=tmp_path / "reports",
            raw_csv_path=raw_path,
            cache_html_dir=tmp_path / "cache",
        )


def test_plan_bulk_jobs_dry_run_writes_no_files(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    jobs_dir = tmp_path / "jobs"
    reports_dir = tmp_path / "reports"
    _write_raw(raw_path, [])

    result = plan_bulk_jobs(
        track="funabashi",
        anchor_date="2026-06-22",
        window_days=1,
        windows=1,
        race_no_from=1,
        race_no_to=2,
        jobs_per_wave=5,
        job_prefix="job_20260623_funabashi",
        jobs_dir=jobs_dir,
        reports_dir=reports_dir,
        raw_csv_path=raw_path,
        cache_html_dir=tmp_path / "cache",
        dry_run=True,
    )

    assert result.dry_run
    assert result.total_candidate_races == 2
    assert not jobs_dir.exists()
    assert not reports_dir.exists()


def _write_raw(path: Path, race_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for race_id in race_ids:
            race_date, track, race_no = _split_race_id(race_id)
            row = {column: "" for column in REQUIRED_COLUMNS}
            row.update(
                {
                    "race_id": race_id,
                    "date": race_date,
                    "track": track,
                    "race_no": race_no,
                    "race_name": "Existing Race",
                    "distance": "1400",
                    "surface": "dirt",
                    "field_size": "1",
                    "horse_no": "1",
                    "gate_no": "1",
                    "horse_name": "Existing Horse",
                    "age": "4",
                    "finish_position": "1",
                }
            )
            writer.writerow(row)


def _write_cache(cache_dir: Path, race_id: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{race_id}.html").write_text("<html>cached</html>", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _split_race_id(race_id: str) -> tuple[str, str, str]:
    raw_date, track, race_no = race_id.split("_")
    race_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    return race_date, track, race_no
