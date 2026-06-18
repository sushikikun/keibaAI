from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_BATCH_LOG_PATH = Path("data/reports/append_batches.csv")
BATCH_LOG_COLUMNS = (
    "batch_id",
    "created_at",
    "mode",
    "append_csv_path",
    "append_csv_sha256",
    "before_raw_sha256",
    "after_raw_sha256",
    "before_raw_rows",
    "after_raw_rows",
    "before_race_count",
    "after_race_count",
    "added_rows",
    "added_races",
    "track_scope",
    "date_min",
    "date_max",
    "race_count_expected",
    "race_count_actual",
    "validation_status",
    "report_path",
)


@dataclass(frozen=True)
class AppendBatchLogEntry:
    batch_id: str
    created_at: str
    mode: str
    append_csv_path: str
    append_csv_sha256: str
    before_raw_sha256: str
    after_raw_sha256: str
    before_raw_rows: int
    after_raw_rows: int
    before_race_count: int
    after_race_count: int
    added_rows: int
    added_races: int
    track_scope: str = ""
    date_min: str = ""
    date_max: str = ""
    race_count_expected: str = ""
    race_count_actual: str = ""
    validation_status: str = ""
    report_path: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            column: str(getattr(self, column))
            for column in BATCH_LOG_COLUMNS
        }


def make_batch_id(now: datetime | None = None) -> str:
    value = now or datetime.now()
    return f"append_{value.strftime('%Y%m%d_%H%M%S')}"


def append_batch_log(
    entry: AppendBatchLogEntry,
    *,
    log_path: str | Path = DEFAULT_BATCH_LOG_PATH,
) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = _read_existing_rows(path)
    should_rewrite = bool(existing_rows) or (path.exists() and path.stat().st_size > 0)

    mode = "w" if should_rewrite else "a"
    with path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATCH_LOG_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in existing_rows:
            writer.writerow({column: row.get(column, "") for column in BATCH_LOG_COLUMNS})
        writer.writerow(entry.as_row())

    return path


def file_sha256(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""

    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_batch_log(log_path: str | Path = DEFAULT_BATCH_LOG_PATH) -> list[dict[str, str]]:
    path = Path(log_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames == list(BATCH_LOG_COLUMNS):
            return list(reader)
        return list(reader)


__all__ = [
    "AppendBatchLogEntry",
    "BATCH_LOG_COLUMNS",
    "DEFAULT_BATCH_LOG_PATH",
    "append_batch_log",
    "file_sha256",
    "make_batch_id",
    "read_batch_log",
]
