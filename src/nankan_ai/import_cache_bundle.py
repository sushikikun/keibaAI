from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable

from .append_batch_log import file_sha256
from .fetch_plan import DEFAULT_CACHE_HTML_DIR

DEFAULT_IMPORTS_DIR = Path("data/cache/imports")
RACE_ID_PATTERN = re.compile(r"^\d{8}_(kawasaki|oi|funabashi|urawa)_\d{1,2}$")


@dataclass
class CacheBundleImportResult:
    bundle_path: Path
    report_path: Path
    imported: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def import_cache_bundle(
    bundle_path: str | Path,
    *,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    imports_dir: str | Path = DEFAULT_IMPORTS_DIR,
    now: datetime | None = None,
) -> CacheBundleImportResult:
    bundle = Path(bundle_path)
    report_path = _report_path(Path(imports_dir), now)
    result = CacheBundleImportResult(bundle_path=bundle, report_path=report_path)

    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
            unsafe_names = [name for name in names if not _is_safe_zip_name(name)]
            if unsafe_names:
                result.errors.extend(f"unsafe zip path: {name}" for name in unsafe_names)
                _write_report(result)
                return result

            if "manifest.json" not in names:
                result.errors.append("manifest.json is missing from bundle.")
                _write_report(result)
                return result

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            entries = _manifest_entries(manifest)
            html_entries = [name for name in names if name.startswith("html/") and name.endswith(".html")]
            _validate_manifest_entries(entries, html_entries, result)
            if result.errors:
                _write_report(result)
                return result

            cache_dir = Path(cache_html_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            for entry in entries:
                _import_entry(archive, entry, cache_dir, result)
    except FileNotFoundError:
        result.errors.append(f"bundle file not found: {bundle}")
    except zipfile.BadZipFile as exc:
        result.errors.append(f"bundle is not a valid zip file: {exc}")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        result.errors.append(f"manifest.json is invalid: {exc}")

    _write_report(result)
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a portable cache bundle into data/cache/html without touching raw CSV."
    )
    parser.add_argument("bundle_path")
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--imports-dir", default=str(DEFAULT_IMPORTS_DIR))
    args = parser.parse_args(argv)

    result = import_cache_bundle(
        args.bundle_path,
        cache_html_dir=args.cache_html_dir,
        imports_dir=args.imports_dir,
    )
    print(f"report: {result.report_path}")
    print(f"imported: {len(result.imported)}")
    print(f"skipped_existing: {len(result.skipped_existing)}")
    print(f"warnings: {len(result.warnings)}")
    print(f"errors: {len(result.errors)}")
    print("note: raw CSV was not changed and append CSV was not generated.")
    return 0 if result.is_valid else 1


def _manifest_entries(manifest: dict[str, object]) -> list[dict[str, str]]:
    raw_entries = manifest.get("html_files")
    if not isinstance(raw_entries, list):
        raise TypeError("manifest html_files must be a list.")
    entries: list[dict[str, str]] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise TypeError("manifest html_files entries must be objects.")
        entries.append(
            {
                "race_id": str(raw_entry.get("race_id", "")).strip(),
                "path": str(raw_entry.get("path", "")).strip(),
                "sha256": str(raw_entry.get("sha256", "")).strip(),
            }
        )
    return entries


def _validate_manifest_entries(
    entries: list[dict[str, str]],
    html_entries: list[str],
    result: CacheBundleImportResult,
) -> None:
    seen_race_ids: set[str] = set()
    manifest_paths = {entry["path"] for entry in entries}
    for entry in entries:
        race_id = entry["race_id"]
        path = entry["path"]
        if race_id in seen_race_ids:
            result.errors.append(f"bundle has duplicate race_id in manifest: {race_id}")
        seen_race_ids.add(race_id)
        if not RACE_ID_PATTERN.match(race_id):
            result.errors.append(f"invalid race_id in manifest: {race_id}")
        if path != f"html/{race_id}.html":
            result.errors.append(f"manifest path does not match race_id: race_id={race_id}, path={path}")
        if path not in html_entries:
            result.errors.append(f"manifest references missing HTML: {path}")

    for html_path in html_entries:
        if html_path not in manifest_paths:
            result.warnings.append(f"HTML is not listed in manifest and will not be imported: {html_path}")


def _import_entry(
    archive: zipfile.ZipFile,
    entry: dict[str, str],
    cache_html_dir: Path,
    result: CacheBundleImportResult,
) -> None:
    race_id = entry["race_id"]
    path = entry["path"]
    if result.errors and any(race_id in error for error in result.errors):
        return
    if path not in archive.namelist():
        return

    data = archive.read(path)
    if not data:
        result.errors.append(f"HTML file is empty and was not imported: {path}")
        return

    expected_sha = entry.get("sha256", "")
    actual_sha = _sha256_bytes(data)
    if expected_sha and expected_sha != actual_sha:
        result.errors.append(f"HTML sha256 mismatch for {path}")
        return

    output_path = cache_html_dir / f"{race_id}.html"
    if output_path.exists():
        result.skipped_existing.append(race_id)
        return
    output_path.write_bytes(data)
    result.imported.append(race_id)


def _is_safe_zip_name(name: str) -> bool:
    if "\\" in name or ":" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and all(part for part in path.parts)


def _report_path(imports_dir: Path, now: datetime | None) -> Path:
    value = now or datetime.now()
    return imports_dir / f"import_cache_bundle_{value.strftime('%Y%m%d_%H%M%S')}.md"


def _write_report(result: CacheBundleImportResult) -> None:
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Cache Bundle Import Report",
        "",
        f"- bundle_path: `{result.bundle_path}`",
        f"- bundle_sha256: `{file_sha256(result.bundle_path)}`",
        f"- imported: {len(result.imported)}",
        f"- skipped_existing: {len(result.skipped_existing)}",
        f"- warnings: {len(result.warnings)}",
        f"- errors: {len(result.errors)}",
        "- raw_changed: no",
        "- append_csv_generated: no",
        "",
        "## Imported",
        *[f"- `{race_id}`" for race_id in result.imported],
        "",
        "## Skipped Existing",
        *[f"- `{race_id}`" for race_id in result.skipped_existing],
        "",
        "## Warnings",
        *[f"- {warning}" for warning in result.warnings],
        "",
        "## Errors",
        *[f"- {error}" for error in result.errors],
        "",
    ]
    result.report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


__all__ = [
    "DEFAULT_IMPORTS_DIR",
    "CacheBundleImportResult",
    "import_cache_bundle",
]


if __name__ == "__main__":
    raise SystemExit(main())
