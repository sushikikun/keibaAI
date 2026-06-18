from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from .schema import REQUIRED_COLUMNS

DEFAULT_CACHE_HTML_DIR = Path("data/cache/html")
RACE_ID_PATTERN = re.compile(r"^(?P<date>\d{8})_(?P<track>[a-z]+)_(?P<race_no>\d{1,2})$")


@dataclass
class ParsedRacePage:
    race_id: str
    rows: list[dict[str, str]]
    source_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def race_count(self) -> int:
        return 1 if self.rows else 0


def parse_result_page_file(html_path: str | Path) -> ParsedRacePage:
    path = Path(html_path)
    html = _read_html(path)
    race_id = path.stem
    return parse_result_page_html(html, race_id=race_id, source_path=path)


def parse_result_page_html(
    html: str,
    *,
    race_id: str,
    source_path: str | Path | None = None,
) -> ParsedRacePage:
    context = _context_from_race_id(race_id)
    warnings: list[str] = []
    tables = _extract_tables(html)
    metadata = _extract_metadata(html, tables)
    result_table = _find_result_table(tables)
    if result_table is None:
        return ParsedRacePage(
            race_id=race_id,
            rows=[],
            source_path=Path(source_path) if source_path else None,
            warnings=["result table with horse_no/horse_name columns was not found."],
        )

    header_index, headers = result_table
    header_map = _build_header_map(headers)
    entries: list[dict[str, str]] = []
    for cells in tables[header_index.table_index][header_index.row_index + 1 :]:
        row = _parse_entry_row(
            cells,
            header_map,
            race_id=race_id,
            context=context,
            metadata=metadata,
        )
        if row is not None:
            entries.append(row)

    if not entries:
        warnings.append("result table was found, but no entry rows were parsed.")

    field_size = str(len(entries)) if entries else ""
    for row in entries:
        if not row["field_size"]:
            row["field_size"] = field_size

    return ParsedRacePage(
        race_id=race_id,
        rows=entries,
        source_path=Path(source_path) if source_path else None,
        warnings=warnings,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse cached official result HTML files into in-memory Nankan CSV rows."
    )
    parser.add_argument("html_paths", nargs="*")
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    args = parser.parse_args(argv)

    paths = [Path(path) for path in args.html_paths] or sorted(Path(args.cache_html_dir).glob("*.html"))
    parsed_pages = [parse_result_page_file(path) for path in paths]
    row_count = sum(len(page.rows) for page in parsed_pages)
    warning_count = sum(len(page.warnings) for page in parsed_pages)
    print(f"OK: parsed {len(parsed_pages)} HTML files")
    print(f"rows: {row_count}")
    print(f"warnings: {warning_count}")
    for page in parsed_pages:
        for warning in page.warnings:
            print(f"WARNING: {page.race_id}: {warning}")
    return 0 if row_count > 0 or not paths else 1


class _TableIndex:
    def __init__(self, table_index: int, row_index: int) -> None:
        self.table_index = table_index
        self.row_index = row_index


