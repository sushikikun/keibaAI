from __future__ import annotations

import csv
from pathlib import Path

from nankan_ai.build_append_from_cache import build_append_from_cache
from nankan_ai.parse_result_pages import parse_result_page_html
from nankan_ai.schema import REQUIRED_COLUMNS


FIXTURE_HTML = """
<!doctype html>
<html>
  <body>
    <h1 data-race-name="Fixture Kawasaki Race">Fixture Kawasaki Race</h1>
    <table>
      <tr><th>距離</th><td>ダート 1400m</td><th>天候</th><td>晴</td></tr>
      <tr><th>馬場状態</th><td>稍重</td><th>条件</th><td>C3</td></tr>
    </table>
    <table>
      <tr>
        <th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th><th>性齢</th>
        <th>負担重量</th><th>騎手</th><th>調教師</th><th>馬体重</th>
        <th>タイム</th><th>着差</th><th>上がり3F</th><th>人気</th><th>単勝オッズ</th>
      </tr>
      <tr>
        <td>1</td><td>1</td><td>1</td><td>テストホースA</td><td>牡4</td>
        <td>56.0</td><td>テスト騎手A</td><td>テスト調教師A</td><td>500(+2)</td>
        <td>1:32.0</td><td></td><td>39.0</td><td>1</td><td>2.4</td>
      </tr>
      <tr>
        <td>2</td><td>2</td><td>2</td><td>テストホースB</td><td>牝5</td>
        <td>54.0</td><td>テスト騎手B</td><td>テスト調教師B</td><td>488(-4)</td>
        <td>1:32.5</td><td>3</td><td>39.2</td><td>2</td><td>3.1</td>
      </tr>
      <tr>
        <td>競走除外</td><td>3</td><td>3</td><td>テストホースC</td><td>セ6</td>
        <td>56.0</td><td>テスト騎手C</td><td>テスト調教師C</td><td>計不</td>
        <td></td><td></td><td></td><td></td><td></td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parse_result_page_html_maps_existing_schema() -> None:
    parsed = parse_result_page_html(FIXTURE_HTML, race_id="20260618_kawasaki_1")

    assert parsed.warnings == []
    assert len(parsed.rows) == 3
    first = parsed.rows[0]
    excluded = parsed.rows[2]
    assert list(first.keys()) == list(REQUIRED_COLUMNS)
    assert first["race_id"] == "20260618_kawasaki_1"
    assert first["date"] == "2026-06-18"
    assert first["track"] == "kawasaki"
    assert first["race_no"] == "1"
    assert first["race_name"] == "Fixture Kawasaki Race"
    assert first["distance"] == "1400"
    assert first["surface"] == "dirt"
    assert first["weather"] == "晴"
    assert first["track_condition"] == "稍重"
    assert first["class_name"] == "C3"
    assert first["field_size"] == "3"
    assert first["sex"] == "牡"
    assert first["age"] == "4"
    assert first["body_weight"] == "500"
    assert first["body_weight_diff"] == "2"
    assert first["win_odds_final"] == "2.4"
    assert first["passing_order"] == ""
    assert excluded["finish_position"] == "EXC"
    assert excluded["body_weight"] == ""
    assert excluded["win_odds_final"] == ""


def test_build_append_from_cache_writes_header_and_can_validate(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    cache_dir = tmp_path / "cache"
    output_path = tmp_path / "incoming.csv"
    cache_dir.mkdir(parents=True)
    _write_raw_header(raw_path)
    (cache_dir / "20260618_kawasaki_1.html").write_text(FIXTURE_HTML, encoding="utf-8")

    result = build_append_from_cache(
        cache_html_dir=cache_dir,
        output_path=output_path,
        raw_csv_path=raw_path,
        run_validation=True,
    )

    assert result.row_count == 3
    assert result.race_count == 1
    assert result.validation_status == "passed"
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        assert next(reader) == list(REQUIRED_COLUMNS)


def _write_raw_header(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(REQUIRED_COLUMNS)
