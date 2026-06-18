# Bulk Fetch Job Workflow

This workflow is for processing multiple cache-bundle jobs without manually
running every command one by one. It does not create prediction models, add
features, or fetch anything on the local PC.

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
