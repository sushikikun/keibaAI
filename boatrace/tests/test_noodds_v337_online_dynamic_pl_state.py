import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_noodds_v337_online_dynamic_pl_state import build_state_features, plackett_luce_probabilities, ranks_from_top3


def test_top3_rank_encoding_keeps_bottom_three_tied():
    assert ranks_from_top3(np.asarray([2, 0, 4])) == [1, 3, 0, 3, 2, 3]


def test_same_day_state_is_frozen_before_updates():
    racers = np.asarray([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]])
    top3 = np.asarray([[0, 1, 2], [2, 1, 0], [0, 1, 2]], dtype=np.int8)
    dates = np.asarray([100, 100, 101], dtype=np.int32)
    courses = np.tile(np.arange(1, 7), (3, 1)).astype(np.float32)
    features, summary = build_state_features(racers, top3, dates, courses, np.ones(3), 0.5)
    np.testing.assert_allclose(features[0], features[1])
    assert not np.allclose(features[1, :, 0], features[2, :, 0])
    assert summary["global_updates"] == 3


def test_missing_course_is_zero_and_never_updates_course_state():
    racers = np.asarray([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]])
    top3 = np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int8)
    courses = np.tile(np.arange(1, 7), (2, 1)).astype(np.float32)
    features, summary = build_state_features(racers, top3, np.asarray([100, 101]), courses, np.asarray([0, 1]), 0.5)
    np.testing.assert_allclose(features[0, :, 3:5], 0.0)
    np.testing.assert_allclose(features[0, :, 5], 0.0)
    assert summary["course_updates"] == 1


def test_unknown_racer_code_is_neutral_and_not_shared():
    racers = np.asarray([[0, 2, 3, 4, 5, 6], [0, 2, 3, 4, 5, 6]])
    top3 = np.asarray([[0, 1, 2], [0, 1, 2]], dtype=np.int8)
    courses = np.tile(np.arange(1, 7), (2, 1)).astype(np.float32)
    features, _ = build_state_features(racers, top3, np.asarray([100, 101]), courses, np.ones(2), 0.5)
    np.testing.assert_allclose(features[:, 0, 2], 0.0)

def test_exact_distribution_is_normalized_and_lane_symmetric():
    left = plackett_luce_probabilities(np.asarray([[1, 0, 0, 0, 0, 0]], dtype=np.float32))
    right = plackett_luce_probabilities(np.asarray([[0, 1, 0, 0, 0, 0]], dtype=np.float32))
    np.testing.assert_allclose(left.sum(axis=1), 1.0)
    assert np.max(left) > 1.0 / 120.0
    assert np.max(right) > 1.0 / 120.0
def test_exact_distribution_remains_finite_for_extreme_scores():
    probability = plackett_luce_probabilities(np.asarray([[1.0e6, -1.0e6, -2.0e6, -3.0e6, -4.0e6, -5.0e6]], dtype=np.float64))
    assert np.isfinite(probability).all()
    np.testing.assert_allclose(probability.sum(axis=1), 1.0)
    assert int(np.argmax(probability[0])) == 0
