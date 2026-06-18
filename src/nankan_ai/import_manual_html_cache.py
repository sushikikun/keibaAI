from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .fetch_plan import DEFAULT_CACHE_HTML_DIR

DEFAULT_MANUAL_HTML_DIR = Path("data/manual_html")
DEFAULT_MANUAL_IMPORT_LOG_PATH = Path("data/cache/metadata/manual_import_log.csv")
RACE_ID_FILENAME_PATTERN = re.compile(r"^\d{8}_(kawasaki|oi|funabashi|urawa)_\d{1,2}$")
MANUAL_IMPORT_LOG_COLUMNS = (
    "imported_at",
    "race_id",
    "source_path",
    "cache_html_path",
    "status",
    "source_sha256",
    "error",
)


@dataclass(frozen=True)
class ManualHtmlImportResult:
    race_id: str
    source_path: Path
    cache_html_path: Path
    status: str
    source_sha256: str = ""
    error: str = ""

    def as_log_row(self, imported_at: str) -> dict[str, str]:
        return {
            "imported_at": imported_at,
            "race_id": self.race_id,
            "source_path": _path_string(self.source_path),
            "cache_html_path": _path_string(self.cache_html_path),
            "status": self.status,
            "source_sha256": self.source_sha256,
            "error": self.error,
        }


def import_manual_html_cache(
    *,
    manual_html_dir: str | Path = DEFAULT_MANUAL_HTML_DIR,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    log_path: str | Path = DEFAULT_MANUAL_IMPORT_LOG_PATH,
) -> list[ManualHtmlImportResult]:
    manual_dir = Path(manual_html_dir)
    cache_dir = Path(cache_html_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    results: list[ManualHtmlImportResult] = []
    for source_path in sorted(manual_dir.glob("*.html")):
        race_id = source_path.stem
        cache_path = cache_dir / source_path.name
        source_hash = _sha256(source_path)
        if not RACE_ID_FILENAME_PATTERN.match(race_id):
            results.append(
                ManualHtmlImportResult(
                    race_id=race_id,
                    source_path=source_path,
                    cache_html_path=cache_path,
                    status="skipped_invalid_name",
                    source_sha256=source_hash,
                    error="filename must be <race_id>.html",
                )
            )
            continue
        if cache_path.exists():
            results.append(
                ManualHtmlImportResult(
                    race_id=race_id,
                    source_path=source_path,
                    cache_html_path=cache_path,
                    status="skipped_exists",
                    source_sha256=source_hash,
                )
            )
            continue

        try:
            shutil.copy2(source_path, cache_path)
            results.append(
                ManualHtmlImportResult(
                    race_id=race_id,
                    source_path=source_path,
                    cache_html_path=cache_path,
                    status="imported",
                    source_sha256=source_hash,
                )
            )
        except OSError as exc:
            results.append(
                ManualHtmlImportResult(
                    race_id=race_id,
                    source_path=source_path,
                    cache_html_path=cache_path,
                    status="failed",
                    source_sha256=source_hash,
                    error=str(exc),
                )
            )

    if results:
        append_manual_import_log(results, log_path=log_path)
    return results


def append_manual_import_log(
    results: list[ManualHtmlImportResult],
    *,
    log_path: str | Path = DEFAULT_MANUAL_IMPORT_LOG_PATH,
) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0
    imported_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_IMPORT_LOG_COLUMNS, lineterminator="\n")
        if not file_exists:
            writer.writeheader()
        writer.writerows(result.as_log_row(imported_at) for result in results)
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import manually saved official result HTML files into the cache."
    )
    parser.add_argument("--manual-html-dir", default=str(DEFAULT_MANUAL_HTML_DIR))
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--log-path", default=str(DEFAULT_MANUAL_IMPORT_LOG_PATH))
    args = parser.parse_args(argv)

    results = import_manual_html_cache(
        manual_html_dir=args.manual_html_dir,
        cache_html_dir=args.cache_html_dir,
        log_path=args.log_path,
    )
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    print(f"OK: checked {len(results)} manual HTML files")
    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")
    print(f"cache_html_dir: {args.cache_html_dir}")
    print(f"manual_import_log: {args.log_path}")
    print("note: raw CSV was not changed.")
    return 0 if not any(result.status == "failed" for result in results) else 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "DEFAULT_MANUAL_HTML_DIR",
    "DEFAULT_MANUAL_IMPORT_LOG_PATH",
    "MANUAL_IMPORT_LOG_COLUMNS",
    "ManualHtmlImportResult",
    "append_manual_import_log",
    "import_manual_html_cache",
]


if __name__ == "__main__":
    raise SystemExit(main())

