from __future__ import annotations

import csv
import hashlib
import json
import uuid
from pathlib import Path

from nankan_ai.append_batch_log import read_batch_log
from nankan_ai.merge_append_csv import merge_append_csv
from nankan_ai.schema import REQUIRED_COLUMNS
from nankan_ai.validate_append_csv import validate_append_csv


def test_validate_append_csv_accepts_new_kawasaki_race() -> None:
    work = _fresh_work_dir("valid-append")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260619_kawasaki_1", "2026-06-19"))

    result = validate_append_csv(append_path, raw_csv_path=raw_path)

    assert result.is_valid
    assert result.row_count == 2
    assert result.race_count == 1


def test_validate_append_csv_rejects_existing_race_id() -> None:
    work = _fresh_work_dir("duplicate-race")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))

    result = validate_append_csv(append_path, raw_csv_path=raw_path)

    assert not result.is_valid
    assert "already exists" in "\n".join(issue.message for issue in result.errors)


def test_validate_append_csv_rejects_horse_no_duplicate() -> None:
    work = _fresh_work_dir("duplicate-horse-no")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    rows = _race_rows("20260619_kawasaki_1", "2026-06-19")
    rows[1]["horse_no"] = "1"
    _write_csv(append_path, rows)

    result = validate_append_csv(append_path, raw_csv_path=raw_path)

    assert not result.is_valid
    assert "horse_no is duplicated" in "\n".join(issue.message for issue in result.errors)


def test_merge_append_csv_dry_run_does_not_change_raw() -> None:
    work = _fresh_work_dir("dry-run")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    db_path = work / "nankan.duckdb"
    training_path = work / "training_rows.csv"
    backups_dir = work / "backups"
    reports_dir = work / "reports"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260619_kawasaki_1", "2026-06-19"))
    before_hash = _sha256(raw_path)

    status = merge_append_csv(
        append_path,
        raw_csv_path=raw_path,
        db_path=db_path,
        training_rows_path=training_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        apply=False,
        race_count_expected=1,
    )

    assert status == 0
    assert _sha256(raw_path) == before_hash
    assert not backups_dir.exists()
    assert len(list(reports_dir.glob("append_report_*.md"))) == 1
    batch_rows = read_batch_log(reports_dir / "append_batches.csv")
    assert len(batch_rows) == 1
    assert batch_rows[0]["mode"] == "dry_run"
    assert batch_rows[0]["before_raw_sha256"] == before_hash
    assert batch_rows[0]["after_raw_sha256"] == before_hash
    assert batch_rows[0]["before_raw_rows"] == "2"
    assert batch_rows[0]["after_raw_rows"] == "2"
    assert batch_rows[0]["added_rows"] == "2"
    assert batch_rows[0]["track_scope"] == "kawasaki"
    assert batch_rows[0]["date_min"] == "2026-06-19"
    assert batch_rows[0]["date_max"] == "2026-06-19"
    assert batch_rows[0]["race_count_expected"] == "1"
    assert batch_rows[0]["race_count_actual"] == "1"


def test_merge_append_csv_apply_backs_up_and_appends() -> None:
    work = _fresh_work_dir("apply")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    db_path = work / "nankan.duckdb"
    training_path = work / "training_rows.csv"
    backups_dir = work / "backups"
    reports_dir = work / "reports"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260619_kawasaki_1", "2026-06-19"))

    status = merge_append_csv(
        append_path,
        raw_csv_path=raw_path,
        db_path=db_path,
        training_rows_path=training_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        apply=True,
    )

    assert status == 0
    assert _csv_data_row_count(raw_path) == 4
    assert _csv_data_row_count(training_path) == 4
    assert len(list(backups_dir.glob("nankan_past_races_before_append_*.csv"))) == 1
    assert len(list(reports_dir.glob("append_report_*.md"))) == 1
    assert len(list(reports_dir.glob("append_state_append_*.json"))) == 1
    assert (reports_dir / "dataset_manifest_2.json").exists()
    batch_rows = read_batch_log(reports_dir / "append_batches.csv")
    assert len(batch_rows) == 1
    assert batch_rows[0]["mode"] == "applied"
    assert batch_rows[0]["before_raw_rows"] == "2"
    assert batch_rows[0]["after_raw_rows"] == "4"
    assert batch_rows[0]["added_rows"] == "2"
    assert batch_rows[0]["track_scope"] == "kawasaki"
    assert batch_rows[0]["date_min"] == "2026-06-19"
    assert batch_rows[0]["date_max"] == "2026-06-19"
    assert batch_rows[0]["race_count_actual"] == "1"
    assert batch_rows[0]["validation_status"] == "passed"


