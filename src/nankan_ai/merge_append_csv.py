from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .append_batch_log import AppendBatchLogEntry, append_batch_log, file_sha256, make_batch_id
from .audit_dataset import AuditReport, audit_dataset
from .dataset_manifest import build_dataset_manifest, write_dataset_manifest
from .export_training_rows import export_training_rows
from .load_to_duckdb import load_csv_to_duckdb
from .schema import DEFAULT_DB_PATH, DEFAULT_RAW_CSV_PATH, DEFAULT_TRAINING_ROWS_PATH, REQUIRED_COLUMNS
from .validate_append_csv import (
    DEFAULT_APPEND_CSV_PATH,
    format_append_validation_result,
    validate_append_csv,
)
from .validate_csv import format_validation_result, validate_csv

DEFAULT_BACKUPS_DIR = Path("data/backups")
DEFAULT_REPORTS_DIR = Path("data/reports")

APPLY_STEPS = (
    "backup_created",
    "raw_appended",
    "duckdb_loaded",
    "training_exported",
    "audit_done",
    "manifest_created",
    "batch_logged",
)


@dataclass(frozen=True)
class CsvSummary:
    rows: int
    races: int
    track_scope: str = ""
    date_min: str = ""
    date_max: str = ""


@dataclass
class AppendState:
    batch_id: str
    mode: str
    append_csv_path: str
    backup_path: str = ""
    before_raw_sha256: str = ""
    after_raw_sha256: str = ""
    before_raw_rows: int = 0
    after_raw_rows: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str = ""
    error_message: str = ""
    created_at: str = ""
    updated_at: str = ""
    raw_csv_path: str = ""
    db_path: str = ""
    training_rows_path: str = ""
    report_path: str = ""
    manifest_path: str = ""
    before_race_count: int = 0
    after_race_count: int = 0
    added_rows: int = 0
    added_races: int = 0
    track_scope: str = ""
    date_min: str = ""
    date_max: str = ""
    validation_status: str = ""


