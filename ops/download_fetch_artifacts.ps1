param(
    [string[]]$JobIds = @(
        "job_20260618_191957_p02",
        "job_20260618_191957_p03",
        "job_20260618_191957_p04",
        "job_20260618_191957_p05"
    ),
    [string]$Repo = "",
    [string]$BundlesDir = "data/cache/bundles",
    [string]$WorkDir = ".tmp/fetch_artifact_downloads",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

if ($Execute -and -not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh CLI was not found. Install GitHub CLI or run without -Execute to print commands."
}

if (-not $Repo) {
    if ($Execute) {
        $Repo = (& gh repo view --json nameWithOwner -q ".nameWithOwner").Trim()
        if ($LASTEXITCODE -ne 0 -or -not $Repo) {
            throw "Could not infer GitHub repository. Pass -Repo owner/name."
        }
    } else {
        $Repo = "<owner>/<repo>"
    }
}

if ($Execute) {
    New-Item -ItemType Directory -Force -Path $BundlesDir | Out-Null
    New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
}

foreach ($jobId in $JobIds) {
    $artifactName = "cache-bundle-$jobId"
    $jobDir = Join-Path $WorkDir $jobId
    $expectedBundle = Join-Path $BundlesDir "cache_bundle_$jobId.zip"

    if (-not $Execute) {
        Write-Output "[dry-run] Find artifact '$artifactName' in $Repo"
        Write-Output "[dry-run] gh run download <latest-success-run-id> -n $artifactName -D $jobDir --repo $Repo"
        Write-Output "[dry-run] Copy cache_bundle_$jobId.zip to $expectedBundle"
        continue
    }

    $artifactJson = gh api "repos/$Repo/actions/artifacts?name=$artifactName" | ConvertFrom-Json
    $artifact = $artifactJson.artifacts |
        Where-Object { -not $_.expired } |
        Sort-Object created_at -Descending |
        Select-Object -First 1

    if (-not $artifact) {
        throw "Artifact not found or expired: $artifactName"
    }

    if (Test-Path -LiteralPath $jobDir) {
        Remove-Item -LiteralPath $jobDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $jobDir | Out-Null

    gh run download $artifact.workflow_run.id -n $artifactName -D $jobDir --repo $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to download artifact: $artifactName"
    }

    $bundle = Get-ChildItem -LiteralPath $jobDir -Filter "cache_bundle_$jobId.zip" -Recurse |
        Select-Object -First 1
    if (-not $bundle) {
        throw "Downloaded artifact did not contain cache_bundle_$jobId.zip"
    }

    if (Test-Path -LiteralPath $expectedBundle) {
        Write-Output "exists, not overwritten: $expectedBundle"
    } else {
        Copy-Item -LiteralPath $bundle.FullName -Destination $expectedBundle
        Write-Output "copied: $expectedBundle"
    }
}

if (-not $Execute) {
    Write-Output ""
    Write-Output "No artifacts were downloaded. Re-run with -Execute when ready."
}