class _TableCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            if self._table_depth == 0:
                self._current_table = []
            self._table_depth += 1
        elif tag == "tr" and self._table_depth == 1:
            self._current_row = []
        elif tag in {"td", "th"} and self._table_depth == 1:
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._current_cell is not None:
            if self._current_row is not None:
                self._current_row.append(_clean_text(" ".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(cell for cell in self._current_row):
                assert self._current_table is not None
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current_cell is not None:
            self._current_cell.append(data)


class _VisibleTextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = _clean_text(data)
            if text:
                self.parts.append(text)


def _read_html(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_tables(html: str) -> list[list[list[str]]]:
    parser = _TableCollector()
    parser.feed(html)
    return parser.tables


def _extract_visible_text(html: str) -> list[str]:
    parser = _VisibleTextCollector()
    parser.feed(html)
    return parser.parts


def _extract_metadata(html: str, tables: list[list[list[str]]]) -> dict[str, str]:
    metadata = {
        "race_name": _data_attribute(html, "race-name"),
        "distance": _data_attribute(html, "distance"),
        "surface": _data_attribute(html, "surface"),
        "weather": _data_attribute(html, "weather"),
        "track_condition": _data_attribute(html, "track-condition"),
        "class_name": _data_attribute(html, "class-name"),
    }

    for table in tables:
        for cells in table:
            for key, value in _cell_pairs(cells):
                _apply_metadata_pair(metadata, key, value)

    visible_text = " ".join(_extract_visible_text(html))
    if not metadata["race_name"]:
        metadata["race_name"] = _first_heading(html)
    if not metadata["distance"]:
        metadata["distance"] = _extract_distance(visible_text)
    if not metadata["surface"]:
        metadata["surface"] = _extract_surface(visible_text)
    return {key: _clean_text(value) for key, value in metadata.items()}


def _find_result_table(tables: list[list[list[str]]]) -> tuple[_TableIndex, list[str]] | None:
    for table_index, table in enumerate(tables):
        for row_index, cells in enumerate(table):
            normalized = [_normalize_label(cell) for cell in cells]
            if any("馬番" in cell for cell in normalized) and any("馬名" in cell for cell in normalized):
                return _TableIndex(table_index, row_index), cells
    return None


def _build_header_map(headers: list[str]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalized = _normalize_label(header)
        _maybe_map(header_map, "finish_position", index, normalized, ("着順",))
        _maybe_map(header_map, "gate_no", index, normalized, ("枠番", "枠"))
        _maybe_map(header_map, "horse_no", index, normalized, ("馬番",))
        _maybe_map(header_map, "horse_name", index, normalized, ("馬名",))
        _maybe_map(header_map, "sex_age", index, normalized, ("性齢", "性年齢"))
        _maybe_map(header_map, "carried_weight", index, normalized, ("負担重量", "斤量", "重量"))
        _maybe_map(header_map, "jockey_name", index, normalized, ("騎手",))
        _maybe_map(header_map, "trainer_name", index, normalized, ("調教師",))
        _maybe_map(header_map, "body_weight", index, normalized, ("馬体重",))
        _maybe_map(header_map, "body_weight_diff", index, normalized, ("増減",))
        _maybe_map(header_map, "finish_time", index, normalized, ("タイム", "走破タイム"))
        _maybe_map(header_map, "margin", index, normalized, ("着差",))
        _maybe_map(header_map, "last_3f", index, normalized, ("上がり", "上り", "3F"))
        _maybe_map(header_map, "popularity", index, normalized, ("人気",))
        _maybe_map(header_map, "win_odds_final", index, normalized, ("単勝オッズ", "単勝"))
    return header_map


def _parse_entry_row(
    cells: list[str],
    header_map: dict[str, int],
    *,
    race_id: str,
    context: dict[str, str],
    metadata: dict[str, str],
) -> dict[str, str] | None:
    horse_no = _cell(cells, header_map, "horse_no")
    horse_name = _cell(cells, header_map, "horse_name")
    if not _clean_int(horse_no) and not horse_name:
        return None

    row = {column: "" for column in REQUIRED_COLUMNS}
    row.update(
        {
            "race_id": race_id,
            "date": context.get("date", ""),
            "track": context.get("track", ""),
            "race_no": context.get("race_no", ""),
            "race_name": metadata.get("race_name", ""),
            "distance": _clean_int(metadata.get("distance", "")),
            "surface": metadata.get("surface", ""),
            "weather": metadata.get("weather", ""),
            "track_condition": metadata.get("track_condition", ""),
            "class_name": metadata.get("class_name", ""),
            "horse_no": _clean_int(horse_no),
            "gate_no": _clean_int(_cell(cells, header_map, "gate_no")),
            "horse_name": horse_name,
            "carried_weight": _clean_decimal(_cell(cells, header_map, "carried_weight")),
            "jockey_name": _cell(cells, header_map, "jockey_name"),
            "trainer_name": _cell(cells, header_map, "trainer_name"),
            "finish_position": _normalize_finish_position(_cell(cells, header_map, "finish_position")),
            "finish_time": _cell(cells, header_map, "finish_time"),
            "margin": _cell(cells, header_map, "margin"),
            "passing_order": "",
            "last_3f": _clean_decimal(_cell(cells, header_map, "last_3f")),
            "popularity": _clean_int(_cell(cells, header_map, "popularity")),
            "win_odds_final": _clean_decimal(_cell(cells, header_map, "win_odds_final")),
        }
    )

    sex, age = _split_sex_age(_cell(cells, header_map, "sex_age"))
    row["sex"] = sex
    row["age"] = age
    body_weight, body_weight_diff = _split_body_weight(_cell(cells, header_map, "body_weight"))
    row["body_weight"] = body_weight
    row["body_weight_diff"] = _clean_int(_cell(cells, header_map, "body_weight_diff")) or _clean_int(body_weight_diff)
    return row


def _context_from_race_id(race_id: str) -> dict[str, str]:
    match = RACE_ID_PATTERN.match(race_id)
    if not match:
        return {"date": "", "track": "", "race_no": ""}
    date_text = match.group("date")
    return {
        "date": f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]}",
        "track": match.group("track"),
        "race_no": match.group("race_no"),
    }


def _cell(cells: list[str], header_map: dict[str, int], column: str) -> str:
    index = header_map.get(column)
    if index is None or index >= len(cells):
        return ""
    return _clean_text(cells[index])


def _cell_pairs(cells: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index in range(0, len(cells) - 1, 2):
        pairs.append((cells[index], cells[index + 1]))
    if len(cells) == 2:
        pairs.append((cells[0], cells[1]))
    return pairs


def _apply_metadata_pair(metadata: dict[str, str], key: str, value: str) -> None:
    normalized_key = _normalize_label(key)
    clean_value = _clean_text(value)
    if not clean_value:
        return
    if not metadata["race_name"] and any(label in normalized_key for label in ("競走名", "レース名", "レース")):
        metadata["race_name"] = clean_value
    elif not metadata["distance"] and any(label in normalized_key for label in ("距離", "コース")):
        metadata["distance"] = _extract_distance(clean_value)
        metadata["surface"] = metadata["surface"] or _extract_surface(clean_value)
    elif not metadata["weather"] and "天候" in normalized_key:
        metadata["weather"] = clean_value
    elif not metadata["track_condition"] and any(label in normalized_key for label in ("馬場", "馬場状態")):
        metadata["track_condition"] = clean_value
    elif not metadata["class_name"] and any(label in normalized_key for label in ("条件", "クラス", "格")):
        metadata["class_name"] = clean_value


def _maybe_map(
    header_map: dict[str, int],
    key: str,
    index: int,
    normalized_header: str,
    labels: tuple[str, ...],
) -> None:
    if key in header_map:
        return
    if any(_normalize_label(label) in normalized_header for label in labels):
        header_map[key] = index


def _data_attribute(html: str, attribute_name: str) -> str:
    pattern = re.compile(rf"\bdata-{re.escape(attribute_name)}=[\"']([^\"']*)[\"']", re.IGNORECASE)
    match = pattern.search(html)
    return _clean_text(match.group(1)) if match else ""


def _first_heading(html: str) -> str:
    match = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return _clean_text(text)


def _extract_distance(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    match = re.search(r"(\d{3,4})\s*m", normalized, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_surface(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    if "ダート" in normalized or re.search(r"(^|\s)ダ\s*\d{3,4}", normalized):
        return "dirt"
    if "芝" in normalized:
        return "turf"
    return ""


def _split_sex_age(value: str) -> tuple[str, str]:
    text = unicodedata.normalize("NFKC", value).strip()
    match = re.match(r"([^\d]+)(\d+)", text)
    if not match:
        return text, ""
    return match.group(1).strip(), match.group(2)


def _split_body_weight(value: str) -> tuple[str, str]:
    text = unicodedata.normalize("NFKC", value).replace(",", "").strip()
    if not text or any(token in text for token in ("計不", "不明", "--")):
        return "", ""
    match = re.match(r"(?P<body>-?\d+)\s*(?:\((?P<diff>[+-]?\d+)\))?", text)
    if not match:
        return "", ""
    return match.group("body") or "", match.group("diff") or ""


def _normalize_finish_position(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    if not text:
        return ""
    if any(token in text for token in ("取消", "出走取消")):
        return "SCR"
    if any(token in text for token in ("除外", "競走除外")):
        return "EXC"
    if any(token in text for token in ("中止", "競走中止")):
        return "DNF"
    match = re.search(r"\d+", text)
    return match.group(0) if match else ""


def _clean_int(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).replace(",", "").strip()
    if not text or text in {"-", "--"}:
        return ""
    match = re.search(r"-?\d+", text)
    return match.group(0) if match else ""


def _clean_decimal(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.replace(",", "").replace("倍", "").replace("kg", "").replace("Kg", "").strip()
    if not text or text in {"-", "--"}:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def _normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"[\s　:：()（）/]+", "", text)


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


__all__ = [
    "ParsedRacePage",
    "parse_result_page_file",
    "parse_result_page_html",
]


if __name__ == "__main__":
    raise SystemExit(main())
