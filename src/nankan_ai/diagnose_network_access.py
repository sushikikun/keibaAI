from __future__ import annotations

import argparse
import socket
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

from .fetch_result_pages import USER_AGENT

DEFAULT_HOST = "www.keiba.go.jp"
DEFAULT_PORT = 443
DEFAULT_URL = (
    "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable"
    "?k_raceDate=2025%2F09%2F08&k_raceNo=1&k_babaCode=21"
)


@dataclass(frozen=True)
class NetworkCheckResult:
    step: str
    ok: bool
    detail: str = ""
    exception_type: str = ""
    exception_message: str = ""

    def format(self) -> str:
        status = "OK" if self.ok else "NG"
        parts = [f"{self.step}: {status}"]
        if self.detail:
            parts.append(self.detail)
        if self.exception_type or self.exception_message:
            parts.append(f"{self.exception_type}: {self.exception_message}".strip(": "))
        return " | ".join(parts)


def check_dns(
    host: str = DEFAULT_HOST,
    *,
    resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
) -> NetworkCheckResult:
    try:
        addresses = resolver(host, DEFAULT_PORT, type=socket.SOCK_STREAM)
        resolved = sorted({str(item[4][0]) for item in addresses if item and len(item) >= 5})
        detail = ", ".join(resolved[:5]) if resolved else "resolved without address details"
        return NetworkCheckResult("DNS", True, detail=detail)
    except Exception as exc:  # noqa: BLE001 - diagnostics should report the concrete exception.
        return _failure("DNS", exc)


def check_tcp_443(
    host: str = DEFAULT_HOST,
    *,
    port: int = DEFAULT_PORT,
    timeout_seconds: float = 10,
    connector: Callable[..., object] = socket.create_connection,
) -> NetworkCheckResult:
    sock: object | None = None
    try:
        sock = connector((host, port), timeout=timeout_seconds)
        return NetworkCheckResult("TCP 443", True, detail=f"{host}:{port}")
    except Exception as exc:  # noqa: BLE001
        return _failure("TCP 443", exc)
    finally:
        close = getattr(sock, "close", None)
        if callable(close):
            close()


def check_https_get(
    url: str = DEFAULT_URL,
    *,
    timeout_seconds: float = 10,
    opener: Callable[..., object] = urlopen,
) -> NetworkCheckResult:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", "")
            response.read(256)
        detail = f"status={status}" if status else "GET completed"
        return NetworkCheckResult("HTTPS GET", True, detail=detail)
    except (OSError, URLError) as exc:
        return _failure("HTTPS GET", exc)
    except Exception as exc:  # noqa: BLE001
        return _failure("HTTPS GET", exc)


def diagnose_network_access(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    url: str = DEFAULT_URL,
    timeout_seconds: float = 10,
) -> list[NetworkCheckResult]:
    return [
        check_dns(host),
        check_tcp_443(host, port=port, timeout_seconds=timeout_seconds),
        check_https_get(url, timeout_seconds=timeout_seconds),
    ]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose local network access to the official Keiba result pages."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    args = parser.parse_args(argv)

    results = diagnose_network_access(
        host=args.host,
        port=args.port,
        url=args.url,
        timeout_seconds=args.timeout_seconds,
    )
    print("Network access diagnosis")
    print(f"host: {args.host}")
    print(f"port: {args.port}")
    print(f"url: {args.url}")
    for result in results:
        print(result.format())
    print("note: this command does not modify raw CSV or HTML cache files.")
    return 0


def _failure(step: str, exc: BaseException) -> NetworkCheckResult:
    return NetworkCheckResult(
        step,
        False,
        exception_type=exc.__class__.__name__,
        exception_message=str(exc),
    )


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_URL",
    "NetworkCheckResult",
    "check_dns",
    "check_https_get",
    "check_tcp_443",
    "diagnose_network_access",
]


if __name__ == "__main__":
    raise SystemExit(main())

