from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from nankan_ai.diagnose_fetch_backends import diagnose_command_backend
from nankan_ai.fetch_result_pages import (
    BROWSER_BACKEND_UNAVAILABLE_ERROR,
    build_curl_fetch_command,
    build_fetch_command,
    build_powershell_fetch_command,
    fetch_result_pages,
)


def test_build_powershell_fetch_command_contains_url_output_and_timeout(tmp_path: Path) -> None:
    output_path = tmp_path / "page.html"

    command = build_powershell_fetch_command("https://example.test/page", output_path, 12)

    assert command[0] == "powershell.exe"
    assert "-Command" in command
    script = command[command.index("-Command") + 1]
    assert "Invoke-WebRequest" in script
    assert "'https://example.test/page'" in script
    assert str(output_path) in script
    assert "$timeoutSeconds = 12" in script


def test_build_curl_fetch_command_contains_output_and_status_marker(tmp_path: Path) -> None:
    output_path = tmp_path / "page.html"

    command = build_curl_fetch_command("https://example.test/page", output_path, 12)

    assert command[0] == "curl.exe"
    assert "-o" in command
    assert command[command.index("-o") + 1] == str(output_path)
    assert "STATUS_CODE=%{http_code}" in command
    assert command[-1] == "https://example.test/page"


def test_build_fetch_command_rejects_python_external_command(tmp_path: Path) -> None:
    try:
        build_fetch_command("python", "https://example.test", tmp_path / "page.html", 10)
    except ValueError as exc:
        assert "python backend does not use" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_build_fetch_command_rejects_browser_external_command(tmp_path: Path) -> None:
    try:
        build_fetch_command("browser", "https://example.test", tmp_path / "page.html", 10)
    except ValueError as exc:
        assert "browser backend does not use" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_fetch_result_pages_uses_curl_backend_runner(tmp_path: Path) -> None:
    plan_path = _write_fetch_plan(tmp_path)
    log_path = tmp_path / "fetch_log.csv"
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text("<html>ok</html>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="STATUS_CODE=200", stderr="")

    results = fetch_result_pages(
        plan_path,
        fetch_log_path=log_path,
        apply=True,
        delay_seconds=0,
        timeout_seconds=5,
        backend="curl",
        command_runner=fake_runner,
    )

    cache_path = tmp_path / "cache" / "20250908_kawasaki_1.html"
    assert len(calls) == 1
    assert results[0].status == "fetched"
    assert results[0].http_status == "200"
    assert cache_path.read_text(encoding="utf-8") == "<html>ok</html>"
    assert _read_log(log_path)[0]["status"] == "fetched"


def test_fetch_result_pages_browser_backend_reports_handoff_requirement(tmp_path: Path) -> None:
    plan_path = _write_fetch_plan(tmp_path)
    log_path = tmp_path / "fetch_log.csv"

    results = fetch_result_pages(
        plan_path,
        fetch_log_path=log_path,
        apply=True,
        delay_seconds=0,
        timeout_seconds=5,
        backend="browser",
    )

    cache_path = tmp_path / "cache" / "20250908_kawasaki_1.html"
    assert results[0].status == "failed"
    assert BROWSER_BACKEND_UNAVAILABLE_ERROR in results[0].error
    assert not cache_path.exists()
    log_rows = _read_log(log_path)
    assert log_rows[0]["status"] == "failed"
    assert BROWSER_BACKEND_UNAVAILABLE_ERROR in log_rows[0]["error"]


def test_fetch_result_pages_skips_backend_when_cache_exists(tmp_path: Path) -> None:
    plan_path = _write_fetch_plan(tmp_path)
    cache_path = tmp_path / "cache" / "20250908_kawasaki_1.html"
    cache_path.parent.mkdir()
    cache_path.write_text("<html>cached</html>", encoding="utf-8")

    def forbidden_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("backend should not be called when cache exists")

    results = fetch_result_pages(
        plan_path,
        fetch_log_path=tmp_path / "fetch_log.csv",
        apply=True,
        delay_seconds=0,
        backend="curl",
        command_runner=forbidden_runner,
    )

    assert results[0].status == "cached"
    assert cache_path.read_text(encoding="utf-8") == "<html>cached</html>"


def test_fetch_result_pages_browser_backend_respects_existing_cache(tmp_path: Path) -> None:
    plan_path = _write_fetch_plan(tmp_path)
    cache_path = tmp_path / "cache" / "20250908_kawasaki_1.html"
    cache_path.parent.mkdir()
    cache_path.write_text("<html>browser cached</html>", encoding="utf-8")

    results = fetch_result_pages(
        plan_path,
        fetch_log_path=tmp_path / "fetch_log.csv",
        apply=True,
        delay_seconds=0,
        backend="browser",
    )

    assert results[0].status == "cached"
    assert cache_path.read_text(encoding="utf-8") == "<html>browser cached</html>"


def test_fetch_result_pages_failed_backend_does_not_keep_temp_file(tmp_path: Path) -> None:
    plan_path = _write_fetch_plan(tmp_path)

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text("", encoding="utf-8")
        return subprocess.CompletedProcess(command, 7, stdout="STATUS_CODE=000", stderr="blocked")

    results = fetch_result_pages(
        plan_path,
        fetch_log_path=tmp_path / "fetch_log.csv",
        apply=True,
        delay_seconds=0,
        backend="curl",
        command_runner=fake_runner,
    )

    cache_dir = tmp_path / "cache"
    assert results[0].status == "failed"
    assert not (cache_dir / "20250908_kawasaki_1.html").exists()
    assert not list(cache_dir.glob("*.tmp"))


def test_diagnose_command_backend_with_fake_curl_runner(tmp_path: Path) -> None:
    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text("<html>ok</html>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="STATUS_CODE=200", stderr="")

    result = diagnose_command_backend(
        "curl",
        "https://example.test/page",
        timeout_seconds=5,
        command_runner=fake_runner,
    )

    assert result.available
    assert result.exit_code == "0"
    assert result.status_code == "200"


def _write_fetch_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "fetch_plan.csv"
    cache_path = tmp_path / "cache" / "20250908_kawasaki_1.html"
    with plan_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "race_id",
                "date",
                "track",
                "race_no",
                "official_url",
                "cache_html_path",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "race_id": "20250908_kawasaki_1",
                "date": "2025-09-08",
                "track": "kawasaki",
                "race_no": "1",
                "official_url": "https://example.test/page",
                "cache_html_path": str(cache_path),
            }
        )
    return plan_path


def _read_log(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
