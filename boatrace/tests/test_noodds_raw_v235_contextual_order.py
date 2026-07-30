from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v235_contextual_order import (
    build_context_matrix,
    context_layout,
    grouped_softmax_objective,
    predict_contextual_trifecta,
    remaining_candidates,
)


class ZeroModel:
    @property
    def booster_(self):
        return self

    def predict(self, matrix):
        return np.zeros(len(matrix), dtype=np.float64)


class NooddsRawV235ContextualOrderTests(unittest.TestCase):
    def test_remaining_candidates_preserve_lane_order(self):
        first = np.array([0, 5])
        second = np.array([2, 1])
        np.testing.assert_array_equal(
            remaining_candidates(first),
            np.array([[1, 2, 3, 4, 5], [0, 1, 2, 3, 4]]),
        )
        np.testing.assert_array_equal(
            remaining_candidates(first, second),
            np.array([[1, 3, 4, 5], [0, 2, 3, 4]]),
        )

    def test_context_matrix_contains_selected_and_difference(self):
        block = np.zeros((1, 6, 3), dtype=np.float32)
        block[0, :, 0] = np.arange(6)
        block[0, :, 1] = np.arange(10, 16)
        block[0, :, 2] = 99
        layout = context_layout(
            ["lane_code", "strength", "race_value"],
            [0],
            ["lane_code", "strength"],
        )
        matrix, candidates = build_context_matrix(
            block, np.array([1]), layout
        )
        self.assertEqual(matrix.shape, (5, 6))
        np.testing.assert_array_equal(candidates, [[0, 2, 3, 4, 5]])
        np.testing.assert_array_equal(matrix[:, 3], 1)
        np.testing.assert_array_equal(matrix[:, 4], 11)
        np.testing.assert_array_equal(matrix[:, 5], [-1, 1, 2, 3, 4])

    def test_grouped_objective_gradient_sums_to_zero(self):
        objective = grouped_softmax_objective(4)
        labels = np.array([1, 0, 0, 0, 0, 0, 1, 0], dtype=float)
        scores = np.zeros(8, dtype=float)
        gradient, hessian = objective(labels, scores)
        np.testing.assert_allclose(gradient.reshape(-1, 4).sum(axis=1), 0.0)
        self.assertTrue(np.all(hessian > 0))

    def test_zero_scores_produce_uniform_trifecta_distribution(self):
        race_matrix = np.zeros((2, 6, 3), dtype=np.float32)
        race_matrix[:, :, 0] = np.arange(6)
        layout = context_layout(
            ["lane_code", "strength", "race_value"],
            [0],
            ["lane_code", "strength"],
        )
        probs = predict_contextual_trifecta(
            (ZeroModel(), ZeroModel(), ZeroModel()),
            race_matrix,
            np.array([0, 1], dtype=np.int32),
            layout,
        )
        np.testing.assert_allclose(probs.sum(axis=1), 1.0)
        np.testing.assert_allclose(probs, 1.0 / 120.0)


if __name__ == "__main__":
    unittest.main()
