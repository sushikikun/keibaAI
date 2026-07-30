from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "<CODEX_HOME>_deps"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_racer_sequence_sidecar_v246 import (
    FEATURE_NAMES,
    build_sequences,
)


class RacerSequenceSidecarV246Tests(unittest.TestCase):
    def test_same_day_results_are_frozen_and_history_is_right_aligned(self):
        racers = np.asarray(
            [[f"r{i}" for i in range(6)]] * 3,
            dtype=object,
        )
        observations = {
            "racers": racers,
            "finishes": np.asarray(
                [
                    [1, 2, 3, 4, 5, 6],
                    [6, 5, 4, 3, 2, 1],
                    [2, 1, 4, 3, 6, 5],
                ],
                dtype=np.int8,
            ),
            "start_st": np.full((3, 6), 0.12, dtype=np.float32),
            "start_missing": np.zeros((3, 6), dtype=np.float32),
            "exhibition": np.full(
                (3, 6), 6.75, dtype=np.float32
            ),
            "exhibition_missing": np.zeros(
                (3, 6), dtype=np.float32
            ),
            "venues": np.asarray(["01", "01", "02"], dtype=object),
            "race_numbers": np.asarray([1, 2, 3], dtype=np.int8),
        }
        features, mask, summary = build_sequences(
            np.asarray([100, 101, 101], dtype=np.int32),
            observations,
            sequence_length=12,
        )
        self.assertFalse(mask[0].any())
        np.testing.assert_array_equal(mask[1], mask[2])
        self.assertTrue(np.all(mask[1, :, -1]))
        self.assertFalse(np.any(mask[1, :, :-1]))
        # Both day-101 races see only day 100, never each other.
        np.testing.assert_allclose(
            features[1, :, -1, :-1],
            features[2, :, -1, :-1],
        )
        same_venue = FEATURE_NAMES.index("same_venue")
        np.testing.assert_array_equal(
            features[1, :, -1, same_venue], 1.0
        )
        np.testing.assert_array_equal(
            features[2, :, -1, same_venue], 0.0
        )
        self.assertEqual(summary["mean_history_length"], 2 / 3)

    def test_missing_past_measurements_use_explicit_indicators(self):
        observations = {
            "racers": np.asarray(
                [[f"a{i}" for i in range(6)]] * 2,
                dtype=object,
            ),
            "finishes": np.zeros((2, 6), dtype=np.int8),
            "start_st": np.zeros((2, 6), dtype=np.float32),
            "start_missing": np.ones((2, 6), dtype=np.float32),
            "exhibition": np.zeros((2, 6), dtype=np.float32),
            "exhibition_missing": np.ones(
                (2, 6), dtype=np.float32
            ),
            "venues": np.asarray(["01", "01"], dtype=object),
            "race_numbers": np.asarray([1, 2], dtype=np.int8),
        }
        features, mask, _summary = build_sequences(
            np.asarray([200, 201], dtype=np.int32),
            observations,
            sequence_length=12,
        )
        self.assertTrue(np.all(mask[1, :, -1]))
        for name in (
            "past_finish_missing",
            "past_start_st_missing",
            "past_exhibition_missing",
        ):
            column = FEATURE_NAMES.index(name)
            np.testing.assert_array_equal(
                features[1, :, -1, column], 1.0
            )


if __name__ == "__main__":
    unittest.main()