def merge_append_csv(
    append_csv_path: str | Path = DEFAULT_APPEND_CSV_PATH,
    *,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
    training_rows_path: str | Path = DEFAULT_TRAINING_ROWS_PATH,
    backups_dir: str | Path = DEFAULT_BACKUPS_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    apply: bool = False,
    race_count_expected: int | None = None,
    resume_state_path: str | Path | None = None,
    fail_after_step: str | None = None,
) -> int:
    append_path = Path(append_csv_path)
    raw_path = Path(raw_csv_path)
    db = Path(db_path)
    training_path = Path(training_rows_path)
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)

    if resume_state_path is not None:
        state_path = _resolve_resume_state_path(resume_state_path, reports, append_path)
        return _resume_append(
            state_path,
            reports_dir=reports,
            backups_dir=Path(backups_dir),
            race_count_expected=race_count_expected,
            fail_after_step=fail_after_step,
        )

    if apply:
        append_race_ids = _race_ids_from_csv(append_path)
        existing_race_ids = _race_ids_from_csv(raw_path)
        if append_race_ids and append_race_ids <= existing_race_ids:
            print("NG: append CSV race_id values already exist in raw CSV.")
            print("raw was not changed.")
            print("If this is recovery after a partial apply, run:")
            print("python -m nankan_ai.merge_append_csv --resume data/reports/append_state_<batch_id>.json")
            return 1

    now = datetime.now()
    batch_id = make_batch_id(now)
    timestamp = batch_id.removeprefix("append_")
    created_at = now.isoformat(timespec="seconds")
    mode = "applied" if apply else "dry_run"
    batch_log_path = reports / "append_batches.csv"
    before = _csv_summary_or_empty(raw_path)
    before_raw_sha256 = file_sha256(raw_path)
    append_csv_sha256 = file_sha256(append_path)

    validation = validate_append_csv(append_path, raw_csv_path=raw_path)
    print(format_append_validation_result(validation))
    if not validation.is_valid:
        report_path = _write_report(
            reports,
            timestamp,
            title="Append Validation Failed",
            lines=[
                f"- batch_id: `{batch_id}`",
                f"- mode: `{mode}`",
                f"- append_csv: `{append_path}`",
                f"- raw_csv: `{raw_path}`",
                "",
                "## Validation",
                "```text",
                format_append_validation_result(validation),
                "```",
            ],
        )
        append_batch_log(
            AppendBatchLogEntry(
                batch_id=batch_id,
                created_at=created_at,
                mode=mode,
                append_csv_path=_path_string(append_path),
                append_csv_sha256=append_csv_sha256,
                before_raw_sha256=before_raw_sha256,
                after_raw_sha256=before_raw_sha256,
                before_raw_rows=before.rows,
                after_raw_rows=before.rows,
                before_race_count=before.races,
                after_race_count=before.races,
                added_rows=0,
                added_races=0,
                race_count_expected="" if race_count_expected is None else str(race_count_expected),
                race_count_actual="0",
                validation_status="failed",
                report_path=_path_string(report_path),
            ),
            log_path=batch_log_path,
        )
        print("NG: append CSV has errors; merge was not run.")
        print(f"report: {report_path}")
        print(f"batch_log: {batch_log_path}")
        return 1

    incoming = _csv_summary(append_path)
    projected = CsvSummary(rows=before.rows + incoming.rows, races=before.races + incoming.races)

    if not apply:
        report_path = _write_dry_run_report(
            reports,
            timestamp,
            batch_id=batch_id,
            append_path=append_path,
            raw_path=raw_path,
            before=before,
            incoming=incoming,
            projected=projected,
            validation_text=format_append_validation_result(validation),
            race_count_expected=race_count_expected,
        )
        append_batch_log(
            AppendBatchLogEntry(
                batch_id=batch_id,
                created_at=created_at,
                mode="dry_run",
                append_csv_path=_path_string(append_path),
                append_csv_sha256=append_csv_sha256,
                before_raw_sha256=before_raw_sha256,
                after_raw_sha256=before_raw_sha256,
                before_raw_rows=before.rows,
                after_raw_rows=before.rows,
                before_race_count=before.races,
                after_race_count=before.races,
                added_rows=incoming.rows,
                added_races=incoming.races,
                track_scope=incoming.track_scope,
                date_min=incoming.date_min,
                date_max=incoming.date_max,
                race_count_expected="" if race_count_expected is None else str(race_count_expected),
                race_count_actual=str(incoming.races),
                validation_status="passed",
                report_path=_path_string(report_path),
            ),
            log_path=batch_log_path,
        )
        print("DRY-RUN: existing raw CSV was not changed.")
        print(f"current_raw_rows: {before.rows}")
        print(f"current_races: {before.races}")
        print(f"append_rows: {incoming.rows}")
        print(f"append_races: {incoming.races}")
        print(f"projected_raw_rows: {projected.rows}")
        print(f"projected_races: {projected.races}")
        print(f"report: {report_path}")
        print(f"batch_log: {batch_log_path}")
        return 0

    state = AppendState(
        batch_id=batch_id,
        mode="applied",
        append_csv_path=_path_string(append_path),
        before_raw_sha256=before_raw_sha256,
        after_raw_sha256=before_raw_sha256,
        before_raw_rows=before.rows,
        after_raw_rows=before.rows,
        created_at=created_at,
        raw_csv_path=_path_string(raw_path),
        db_path=_path_string(db),
        training_rows_path=_path_string(training_path),
        before_race_count=before.races,
        after_race_count=before.races,
        added_rows=incoming.rows,
        added_races=incoming.races,
        track_scope=incoming.track_scope,
        date_min=incoming.date_min,
        date_max=incoming.date_max,
        validation_status="passed",
    )
    state_path = _append_state_path(reports, batch_id)
    _write_state(state, state_path)
    return _run_apply_from_state(
        state,
        state_path,
        append_path=append_path,
        raw_path=raw_path,
        db_path=db,
        training_rows_path=training_path,
        backups_dir=Path(backups_dir),
        reports_dir=reports,
        race_count_expected=race_count_expected,
        fail_after_step=fail_after_step,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run, apply, or resume an incoming Nankan append CSV into raw data."
    )
    parser.add_argument(
        "append_csv_path",
        nargs="?",
        default=str(DEFAULT_APPEND_CSV_PATH),
        help="Path to data/incoming/nankan_past_races_append.csv",
    )
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--training-rows-path", default=str(DEFAULT_TRAINING_ROWS_PATH))
    parser.add_argument("--backups-dir", default=str(DEFAULT_BACKUPS_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument(
        "--race-count-expected",
        type=int,
        default=None,
        help="Optional expected number of races in this append batch.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually append to raw CSV.")
    parser.add_argument(
        "--resume",
        nargs="?",
        const="latest",
        default=None,
        help=(
            "Resume a partial apply from an append_state JSON. "
            "Pass a path, or omit the value to use the latest state for the append CSV."
        ),
    )
    args = parser.parse_args(argv)

    return merge_append_csv(
        args.append_csv_path,
        raw_csv_path=args.raw_csv_path,
        db_path=args.db_path,
        training_rows_path=args.training_rows_path,
        backups_dir=args.backups_dir,
        reports_dir=args.reports_dir,
        apply=args.apply,
        race_count_expected=args.race_count_expected,
        resume_state_path=args.resume,
    )


def _resume_append(
    state_path: Path,
    *,
    reports_dir: Path,
    backups_dir: Path,
    race_count_expected: int | None,
    fail_after_step: str | None,
) -> int:
    state = _read_state(state_path)
    append_path = Path(state.append_csv_path)
    raw_path = Path(state.raw_csv_path or DEFAULT_RAW_CSV_PATH)
    db_path = Path(state.db_path or DEFAULT_DB_PATH)
    training_rows_path = Path(state.training_rows_path or DEFAULT_TRAINING_ROWS_PATH)
    return _run_apply_from_state(
        state,
        state_path,
        append_path=append_path,
        raw_path=raw_path,
        db_path=db_path,
        training_rows_path=training_rows_path,
        backups_dir=backups_dir,
        reports_dir=reports_dir,
        race_count_expected=race_count_expected,
        fail_after_step=fail_after_step,
        is_resume=True,
    )


def _run_apply_from_state(
    state: AppendState,
    state_path: Path,
    *,
    append_path: Path,
    raw_path: Path,
    db_path: Path,
    training_rows_path: Path,
    backups_dir: Path,
    reports_dir: Path,
    race_count_expected: int | None,
    fail_after_step: str | None,
    is_resume: bool = False,
) -> int:
    current_step = ""
    post_validation_text = ""
    audit_report: AuditReport | None = None
    loaded_rows = 0
    training_rows = _csv_data_row_count(training_rows_path) if training_rows_path.exists() else 0
    manifest_path = Path(state.manifest_path) if state.manifest_path else Path()
    report_path = Path(state.report_path) if state.report_path else Path()

    try:
        if "backup_created" not in state.completed_steps:
            current_step = "backup_created"
            backup_path = _backup_raw(raw_path, backups_dir, _timestamp_from_batch_id(state.batch_id))
            state.backup_path = _path_string(backup_path)
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)
        elif not state.backup_path:
            raise RuntimeError("append state says backup_created but backup_path is blank.")

        append_race_ids = _race_ids_from_csv(append_path)
        raw_race_ids = _race_ids_from_csv(raw_path)
        if "raw_appended" not in state.completed_steps:
            current_step = "raw_appended"
            if append_race_ids <= raw_race_ids:
                print("RESUME: append race_id values are already present in raw; raw append skipped.")
            else:
                _append_rows(raw_path, append_path)
            after = _csv_summary(raw_path)
            state.after_raw_rows = after.rows
            state.after_race_count = after.races
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)
        elif append_race_ids <= raw_race_ids:
            print("RESUME: raw_appended already completed; raw append skipped.")
        else:
            raise RuntimeError("append state says raw_appended, but append race_id values are missing from raw.")

        post_validation = validate_csv(raw_path)
        post_validation_text = format_validation_result(post_validation)
        if not post_validation.is_valid:
            state.validation_status = "failed_after_append"
            _fail_state(state, state_path, "raw_appended", post_validation_text, raw_path)
            report_path = _write_failed_after_append_report(
                reports_dir,
                state,
                append_path=append_path,
                raw_path=raw_path,
                validation_text=post_validation_text,
            )
            _log_apply_state(
                state,
                append_path=append_path,
                raw_path=raw_path,
                report_path=report_path,
                validation_status="failed_after_append",
                race_count_expected=race_count_expected,
            )
            print(f"NG: raw CSV validation failed after append. Report: {report_path}")
            print(f"append_state: {state_path}")
            return 1

        if "duckdb_loaded" not in state.completed_steps:
            current_step = "duckdb_loaded"
            loaded_rows = load_csv_to_duckdb(raw_path, db_path=db_path)
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)

        if "training_exported" not in state.completed_steps:
            current_step = "training_exported"
            training_rows = export_training_rows(db_path=db_path, output_path=training_rows_path)
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)
        else:
            training_rows = _csv_data_row_count(training_rows_path)

        if "audit_done" not in state.completed_steps:
            current_step = "audit_done"
            audit_report = audit_dataset(db_path=db_path)
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)

        after = _csv_summary(raw_path)
        manifest_label = str(after.races)
        manifest_path = reports_dir / f"dataset_manifest_{manifest_label}.json"
        if "manifest_created" not in state.completed_steps:
            current_step = "manifest_created"
            manifest = build_dataset_manifest(
                raw_csv_path=raw_path,
                db_path=db_path,
                training_rows_path=training_rows_path,
                label=manifest_label,
                pytest_result="not_run_by_merge_append_csv",
            )
            write_dataset_manifest(manifest, manifest_path)
            state.manifest_path = _path_string(manifest_path)
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)

        report_path = reports_dir / f"append_report_{_timestamp_from_batch_id(state.batch_id)}.md"
        if "batch_logged" not in state.completed_steps:
            current_step = "batch_logged"
            report_path = _write_apply_report(
                reports_dir,
                state,
                append_path=append_path,
                raw_path=raw_path,
                db_path=db_path,
                training_rows_path=training_rows_path,
                manifest_path=manifest_path,
                post_validation_text=post_validation_text,
                audit_report=audit_report,
                loaded_rows=loaded_rows,
                training_rows=training_rows,
                race_count_expected=race_count_expected,
                resumed=is_resume,
            )
            state.report_path = _path_string(report_path)
            _log_apply_state(
                state,
                append_path=append_path,
                raw_path=raw_path,
                report_path=report_path,
                validation_status="passed",
                race_count_expected=race_count_expected,
            )
            _complete_step(state, state_path, current_step, raw_path)
            _maybe_fail(fail_after_step, current_step)

        print(f"OK: appended {state.added_rows} rows / {state.added_races} races.")
        print(f"backup: {state.backup_path}")
        print(f"report: {report_path}")
        print(f"manifest: {manifest_path}")
        print(f"append_state: {state_path}")
        return 0
    except Exception as exc:  # noqa: BLE001 - state must be persisted for recovery.
        failed_step = current_step or "apply"
        _fail_state(state, state_path, failed_step, f"{exc.__class__.__name__}: {exc}", raw_path)
        print(f"NG: append apply failed at step={failed_step}")
        print(f"error: {exc.__class__.__name__}: {exc}")
        print(f"append_state: {state_path}")
        print(f"resume: python -m nankan_ai.merge_append_csv --resume {state_path}")
        return 1


