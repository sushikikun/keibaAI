import tempfile
import unittest
from pathlib import Path

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_noodds_v286_dynamic_equipment_history_on_v283 import (
    RUNNER_FEATURE_NAMES,
    build_dynamic_equipment_features,
    candidate_features,
    load_v283_oof,
)


INITIAL = np.asarray([1.0 / 6.0, 1.0 / 3.0, 0.5], dtype=np.float64)


def combo(first: int, second: int, third: int) -> int:
    matches = np.flatnonzero((A == first) & (B == second) & (C == third))
    if len(matches) != 1:
        raise AssertionError("combo lookup failed")
    return int(matches[0])


def fixture(races: int):
    raw = np.zeros((races, 6, 143), dtype=np.float32)
    raw[:, :, 2] = np.arange(100, 106, dtype=np.float32)
    raw[:, :, 3] = np.arange(200, 206, dtype=np.float32)
    raw[:, :, 9] = 40.0
    raw[:, :, 10] = 35.0
    return raw


def build(raw, targets, dates):
    return build_dynamic_equipment_features(
        raw,
        np.asarray(targets, dtype=np.int64),
        np.asarray(dates),
        window_days=180,
        motor_shrinkage=20.0,
        boat_shrinkage=20.0,
        initial_rates=INITIAL,
        snapshot_scale=0.01,
        valid_snapshot_range=(0.0, 100.0),
    )


class DynamicEquipmentHistoryOnV283Tests(unittest.TestCase):
    def test_same_day_results_are_deferred(self):
        raw = fixture(3)
        features = build(
            raw,
            [combo(0, 1, 2), combo(5, 4, 3), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[0], features[1])
        np.testing.assert_allclose(features[0], 0.0)
        np.testing.assert_allclose(features[2, :, 0], np.log1p(2.0))
        np.testing.assert_allclose(features[2, :, 5], np.log1p(2.0))

    def test_window_includes_day_180_and_excludes_day_181(self):
        raw = fixture(3)
        raw[1, :, 2:4] += 1000
        features = build(
            raw,
            [combo(0, 1, 2)] * 3,
            ["2025-01-01", "2025-06-30", "2025-07-01"],
        )
        np.testing.assert_allclose(features[1, :, 0], 0.0)
        np.testing.assert_allclose(features[2, :, 0], 0.0)
        np.testing.assert_allclose(features[2, :, 10], 0.0)

    def test_motor_and_boat_histories_are_separate(self):
        raw = fixture(2)
        raw[1, :, 3] += 1000
        features = build(
            raw,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[1, :, 0], np.log1p(1.0))
        np.testing.assert_allclose(features[1, :, 5], 0.0)
        np.testing.assert_allclose(features[1, :, 10], 1.0)
        np.testing.assert_allclose(features[1, :, 11], 0.0)

    def test_missing_ids_are_zero_and_do_not_update(self):
        raw = fixture(2)
        raw[0, :, 2:4] = 0
        features = build(
            raw,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[0], 0.0)
        np.testing.assert_allclose(features[1], 0.0)

    def test_fixed_shrinkage_and_snapshot_difference(self):
        raw = fixture(2)
        features = build(
            raw,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        motor_rate = (np.ones(3) + 20.0 * INITIAL) / 21.0
        np.testing.assert_allclose(features[1, 0, 1:4], motor_rate - INITIAL)
        self.assertAlmostEqual(features[1, 0, 4], 0.40 - motor_rate[1], places=7)
        self.assertAlmostEqual(features[1, 0, 9], 0.35 - motor_rate[1], places=7)

    def test_invalid_snapshot_is_not_used(self):
        raw = fixture(2)
        raw[1, :, 9] = np.nan
        raw[1, :, 10] = 101.0
        features = build(
            raw,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[1, :, 4], 0.0)
        np.testing.assert_allclose(features[1, :, 9], 0.0)

    def test_three_column_targets_match_combo_targets(self):
        raw = fixture(2)
        combos = build(
            raw,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        columns = build(
            raw,
            [[0, 1, 2], [0, 1, 2]],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(columns, combos)

    def test_candidate_projection_follows_trifecta_order(self):
        runner = np.zeros((1, 6, len(RUNNER_FEATURE_NAMES)), dtype=np.float32)
        runner[0, :, 0] = np.arange(10, 16)
        projected = candidate_features(runner, np.asarray([0]))
        width = len(RUNNER_FEATURE_NAMES)
        np.testing.assert_allclose(projected[0, 0, :width], runner[0, A[0]])
        np.testing.assert_allclose(projected[0, 0, width:2 * width], runner[0, B[0]])
        np.testing.assert_allclose(projected[0, 0, 2 * width:3 * width], runner[0, C[0]])

    def test_v283_loader_preserves_parent_and_old_references(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = {}
            for offset, fold in enumerate(("d6", "d7", "d8")):
                path = Path(temp) / f"{fold}.npz"
                probability = np.full((1, 120), 1.0 / 120.0, dtype=np.float32)
                v280 = probability.copy()
                v280[0, 0] += 0.001
                v280[0, 1:] -= 0.001 / 119.0
                np.savez_compressed(
                    path,
                    standalone=probability,
                    v280=v280,
                    v270=probability,
                    v269=probability,
                    v242=probability,
                    v251=probability,
                    race_indices=np.asarray([offset], dtype=np.int64),
                    race_dates=np.asarray([f"2026-01-0{offset + 1}"]),
                    true_combo=np.asarray([0], dtype=np.int64),
                )
                paths[fold] = path
            loaded = load_v283_oof(paths)
        np.testing.assert_allclose(loaded["probability"], 1.0 / 120.0)
        self.assertFalse(np.allclose(loaded["v280"], loaded["probability"]))


if __name__ == "__main__":
    unittest.main()
