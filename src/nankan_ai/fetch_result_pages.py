from __future__ import annotations

import argparse
import csv
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .fetch_plan import DEFAULT_CACHE_HTML_DIR

DEFAULT_FETCH_LOG_PATH = Path("data/cache/metadata/fetch_log.csv")
SUPPORTED_FETCH_BACKENDS = ("python", "powershell", "curl", "browser")
BROWSER_BACKEND_UNAVAILABLE_ERROR = (
    "browser backend requires the Codex in-app browser handoff; "
    "the Python CLI cannot directly control that browser. "
    "Use the documented browser cache workflow to save HTML into data/cache/html."
)
STATUS_CODE_PATTERN = re.compile(r"STATUS_CODE=(\d+)")
FETCH_LOG_COLUMNS = (
    "fetched_at",
    "mode",
    "race_id",
    "date",
    "track",
    "race_no",
    "official_url",
    "cache_html_path",
    "status",
    "http_status",
    "error",
)
USER_AGENT = "nankan-ai-data-layer/0.1 (+low-frequency manual-range fetch)"


@dataclass(frozen=True)
class FetchResult:
    race_id: str
    status: str
    cache_html_path: str
    http_status: str = ""
    error: str = ""


@dataclass(frozen=True)
class FetchCommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def fetch_result_pages(
    fetch_plan_csv_path: str | Path,
    *,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    fetch_log_path: str | Path = DEFAULT_FETCH_LOG_PATH,
    apply: bool = False,
    delay_seconds: float = 1.0,
    timeout_seconds: int = 30,
    backend: str = "python",
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[FetchResult]:
    backend = _normalize_backend(backend)
    plan_rows = _read_fetch_plan(fetch_plan_csv_path)
    cache_dir = Path(cache_html_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    results: list[FetchResult] = []
    log_rows: list[dict[str, str]] = []
    for index, row in enumerate(plan_rows):
        race_id = _clean(row.get("race_id"))
        url = _clean(row.get("official_url")) or _clean(row.get("url"))
        cache_path = _cache_path(row, cache_dir)

        if cache_path.exists():
            result = FetchResult(race_id=race_id, status="cached", cache_html_path=_path_string(cache_path))
        elif not apply:
            result = FetchResult(race_id=race_id, status="dry_run", cache_html_path=_path_string(cache_path))
        elif not url:
            result = FetchResult(
                race_id=race_id,
                status="failed",
                cache_html_path=_path_string(cache_path),
                error="official_url is blank.",
            )
        else:
            result = _fetch_one(
                race_id=race_id,
                url=url,
                cache_path=cache_path,
                timeout_seconds=timeout_seconds,
                backend=backend,
                command_runner=command_runner,
            )
            if delay_seconds > 0 and index < len(plan_rows) - 1:
                time.sleep(delay_seconds)

        results.append(result)
        log_rows.append(_log_row(row, result, mode="apply" if apply else "dry_run"))

    append_fetch_log(log_rows, fetch_log_path)
    return results


def append_fetch_log(rows: list[dict[str, str]], fetch_log_path: str | Path = DEFAULT_FETCH_LOG_PATH) -> Path:
    path = Path(fetch_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FETCH_LOG_COLUMNS, lineterminator="\n")
        if not file_exists:
            writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in FETCH_LOG_COLUMNS} for row in rows)
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch official result pages from a fetch plan into the local HTML cache."
    )
    parser.add_argument("fetch_plan_csv_path")
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--fetch-log-path", default=str(DEFAULT_FETCH_LOG_PATH))
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--backend",
        choices=SUPPORTED_FETCH_BACKENDS,
        default="python",
        help="Fetch backend. Default is python urllib.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually fetch pages. Default is dry-run.")
    args = parser.parse_args(argv)

    results = fetch_result_pages(
        args.fetch_plan_csv_path,
        cache_html_dir=args.cache_html_dir,
        fetch_log_path=args.fetch_log_path,
        apply=args.apply,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        backend=args.backend,
    )
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    print(f"OK: processed {len(results)} planned races")
    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")
    print(f"fetch_log: {args.fetch_log_path}")
    print(f"backend: {args.backend}")
    return 0 if not any(result.status == "failed" for result in results) else 1


def _read_fetch_plan(fetch_plan_csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(fetch_plan_csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in ("race_id", "date", "track", "race_no") if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"fetch plan is missing columns: {', '.join(missing)}")
        if "official_url" not in (reader.fieldnames or []) and "url" not in (reader.fieldnames or []):
            raise ValueError("fetch plan is missing official_url column.")
        return [dict(row) for row in reader]


def _cache_path(row: dict[str, str], cache_html_dir: Path) -> Path:
    value = _clean(row.get("cache_html_path"))
    if value:
        return Path(value)
    return cache_html_dir / f"{_clean(row.get('race_id'))}.html"


def _fetch_one(
    *,
    race_id: str,
    url: str,
    cache_path: Path,
    timeout_seconds: int,
    backend: str,
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> FetchResult:
    backend = _normalize_backend(backend)
    if backend == "python":
        return _fetch_one_python(
            race_id=race_id,
            url=url,
            cache_path=cache_path,
            timeout_seconds=timeout_seconds,
        )
    if backend == "browser":
        return _fetch_one_browser(race_id=race_id, cache_path=cache_path)
    return _fetch_one_command(
        race_id=race_id,
        url=url,
        cache_path=cache_path,
        timeout_seconds=timeout_seconds,
        backend=backend,
        command_runner=command_runner,
        )


def _fetch_one_browser(*, race_id: str, cache_path: Path) -> FetchResult:
    return FetchResult(
        race_id=race_id,
        status="failed",
        cache_html_path=_path_string(cache_path),
        error=BROWSER_BACKEND_UNAVAILABLE_ERROR,
    )


def _fetch_one_python(
    *,
    race_id: str,
    url: str,
    cache_path: Path,
    timeout_seconds: int,
) -> FetchResult:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            status = getattr(response, "status", "")
        cache_path.write_bytes(body)
        return FetchResult(
            race_id=race_id,
            status="fetched",
            cache_html_path=_path_string(cache_path),
            http_status=str(status),
        )
    except HTTPError as exc:
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            http_status=str(exc.code),
            error=str(exc),
        )
    except (OSError, URLError) as exc:
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            error=str(exc),
        )


