# Browser Fetch Backend Investigation

This document records the browser-based fetch test for the official Nankan
result page cache workflow.

## Purpose

Python urllib, PowerShell, and curl may fail to open HTTPS/TCP 443 from the
local CLI environment while the Codex in-app browser can open `keiba.go.jp`.
The goal is to check whether one official result page can still be cached as
HTML without changing `data/raw/nankan_past_races.csv`.

## Test Target

- race_id: `20250908_kawasaki_1`
- track: `kawasaki`
- date: `2025-09-08`
- race_no: `1`
- official_url: `https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_raceDate=2025%2F09%2F08&k_raceNo=1&k_babaCode=21`
- cache_path: `data/cache/html/20250908_kawasaki_1.html`

## Result

- The Codex in-app browser opened the official result page.
- Browser page title: `レース成績表`
- Browser-read HTML length: `79065` characters
- Direct browser write to the workspace failed with `EPERM`.
- Writing the browser-read HTML to the local temp directory succeeded.
- Copying that temp HTML into `data/cache/html/20250908_kawasaki_1.html` succeeded.
- Saved cache file size: `82173` bytes
- Existing raw CSV was not changed.

## Parser and Append CSV Check

The cached HTML was parsed with the existing parser.

```powershell
.\.venv\Scripts\python.exe -m nankan_ai.parse_result_pages data\cache\html\20250908_kawasaki_1.html
```

Result:

- parsed HTML files: `1`
- rows: `10`
- warnings: `0`

The append CSV was then generated from cache and validated.

```powershell
.\.venv\Scripts\python.exe -m nankan_ai.build_append_from_cache --fetch-plan-csv data\jobs\fetch_job_job_20260618_120030.csv --validate
```

Result:

- output: `data/incoming/nankan_past_races_append.csv`
- rows: `10`
- races: `1`
- validation: `passed`

## `--backend browser`

`fetch_result_pages.py` now accepts `--backend browser`.

Important limitation:

- The Python CLI cannot directly control the Codex in-app browser.
- If a target race is already cached, `--backend browser` respects that cache
  and does not overwrite it.
- If a target race is not cached, `--backend browser` returns a clear failure
  explaining that the Codex browser handoff workflow is required.

This prevents the browser backend from pretending to perform a fetch that the
Python process cannot actually execute.

## Recommended Workflow for This PC

1. Create or choose a small fetch plan.
2. Use the Codex in-app browser to open only the required official result page.
3. Save the page HTML into `data/cache/html/<race_id>.html`.
4. Run `parse_result_pages`.
5. Run `build_append_from_cache --validate`.
6. Run `validate_append_csv` and `merge_append_csv` dry-run if needed.
7. Do not run `merge_append_csv --apply` until the append CSV has been reviewed.

## Rules

- Do not edit `data/raw/nankan_past_races.csv` during browser fetch tests.
- Do not overwrite existing cache files.
- Do not expand the target range without an explicit instruction.
- Do not infer missing values from the page.
- Do not build prediction models or new features from this step.
