from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, TextIO


SNAPSHOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def open_text(path: Path, mode: str = "rt", *, newline: str | None = "") -> TextIO:
    if "b" in mode:
        raise ValueError("open_text only supports text modes")
    if path.suffix.lower() == ".gz":
        return gzip.open(path, mode, encoding="utf-8", newline=newline)
    return path.open(mode, encoding="utf-8-sig" if "r" in mode else "utf-8", newline=newline)


def open_deterministic_gzip_text(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    compressed = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    return io.TextIOWrapper(compressed, encoding="utf-8", newline="")


def read_csv_rows(path: Path) -> Iterator[dict[str, str]]:
    with open_text(path, "rt", newline="") as handle:
        yield from csv.DictReader(handle)


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def parse_int(value: object, *, minimum: int | None = None, maximum: int | None = None) -> int:
    text = str(value).strip()
    if not text or not re.fullmatch(r"[+-]?\d+", text):
        raise ValueError(f"not an integer: {value!r}")
    parsed = int(text)
    if minimum is not None and parsed < minimum:
        raise ValueError(f"value {parsed} is below {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"value {parsed} is above {maximum}")
    return parsed


def parse_finite_float(value: object) -> float:
    parsed = float(str(value).strip())
    if not math.isfinite(parsed):
        raise ValueError(f"not finite: {value!r}")
    return parsed


def ensure_relative_to(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def count_reasons(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in filter(None, row.get("exclusion_reasons", "").split("|")):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))
