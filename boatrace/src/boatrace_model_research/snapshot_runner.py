from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import atomic_write_json, read_json, sha256_file
from .snapshot import build_snapshot as _build_snapshot


def build_snapshot(**kwargs: Any) -> dict[str, Any]:
    """Build a snapshot and make zero-count target states explicit in its profile."""
    result = _build_snapshot(**kwargs)
    snapshot_dir = Path(result["snapshot_dir"])
    profile_path = snapshot_dir / "dataset_profile.json"
    manifest_path = snapshot_dir / "dataset_manifest.json"
    profile = read_json(profile_path)
    counts = profile["eligibility"]["target_status_counts"]
    for status in ("unique_order", "tied", "void"):
        counts.setdefault(status, 0)
    profile["eligibility"]["target_status_counts"] = {
        status: int(counts[status]) for status in ("unique_order", "tied", "void")
    }
    atomic_write_json(profile_path, profile)

    manifest = read_json(manifest_path)
    for artifact in manifest["artifacts"]:
        if artifact["name"] == "dataset_profile":
            artifact["sha256"] = sha256_file(profile_path)
    project_root = Path(kwargs["project_root"]).resolve()
    runner_relative = "src/boatrace_model_research/snapshot_runner.py"
    manifest["implementation_files"].append(
        {
            "path": runner_relative,
            "sha256": sha256_file(project_root / runner_relative),
        }
    )
    atomic_write_json(manifest_path, manifest)
    result["target_status_counts"] = profile["eligibility"]["target_status_counts"]
    result["dataset_manifest_sha256"] = sha256_file(manifest_path)
    return result
