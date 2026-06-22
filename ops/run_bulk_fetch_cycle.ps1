param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $true)]
    [string]$JobPrefix,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedStartRawSha256,

    [switch]$ApplyIfSafe,
    [switch]$DryRunOnly,
    [switch]$PlanOnly,

    [double]$DelaySeconds = 1.0,

    [ValidateSet("python", "powershell", "curl")]
    [string]$Backend = "python"
)

$ErrorActionPreference = "Stop"

$ExpectedRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Workflow = "fetch_cache_bundle.yml"
$RawCsv = "data/raw/nankan_past_races.csv"
$DuckDb = "data/nankan.duckdb"
$TrainingRowsCsv = "data/processed/training_rows.csv"
$IncomingCsv = "data/incoming/nankan_past_races_append.csv"
$BundlesDir = "data/cache/bundles"
$ReportsDir = "data/reports"

function Stop-Cycle {
    param([string]$Message)
    throw $Message
}

function Get-PythonExe {
    $venvPython = ".\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }
    return "python"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Exe,
        [string[]]$Args = @(),
        [switch]$NoRun
    )

    $display = @($Exe) + $Args
    Write-Output ("> " + (($display | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }) -join " "))

    if ($NoRun) {
        return ""
    }

    $output = & $Exe @Args
    $exitCode = $LASTEXITCODE
    if ($output) {
        $output | Write-Output
    }
    if ($exitCode -ne 0) {
        Stop-Cycle "Command failed with exit code ${exitCode}: $Exe $($Args -join ' ')"
    }
    return $output
}

function Assert-ProjectRoot {
    $actual = (Resolve-Path -LiteralPath ".").Path
    if ($actual -ne $ExpectedRoot) {
        Stop-Cycle "Wrong working directory. Expected '$ExpectedRoot', actual '$actual'."
    }
    Write-Output "OK: project root is $actual"
}

function Assert-RawSha256 {
    param([string]$Expected)
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $RawCsv).Hash.ToUpperInvariant()
    if ($actual -ne $Expected.ToUpperInvariant()) {
        Stop-Cycle "Raw SHA256 mismatch. expected=$($Expected.ToUpperInvariant()) actual=$actual"
    }
    Write-Output "OK: raw SHA256 matches $actual"
}

