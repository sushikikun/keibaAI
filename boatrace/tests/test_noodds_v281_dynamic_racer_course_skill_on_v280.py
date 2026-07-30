import tempfile
import unittest
from pathlib import Path

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_noodds_v281_dynamic_racer_course_skill_on_v280 import (
    RUNNER_FEATURE_NAMES,
    build_dynamic_racer_course_features,
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
    course = np.zeros((races, 6, 5), dtype=np.float32)
    course[:, :, 0] = np.arange(1, 7, dtype=np.float32)
    available = np.ones(races, dtype=np.uint8)
    return raw, course, available


def build(raw, course, available, targets, dates):
    return build_dynamic_racer_course_features(
        raw,
        course,
        available,
        np.asarray(targets, dtype=np.int64),
        np.asarray(dates),
        initial_global_rates=INITIAL,
        overall_shrinkage=50.0,
        racer_course_shrinkage=20.0,
    )


class DynamicRacerCourseSkillOnV280Tests(unittest.TestCase):
    def test_same_day_results_do_not_change_later_same_day_features(self):
        raw, course, available = fixture(3)
        features = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(5, 4, 3), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-01", "2026-01-02"],
        )

        np.testing.assert_allclose(features[0], features[1])
        np.testing.assert_allclose(features[0, :, :4], 0.0)
        np.testing.assert_allclose(features[0, :, 4], 1.0)
        np.testing.assert_allclose(features[2, :, 0], np.log1p(2.0))

    def test_hierarchical_shrinkage_matches_fixed_formula(self):
        raw, course, available = fixture(2)
        features = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )

        racer_overall = (np.ones(3) + 50.0 * INITIAL) / 51.0
        racer_course = (np.ones(3) + 20.0 * racer_overall) / 21.0
        np.testing.assert_allclose(features[1, 0, 0], np.log1p(1.0))
        np.testing.assert_allclose(
            features[1, 0, 1:4], racer_course - racer_overall, rtol=1e-6
        )

    def test_missing_course_is_zero_and_does_not_update_course_state(self):
        raw, course, available = fixture(2)
        available[0] = 0
        course[0, :, 0] = 0
        features = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )

        np.testing.assert_allclose(features[0], 0.0)
        np.testing.assert_allclose(features[1, :, 0], 0.0)
        np.testing.assert_allclose(features[1, :, 1:4], 0.0, atol=1e-7)
        np.testing.assert_allclose(features[1, :, 4], 1.0)

    def test_three_column_targets_match_combo_targets(self):
        raw, course, available = fixture(2)
        combo_features = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        column_features = build_dynamic_racer_course_features(
            raw,
            course,
            available,
            np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int8),
            np.asarray(["2026-01-01", "2026-01-02"]),
            initial_global_rates=INITIAL,
            overall_shrinkage=50.0,
            racer_course_shrinkage=20.0,
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
