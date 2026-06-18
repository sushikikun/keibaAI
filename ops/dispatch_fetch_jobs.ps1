param(
    [string[]]$JobIds = @(
        "job_20260618_191957_p02",
        "job_20260618_191957_p03",
        "job_20260618_191957_p04",
        "job_20260618_191957_p05"
    ),
    [string]$Workflow = "fetch_cache_bundle.yml",
    [ValidateSet("python", "powershell", "curl")]
    [string]$Backend = "python",
    [string]$DelaySeconds = "1.0",
    [string]$WorkerPackagePath = "",
    [string]$Repo = "",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Invoke-Or-Print {
    param([string[]]$CommandParts)

    $display = ($CommandParts | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }) -join " "

    if (-not $Execute) {
        Write-Output "[dry-run] $display"
        return
    }

    & $CommandParts[0] @($CommandParts[1..($CommandParts.Count - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $display"
    }
}

if ($Execute -and -not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh CLI was not found. Install GitHub CLI or run without -Execute to print commands."
}

foreach ($jobId in $JobIds) {
    $jobCsvPath = "data/jobs/fetch_job_$jobId.csv"
    $jobJsonPath = "data/jobs/fetch_job_$jobId.json"

    if (-not (Test-Path -LiteralPath $jobCsvPath)) {
        throw "Fetch job CSV not found: $jobCsvPath"
    }
    if (-not (Test-Path -LiteralPath $jobJsonPath)) {
        throw "Fetch job JSON not found: $jobJsonPath"
    }

    $command = @(
        "gh", "workflow", "run", $Workflow,
        "-f", "job_id=$jobId",
        "-f", "backend=$Backend",
        "-f", "delay_seconds=$DelaySeconds",
        "-f", "job_csv_path=$jobCsvPath",
        "-f", "job_json_path=$jobJsonPath",
        "-f", "worker_package_path=$WorkerPackagePath"
    )
    if ($Repo) {
        $command += @("--repo", $Repo)
    }

    Invoke-Or-Print -CommandParts $command
}

if (-not $Execute) {
    Write-Output ""
    Write-Output "No GitHub Actions runs were started. Re-run with -Execute when ready."
}
