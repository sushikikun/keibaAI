from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "<CODEX_HOME>_deps"))
sys.path.insert(0, str(ROOT / "scripts"))

from noodds_candidate_acceleration import (
    clustered_subset,
    futility_decision,
    preflight_candidate_output,
    validate_baseline_file,
)


class CandidateAccelerationTests(unittest.TestCase):
    def test_clustered_subset_is_stable_and_selects_whole_dates(self):
        dates = np.asarray(
            ["2026-01-01"] * 3
            + ["2026-01-02"] * 2
            + ["2026-01-03"] * 4
            + ["2026-01-04"] * 2
        )
        indices = np.arange(len(dates))
        first = clustered_subset(indices, dates, 0.5, 1, 26101, "d6", "validation")
        second = clustered_subset(indices, dates, 0.5, 1, 26101, "d6", "validation")
        np.testing.assert_array_equal(first, second)
        selected_dates = set(dates[first].tolist())
        for race_date in selected_dates:
            np.testing.assert_array_equal(
                first[dates[first] == race_date],
                indices[dates == race_date],
            )

    def test_futility_requires_mean_and_ci_failure(self):
        protocol = {
            "screen": {
                "futility_gate": {
                    "pooled_logloss_delta_greater_than": 0.02,
                    "daily_cluster_ci95_lower_greater_than": 0.0,
                    "require_both": True,
                }
            }
        }
        self.assertTrue(futility_decision(0.03, (0.01, 0.05), protocol)["stop_for_futility"])
        self.assertFalse(futility_decision(0.03, (-0.01, 0.05), protocol)["stop_for_futility"])
        self.assertFalse(futility_decision(0.01, (0.001, 0.03), protocol)["stop_for_futility"])

    def test_validate_baseline_requires_exact_alignment(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "baseline.npz"
            indices = np.asarray([4, 8], dtype=np.int64)
            targets = np.asarray([1, 2], dtype=np.int64)
            dates = np.asarray(["2026-01-01", "2026-01-02"])
            probabilities = np.full((2, 120), 1.0 / 120.0)
            np.savez_compressed(
                path,
                standalone=probabilities,
                race_indices=indices,
                race_dates=dates,
                true_combo=targets,
            )
            loaded = validate_baseline_file(
                path,
                indices,
                targets,
                dates,
                ["standalone", "race_indices", "race_dates", "true_combo"],
                1.0e-5,
            )
            np.testing.assert_allclose(loaded, probabilities)
            with self.assertRaises(ValueError):
                validate_baseline_file(
                    path,
                    indices[::-1],
                    targets,
                    dates,
                    ["standalone", "race_indices", "race_dates", "true_combo"],
                    1.0e-5,
                )

    def test_nonempty_output_requires_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "partial.txt").write_text("partial", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                preflight_candidate_output(output, resume=False)
            preflight_candidate_output(output, resume=True)


if __name__ == "__main__":
    unittest.main()
