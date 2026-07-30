import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_multidimensional_skill_sidecar_v252 import (
    DIMENSIONS, PER_DIMENSION_FEATURES, ascending_ranks, build_features,
)


def test_ascending_ranks_preserves_ties_and_rejects_missing():
    assert ascending_ranks([0.1, 0.2, 0.2, 0.3, 0.4, 0.5]) == [0, 1, 1, 2, 3, 4]
    assert ascending_ranks([0.1, np.nan, 0.2, 0.3, 0.4, 0.5]) is None


def test_same_day_is_frozen_and_missing_timing_does_not_update():
    racers = np.asarray([
        ["a", "b", "c", "d", "e", "f"],
        ["a", "b", "c", "d", "e", "f"],
        ["a", "b", "c", "d", "e", "f"],
    ], dtype=object)
    finishes = np.asarray([
        [1, 2, 3, 4, 5, 6],
        [6, 5, 4, 3, 2, 1],
        [1, 3, 2, 6, 5, 4],
    ], dtype=np.int8)
    dates = np.asarray([100, 100, 101], dtype=np.int32)
    start = np.asarray([
        [np.nan] * 6,
        [np.nan] * 6,
        [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
    ], dtype=np.float32)
    exhibition = np.asarray([
        [6.8, 6.9, 7.0, 7.1, 7.2, 7.3],
        [7.3, 7.2, 7.1, 7.0, 6.9, 6.8],
        [6.9, 7.0, 7.1, 7.2, 7.3, 7.4],
    ], dtype=np.float32)
    features, summary = build_features(racers, finishes, dates, start, exhibition)
    np.testing.assert_allclose(features[0], features[1])
    assert not np.allclose(features[1, :, : 3 * len(PER_DIMENSION_FEATURES)], features[2, :, : 3 * len(PER_DIMENSION_FEATURES)])
    start_offset = DIMENSIONS.index("start") * len(PER_DIMENSION_FEATURES)
    np.testing.assert_allclose(features[2, :, start_offset + 3], 0.0)
    assert summary["updates_by_dimension"]["start"] == 1
    assert summary["updates_by_dimension"]["exhibition"] == 3
