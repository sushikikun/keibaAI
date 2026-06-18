from __future__ import annotations

import socket

from nankan_ai.diagnose_network_access import (
    NetworkCheckResult,
    check_dns,
    check_https_get,
    check_tcp_443,
)


def test_check_dns_reports_resolved_addresses() -> None:
    def fake_resolver(*args: object, **kwargs: object) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("203.0.113.10", 443))]

    result = check_dns("example.test", resolver=fake_resolver)

    assert result.ok
    assert result.step == "DNS"
    assert "203.0.113.10" in result.detail


def test_check_dns_reports_exception_name() -> None:
    def fake_resolver(*args: object, **kwargs: object) -> list[tuple]:
        raise OSError("blocked")

    result = check_dns("example.test", resolver=fake_resolver)

    assert not result.ok
    assert result.exception_type == "OSError"
    assert result.exception_message == "blocked"


def test_check_tcp_443_closes_socket() -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    fake_socket = FakeSocket()

    def fake_connector(*args: object, **kwargs: object) -> FakeSocket:
        return fake_socket

    result = check_tcp_443("example.test", connector=fake_connector)

    assert result.ok
    assert fake_socket.closed


def test_check_https_get_reports_status() -> None:
    class FakeResponse:
        status = 200

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"ok"

    def fake_opener(*args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse()

    result = check_https_get("https://example.test", opener=fake_opener)

    assert result.ok
    assert result.detail == "status=200"


def test_network_check_result_format_includes_exception() -> None:
    result = NetworkCheckResult(
        step="HTTPS GET",
        ok=False,
        exception_type="PermissionError",
        exception_message="blocked",
    )

    assert result.format() == "HTTPS GET: NG | PermissionError: blocked"