function Get-TargetJobs {
    $csvFiles = Get-ChildItem -LiteralPath "data/jobs" -Filter "fetch_job_$JobPrefix*.csv" |
        Sort-Object Name
    if (-not $csvFiles) {
        Stop-Cycle "No fetch job CSV files found for JobPrefix=$JobPrefix"
    }

    $jobs = @()
    foreach ($csv in $csvFiles) {
        $jobId = $csv.BaseName -replace "^fetch_job_", ""
        $jsonPath = Join-Path "data/jobs" "fetch_job_$jobId.json"
        if (-not (Test-Path -LiteralPath $jsonPath)) {
            Stop-Cycle "Fetch job JSON not found: $jsonPath"
        }
        $jobs += [pscustomobject]@{
            JobId = $jobId
            CsvPath = ("data/jobs/fetch_job_$jobId.csv")
            JsonPath = $jsonPath.Replace("\", "/")
        }
    }
    return $jobs
}

function Test-RaceIdConsistency {
    param([object[]]$Jobs)

    $rawIds = [System.Collections.Generic.HashSet[string]]::new()
    Import-Csv -LiteralPath $RawCsv | ForEach-Object {
        if ($_.race_id) {
            [void]$rawIds.Add([string]$_.race_id)
        }
    }

    $allIds = @()
    $allIssues = @()
    $rawOverlap = @()
    $jobSummaries = @()

    foreach ($job in $Jobs) {
        $rows = @(Import-Csv -LiteralPath $job.CsvPath)
        $ids = @($rows | ForEach-Object { [string]$_.race_id })
        $idCounts = $ids | Group-Object
        $withinDupes = @($idCounts | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })

        foreach ($row in $rows) {
            $raceId = [string]$row.race_id
            $date = [string]$row.date
            $track = [string]$row.track
            $raceNo = [string]$row.race_no
            if ($rawIds.Contains($raceId)) {
                $rawOverlap += $raceId
            }
            if ($raceId -notmatch "^(\d{8})_(kawasaki)_(\d{1,2})$") {
                $allIssues += "race_id format mismatch: $($job.JobId) $raceId"
                continue
            }
            $expectedDate = "$($Matches[1].Substring(0,4))-$($Matches[1].Substring(4,2))-$($Matches[1].Substring(6,2))"
            $expectedTrack = $Matches[2]
            $expectedRaceNo = $Matches[3]
            if ($date -ne $expectedDate) {
                $allIssues += "date mismatch: $($job.JobId) $raceId date=$date expected=$expectedDate"
            }
            if ($track -ne $expectedTrack -or $track -ne "kawasaki") {
                $allIssues += "track mismatch: $($job.JobId) $raceId track=$track"
            }
            if ($raceNo -ne $expectedRaceNo) {
                $allIssues += "race_no mismatch: $($job.JobId) $raceId race_no=$raceNo expected=$expectedRaceNo"
            }
            $allIds += [pscustomobject]@{
                JobId = $job.JobId
                RaceId = $raceId
            }
        }

        $dates = @($rows | ForEach-Object { $_.date } | Where-Object { $_ } | Sort-Object)
        $jobSummaries += [pscustomobject]@{
            job_id = $job.JobId
            rows = $rows.Count
            date_min = if ($dates) { $dates[0] } else { "" }
            date_max = if ($dates) { $dates[-1] } else { "" }
            within_job_duplicate_count = $withinDupes.Count
            within_job_duplicate_ids = $withinDupes
        }
    }

    $betweenDupes = @(
        $allIds |
            Group-Object RaceId |
            Where-Object { $_.Count -gt 1 } |
            ForEach-Object {
                [pscustomobject]@{
                    race_id = $_.Name
                    jobs = @($_.Group | ForEach-Object { $_.JobId } | Sort-Object -Unique)
                }
            }
    )

    $withinDupeTotal = ($jobSummaries | Measure-Object -Property within_job_duplicate_count -Sum).Sum
    if ($null -eq $withinDupeTotal) { $withinDupeTotal = 0 }

    $result = [pscustomobject]@{
        raw_overlap_count = @($rawOverlap | Sort-Object -Unique).Count
        raw_overlap_ids = @($rawOverlap | Sort-Object -Unique)
        between_job_duplicate_count = $betweenDupes.Count
        between_job_duplicate_ids = $betweenDupes
        within_job_duplicate_count_total = [int]$withinDupeTotal
        consistency_issue_count = $allIssues.Count
        consistency_issues = $allIssues
        job_summaries = $jobSummaries
    }

    Write-Output ($result | ConvertTo-Json -Depth 8)
    if (
        $result.raw_overlap_count -gt 0 -or
        $result.between_job_duplicate_count -gt 0 -or
        $result.within_job_duplicate_count_total -gt 0 -or
        $result.consistency_issue_count -gt 0
    ) {
        Stop-Cycle "Fetch job duplicate/consistency check failed. Stop before Actions dispatch."
    }
    Write-Output "OK: fetch job duplicate/consistency check passed."
    return $result
}

function Assert-NoForbiddenStaged {
    $staged = @(git diff --cached --name-only)
    $forbiddenPatterns = @(
        "^data/raw/",
        "^data/nankan\.duckdb$",
        "^data/processed/",
        "^data/cache/html/.*\.html$",
        "^data/cache/bundles/.*\.zip$",
        "^data/backups/",
        "^data/reports/",
        "^\.venv/",
        "__pycache__",
        "^\.pytest_cache/"
    )
    foreach ($path in $staged) {
        foreach ($pattern in $forbiddenPatterns) {
            if ($path -match $pattern) {
                Stop-Cycle "Forbidden staged path detected: $path"
            }
        }
    }
    return $staged
}

