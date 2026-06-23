from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .append_batch_log import file_sha256
from .schema import DEFAULT_RAW_CSV_PATH, TRACKS

DEFAULT_JOBS_DIR = Path("data/jobs")
DEFAULT_REPORTS_DIR = Path("data/reports")
DEFAULT_BUNDLES_DIR = Path("data/cache/bundles")
DEFAULT_WORKFLOW = "fetch_cache_bundle.yml"
DEFAULT_WORK_DIR = Path(".tmp/fetch_artifact_downloads")
VALID_MODES = ("list", "dispatch", "download", "dry-run", "apply")
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class BulkWaveRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class WaveJob:
    job_id: str
    part_number: int
    wave: str
    track: str
    date_from: str
    date_to: str
    race_count: int
    raw_sha256_at_export: str
    csv_path: Path
    json_path: Path

    @property
    def artifact_name(self) -> str:
        return f"cache-bundle-{self.job_id}"

    @property
    def bundle_path(self) -> Path:
        return DEFAULT_BUNDLES_DIR / f"cache_bundle_{self.job_id}.zip"


@dataclass(frozen=True)
class WaveSelection:
    track: str
    wave: str
    job_prefix: str
    jobs: list[WaveJob]

    @property
    def job_count(self) -> int:
        return len(self.jobs)

    @property
    def total_candidate_races(self) -> int:
        return sum(job.race_count for job in self.jobs)

    @property
    def date_min(self) -> str:
        return min((job.date_from for job in self.jobs if job.date_from), default="")

    @property
    def date_max(self) -> str:
        return max((job.date_to for job in self.jobs if job.date_to), default="")

    @property
    def raw_sha256_values(self) -> list[str]:
        return sorted({job.raw_sha256_at_export for job in self.jobs if job.raw_sha256_at_export})


