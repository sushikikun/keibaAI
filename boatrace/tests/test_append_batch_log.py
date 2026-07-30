from __future__ import annotations

from datetime import datetime
from pathlib import Path

from nankan_ai.append_batch_log import (
    AppendBatchLogEntry,
    BATCH_LOG_COLUMNS,
    append_batch_log,
    file_sha256,
    make_batch_id,
    read_batch_log,
)


def test_make_batch_id_uses_expected_format() -> None:
    batch_id = make_batch_id(datetime(2026, 6, 18, 3, 4, 5))

    assert batch_id == "append_20260618_030405"


def test_append_batch_log_writes_header_and_row() -> None:
    work = _fresh_work_dir("append-batch-log")
    log_path = work / "append_batches.csv"
    entry = AppendBatchLogEntry(
        batch_id="append_20260618_030405",
        created_at="2026-06-18T03:04:05",
        mode="dry_run",
        append_csv_path="data/incoming/nankan_past_races_append.csv",
        append_csv_sha256="a" * 64,
        before_raw_sha256="b" * 64,
        after_raw_sha256="b" * 64,
        before_raw_rows=5681,
        after_raw_rows=5681,
        before_race_count=500,
        after_race_count=500,
        added_rows=1000,
        added_races=100,
        track_scope="kawasaki",
        date_min="2025-01-01",
        date_max="2025-02-01",
        race_count_expected="100",
        race_count_actual="100",
        validation_status="passed",
        report_path="data/reports/append_report_20260618_030405.md",
    )

    append_batch_log(entry, log_path=log_path)
    rows = read_batch_log(log_path)

    assert log_path.read_text(encoding="utf-8").splitlines()[0] == ",".join(BATCH_LOG_COLUMNS)
    assert len(rows) == 1
    assert rows[0]["batch_id"] == "append_20260618_030405"
    assert rows[0]["mode"] == "dry_run"
    assert rows[0]["validation_status"] == "passed"
    assert rows[0]["track_scope"] == "kawasaki"
    assert rows[0]["date_min"] == "2025-01-01"
    assert rows[0]["date_max"] == "2025-02-01"
    assert rows[0]["race_count_expected"] == "100"
    assert rows[0]["race_count_actual"] == "100"


def test_file_sha256_returns_empty_for_missing_file() -> None:
    assert file_sha256(_fresh_work_dir("missing-hash") / "missing.csv") == ""


def test_append_batch_log_migrates_older_header() -> None:
    work = _fresh_work_dir("append-batch-log-migrate")
    log_path = work / "append_batches.csv"
    log_path.write_text(
        "batch_id,created_at,mode,append_csv_path,append_csv_sha256,before_raw_sha256,after_raw_sha256,before_raw_rows,after_raw_rows,before_race_count,after_race_count,added_rows,added_races,validation_status,report_path\n"
        "append_20260618_010101,2026-06-18T01:01:01,dry_run,append.csv,a,b,b,1,1,1,1,0,0,passed,report.md\n",
        encoding="utf-8",
    )

    append_batch_log(
        AppendBatchLogEntry(
            batch_id="append_20260618_020202",
            created_at="2026-06-18T02:02:02",
            mode="dry_run",
            append_csv_path="append2.csv",
            append_csv_sha256="c",
            before_raw_sha256="d",
            after_raw_sha256="d",
            before_raw_rows=1,
            after_raw_rows=1,
            before_race_count=1,
            after_race_count=1,
            added_rows=2,
            added_races=1,
            track_scope="kawasaki",
            date_min="2026-06-18",
            date_max="2026-06-18",
            race_count_actual="1",
            validation_status="passed",
            report_path="report2.md",
        ),
        log_path=log_path,
    )

    rows = read_batch_log(log_path)
    assert log_path.read_text(encoding="utf-8").splitlines()[0] == ",".join(BATCH_LOG_COLUMNS)
    assert len(rows) == 2
    assert rows[0]["track_scope"] == ""
    assert rows[1]["track_scope"] == "kawasaki"


def _fresh_work_dir(name: str) -> Path:
    path = Path(".tmp/test-output") / name
    if path.exists():
        for child in path.iterdir():
            if child.is_file():
                child.unlink()
    else:
        path.mkdir(parents=True)
    return path
