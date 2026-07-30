import tempfile
import unittest
from pathlib import Path

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_noodds_v283_current_meet_form_on_v280 import (
    RUNNER_FEATURE_NAMES,
    build_current_meet_form_features,
    candidate_features,
    load_v280_oof,
)


INITIAL = np.asarray([1.0 / 6.0, 1.0 / 3.0, 0.5], dtype=np.float64)


def combo(first: int, second: int, third: int) -> int:
    matches = np.flatnonzero((A == first) & (B == second) & (C == third))
    if len(matches) != 1:
        raise AssertionError("combo lookup failed")
    return int(matches[0])


def fixture(races: int):
    raw = np.zeros((races, 6, 143), dtype=np.float32)
    raw[:, :, 0] = np.arange(6, dtype=np.float32)
    raw[:, :, 67] = 0.18
    raw[:, :, 55] = 6.8
    race = np.zeros((races, 8), dtype=np.float32)
    race[:, 0] = 1
    return raw, race


def build(raw, race, targets, dates):
    return build_current_meet_form_features(
        raw,
        race,
        np.asarray(targets, dtype=np.int64),
        np.asarray(dates),
        window_days=7,
        overall_shrinkage=50.0,
        meet_shrinkage=10.0,
        initial_start_st=0.18,
        initial_exhibition_time=6.8,
        valid_start_st_range=(-1.0, 1.0),
        valid_exhibition_time_range=(5.0, 10.0),
    )


class CurrentMeetFormOnV280Tests(unittest.TestCase):
    def test_same_day_results_do_not_change_later_same_day_features(self):
        raw, race = fixture(3)
        features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(5, 4, 3), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[0], features[1])
        np.testing.assert_allclose(features[0, :, :6], 0.0)
        np.testing.assert_allclose(features[0, :, 6], 1.0)
        np.testing.assert_allclose(features[0, :, 7], 0.0)
        np.testing.assert_allclose(features[2, :, 0], np.log1p(2.0))

    def test_window_includes_day_seven_and_excludes_day_eight(self):
        raw, race = fixture(3)
        raw[1, :, 0] += 100
        features = build(
            raw,
            race,
            [combo(0, 1, 2)] * 3,
            ["2026-01-01", "2026-01-08", "2026-01-09"],
        )
        np.testing.assert_allclose(features[1, :, 0], 0.0)
        np.testing.assert_allclose(features[2, :, 0], 0.0)
        np.testing.assert_allclose(features[2, :, 6], 1.0)

    def test_separate_venue_has_no_meet_history(self):
        raw, race = fixture(2)
        race[1, 0] = 2
        features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[1, :, 0], 0.0)
        np.testing.assert_allclose(features[1, :, 6], 1.0)

    def test_hierarchical_result_shrinkage_matches_formula(self):
        raw, race = fixture(2)
        features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        overall = (np.ones(3) + 50.0 * INITIAL) / 51.0
        meet = (np.ones(3) + 10.0 * overall) / 11.0
        np.testing.assert_allclose(features[1, 0, 0], np.log1p(1.0))
        np.testing.assert_allclose(features[1, 0, 1:4], meet - overall, rtol=1e-6)

    def test_measurement_shrinkage_and_coverage(self):
        raw, race = fixture(2)
        raw[0, 0, 67] = 0.10
        raw[0, 0, 55] = 6.70
        features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        overall_st = (0.10 + 50.0 * 0.18) / 51.0
        meet_st = (0.10 + 10.0 * overall_st) / 11.0
        overall_ex = (6.70 + 50.0 * 6.8) / 51.0
        meet_ex = (6.70 + 10.0 * overall_ex) / 11.0
        self.assertAlmostEqual(features[1, 0, 4], meet_st - overall_st, places=7)
        self.assertAlmostEqual(features[1, 0, 5], meet_ex - overall_ex, places=7)
        self.assertAlmostEqual(features[1, 0, 7], 1.0, places=7)

    def test_missing_measurements_are_not_imputed_as_observations(self):
        raw, race = fixture(2)
        raw[0, :, 67] = np.nan
        raw[0, :, 55] = np.nan
        features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(features[1, :, 4:6], 0.0, atol=1e-7)
        np.testing.assert_allclose(features[1, :, 7], 0.0)

    def test_three_column_targets_match_combo_targets(self):
        raw, race = fixture(2)
        combo_features = build(
            raw,
            race,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        column_features = build(
            raw,
            race,
            [[0, 1, 2], [0, 1, 2]],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(column_features, combo_features)

    def test_candidate_projection_follows_trifecta_order(self):
        runner = np.zeros((1, 6, len(RUNNER_FEATURE_NAMES)), dtype=np.float32)
        runner[0, :, 0] = np.arange(10, 16)
        projected = candidate_features(runner, np.asarray([0]))
        width = len(RUNNER_FEATURE_NAMES)
        np.testing.assert_allclose(projected[0, 0, :width], runner[0, A[0]])
        np.testing.assert_allclose(projected[0, 0, width:2 * width], runner[0, B[0]])
        np.testing.assert_allclose(projected[0, 0, 2 * width:3 * width], runner[0, C[0]])

    def test_v280_loader_preserves_parent_and_v270_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = {}
            for offset, fold in enumerate(("d6", "d7", "d8")):
                path = Path(temp) / f"{fold}.npz"
                probability = np.full((1, 120), 1.0 / 120.0, dtype=np.float32)
                v270 = probability.copy()
                v270[0, 0] += 0.001
                v270[0, 1:] -= 0.001 / 119.0
                np.savez_compressed(
                    path,
                    standalone=probability,
                    v270=v270,
                    v269=probability,
                    v242=probability,
                    v251=probability,
                    race_indices=np.asarray([offset], dtype=np.int64),
                    race_dates=np.asarray([f"2026-01-0{offset + 1}"]),
                    true_combo=np.asarray([0], dtype=np.int64),
                )
                paths[fold] = path
            loaded = load_v280_oof(paths)
        np.testing.assert_allclose(loaded["probability"], 1.0 / 120.0)
        self.assertFalse(np.allclose(loaded["v270"], loaded["probability"]))


if __name__ == "__main__":
    unittest.main()