def _fetch_one_command(
    *,
    race_id: str,
    url: str,
    cache_path: Path,
    timeout_seconds: int,
    backend: str,
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> FetchResult:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_name(f"{cache_path.name}.{backend}.tmp")
    if temp_path.exists():
        temp_path.unlink()

    command = build_fetch_command(backend, url, temp_path, timeout_seconds)
    try:
        completed = command_runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(timeout_seconds + 5, timeout_seconds),
        )
    except FileNotFoundError as exc:
        _remove_temp_file(temp_path)
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            error=f"{backend} backend executable was not found: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        _remove_temp_file(temp_path)
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            error=f"{backend} backend timed out: {exc}",
        )
    except OSError as exc:
        _remove_temp_file(temp_path)
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            error=f"{backend} backend failed to start: {exc}",
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    status_code = _extract_status_code(stdout + "\n" + stderr)
    if completed.returncode != 0 or not temp_path.exists() or temp_path.stat().st_size == 0:
        _remove_temp_file(temp_path)
        error = _command_error_message(backend, completed.returncode, stdout, stderr)
        return FetchResult(
            race_id=race_id,
            status="failed",
            cache_html_path=_path_string(cache_path),
            http_status=status_code,
            error=error,
        )

    temp_path.replace(cache_path)
    return FetchResult(
        race_id=race_id,
        status="fetched",
        cache_html_path=_path_string(cache_path),
        http_status=status_code,
    )


def build_fetch_command(
    backend: str,
    url: str,
    output_path: str | Path,
    timeout_seconds: int,
) -> list[str]:
    normalized = _normalize_backend(backend)
    if normalized == "powershell":
        return build_powershell_fetch_command(url, output_path, timeout_seconds)
    if normalized == "curl":
        return build_curl_fetch_command(url, output_path, timeout_seconds)
    if normalized == "browser":
        raise ValueError("browser backend does not use an external fetch command.")
    raise ValueError("python backend does not use an external fetch command.")


def build_powershell_fetch_command(
    url: str,
    output_path: str | Path,
    timeout_seconds: int,
) -> list[str]:
    quoted_url = _powershell_quote(url)
    quoted_output_path = _powershell_quote(str(output_path))
    script = (
        "$ProgressPreference='SilentlyContinue'; "
        "$ErrorActionPreference='Stop'; "
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        f"$url = {quoted_url}; "
        f"$outputPath = {quoted_output_path}; "
        f"$timeoutSeconds = {int(timeout_seconds)}; "
        "$response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSeconds; "
        "[System.IO.File]::WriteAllText($outputPath, $response.Content, [System.Text.Encoding]::UTF8); "
        "Write-Output ('STATUS_CODE=' + [int]$response.StatusCode)"
    )
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]


def build_curl_fetch_command(
    url: str,
    output_path: str | Path,
    timeout_seconds: int,
) -> list[str]:
    return [
        "curl.exe",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        str(int(timeout_seconds)),
        "-w",
        "STATUS_CODE=%{http_code}",
        "-o",
        str(output_path),
        url,
    ]


def _log_row(row: dict[str, str], result: FetchResult, *, mode: str) -> dict[str, str]:
    return {
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        "race_id": _clean(row.get("race_id")),
        "date": _clean(row.get("date")),
        "track": _clean(row.get("track")),
        "race_no": _clean(row.get("race_no")),
        "official_url": _clean(row.get("official_url")) or _clean(row.get("url")),
        "cache_html_path": result.cache_html_path,
        "status": result.status,
        "http_status": result.http_status,
        "error": result.error,
    }


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _normalize_backend(backend: str) -> str:
    normalized = backend.strip().lower()
    if normalized not in SUPPORTED_FETCH_BACKENDS:
        raise ValueError(f"backend must be one of: {', '.join(SUPPORTED_FETCH_BACKENDS)}")
    return normalized


def _extract_status_code(text: str) -> str:
    match = STATUS_CODE_PATTERN.search(text)
    return match.group(1) if match else ""


def _command_error_message(backend: str, returncode: int, stdout: str, stderr: str) -> str:
    output = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
    if not output:
        output = "no output"
    return f"{backend} backend exited with code {returncode}: {output}"


def _remove_temp_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


__all__ = [
    "DEFAULT_FETCH_LOG_PATH",
    "FETCH_LOG_COLUMNS",
    "BROWSER_BACKEND_UNAVAILABLE_ERROR",
    "SUPPORTED_FETCH_BACKENDS",
    "FetchCommandResult",
    "FetchResult",
    "append_fetch_log",
    "build_curl_fetch_command",
    "build_fetch_command",
    "build_powershell_fetch_command",
    "fetch_result_pages",
]


if __name__ == "__main__":
    raise SystemExit(main())
