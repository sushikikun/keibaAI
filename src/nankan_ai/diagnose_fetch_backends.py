from __future__ import annotations

import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .diagnose_network_access import DEFAULT_URL
from .fetch_result_pages import (
    USER_AGENT,
    build_fetch_command,
)

FETCH_BACKENDS = ("python", "powershell", "curl")


@dataclass(frozen=True)
class FetchBackendDiagnosticResult:
    backend: str
    available: bool
    exit_code: str = ""
    status_code: str = ""
    error_message: str = ""

    def format(self) -> str:
        state = "available" if self.available else "unavailable"
        parts = [
            f"backend={self.backend}",
            f"state={state}",
            f"exit_code={self.exit_code or '(blank)'}",
            f"status_code={self.status_code or '(blank)'}",
        ]
        if self.error_message:
            parts.append(f"error={self.error_message}")
        return " | ".join(parts)


def diagnose_fetch_backends(
    *,
    url: str = DEFAULT_URL,
    timeout_seconds: int = 20,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    opener: Callable[..., object] = urlopen,
) -> list[FetchBackendDiagnosticResult]:
    return [
        diagnose_python_urllib(url, timeout_seconds=timeout_seconds, opener=opener),
        diagnose_command_backend(
            "powershell",
            url,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
        ),
        diagnose_command_backend(
            "curl",
            url,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
        ),
    ]


def diagnose_python_urllib(
    url: str = DEFAULT_URL,
    *,
    timeout_seconds: int = 20,
    opener: Callable[..., object] = urlopen,
) -> FetchBackendDiagnosticResult:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=timeout_seconds) as response:
            status_code = str(getattr(response, "status", "") or "")
            response.read(256)
        return FetchBackendDiagnosticResult(
            backend="python",
            available=True,
            exit_code="0",
            status_code=status_code,
        )
    except HTTPError as exc:
        return FetchBackendDiagnosticResult(
            backend="python",
            available=False,
            exit_code="1",
            status_code=str(exc.code),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )
    except (OSError, URLError) as exc:
        return _backend_failure("python", exc, exit_code="1")
    except Exception as exc:  # noqa: BLE001 - backend diagnostics should report exact failures.
        return _backend_failure("python", exc, exit_code="1")


def diagnose_command_backend(
    backend: str,
    url: str = DEFAULT_URL,
    *,
    timeout_seconds: int = 20,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> FetchBackendDiagnosticResult:
    with tempfile.TemporaryDirectory(prefix=f"nankan_fetch_{backend}_") as temp_dir:
        output_path = Path(temp_dir) / f"{backend}.html"
        command = build_fetch_command(backend, url, output_path, timeout_seconds)
        try:
            completed = command_runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds + 5,
            )
        except FileNotFoundError as exc:
            return _backend_failure(backend, exc, exit_code="")
        except subprocess.TimeoutExpired as exc:
            return _backend_failure(backend, exc, exit_code="")
        except OSError as exc:
            return _backend_failure(backend, exc, exit_code="")

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status_code = _extract_status_code(stdout + "\n" + stderr)
        available = completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
        error_message = ""
        if not available:
            output = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
            error_message = output or "command did not create a non-empty HTML file."
        return FetchBackendDiagnosticResult(
            backend=backend,
            available=available,
            exit_code=str(completed.returncode),
            status_code=status_code,
            error_message=error_message,
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose official result page fetch backends without changing raw/cache files."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args(argv)

    results = diagnose_fetch_backends(url=args.url, timeout_seconds=args.timeout_seconds)
    print("Fetch backend diagnosis")
    print(f"url: {args.url}")
    for result in results:
        print(result.format())
    print("note: this command does not modify raw CSV or HTML cache files.")
    return 0


def _backend_failure(
    backend: str,
    exc: BaseException,
    *,
    exit_code: str,
) -> FetchBackendDiagnosticResult:
    return FetchBackendDiagnosticResult(
        backend=backend,
        available=False,
        exit_code=exit_code,
        error_message=f"{exc.__class__.__name__}: {exc}",
    )


def _extract_status_code(text: str) -> str:
    marker = "STATUS_CODE="
    index = text.rfind(marker)
    if index == -1:
        return ""
    rest = text[index + len(marker) :].strip()
    digits = []
    for char in rest:
        if not char.isdigit():
            break
        digits.append(char)
    return "".join(digits)


__all__ = [
    "FETCH_BACKENDS",
    "FetchBackendDiagnosticResult",
    "diagnose_command_backend",
    "diagnose_fetch_backends",
    "diagnose_python_urllib",
]


if __name__ == "__main__":
    raise SystemExit(main())