def test_merge_append_csv_apply_failure_writes_append_state_after_raw_append() -> None:
    work = _fresh_work_dir("apply-failure-state")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    db_path = work / "nankan.duckdb"
    training_path = work / "training_rows.csv"
    backups_dir = work / "backups"
    reports_dir = work / "reports"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260619_kawasaki_1", "2026-06-19"))

    status = merge_append_csv(
        append_path,
        raw_csv_path=raw_path,
        db_path=db_path,
        training_rows_path=training_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        apply=True,
        fail_after_step="raw_appended",
    )

    assert status == 1
    assert _csv_data_row_count(raw_path) == 4
    assert not training_path.exists()
    state_path = next(reports_dir.glob("append_state_append_*.json"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "backup_created" in state["completed_steps"]
    assert "raw_appended" in state["completed_steps"]
    assert state["failed_step"] == "raw_appended"
    assert "simulated failure" in state["error_message"]
    assert Path(state["backup_path"]).exists()
    assert not (reports_dir / "append_batches.csv").exists()


def test_merge_append_csv_resume_continues_after_raw_append_without_double_append() -> None:
    work = _fresh_work_dir("resume-no-double-append")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    db_path = work / "nankan.duckdb"
    training_path = work / "training_rows.csv"
    backups_dir = work / "backups"
    reports_dir = work / "reports"
    _write_csv(raw_path, _race_rows("20260618_kawasaki_1", "2026-06-18"))
    _write_csv(append_path, _race_rows("20260619_kawasaki_1", "2026-06-19"))

    failed_status = merge_append_csv(
        append_path,
        raw_csv_path=raw_path,
        db_path=db_path,
        training_rows_path=training_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        apply=True,
        fail_after_step="raw_appended",
    )
    assert failed_status == 1
    state_path = next(reports_dir.glob("append_state_append_*.json"))
    rows_after_failure = _csv_data_row_count(raw_path)

    resumed_status = merge_append_csv(
        resume_state_path=state_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
    )

    assert resumed_status == 0
    assert _csv_data_row_count(raw_path) == rows_after_failure
    assert _csv_data_row_count(raw_path) == 4
    assert _csv_data_row_count(training_path) == 4
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["completed_steps"] == [
        "backup_created",
        "raw_appended",
        "duckdb_loaded",
        "training_exported",
        "audit_done",
        "manifest_created",
        "batch_logged",
    ]
    assert state["failed_step"] == ""
    batch_rows = read_batch_log(reports_dir / "append_batches.csv")
    assert len(batch_rows) == 1
    assert batch_rows[0]["mode"] == "applied"
    assert batch_rows[0]["before_raw_rows"] == "2"
    assert batch_rows[0]["after_raw_rows"] == "4"
    assert batch_rows[0]["added_rows"] == "2"


def test_merge_append_csv_apply_refuses_when_append_race_already_exists() -> None:
    work = _fresh_work_dir("apply-existing-race-refused")
    raw_path = work / "raw.csv"
    append_path = work / "append.csv"
    db_path = work / "nankan.duckdb"
    training_path = work / "training_rows.csv"
    backups_dir = work / "backups"
    reports_dir = work / "reports"
    rows = _race_rows("20260618_kawasaki_1", "2026-06-18")
    _write_csv(raw_path, rows)
    _write_csv(append_path, rows)
    before_hash = _sha256(raw_path)

    status = merge_append_csv(
        append_path,
        raw_csv_path=raw_path,
        db_path=db_path,
        training_rows_path=training_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        apply=True,
    )

    assert status == 1
    assert _sha256(raw_path) == before_hash
    assert _csv_data_row_count(raw_path) == 2
    assert not backups_dir.exists()
    assert not list(reports_dir.glob("append_state_append_*.json"))


def _race_rows(race_id: str, race_date: str) -> list[dict[str, str]]:
    return [
        _row(
            race_id=race_id,
            race_date=race_date,
            horse_no="1",
            gate_no="1",
            horse_name="Append Horse A",
            finish_position="1",
            margin="",
            win_odds_final="2.0",
        ),
        _row(
            race_id=race_id,
            race_date=race_date,
            horse_no="2",
            gate_no="2",
            horse_name="Append Horse B",
            finish_position="2",
            margin="1",
            win_odds_final="3.0",
        ),
    ]


def _row(
    *,
    race_id: str,
    race_date: str,
    horse_no: str,
    gate_no: str,
    horse_name: str,
    finish_position: str,
    margin: str,
    win_odds_final: str,
) -> dict[str, str]:
    return {
        "race_id": race_id,
        "date": race_date,
        "track": "kawasaki",
        "race_no": race_id.rsplit("_", 1)[1],
        "race_name": "Append Fixture Race",
        "distance": "1400",
        "surface": "dirt",
        "weather": "fine",
        "track_condition": "standard",
        "class_name": "fixture",
        "field_size": "2",
        "horse_no": horse_no,
        "gate_no": gate_no,
        "horse_name": horse_name,
        "sex": "M",
        "age": "4",
        "carried_weight": "56.0",
        "jockey_name": "Append Jockey",
        "trainer_name": "Append Trainer",
        "body_weight": "500",
        "body_weight_diff": "0",
        "finish_position": finish_position,
        "finish_time": "1:30.0",
        "margin": margin,
        "passing_order": "",
        "last_3f": "38.0",
        "popularity": horse_no,
        "win_odds_final": win_odds_final,
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _csv_data_row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _test_output_dir() -> Path:
    path = Path(".tmp/test-output")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fresh_work_dir(name: str) -> Path:
    path = _test_output_dir() / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path