def _write_dry_run_report(
    reports: Path,
    timestamp: str,
    *,
    batch_id: str,
    append_path: Path,
    raw_path: Path,
    before: CsvSummary,
    incoming: CsvSummary,
    projected: CsvSummary,
    validation_text: str,
    race_count_expected: int | None,
) -> Path:
    return _write_report(
        reports,
        timestamp,
        title="Append Dry Run Report",
        lines=[
            f"- batch_id: `{batch_id}`",
            f"- append_csv: `{append_path}`",
            f"- raw_csv: `{raw_path}`",
            "",
            "## Summary",
            f"- current_raw_rows: {before.rows}",
            f"- current_races: {before.races}",
            f"- append_rows: {incoming.rows}",
            f"- append_races: {incoming.races}",
            f"- append_track_scope: {incoming.track_scope}",
            f"- append_date_min: {incoming.date_min}",
            f"- append_date_max: {incoming.date_max}",
            f"- race_count_expected: {race_count_expected if race_count_expected is not None else ''}",
            f"- projected_raw_rows: {projected.rows}",
            f"- projected_races: {projected.races}",
            "",
            "## Validation",
            "```text",
            validation_text,
            "```",
        ],
    )


def _write_apply_report(
    reports_dir: Path,
    state: AppendState,
    *,
    append_path: Path,
    raw_path: Path,
    db_path: Path,
    training_rows_path: Path,
    manifest_path: Path,
    post_validation_text: str,
    audit_report: AuditReport | None,
    loaded_rows: int,
    training_rows: int,
    race_count_expected: int | None,
    resumed: bool,
) -> Path:
    audit_text = audit_report.format() if audit_report is not None else "audit step was already completed before resume."
    return _write_report(
        reports_dir,
        _timestamp_from_batch_id(state.batch_id),
        title="Append Report",
        lines=[
            f"- batch_id: `{state.batch_id}`",
            f"- append_csv: `{append_path}`",
            f"- raw_csv: `{raw_path}`",
            f"- backup_csv: `{state.backup_path}`",
            f"- duckdb: `{db_path}`",
            f"- training_rows_csv: `{training_rows_path}`",
            f"- manifest: `{manifest_path}`",
            f"- resumed: {'yes' if resumed else 'no'}",
            "",
            "## Summary",
            f"- before_raw_rows: {state.before_raw_rows}",
            f"- before_races: {state.before_race_count}",
            f"- append_rows: {state.added_rows}",
            f"- append_races: {state.added_races}",
            f"- append_track_scope: {state.track_scope}",
            f"- append_date_min: {state.date_min}",
            f"- append_date_max: {state.date_max}",
            f"- race_count_expected: {race_count_expected if race_count_expected is not None else ''}",
            f"- after_raw_rows: {state.after_raw_rows}",
            f"- after_races: {state.after_race_count}",
            f"- duckdb_loaded_rows: {loaded_rows}",
            f"- training_rows: {training_rows}",
            "",
            "## Post-Append Validation",
            "```text",
            post_validation_text,
            "```",
            "",
            "## Audit",
            "```text",
            audit_text,
            "```",
        ],
    )