@dataclass
class BulkWaveRunResult:
    mode: str
    selection: WaveSelection
    report_path: Path | None = None
    state_path: Path | None = None
    commands: list[list[str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def select_wave_jobs(
    *,
    track: str,
    wave: str,
    job_prefix: str,
    jobs_dir: str | Path = DEFAULT_JOBS_DIR,
) -> WaveSelection:
    normalized_track = track.strip().lower()
    if normalized_track not in TRACKS:
        raise BulkWaveRunnerError(f"track must be one of: {', '.join(sorted(TRACKS))}")
    normalized_wave = _normalize_wave(wave)
    jobs_root = Path(jobs_dir)
    pattern = f"fetch_job_{job_prefix}_{normalized_wave}_p*.json"
    jobs: list[WaveJob] = []
    for json_path in sorted(jobs_root.glob(pattern)):
        job = _read_wave_job(json_path)
        if (
            job.track == normalized_track
            and job.wave == normalized_wave
            and job.job_id.startswith(f"{job_prefix}_{normalized_wave}_")
        ):
            jobs.append(job)

    jobs.sort(key=lambda job: job.part_number)
    if not jobs:
        raise BulkWaveRunnerError(
            f"no fetch jobs found for track={normalized_track}, wave={normalized_wave}, job_prefix={job_prefix}"
        )
    return WaveSelection(
        track=normalized_track,
        wave=normalized_wave,
        job_prefix=job_prefix,
        jobs=jobs,
    )


def run_wave(
    *,
    track: str,
    wave: str,
    job_prefix: str,
    mode: str,
    jobs_dir: str | Path = DEFAULT_JOBS_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    bundles_dir: str | Path = DEFAULT_BUNDLES_DIR,
    raw_csv_path: str | Path = DEFAULT_RAW_CSV_PATH,
    expected_start_raw_sha256: str = "",
    repo: str = "",
    workflow: str = DEFAULT_WORKFLOW,
    backend: str = "python",
    delay_seconds: str = "1.0",
    worker_package_path: str = "",
    allow_apply: bool = False,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
) -> BulkWaveRunResult:
    if mode not in VALID_MODES:
        raise BulkWaveRunnerError(f"mode must be one of: {', '.join(VALID_MODES)}")
    selection = select_wave_jobs(
        track=track,
        wave=wave,
        job_prefix=job_prefix,
        jobs_dir=jobs_dir,
    )
    result = BulkWaveRunResult(mode=mode, selection=selection)
    command_runner = runner or _run_command

    if mode == "list":
        result.messages.append(format_selection(selection))
        return result

    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)

    if mode == "dispatch":
        if not repo:
            raise BulkWaveRunnerError("--repo is required for mode=dispatch")
        result.commands = _dispatch_jobs(
            selection,
            repo=repo,
            workflow=workflow,
            backend=backend,
            delay_seconds=delay_seconds,
            worker_package_path=worker_package_path,
            runner=command_runner,
        )
    elif mode == "download":
        if not repo:
            raise BulkWaveRunnerError("--repo is required for mode=download")
        result.commands = _download_artifacts(
            selection,
            repo=repo,
            bundles_dir=Path(bundles_dir),
            runner=command_runner,
        )
    elif mode == "dry-run":
        _assert_expected_raw_sha(raw_csv_path, expected_start_raw_sha256)
        result.commands = [_process_cache_bundle_jobs_command(selection, expected_start_raw_sha256)]
        command_runner(result.commands[0])
        result.state_path = _write_state(
            selection,
            reports,
            mode="dry-run",
            status="passed",
            expected_start_raw_sha256=expected_start_raw_sha256,
            applied=False,
            now=now,
        )
    elif mode == "apply":
        if not allow_apply:
            raise BulkWaveRunnerError("mode=apply requires --allow-apply")
        _assert_expected_raw_sha(raw_csv_path, expected_start_raw_sha256)
        _assert_dry_run_state(
            selection,
            reports,
            expected_start_raw_sha256=expected_start_raw_sha256,
        )
        command = [*_process_cache_bundle_jobs_command(selection, expected_start_raw_sha256), "--apply"]
        result.commands = [command]
        try:
            command_runner(command)
        except BulkWaveRunnerError as exc:
            guidance = _resume_guidance(reports)
            raise BulkWaveRunnerError(
                "apply failed; do not rerun apply. Resume with merge_append_csv if append_state exists.\n"
                + guidance
            ) from exc
        result.state_path = _write_state(
            selection,
            reports,
            mode="apply",
            status="passed",
            expected_start_raw_sha256=expected_start_raw_sha256,
            applied=True,
            now=now,
        )

    result.report_path = _write_report(result, reports, now=now)
    return result


def format_selection(selection: WaveSelection) -> str:
    lines = [
        f"track: {selection.track}",
        f"wave: {selection.wave}",
        f"job_prefix: {selection.job_prefix}",
        f"job_count: {selection.job_count}",
        f"total_candidate_races: {selection.total_candidate_races}",
        f"date_min: {selection.date_min}",
        f"date_max: {selection.date_max}",
        "raw_sha256_at_export:",
        *[f"- {value}" for value in selection.raw_sha256_values],
        "jobs:",
    ]
    lines.extend(
        f"- {job.job_id} races={job.race_count} date={job.date_from}..{job.date_to}"
        for job in selection.jobs
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one generated fetch-job wave safely.")
    parser.add_argument("--track", required=True, choices=sorted(TRACKS))
    parser.add_argument("--wave", required=True)
    parser.add_argument("--job-prefix", required=True)
    parser.add_argument("--mode", required=True, choices=VALID_MODES)
    parser.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--bundles-dir", default=str(DEFAULT_BUNDLES_DIR))
    parser.add_argument("--raw-csv-path", default=str(DEFAULT_RAW_CSV_PATH))
    parser.add_argument("--expected-start-raw-sha256", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--backend", default="python", choices=("python", "powershell", "curl"))
    parser.add_argument("--delay-seconds", default="1.0")
    parser.add_argument("--worker-package-path", default="")
    parser.add_argument("--allow-apply", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = run_wave(
            track=args.track,
            wave=args.wave,
            job_prefix=args.job_prefix,
            mode=args.mode,
            jobs_dir=args.jobs_dir,
            reports_dir=args.reports_dir,
            bundles_dir=args.bundles_dir,
            raw_csv_path=args.raw_csv_path,
            expected_start_raw_sha256=args.expected_start_raw_sha256,
            repo=args.repo,
            workflow=args.workflow,
            backend=args.backend,
            delay_seconds=args.delay_seconds,
            worker_package_path=args.worker_package_path,
            allow_apply=args.allow_apply,
        )
    except BulkWaveRunnerError as exc:
        print(f"NG: {exc}")
        return 1

    for message in result.messages:
        print(message)
    if result.report_path:
        print(f"report: {result.report_path}")
    if result.state_path:
        print(f"state: {result.state_path}")
    return 0


def _read_wave_job(json_path: Path) -> WaveJob:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    job_id = str(payload.get("job_id", "")).strip()
    match = re.search(r"_(w\d{2})_p(\d+)$", job_id)
    if not match:
        raise BulkWaveRunnerError(f"job_id does not contain wave/part: {job_id}")
    csv_path = Path(str(payload.get("fetch_job_csv") or json_path.with_suffix(".csv")))
    return WaveJob(
        job_id=job_id,
        part_number=int(match.group(2)),
        wave=match.group(1),
        track=str(payload.get("track", "")).strip().lower(),
        date_from=str(payload.get("date_from", "")).strip(),
        date_to=str(payload.get("date_to", "")).strip(),
        race_count=int(payload.get("race_count", 0)),
        raw_sha256_at_export=str(payload.get("raw_sha256_at_export", "")).strip(),
        csv_path=csv_path,
        json_path=json_path,
    )


def _dispatch_jobs(
    selection: WaveSelection,
    *,
    repo: str,
    workflow: str,
    backend: str,
    delay_seconds: str,
    worker_package_path: str,
    runner: CommandRunner,
) -> list[list[str]]:
    commands: list[list[str]] = []
    for job in selection.jobs:
        _assert_job_files_exist(job)
        command = [
            "gh",
            "workflow",
            "run",
            workflow,
            "--repo",
            repo,
            "-f",
            f"job_id={job.job_id}",
            "-f",
            f"backend={backend}",
            "-f",
            f"delay_seconds={delay_seconds}",
            "-f",
            f"job_csv_path={_path_string(job.csv_path)}",
            "-f",
            f"job_json_path={_path_string(job.json_path)}",
            "-f",
            f"worker_package_path={worker_package_path}",
        ]
        runner(command)
        commands.append(command)
    return commands


def _download_artifacts(
    selection: WaveSelection,
    *,
    repo: str,
    bundles_dir: Path,
    runner: CommandRunner,
) -> list[list[str]]:
    bundles_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for job in selection.jobs:
        artifact_id = _latest_artifact_workflow_run_id(job.artifact_name, repo=repo, runner=runner)
        job_dir = DEFAULT_WORK_DIR / job.job_id
        if job_dir.exists():
            _remove_tree_inside_workspace(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        download_command = [
            "gh",
            "run",
            "download",
            str(artifact_id),
            "--repo",
            repo,
            "-n",
            job.artifact_name,
            "-D",
            _path_string(job_dir),
        ]
        runner(download_command)
        commands.append(download_command)
        bundle = _find_downloaded_bundle(job_dir, job.job_id)
        destination = bundles_dir / f"cache_bundle_{job.job_id}.zip"
        if not destination.exists():
            shutil.copy2(bundle, destination)
    _assert_bundles_exist(selection, bundles_dir)
    return commands


def _process_cache_bundle_jobs_command(
    selection: WaveSelection,
    expected_start_raw_sha256: str,
) -> list[str]:
    return [
        sys.executable,
        "ops/process_cache_bundle_jobs.py",
        "--jobs",
        *[job.job_id for job in selection.jobs],
        "--expected-start-raw-sha256",
        expected_start_raw_sha256,
    ]


def _assert_expected_raw_sha(raw_csv_path: str | Path, expected: str) -> None:
    if not expected:
        raise BulkWaveRunnerError("--expected-start-raw-sha256 is required for dry-run/apply")
    actual = file_sha256(raw_csv_path)
    if actual.upper() != expected.upper():
        raise BulkWaveRunnerError(
            f"raw SHA256 mismatch. expected={expected.upper()} actual={actual.upper()}"
        )


def _assert_dry_run_state(
    selection: WaveSelection,
    reports_dir: Path,
    *,
    expected_start_raw_sha256: str,
) -> None:
    state_path = _state_path(selection, reports_dir)
    if not state_path.exists():
        raise BulkWaveRunnerError(f"dry-run state not found: {state_path}")
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if payload.get("dry_run_status") != "passed":
        raise BulkWaveRunnerError(f"dry-run state is not passed: {state_path}")
    if str(payload.get("expected_start_raw_sha256", "")).upper() != expected_start_raw_sha256.upper():
        raise BulkWaveRunnerError("dry-run state raw SHA256 does not match requested apply SHA256")
    if payload.get("job_ids") != [job.job_id for job in selection.jobs]:
        raise BulkWaveRunnerError("dry-run state job list does not match selected wave")


def _write_state(
    selection: WaveSelection,
    reports_dir: Path,
    *,
    mode: str,
    status: str,
    expected_start_raw_sha256: str,
    applied: bool,
    now: datetime | None,
) -> Path:
    path = _state_path(selection, reports_dir)
    payload = {
        "created_at": (now or datetime.now()).isoformat(timespec="seconds"),
        "track": selection.track,
        "wave": selection.wave,
        "job_prefix": selection.job_prefix,
        "job_ids": [job.job_id for job in selection.jobs],
        "expected_start_raw_sha256": expected_start_raw_sha256,
        "dry_run_status": "passed" if mode == "dry-run" and status == "passed" else "",
        "apply_status": "passed" if mode == "apply" and status == "passed" else "",
        "applied": applied,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_report(result: BulkWaveRunResult, reports_dir: Path, *, now: datetime | None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"bulk_wave_{result.selection.track}_{result.selection.wave}_{timestamp}.md"
    lines = [
        "# Bulk Wave Runner Report",
        "",
        f"- created_at: {(now or datetime.now()).isoformat(timespec='seconds')}",
        f"- mode: {result.mode}",
        f"- track: {result.selection.track}",
        f"- wave: {result.selection.wave}",
        f"- job_prefix: {result.selection.job_prefix}",
        f"- job_count: {result.selection.job_count}",
        f"- total_candidate_races: {result.selection.total_candidate_races}",
        f"- date_min: {result.selection.date_min}",
        f"- date_max: {result.selection.date_max}",
        "",
        "## Jobs",
        "",
        *[f"- `{job.job_id}` races={job.race_count}" for job in result.selection.jobs],
    ]
    if result.commands:
        lines.extend(["", "## Commands", ""])
        lines.extend(f"- `{' '.join(command)}`" for command in result.commands)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def _latest_artifact_workflow_run_id(
    artifact_name: str,
    *,
    repo: str,
    runner: CommandRunner,
) -> int:
    command = ["gh", "api", f"repos/{repo}/actions/artifacts?name={artifact_name}"]
    completed = runner(command)
    payload = json.loads(completed.stdout or "{}")
    artifacts = [
        item for item in payload.get("artifacts", [])
        if item.get("name") == artifact_name and not item.get("expired")
    ]
    if not artifacts:
        raise BulkWaveRunnerError(f"artifact not found or expired: {artifact_name}")
    artifacts.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return int(artifacts[0]["workflow_run"]["id"])


def _find_downloaded_bundle(job_dir: Path, job_id: str) -> Path:
    candidates = sorted(job_dir.rglob(f"cache_bundle_{job_id}.zip"))
    if not candidates:
        raise BulkWaveRunnerError(f"downloaded artifact did not contain cache_bundle_{job_id}.zip")
    return candidates[0]


def _assert_bundles_exist(selection: WaveSelection, bundles_dir: Path) -> None:
    missing = [
        bundles_dir / f"cache_bundle_{job.job_id}.zip"
        for job in selection.jobs
        if not (bundles_dir / f"cache_bundle_{job.job_id}.zip").exists()
    ]
    if missing:
        raise BulkWaveRunnerError(
            "cache bundle is missing: " + ", ".join(_path_string(path) for path in missing)
        )


def _assert_job_files_exist(job: WaveJob) -> None:
    if not job.csv_path.exists():
        raise BulkWaveRunnerError(f"fetch job CSV not found: {job.csv_path}")
    if not job.json_path.exists():
        raise BulkWaveRunnerError(f"fetch job JSON not found: {job.json_path}")


def _remove_tree_inside_workspace(path: Path) -> None:
    root = Path.cwd().resolve()
    target = path.resolve()
    if root not in (target, *target.parents):
        raise BulkWaveRunnerError(f"refusing to remove outside workspace: {target}")
    shutil.rmtree(target)


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise BulkWaveRunnerError(
            f"command failed with exit code {completed.returncode}: {' '.join(command)}\n"
            f"{completed.stderr or completed.stdout}"
        )
    return completed


def _resume_guidance(reports_dir: Path) -> str:
    states = sorted(reports_dir.glob("append_state_append_*.json"), key=lambda path: path.stat().st_mtime)
    if not states:
        return "No append_state file was found."
    latest = states[-1]
    return f"Resume command:\n  python -m nankan_ai.merge_append_csv --resume {latest}"


def _state_path(selection: WaveSelection, reports_dir: Path) -> Path:
    return reports_dir / f"bulk_wave_state_{selection.track}_{selection.wave}_{_safe_name(selection.job_prefix)}.json"


def _normalize_wave(wave: str) -> str:
    value = wave.strip().lower()
    if re.fullmatch(r"\d+", value):
        return f"w{int(value):02d}"
    if not re.fullmatch(r"w\d{2}", value):
        raise BulkWaveRunnerError("wave must be like w01 or 1")
    return value


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _path_string(path: Path) -> str:
    return str(path).replace("\\", "/")


__all__ = [
    "BulkWaveRunResult",
    "BulkWaveRunnerError",
    "WaveJob",
    "WaveSelection",
    "format_selection",
    "run_wave",
    "select_wave_jobs",
]


if __name__ == "__main__":
    raise SystemExit(main())
