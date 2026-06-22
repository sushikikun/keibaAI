# Bulk Fetch Job Workflow

This workflow is for processing multiple cache-bundle jobs without manually
running every command one by one. It does not create prediction models, add
features, or fetch anything on the local PC.

## One Command Runner

Use `ops/run_bulk_fetch_cycle.ps1` for the current standard operation. It wraps
the full cycle:

1. preflight checks
2. optional job CSV/JSON commit and push
3. GitHub Actions dispatch
4. Actions completion wait
5. artifact download
6. cache bundle import
7. append CSV build
8. append validation
9. merge dry-run
10. parse-warning classification
11. optional safe apply
12. final checks

Dry-run through artifact processing, without applying to raw:

```powershell
.\ops\run_bulk_fetch_cycle.ps1 `
  -Repo sushikikun/keibaAI `
  -JobPrefix job_20260622_161538 `
  -ExpectedStartRawSha256 755467C05E57FC9494680846AD0E93D33899B8F7975E14B00850BB67E4349855 `
  -DryRunOnly `
  -Backend python `
  -DelaySeconds 1.0
```

Run the same cycle and apply only when all safety checks pass:

```powershell
.\ops\run_bulk_fetch_cycle.ps1 `
  -Repo sushikikun/keibaAI `
  -JobPrefix job_20260622_161538 `
  -ExpectedStartRawSha256 755467C05E57FC9494680846AD0E93D33899B8F7975E14B00850BB67E4349855 `
  -ApplyIfSafe `
  -Backend python `
  -DelaySeconds 1.0
```

Plan-only mode prints and validates the local plan without dispatching Actions,
downloading artifacts, or applying raw changes:

```powershell
.\ops\run_bulk_fetch_cycle.ps1 `
  -Repo sushikikun/keibaAI `
  -JobPrefix job_20260622_161538 `
  -ExpectedStartRawSha256 755467C05E57FC9494680846AD0E93D33899B8F7975E14B00850BB67E4349855 `
  -DryRunOnly `
  -PlanOnly
```

The runner intentionally never uses `git add .`. If target job CSV/JSON files
have local changes, it stages only:

```text
data/jobs/fetch_job_<job_id>.csv
data/jobs/fetch_job_<job_id>.json
```

It stops if any forbidden path is staged, including raw CSV, DuckDB, training
CSV, cache HTML, bundle zip, backups, reports, virtualenv, pycache, or
pytest cache.

Safe apply runs only when all of these are true:

- `-ApplyIfSafe` is specified.
- `-DryRunOnly` is not specified.
- starting raw SHA256 still matches `-ExpectedStartRawSha256`.
- all target jobs pass duplicate and race_id/date/track/race_no checks.
- every Actions run finishes with `success`.
- every target artifact downloads from the matching run/job only.
- every job passes append validation and merge dry-run.
- parse warning classification has `parser_gap = 0`.
- parse warning classification has `unknown = 0`.

The runner stops automatically when:

- working directory is not the project root.
- GitHub CLI auth fails.
- raw SHA256 does not match the expected value.
- job CSV/JSON files are missing.
- job race_id values overlap existing raw race_id values.
- job files contain internal or cross-job duplicate race_id values.
- race_id, date, track, or race_no do not agree.
- unrelated or forbidden files are staged.
- GitHub Actions dispatch, wait, or artifact download fails.
- validation or merge dry-run fails.
- parse classification finds `parser_gap` or `unknown`.
- apply fails at any step.

If apply fails after raw append, do not run the whole cycle again. Use the
printed `append_state` resume command:

```powershell
python -m nankan_ai.merge_append_csv --resume data/reports/append_state_<batch_id>.json
```

## Scope

Current target jobs:

- `job_20260618_191957_p02`
- `job_20260618_191957_p03`
- `job_20260618_191957_p04`
- `job_20260618_191957_p05`

p01 has already been applied. p02-p05 should be processed in order.

## 1. Dispatch GitHub Actions

Print the commands first:

```powershell
.\ops\dispatch_fetch_jobs.ps1
```

Actually start the workflow runs:

```powershell
.\ops\dispatch_fetch_jobs.ps1 -Execute
```

Optional settings:

```powershell
.\ops\dispatch_fetch_jobs.ps1 -Execute -Backend python -DelaySeconds 1.0 -Repo owner/repo
```

Each job is sent to `.github/workflows/fetch_cache_bundle.yml` with these
inputs:

- `job_id`
- `backend`
- `delay_seconds`
- `job_csv_path`
- `job_json_path`
- `worker_package_path`

## 2. Download Artifacts

After GitHub Actions finishes, print the download plan:

```powershell
.\ops\download_fetch_artifacts.ps1
```

Download the latest matching artifacts:

```powershell
.\ops\download_fetch_artifacts.ps1 -Execute -Repo owner/repo
```

The script looks for artifacts named:

- `cache-bundle-job_20260618_191957_p02`
- `cache-bundle-job_20260618_191957_p03`
- `cache-bundle-job_20260618_191957_p04`
- `cache-bundle-job_20260618_191957_p05`

Downloaded bundles are placed under:

```text
data/cache/bundles/
```

## 3. Local Validation Only

Run import, append CSV generation, validate, and merge dry-run for all jobs:

```powershell
.\.venv\Scripts\python.exe .\ops\process_cache_bundle_jobs.py `
  --expected-start-raw-sha256 90149EAFB429FC406E8331A827CFF370E5840444A30205CB1EA289F3F1CC913E
```

Default mode does not apply to raw. It imports cache bundle HTML and writes
`data/incoming/nankan_past_races_append.csv` for each job in turn.

## 4. Sequential Apply

After reviewing dry-run output, apply p02-p05 in order:

```powershell
.\.venv\Scripts\python.exe .\ops\process_cache_bundle_jobs.py `
  --expected-start-raw-sha256 90149EAFB429FC406E8331A827CFF370E5840444A30205CB1EA289F3F1CC913E `
  --apply
```

Apply is sequential. For each job the existing merge pipeline creates:

- backup
- append report
- append state
- batch log row
- DuckDB refresh
- training CSV refresh
- dataset manifest

If one job fails, the script stops before the next job.

## Failure And Resume

If apply fails after raw append, do not re-run the same apply blindly. Use the
latest state file:

```powershell
python -m nankan_ai.merge_append_csv --resume data/reports/append_state_<batch_id>.json
```

The local bulk script prints the latest `append_state` path and the resume
command when it detects a failure.

## Rules

- Do not edit `data/raw/nankan_past_races.csv` by hand.
- Do not run merge apply outside the controlled pipeline.
- Do not add `data/raw/nankan_past_races.csv`, DuckDB, training CSV, cache HTML,
  bundle zip, backups, or reports to Git.
- Do not add prediction models, feature engineering, or betting logic in this
  workflow.