def _write_failed_after_append_report(
    reports_dir: Path,
    state: AppendState,
    *,
    append_path: Path,
    raw_path: Path,
    validation_text: str,
) -> Path:
    return _write_report(
        reports_dir,
        _timestamp_from_batch_id(state.batch_id),
        title="Append Failed After Raw Validation",
        lines=[
            f"- batch_id: `{state.batch_id}`",
            f"- append_csv: `{append_path}`",
            f"- raw_csv: `{raw_path}`",
            f"- backup_csv: `{state.backup_path}`",
            "",
            "## Validation",
            "```text",
            validation_text,
            "```",
        ],
    )


def _log_apply_state(
    state: AppendState,
    *,
    append_path: Path,
    raw_path: Path,
    report_path: Path,
    validation_status: str,
    race_count_expected: int | None,
) -> None:
    append_batch_log(
        AppendBatchLogEntry(
            batch_id=state.batch_id,
            created_at=state.created_at,
            mode="applied",
            append_csv_path=_path_string(append_path),
            append_csv_sha256=file_sha256(append_path),
            before_raw_sha256=state.before_raw_sha256,
            after_raw_sha256=file_sha256(raw_path),
            before_raw_rows=state.before_raw_rows,
            after_raw_rows=state.after_raw_rows,
            before_race_count=state.before_race_count,
            after_race_count=state.after_race_count,
            added_rows=state.added_rows,
            added_races=state.added_races,
            track_scope=state.track_scope,
            date_min=state.date_min,
            date_max=state.date_max,
            race_count_expected="" if race_count_expected is None else str(race_count_expected),
            race_count_actual=str(state.added_races),
            validation_status=validation_status,
            report_path=_path_string(report_path),
        ),
        log_path=Path(report_path).parent / "append_batches.csv",
    )


