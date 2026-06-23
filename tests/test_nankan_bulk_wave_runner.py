from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from nankan_ai.append_batch_log import file_sha256
from nankan_ai.bulk_wave_runner import (
    BulkWaveRunnerError,
    run_wave,
    select_wave_jobs,
)
from nankan_ai.fetch_plan import FETCH_PLAN_COLUMNS


def test_select_wave_jobs_w01_has_10_jobs(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    for part_number in range(1, 11):
        _write_job(jobs_dir, part_number=part_number)

    selection = select_wave_jobs(
        track="funabashi",
        wave="w01",
        job_prefix="job_20260623_050513_funabashi",
        jobs_dir=jobs_dir,
    )

    assert selection.job_count == 10
    assert [job.part_number for job in selection.jobs] == list(range(1, 11))
    assert selection.total_candidate_races == 10_080


def test_select_wave_jobs_sorts_part_numbers_numerically(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    _write_job(jobs_dir, part_number=100, wave="w10")
    _write_job(jobs_dir, part_number=99, wave="w10")

    selection = select_wave_jobs(
        track="funabashi",
        wave="w10",
        job_prefix="job_20260623_050513_funabashi",
        jobs_dir=jobs_dir,
    )

    assert [job.part_number for job in selection.jobs] == [99, 100]
    assert [job.job_id.rsplit("_", 1)[1] for job in selection.jobs] == ["p99", "p100"]


def test_select_wave_jobs_excludes_track_wave_and_prefix_mismatches(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    _write_job(jobs_dir, part_number=1)
    _write_job(jobs_dir, part_number=2, track="oi")
    _write_job(jobs_dir, part_number=3, wave="w02")
    _write_job(jobs_dir, part_number=4, prefix="job_other_funabashi")

    selection = select_wave_jobs(
        track="funabashi",
        wave="w01",
        job_prefix="job_20260623_050513_funabashi",
        jobs_dir=jobs_dir,
    )

    assert [job.job_id for job in selection.jobs] == ["job_20260623_050513_funabashi_w01_p01"]


def test_raw_sha_mismatch_blocks_dry_run_before_process_script(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    raw_path = tmp_path / "raw.csv"
    _write_job(jobs_dir, part_number=1)
    raw_path.write_text("race_id\n20260622_funabashi_1\n", encoding="utf-8")
    calls: list[list[str]] = []

    with pytest.raises(BulkWaveRunnerError, match="raw SHA256 mismatch"):
        run_wave(
            track="funabashi",
            wave="w01",
            job_prefix="job_20260623_050513_funabashi",
            mode="dry-run",
            jobs_dir=jobs_dir,
            reports_dir=tmp_path / "reports",
            raw_csv_path=raw_path,
            expected_start_raw_sha256="bad",
            runner=_recording_runner(calls),
        )

    assert calls == []


def test_apply_requires_allow_apply(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    raw_path = tmp_path / "raw.csv"
    _write_job(jobs_dir, part_number=1)
    raw_path.write_text("race_id\n20260622_funabashi_1\n", encoding="utf-8")
    calls: list[list[str]] = []

    with pytest.raises(BulkWaveRunnerError, match="requires --allow-apply"):
        run_wave(
            track="funabashi",
            wave="w01",
            job_prefix="job_20260623_050513_funabashi",
            mode="apply",
            jobs_dir=jobs_dir,
            reports_dir=tmp_path / "reports",
            raw_csv_path=raw_path,
            expected_start_raw_sha256=file_sha256(raw_path),
            runner=_recording_runner(calls),
        )

    assert calls == []


def test_list_mode_writes_no_files(tmp_path: Path) -> None:
    jobs_dir = tmp_path / "jobs"
    reports_dir = tmp_path / "reports"
    _write_job(jobs_dir, part_number=1)

    result = run_wave(
        track="funabashi",
        wave="w01",
        job_prefix="job_20260623_050513_funabashi",
        mode="list",
        jobs_dir=jobs_dir,
        reports_dir=reports_dir,
    )

    assert "job_count: 1" in result.messages[0]
    assert "job_20260623_050513_funabashi_w01_p01" in result.messages[0]
    assert not reports_dir.exists()


def test_select_wave_jobs_errors_when_target_is_empty(tmp_path: Path) -> None:
    with pytest.raises(BulkWaveRunnerError, match="no fetch jobs found"):
        select_wave_jobs(
            track="funabashi",
            wave="w01",
            job_prefix="job_20260623_050513_funabashi",
            jobs_dir=tmp_path / "jobs",
        )


def _write_job(
    jobs_dir: Path,
    *,
    part_number: int,
    wave: str = "w01",
    track: str = "funabashi",
    prefix: str = "job_20260623_050513_funabashi",
) -> None:
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_id = f"{prefix}_{wave}_p{part_number:02d}"
    csv_path = jobs_dir / f"fetch_job_{job_id}.csv"
    json_path = jobs_dir / f"fetch_job_{job_id}.json"
    _write_fetch_job_csv(csv_path, job_id=job_id, track=track)
    payload = {
        "job_id": job_id,
        "created_at": "2026-06-23T18:54:20+09:00",
        "track": track,
        "date_from": "2026-03-31",
        "date_to": "2026-06-22",
        "race_count": 1008,
        "race_ids": [f"20260622_{track}_1"],
        "source": "keiba.go.jp official result page",
        "raw_sha256_at_export": "abc123",
        "fetch_job_csv": str(csv_path).replace("\\", "/"),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_fetch_job_csv(path: Path, *, job_id: str, track: str) -> None:
    race_id = f"20260622_{track}_1"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FETCH_PLAN_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "race_id": race_id,
                "date": "2026-06-22",
                "track": track,
                "race_no": "1",
                "official_url": f"https://example.test/{job_id}",
                "cache_html_path": f"data/cache/html/{race_id}.html",
            }
        )


def _recording_runner(calls: list[list[str]]):
    def runner(command):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    return runner
