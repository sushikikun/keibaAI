import unittest

import numpy as np

from train_noodds_raw_v200 import A, B, C
from noodds_v287_course_context_features import (
    DIRECT_PAIR_FEATURE_NAMES,
    RUNNER_FEATURE_NAMES,
    _context_key,
    build_course_context_pairwise_features,
    candidate_features,
)


def combo(first, second, third):
    hits = np.flatnonzero((A == first) & (B == second) & (C == third))
    if len(hits) != 1:
        raise AssertionError("combo lookup failed")
    return int(hits[0])


def fixture(races):
    raw = np.zeros((races, 6, 143), dtype=np.float32)
    raw[:, :, 0] = np.arange(10, 16, dtype=np.float32)
    course = np.zeros((races, 6, 5), dtype=np.float32)
    course[:, :, 0] = np.arange(1, 7, dtype=np.float32)
    available = np.ones(races, dtype=np.uint8)
    return raw, course, available


def build(raw, course, available, targets, dates):
    return build_course_context_pairwise_features(
        raw, course, available,
        np.asarray(targets, dtype=np.int64),
        np.asarray(dates),
        overall_shrinkage=20.0,
        context_shrinkage=10.0,
    )


class CourseContextPairwiseTests(unittest.TestCase):
    def test_same_day_results_are_deferred(self):
        raw, course, available = fixture(3)
        runner, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(1, 0, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(runner[0], runner[1])
        np.testing.assert_allclose(pairwise[0], pairwise[1])
        self.assertGreater(pairwise[2, 0, 1, 1], 0.0)

    def test_context_key_is_canonical_and_signed_by_lower_id(self):
        self.assertEqual(_context_key(10, 20, 1, 5), (10, 20, -4))
        self.assertEqual(_context_key(20, 10, 5, 1), (10, 20, -4))

    def test_context_residual_is_antisymmetric(self):
        raw, course, available = fixture(3)
        _, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        self.assertGreater(pairwise[2, 0, 1, 0], 0.0)
        np.testing.assert_allclose(pairwise[2, 0, 1, 0], -pairwise[2, 1, 0, 0])
        np.testing.assert_allclose(pairwise[2, 0, 1, 1], pairwise[2, 1, 0, 1])

    def test_unknown_context_zero_when_overall_pair_is_known(self):
        raw, course, available = fixture(2)
        course[1, :, 0] = [2, 1, 3, 4, 5, 6]
        runner, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(pairwise[1, 0, 1], 0.0)
        self.assertEqual(runner[1, 0, 3], 0.0)

    def test_both_outside_top3_do_not_update(self):
        raw, course, available = fixture(2)
        _, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        np.testing.assert_allclose(pairwise[1, 3, 4], 0.0)
        self.assertGreater(pairwise[1, 0, 4, 1], 0.0)

    def test_missing_course_does_not_emit_or_update_context(self):
        raw, course, available = fixture(3)
        available[1] = 0
        course[1, :, 0] = 0
        runner, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(1, 0, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        np.testing.assert_allclose(runner[1], 0.0)
        np.testing.assert_allclose(pairwise[1], 0.0)
        np.testing.assert_allclose(pairwise[2, 0, 1, 1], np.log1p(1.0))

    def test_tau20_tau10_hierarchical_residual(self):
        raw, course, available = fixture(2)
        _, pairwise, _ = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        overall_rate = 11.0 / 21.0
        context_rate = (1.0 + 10.0 * overall_rate) / 11.0
        np.testing.assert_allclose(
            pairwise[1, 0, 1, 0], context_rate - overall_rate, rtol=1e-6
        )

    def test_three_column_targets_match_combo_targets(self):
        raw, course, available = fixture(2)
        combo_result = build(
            raw, course, available,
            [combo(0, 1, 2), combo(0, 1, 2)],
            ["2026-01-01", "2026-01-02"],
        )
        column_result = build_course_context_pairwise_features(
            raw, course, available,
            np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int8),
            np.asarray(["2026-01-01", "2026-01-02"]),
            overall_shrinkage=20.0,
            context_shrinkage=10.0,
        )
        np.testing.assert_allclose(column_result[0], combo_result[0])
        np.testing.assert_allclose(column_result[1], combo_result[1])

    def test_candidate_projection_order(self):
        runner = np.zeros((1, 6, len(RUNNER_FEATURE_NAMES)), dtype=np.float32)
        runner[0, :, 0] = np.arange(10, 16)
        pairwise = np.zeros(
            (1, 6, 6, len(DIRECT_PAIR_FEATURE_NAMES)), dtype=np.float32
        )
        pairwise[0, 0, 1] = [0.1, 0.2]
        projected = candidate_features(runner, pairwise, np.asarray([0]))
        width = len(RUNNER_FEATURE_NAMES)
        np.testing.assert_allclose(projected[0, 0, :width], runner[0, A[0]])
        np.testing.assert_allclose(
            projected[0, 0, 3 * width:3 * width + 2], [0.1, 0.2]
        )


if __name__ == "__main__":
    unittest.main()