def _complete_step(state: AppendState, state_path: Path, step: str, raw_path: Path) -> None:
    if step not in state.completed_steps:
        state.completed_steps.append(step)
    state.failed_step = ""
    state.error_message = ""
    _refresh_state_raw_fields(state, raw_path)
    _write_state(state, state_path)


def _fail_state(state: AppendState, state_path: Path, failed_step: str, error_message: str, raw_path: Path) -> None:
    state.failed_step = failed_step
    state.error_message = error_message
    _refresh_state_raw_fields(state, raw_path)
    _write_state(state, state_path)


def _refresh_state_raw_fields(state: AppendState, raw_path: Path) -> None:
    if raw_path.exists():
        after = _csv_summary(raw_path)
        state.after_raw_rows = after.rows
        state.after_race_count = after.races
        state.after_raw_sha256 = file_sha256(raw_path)


def _write_state(state: AppendState, state_path: Path) -> Path:
    state.updated_at = datetime.now().isoformat(timespec="seconds")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state_path


def _read_state(state_path: Path) -> AppendState:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return AppendState(**payload)


def _append_state_path(reports_dir: Path, batch_id: str) -> Path:
    return reports_dir / f"append_state_{batch_id}.json"


def _resolve_resume_state_path(value: str | Path, reports_dir: Path, append_path: Path) -> Path:
    if str(value) != "latest":
        path = Path(value)
        if not path.exists():
            raise FileNotFoundError(f"append state not found: {path}")
        return path

    candidates = sorted(reports_dir.glob("append_state_append_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    append_path_text = _path_string(append_path)
    for candidate in candidates:
        try:
            state = _read_state(candidate)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if state.append_csv_path == append_path_text:
            return candidate
    raise FileNotFoundError(f"no append_state JSON found for append CSV: {append_path}")


def _maybe_fail(fail_after_step: str | None, step: str) -> None:
    if fail_after_step == step:
        raise RuntimeError(f"simulated failure after {step}")


def _csv_summary(csv_path: Path) -> CsvSummary:
    rows = _read_rows(csv_path)
    dates = sorted({_clean(row.get("date")) for row in rows if _clean(row.get("date"))})
    tracks = sorted({_clean(row.get("track")) for row in rows if _clean(row.get("track"))})
    return CsvSummary(
        rows=len(rows),
        races=len({_clean(row.get("race_id")) for row in rows if _clean(row.get("race_id"))}),
        track_scope=";".join(tracks),
        date_min=dates[0] if dates else "",
        date_max=dates[-1] if dates else "",
    )


def _csv_summary_or_empty(csv_path: Path) -> CsvSummary:
    if not csv_path.exists():
        return CsvSummary(rows=0, races=0)
    return _csv_summary(csv_path)


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {column: _clean(row.get(column)) for column in REQUIRED_COLUMNS}
            for row in reader
        ]


def _race_ids_from_csv(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {_clean(row.get("race_id")) for row in reader if _clean(row.get("race_id"))}


def _backup_raw(raw_path: Path, backups_dir: Path, timestamp: str) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backups_dir / f"nankan_past_races_before_append_{timestamp}.csv"
    shutil.copy2(raw_path, backup_path)
    return backup_path


def _append_rows(raw_path: Path, append_path: Path) -> None:
    append_rows = _read_rows(append_path)
    needs_newline = _needs_trailing_newline(raw_path)
    with raw_path.open("a", encoding="utf-8", newline="") as handle:
        if needs_newline:
            handle.write("\n")
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
        writer.writerows(append_rows)


def _needs_trailing_newline(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        handle.seek(-1, 2)
        return handle.read(1) not in {b"\n", b"\r"}


def _write_report(
    reports_dir: Path,
    timestamp: str,
    *,
    title: str,
    lines: list[str],
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"append_report_{timestamp}.md"
    content = "\n".join([f"# {title}", "", f"created_at: {datetime.now().isoformat(timespec='seconds')}", "", *lines, ""])
    report_path.write_text(content, encoding="utf-8", newline="\n")
    return report_path


def _csv_data_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _timestamp_from_batch_id(batch_id: str) -> str:
    return batch_id.removeprefix("append_")


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "APPLY_STEPS",
    "AppendState",
    "CsvSummary",
    "merge_append_csv",
]


if __name__ == "__main__":
    raise SystemExit(main())
