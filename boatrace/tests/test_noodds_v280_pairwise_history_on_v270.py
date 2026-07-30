import unittest

import numpy as np

from train_noodds_raw_v200 import A, B, C
from train_noodds_v280_pairwise_history_on_v270 import (
    DIRECT_PAIR_FEATURE_NAMES,
    RUNNER_FEATURE_NAMES,
    build_pairwise_history_features,
    candidate_features,
)


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
    return build_pairwise_history_features(
        raw,
        course,
        available,
        np.asarray(targets, dtype=np.int64),
        np.asarray(dates),
        shrinkage=20.0,
    )


class PairwiseHistoryTests(unittest.TestCase):
    def test_same_day_results_do_not_change_later_same_day_features(self):
        raw, course, available = fixture(3)
        runner, pairwise, _ = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(1, 0, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(runner[0], runner[1])
        np.testing.assert_allclose(pairwise[0], pairwise[1])
        self.assertEqual(pairwise[2, 0, 1, 2], 1.0)
        np.testing.assert_allclose(pairwise[2, 0, 1, 1], np.log1p(2.0))

    def test_pair_residual_is_antisymmetric(self):
        raw, course, available = fixture(2)
        _, pairwise, _ = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        self.assertGreater(pairwise[1, 0, 1, 0], 0.0)
        np.testing.assert_allclose(
            pairwise[1, 0, 1, 0], -pairwise[1, 1, 0, 0]
        )
        np.testing.assert_allclose(pairwise[1, 0, 1, 1:], pairwise[1, 1, 0, 1:])

    def test_unknown_pair_has_zero_residual_count_and_known_flag(self):
        raw, course, available = fixture(2)
        raw[1, :, 0] += 10
        _, pairwise, _ = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(pairwise[1], 0.0)

    def test_two_outside_top3_racers_do_not_update(self):
        raw, course, available = fixture(2)
        _, pairwise, _ = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(pairwise[1, 3, 4], 0.0)
        self.assertEqual(pairwise[1, 0, 4, 2], 1.0)

    def test_missing_course_keeps_pair_history_but_zeroes_interaction(self):
        raw, course, available = fixture(2)
        available[1] = 0
        course[1, :, 0] = 0
        runner, pairwise, _ = build(
            raw,
            course,
            available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        self.assertEqual(pairwise[1, 0, 1, 2], 1.0)
        np.testing.assert_allclose(runner[1, :, 6:], 0.0)

    def test_three_column_targets_match_combo_targets(self):
        raw, course, available = fixture(2)
        from_combo = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        from_columns = build_pairwise_history_features(
            raw, course, available,
            np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int8),
            np.asarray(["2026-01-01", "2026-01-02"]),
            shrinkage=20.0,
        )
        np.testing.assert_allclose(from_columns[0], from_combo[0])
        np.testing.assert_allclose(from_columns[1], from_combo[1])

    def test_candidate_projection_uses_runner_and_direct_pair_order(self):
        runner = np.zeros((1, 6, len(RUNNER_FEATURE_NAMES)), dtype=np.float32)
        runner[0, :, 0] = np.arange(10, 16)
        pairwise = np.zeros((1, 6, 6, 3), dtype=np.float32)
        pairwise[0, 0, 1] = [0.1, 0.2, 1.0]
        course = np.zeros((1, 6, 5), dtype=np.float32)
        course[0, :, 0] = np.arange(1, 7)
        projected = candidate_features(runner, pairwise, course, np.asarray([0]))
        width = len(RUNNER_FEATURE_NAMES)
        direct_width = len(DIRECT_PAIR_FEATURE_NAMES)
        np.testing.assert_allclose(projected[0, 0, :width], runner[0, A[0]])
        offset = 3 * width
        expected = [0.1, 0.2, 1.0, -1.0, -0.1]
        np.testing.assert_allclose(
            projected[0, 0, offset:offset + direct_width], expected,
            rtol=1e-6, atol=1e-7,
        )


if __name__ == "__main__":
    unittest.main()
