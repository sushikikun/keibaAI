from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

from .schema import DEFAULT_RAW_CSV_PATH, TRACKS

DEFAULT_REPORTS_DIR = Path("data/reports")
DEFAULT_CACHE_HTML_DIR = Path("data/cache/html")
OFFICIAL_RESULT_URL = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable"
TRACK_BABA_CODES = {
    "urawa": "18",
    "funabashi": "19",
    "oi": "20",
    "kawasaki": "21",
}
FETCH_PLAN_COLUMNS = (
    "race_id",
    "date",
    "track",
    "race_no",
    "official_url",
    "cache_html_path",
)


@dataclass(frozen=True)
class FetchPlanRow:
    race_id: str
    race_date: str
    track: str
    race_no: int
    official_url: str
    cache_html_path: str

    def as_csv_row(self) -> dict[str, str]:
        return {
            "race_id": self.race_id,
            "date": self.race_date,
            "track": self.track,
            "race_no": str(self.race_no),
            "official_url": self.official_url,
            "cache_html_path": self.cache_html_path,
        }


def build_fetch_plan(
    *,
    track: str,
    date_from: str,
    date_to: str,
    race_no_from: int,
    race_no_to: int,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    cache_html_dir: str | Path = DEFAULT_CACHE_HTML_DIR,
    exclude_existing: bool = True,
    date_order: str = "desc",
) -> list[FetchPlanRow]:
    normalized_track = track.strip().lower()
    if normalized_track not in TRACKS:
        raise ValueError(f"track must be one of: {', '.join(sorted(TRACKS))}")
    if normalized_track not in TRACK_BABA_CODES:
        raise ValueError(f"official baba code is not configured for track={normalized_track}")
    if race_no_from < 1 or race_no_to < race_no_from:
        raise ValueError("race_no_from/race_no_to must be a positive inclusive range.")

    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if end < start:
        raise ValueError("date_to must be on or after date_from.")

    existing_race_ids = load_existing_race_ids(raw_csv_path) if exclude_existing else set()
    cache_dir = Path(cache_html_dir)
    rows: list[FetchPlanRow] = []
    for race_date in _date_range(start, end, order=date_order):
        race_date_text = race_date.isoformat()
        for race_no in range(race_no_from, race_no_to + 1):
            race_id = make_race_id(race_date_text, normalized_track, race_no)
            if race_id in existing_race_ids:
                continue
            cache_path = cache_dir / f"{race_id}.html"
            rows.append(
                FetchPlanRow(
                    race_id=race_id,
                    race_date=race_date_text,
                    track=normalized_track,
                    race_no=race_no,
                    official_url=build_result_page_url(race_date_text, normalized_track, race_no),
                    cache_html_path=_path_string(cache_path),
                )
            )
    return rows


def write_fetch_plan(
    rows: list[FetchPlanRow],
    output_path: str | Path | None = None,
    *,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    now: datetime | None = None,
) -> Path:
    path = Path(output_path) if output_path else _default_fetch_plan_path(Path(reports_dir), now)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FETCH_PLAN_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.as_csv_row() for row in rows)
    return path


def load_existing_race_ids(raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH) -> set[str]:
    path = Path(raw_csv_path)
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            _clean(row.get("race_id"))
            for row in reader
            if _clean(row.get("race_id"))
        }


def make_race_id(race_date: str, track: str, race_no: int) -> str:
    return f"{race_date.replace('-', '')}_{track}_{race_no}"


def build_result_page_url(race_date: str, track: str, race_no: int) -> str:
    query = urlencode(
        {
            "k_raceDate": race_date.replace("-", "/"),
            "k_raceNo": str(race_no),
            "k_babaCode": TRACK_BABA_CODES[track],
        }
    )
    return f"{OFFICIAL_RESULT_URL}?{query}"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a low-frequency official result-page fetch plan."
    )
    parser.add_argument("--track", required=True, choices=sorted(TRACKS))
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--race-no-from", required=True, type=int)
    parser.add_argument("--race-no-to", required=True, type=int)
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--cache-html-dir", default=str(DEFAULT_CACHE_HTML_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Do not exclude race_id values already present in the current raw CSV.",
    )
    parser.add_argument("--date-order", choices=("asc", "desc"), default="desc")
    args = parser.parse_args(argv)

    rows = build_fetch_plan(
        track=args.track,
        date_from=args.date_from,
        date_to=args.date_to,
        race_no_from=args.race_no_from,
        race_no_to=args.race_no_to,
        raw_csv_path=args.raw_csv_path,
        cache_html_dir=args.cache_html_dir,
        exclude_existing=not args.include_existing,
        date_order=args.date_order,
    )
    output_path = write_fetch_plan(rows, args.output_path, reports_dir=args.reports_dir)

    print(f"OK: wrote fetch plan to {output_path}")
    print(f"target_races: {len(rows)}")
    if rows:
        print(f"date_min: {min(row.race_date for row in rows)}")
        print(f"date_max: {max(row.race_date for row in rows)}")
    return 0


def _date_range(start: date, end: date, *, order: str) -> list[date]:
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    if order == "desc":
        return list(reversed(dates))
    if order == "asc":
        return dates
    raise ValueError("date_order must be asc or desc.")


def _default_fetch_plan_path(reports_dir: Path, now: datetime | None) -> Path:
    value = now or datetime.now()
    return reports_dir / f"fetch_plan_{value.strftime('%Y%m%d_%H%M%S')}.csv"


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "DEFAULT_CACHE_HTML_DIR",
    "FETCH_PLAN_COLUMNS",
    "FetchPlanRow",
    "TRACK_BABA_CODES",
    "build_fetch_plan",
    "build_result_page_url",
    "load_existing_race_ids",
    "make_race_id",
    "write_fetch_plan",
]


if __name__ == "__main__":
    raise SystemExit(main())