function Publish-JobFilesIfNeeded {
    param([object[]]$Jobs)

    if ($PlanOnly) {
        Write-Output "PLAN: skip git commit/push helper."
        return
    }

    $initialStaged = @(git diff --cached --name-only)
    if ($initialStaged.Count -gt 0) {
        Stop-Cycle "Staged files already exist. Clear staged files before running this cycle."
    }

    $targetPaths = @()
    foreach ($job in $Jobs) {
        $targetPaths += $job.CsvPath
        $targetPaths += $job.JsonPath
    }

    $statusArgs = @("status", "--porcelain", "--") + $targetPaths
    $jobStatus = @(& git @statusArgs)
    if (-not $jobStatus -or $jobStatus.Count -eq 0) {
        Write-Output "OK: target job files have no local changes; commit/push skipped."
        return
    }

    Write-Output "Target job files have local changes:"
    $jobStatus | Write-Output

    $addArgs = @("add", "--") + $targetPaths
    Invoke-CheckedCommand -Exe "git" -Args $addArgs | Out-Null

    $staged = @(Assert-NoForbiddenStaged)
    $allowed = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($path in $targetPaths) {
        [void]$allowed.Add($path.Replace("\", "/"))
    }
    foreach ($path in $staged) {
        if (-not $allowed.Contains($path.Replace("\", "/"))) {
            Stop-Cycle "Unexpected staged path. Only target job CSV/JSON may be staged: $path"
        }
    }

    if ($staged.Count -eq 0) {
        Write-Output "No target job files were staged."
        return
    }

    Invoke-CheckedCommand -Exe "git" -Args @("commit", "-m", "add bulk fetch jobs $JobPrefix") | Out-Null
    Invoke-CheckedCommand -Exe "git" -Args @("push") | Out-Null
    $remainingStaged = @(git diff --cached --name-only)
    if ($remainingStaged.Count -gt 0) {
        Stop-Cycle "Staged files remain after commit/push."
    }
    Write-Output "OK: target job files committed and pushed."
}

function Get-RecentWorkflowRunIds {
    param([string]$RepoName)
    $json = gh run list --repo $RepoName --workflow $Workflow --limit 50 --json databaseId
    if ($LASTEXITCODE -ne 0) {
        Stop-Cycle "Could not list GitHub Actions runs."
    }
    return @($json | ConvertFrom-Json | ForEach-Object { [int64]$_.databaseId })
}

function Dispatch-Actions {
    param([object[]]$Jobs)

    if ($PlanOnly) {
        foreach ($job in $Jobs) {
            Write-Host "PLAN: gh workflow run $Workflow -f job_id=$($job.JobId) -f backend=$Backend -f delay_seconds=$DelaySeconds -f job_csv_path=$($job.CsvPath) -f job_json_path=$($job.JsonPath) --repo $Repo"
        }
        return @()
    }

    $runs = @()
    foreach ($job in $Jobs) {
        $before = Get-RecentWorkflowRunIds -RepoName $Repo
        Invoke-CheckedCommand -Exe "gh" -Args @(
            "workflow", "run", $Workflow,
            "--repo", $Repo,
            "-f", "job_id=$($job.JobId)",
            "-f", "backend=$Backend",
            "-f", "delay_seconds=$DelaySeconds",
            "-f", "job_csv_path=$($job.CsvPath)",
            "-f", "job_json_path=$($job.JsonPath)",
            "-f", "worker_package_path="
        ) | Out-Null

        $runId = $null
        for ($attempt = 1; $attempt -le 30; $attempt++) {
            Start-Sleep -Seconds 2
            $after = Get-RecentWorkflowRunIds -RepoName $Repo
            $newIds = @($after | Where-Object { $before -notcontains $_ } | Sort-Object -Descending)
            if ($newIds.Count -gt 0) {
                $runId = $newIds[0]
                break
            }
        }
        if (-not $runId) {
            Stop-Cycle "Could not identify dispatched run_id for $($job.JobId)."
        }
        $runs += [pscustomobject]@{
            job_id = $job.JobId
            run_id = [int64]$runId
            artifact_name = "cache-bundle-$($job.JobId)"
        }
        Write-Host "OK: dispatched $($job.JobId) run_id=$runId"
    }
    return $runs
}

function Save-RunIds {
    param([object[]]$Runs, [string]$StartedAt)
    if ($PlanOnly) {
        return ""
    }
    New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null
    $path = Join-Path $ReportsDir "bulk_fetch_runs_$($JobPrefix)_$StartedAt.json"
    @{
        created_at = (Get-Date).ToString("s")
        repo = $Repo
        job_prefix = $JobPrefix
        workflow = $Workflow
        backend = $Backend
        delay_seconds = $DelaySeconds
        runs = $Runs
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
    Write-Output "OK: run_id report saved to $path"
    return $path
}

function Wait-Actions {
    param([object[]]$Runs)
    if ($PlanOnly) {
        Write-Output "PLAN: skip GitHub Actions wait."
        return
    }
    foreach ($run in $Runs) {
        Write-Output "Waiting for $($run.job_id) run_id=$($run.run_id)"
        & gh run watch $run.run_id --repo $Repo --exit-status
        if ($LASTEXITCODE -ne 0) {
            Write-Output "Run failed. Inspect failed logs with:"
            Write-Output "  gh run view $($run.run_id) --repo $Repo --log-failed"
            Stop-Cycle "GitHub Actions run failed: $($run.job_id)"
        }
        $viewJson = gh run view $run.run_id --repo $Repo --json status,conclusion
        $view = $viewJson | ConvertFrom-Json
        if ($view.status -ne "completed" -or $view.conclusion -ne "success") {
            Write-Output "Run failed. Inspect failed logs with:"
            Write-Output "  gh run view $($run.run_id) --repo $Repo --log-failed"
            Stop-Cycle "GitHub Actions run did not finish successfully: $($run.job_id)"
        }
    }
    Write-Output "OK: all Actions runs completed successfully."
}

function Download-Artifacts {
    param([object[]]$Runs)
    if ($PlanOnly) {
        foreach ($run in $Runs) {
            Write-Output "PLAN: gh run download $($run.run_id) -n $($run.artifact_name) -D .tmp/... --repo $Repo"
        }
        return
    }

    New-Item -ItemType Directory -Force -Path $BundlesDir | Out-Null
    $workDir = ".tmp/fetch_artifact_downloads_$($JobPrefix)_$(Get-Date -Format yyyyMMdd_HHmmss)"
    New-Item -ItemType Directory -Force -Path $workDir | Out-Null
    foreach ($run in $Runs) {
        $jobDir = Join-Path $workDir $run.job_id
        New-Item -ItemType Directory -Force -Path $jobDir | Out-Null
        Invoke-CheckedCommand -Exe "gh" -Args @(
            "run", "download", "$($run.run_id)",
            "--repo", $Repo,
            "-n", $run.artifact_name,
            "-D", $jobDir
        ) | Out-Null
        $bundle = Get-ChildItem -LiteralPath $jobDir -Filter "cache_bundle_$($run.job_id).zip" -Recurse |
            Select-Object -First 1
        if (-not $bundle) {
            Stop-Cycle "Downloaded artifact did not contain cache_bundle_$($run.job_id).zip"
        }
        $dest = Join-Path $BundlesDir "cache_bundle_$($run.job_id).zip"
        Copy-Item -LiteralPath $bundle.FullName -Destination $dest -Force
        Write-Output "OK: artifact placed $dest"
    }
}

function Invoke-ProcessDryRun {
    param([object[]]$Jobs)
    if ($PlanOnly) {
        Write-Output "PLAN: skip import/build/validate/merge dry-run."
        return
    }
    $python = Get-PythonExe
    $args = @(
        ".\ops\process_cache_bundle_jobs.py",
        "--jobs"
    )
    foreach ($job in $Jobs) {
        $args += $job.JobId
    }
    $args += @("--expected-start-raw-sha256", $ExpectedStartRawSha256)
    Invoke-CheckedCommand -Exe $python -Args $args | Out-Null
}

function Invoke-ParseClassification {
    param([object[]]$Jobs, [string]$StartedAt)
    if ($PlanOnly) {
        Write-Output "PLAN: skip parse warning classification."
        return [pscustomobject]@{
            parser_gap_total = 0
            unknown_total = 0
            total_unparsed_races = 0
            total_counts = @{}
            csv_report = ""
            md_report = ""
        }
    }

    $python = Get-PythonExe
    $jobIdsJson = ConvertTo-Json -InputObject @($Jobs | ForEach-Object { $_.JobId }) -Compress
    $code = @"
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from nankan_ai.parse_result_pages import (
    _extract_tables,
    _extract_visible_text,
    _find_result_table,
    _read_html,
    parse_result_page_html,
)

JOB_IDS = $jobIdsJson
ROOT = Path(".")
REPORTS = ROOT / "data/reports"
REPORTS.mkdir(parents=True, exist_ok=True)
started = "$StartedAt"

cancel_tokens = ["\u4e2d\u6b62", "\u53d6\u308a\u6b62\u3081", "\u53d6\u6b62", "\u4e0d\u6210\u7acb", "\u958b\u50ac\u4e2d\u6b62", "\u7af6\u8d70\u4e2d\u6b62"]
no_data_tokens = ["\u8a72\u5f53", "\u3042\u308a\u307e\u305b\u3093", "\u30c7\u30fc\u30bf", "\u30a8\u30e9\u30fc", "\u5bfe\u8c61", "\u8868\u793a\u3067\u304d\u307e\u305b\u3093", "\u30ec\u30fc\u30b9\u60c5\u5831"]
horse_tokens = ["\u99ac\u756a", "\u99ac\u540d", "\u7740\u9806", "\u9a0e\u624b", "\u8abf\u6559\u5e2b"]

all_records = []
summary = []
for job_id in JOB_IDS:
    job_csv = ROOT / f"data/jobs/fetch_job_{job_id}.csv"
    with job_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    job_records = []
    parsed_races = 0
    for row in rows:
        race_id = row["race_id"].strip()
        html_path = ROOT / row["cache_html_path"].strip()
        if not html_path.exists():
            record = {
                "job_id": job_id,
                "race_id": race_id,
                "classification_candidate": "unknown",
                "reason": "html_missing",
                "table_count": 0,
                "has_result_table": "no",
                "has_horse_like_header": "unknown",
                "title_or_message": "",
            }
            job_records.append(record)
            all_records.append(record)
            continue
        html = _read_html(html_path)
        parsed = parse_result_page_html(html, race_id=race_id, source_path=html_path)
        if parsed.rows:
            parsed_races += 1
            continue
        tables = _extract_tables(html)
        visible_parts = _extract_visible_text(html)
        visible_text = " ".join(visible_parts)
        compact_visible = re.sub(r"\s+", " ", visible_text).strip()
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1)).strip() if title_match else ""
        result_table = _find_result_table(tables)
        table_text = " ".join(" ".join(cell for cell in row_cells) for table in tables for row_cells in table)
        has_horse_like = any(token in table_text for token in horse_tokens)
        if result_table is not None or has_horse_like:
            classification = "parser_gap"
            reason = "horse-like result table/header was detected but parser returned zero rows"
        elif any(token in compact_visible for token in cancel_tokens):
            classification = "race_cancelled_or_irregular"
            reason = "cancel/irregular wording detected in visible text"
        elif any(token in compact_visible for token in no_data_tokens) or not tables:
            classification = "official_no_result_table"
            reason = "no result table and official no-data/error-like text detected"
        else:
            classification = "official_no_result_table"
            reason = "no result table and no horse-like result header detected"
        record = {
            "job_id": job_id,
            "race_id": race_id,
            "classification_candidate": classification,
            "reason": reason,
            "table_count": len(tables),
            "has_result_table": "yes" if result_table is not None else "no",
            "has_horse_like_header": "yes" if has_horse_like else "no",
            "title_or_message": (title or compact_visible[:160]).replace("\n", " ")[:200],
        }
        job_records.append(record)
        all_records.append(record)
    counts = Counter(r["classification_candidate"] for r in job_records)
    summary.append({
        "job_id": job_id,
        "job_races": len(rows),
        "parsed_races": parsed_races,
        "unparsed_races": len(job_records),
        "classification_counts": dict(counts),
        "parser_gap_count": counts.get("parser_gap", 0),
        "unknown_count": counts.get("unknown", 0),
    })

csv_path = REPORTS / f"bulk_dry_run_parse_warnings_{started}.csv"
md_path = REPORTS / f"bulk_dry_run_parse_warnings_{started}.md"
fieldnames = ["job_id","race_id","classification_candidate","reason","table_count","has_result_table","has_horse_like_header","title_or_message"]
with csv_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(all_records)

lines = [
    "# Bulk Dry-run Parse Warning Classification",
    "",
    f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
    f"- total_unparsed_races: {len(all_records)}",
    "",
    "| job_id | job_races | parsed_races | unparsed_races | official_no_result_table | race_cancelled_or_irregular | parser_gap | unknown |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
for item in summary:
    counts = item["classification_counts"]
    lines.append(
        f"| {item['job_id']} | {item['job_races']} | {item['parsed_races']} | {item['unparsed_races']} | "
        f"{counts.get('official_no_result_table', 0)} | {counts.get('race_cancelled_or_irregular', 0)} | "
        f"{counts.get('parser_gap', 0)} | {counts.get('unknown', 0)} |"
    )
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
payload = {
    "summary": summary,
    "total_unparsed_races": len(all_records),
    "total_counts": dict(Counter(r["classification_candidate"] for r in all_records)),
    "parser_gap_total": sum(1 for r in all_records if r["classification_candidate"] == "parser_gap"),
    "unknown_total": sum(1 for r in all_records if r["classification_candidate"] == "unknown"),
    "csv_report": str(csv_path).replace("\\\\", "/"),
    "md_report": str(md_path).replace("\\\\", "/"),
}
print(json.dumps(payload, ensure_ascii=False))
"@
    $classificationJson = $code | & $python -
    if ($LASTEXITCODE -ne 0) {
        Stop-Cycle "Parse warning classification failed."
    }
    $classification = $classificationJson | ConvertFrom-Json
    Write-Host ($classification | ConvertTo-Json -Depth 8)
    if ($classification.parser_gap_total -gt 0 -or $classification.unknown_total -gt 0) {
        Stop-Cycle "Unsafe parse warnings found. Stop before apply."
    }
    return $classification
}

function Invoke-SafeApply {
    param([object[]]$Jobs, [object]$Classification)

    if ($PlanOnly) {
        Write-Output "PLAN: skip safe apply."
        return
    }
    if ($DryRunOnly -or -not $ApplyIfSafe) {
        Write-Output "Apply not requested. Stop after dry-run/classification."
        return
    }
    Assert-RawSha256 -Expected $ExpectedStartRawSha256
    if ($Classification.parser_gap_total -gt 0 -or $Classification.unknown_total -gt 0) {
        Stop-Cycle "Apply blocked: parser_gap or unknown parse warnings exist."
    }

    $python = Get-PythonExe
    $args = @(
        ".\ops\process_cache_bundle_jobs.py",
        "--jobs"
    )
    foreach ($job in $Jobs) {
        $args += $job.JobId
    }
    $args += @(
        "--expected-start-raw-sha256", $ExpectedStartRawSha256,
        "--apply"
    )
    Invoke-CheckedCommand -Exe $python -Args $args | Out-Null
}

function Write-ResumeGuidance {
    $states = @(Get-ChildItem -LiteralPath $ReportsDir -Filter "append_state_append_*.json" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if ($states.Count -gt 0) {
        Write-Output "Latest append_state: $($states[0].FullName)"
        Write-Output "Resume command:"
        Write-Output "  python -m nankan_ai.merge_append_csv --resume $($states[0].FullName)"
    } else {
        Write-Output "No append_state file was found."
    }
}

function Get-FinalCounts {
    if ($PlanOnly) {
        return [pscustomobject]@{}
    }
    $python = Get-PythonExe
    $code = @"
import csv
import json
from pathlib import Path
from nankan_ai.append_batch_log import file_sha256

raw = Path("data/raw/nankan_past_races.csv")
duckdb_path = Path("data/nankan.duckdb")
training = Path("data/processed/training_rows.csv")

with raw.open("r", encoding="utf-8-sig", newline="") as f:
    raw_rows = list(csv.DictReader(f))

duckdb_rows = None
duckdb_races = None
if duckdb_path.exists():
    try:
        import duckdb
        con = duckdb.connect(str(duckdb_path), read_only=True)
        duckdb_rows = con.execute("select count(*) from past_race_rows").fetchone()[0]
        duckdb_races = con.execute("select count(distinct race_id) from past_race_rows").fetchone()[0]
        con.close()
    except Exception as exc:
        duckdb_rows = f"unavailable: {exc.__class__.__name__}: {exc}"
        duckdb_races = "unavailable"

training_rows = None
if training.exists():
    with training.open("r", encoding="utf-8-sig", newline="") as f:
        training_rows = sum(1 for _ in csv.DictReader(f))

print(json.dumps({
    "raw_rows": len(raw_rows),
    "race_count": len({row["race_id"] for row in raw_rows}),
    "duckdb_rows": duckdb_rows,
    "duckdb_races": duckdb_races,
    "training_rows": training_rows,
    "raw_sha256": file_sha256(raw),
}, ensure_ascii=False))
"@
    $json = $code | & $python -
    if ($LASTEXITCODE -ne 0) {
        Stop-Cycle "Final count check failed."
    }
    return ($json | ConvertFrom-Json)
}

function Invoke-FinalChecks {
    if ($PlanOnly) {
        Write-Output "PLAN: skip final checks."
        return
    }
    $counts = Get-FinalCounts
    Write-Output ($counts | ConvertTo-Json -Depth 5)

    $python = Get-PythonExe
    Invoke-CheckedCommand -Exe $python -Args @("-m", "pytest") | Out-Null

    $staged = @(Assert-NoForbiddenStaged)
    if ($staged.Count -gt 0) {
        Stop-Cycle "Staged files remain after cycle: $($staged -join ', ')"
    }
    Write-Output "OK: git staged files are empty."
}

function Write-CycleSummary {
    param([object[]]$Jobs, [object[]]$Runs, [object]$Classification, [string]$StartedAt)
    if ($PlanOnly) {
        return
    }
    New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null
    $path = Join-Path $ReportsDir "bulk_fetch_cycle_$($JobPrefix)_$StartedAt.md"
    $lines = @(
        "# Bulk Fetch Cycle Summary",
        "",
        "- created_at: $(Get-Date -Format s)",
        "- repo: $Repo",
        "- job_prefix: $JobPrefix",
        "- backend: $Backend",
        "- apply_if_safe: $ApplyIfSafe",
        "- dry_run_only: $DryRunOnly",
        "",
        "## Jobs",
        "",
        "| job_id | run_id | artifact |",
        "|---|---:|---|"
    )
    foreach ($job in $Jobs) {
        $run = @($Runs | Where-Object { $_.job_id -eq $job.JobId } | Select-Object -First 1)
        $runId = if ($run) { $run.run_id } else { "" }
        $artifact = if ($run) { $run.artifact_name } else { "" }
        $lines += "| $($job.JobId) | $runId | $artifact |"
    }
    $lines += @(
        "",
        "## Parse Classification",
        "",
        "- total_unparsed_races: $($Classification.total_unparsed_races)",
        "- parser_gap_total: $($Classification.parser_gap_total)",
        "- unknown_total: $($Classification.unknown_total)",
        "- classification_csv: $($Classification.csv_report)",
        "- classification_md: $($Classification.md_report)"
    )
    Set-Content -LiteralPath $path -Value ($lines -join "`n") -Encoding UTF8
    Write-Output "OK: cycle summary saved to $path"
}

try {
    $startedAt = Get-Date -Format "yyyyMMdd_HHmmss"
    Assert-ProjectRoot
    $jobs = @(Get-TargetJobs)
    Write-Output "Target jobs:"
    $jobs | Format-Table -AutoSize | Out-String | Write-Output

    if (-not $PlanOnly) {
        Invoke-CheckedCommand -Exe "gh" -Args @("auth", "status") | Out-Null
    } else {
        Write-Output "PLAN: skip gh auth status."
    }

    Write-Output "Git status:"
    git status --short

    Assert-RawSha256 -Expected $ExpectedStartRawSha256
    Test-RaceIdConsistency -Jobs $jobs | Out-Null
    Publish-JobFilesIfNeeded -Jobs $jobs

    if ($PlanOnly) {
        Dispatch-Actions -Jobs $jobs
        $runs = @()
        Write-Output "PLAN: skip run_id save, Actions wait, and artifact download."
    } else {
        $runs = @(Dispatch-Actions -Jobs $jobs)
        Save-RunIds -Runs $runs -StartedAt $startedAt | Out-Null
        Wait-Actions -Runs $runs
        Download-Artifacts -Runs $runs
    }
    Invoke-ProcessDryRun -Jobs $jobs
    $classification = Invoke-ParseClassification -Jobs $jobs -StartedAt $startedAt
    Invoke-SafeApply -Jobs $jobs -Classification $classification
    Invoke-FinalChecks
    Write-CycleSummary -Jobs $jobs -Runs $runs -Classification $classification -StartedAt $startedAt
    Write-Output "OK: bulk fetch cycle completed."
} catch {
    Write-Output "NG: bulk fetch cycle stopped."
    Write-Output $_.Exception.Message
    Write-ResumeGuidance
    exit 1
}
