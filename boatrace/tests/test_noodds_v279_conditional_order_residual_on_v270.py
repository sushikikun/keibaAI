import unittest

import numpy as np

from train_noodds_v279_conditional_order_residual_on_v270 import (
    build_stage1_matrix,
    build_stage2_matrix,
    build_stage3_matrix,
    compose_conditionals,
    conditional_softmax,
    group_softmax_objective,
    parent_conditionals,
    predict_head_set,
    remaining_after_first,
    remaining_after_pair,
)


class ZeroModel:
    def predict(self, matrix):
        return np.zeros(len(matrix), dtype=np.float64)


class ConditionalOrderResidualTests(unittest.TestCase):
    def test_parent_factorization_reconstructs_all_120_probabilities(self):
        rng = np.random.default_rng(27901)
        base = rng.dirichlet(np.ones(120), size=7)
        p1, p2, p3 = parent_conditionals(base)
        reconstructed = compose_conditionals(p1, p2, p3)

        np.testing.assert_allclose(reconstructed, base, rtol=1e-11, atol=1e-13)
        np.testing.assert_allclose(p1.sum(axis=1), 1.0)
        for first in range(6):
            np.testing.assert_allclose(p2[:, first].sum(axis=1), 1.0)

    def test_zero_residual_softmax_preserves_parent_conditional(self):
        base = np.asarray([[0.1, 0.2, 0.3, 0.15, 0.25]], dtype=np.float64)
        adjusted = conditional_softmax(base, np.zeros_like(base))
        np.testing.assert_allclose(adjusted, base)

    def test_candidate_masks_exclude_previous_lanes(self):
        first = np.asarray([0, 5])
        second = np.asarray([1, 3])
        stage2 = remaining_after_first(first)
        stage3 = remaining_after_pair(first, second)

        self.assertEqual(stage2.shape, (2, 5))
        self.assertEqual(stage3.shape, (2, 4))
        self.assertNotIn(0, stage2[0])
        self.assertNotIn(5, stage2[1])
        self.assertNotIn(0, stage3[0])
        self.assertNotIn(1, stage3[0])
        self.assertNotIn(5, stage3[1])
        self.assertNotIn(3, stage3[1])

    def test_stage_matrices_project_candidate_and_context_runners(self):
        runner = np.zeros((2, 6, 3), dtype=np.float32)
        for race in range(2):
            for lane in range(6):
                runner[race, lane] = [race, lane, 10 * race + lane]
        race = np.asarray([[1, 2], [3, 4]], dtype=np.float32)
        first = np.asarray([0, 5])
        second = np.asarray([1, 3])

        x1 = build_stage1_matrix(runner, race)
        x2, c2 = build_stage2_matrix(runner, race, first)
        x3, c3 = build_stage3_matrix(runner, race, first, second)

        self.assertEqual(x1.shape, (12, 6))
        self.assertEqual(x2.shape, (10, 10))
        self.assertEqual(x3.shape, (8, 14))
        np.testing.assert_allclose(x2[0, 1:4], runner[0, c2[0, 0]])
        np.testing.assert_allclose(x2[0, 7:10], runner[0, first[0]])
        np.testing.assert_allclose(x3[0, 1:4], runner[0, c3[0, 0]])
        np.testing.assert_allclose(x3[0, 7:10], runner[0, first[0]])
        np.testing.assert_allclose(x3[0, 11:14], runner[0, second[0]])

    def test_group_objective_has_zero_sum_gradient_per_race(self):
        target = np.eye(5, dtype=np.float64)[[1, 3]]
        prediction = np.zeros_like(target)
        gradient, hessian = group_softmax_objective(
            target.ravel(), prediction.ravel(), 5
        )
        np.testing.assert_allclose(
            gradient.reshape(-1, 5).sum(axis=1),
            0.0,
            atol=1e-12,
        )
        self.assertTrue(np.all(hessian > 0.0))

    def test_zero_head_models_reproduce_v270_after_all_context_inference(self):
        rng = np.random.default_rng(27902)
        base = rng.dirichlet(np.ones(120), size=3)
        data = {
            "base": base,
            "runner": rng.normal(size=(3, 6, 26)).astype(np.float32),
            "race": rng.normal(size=(3, 17)).astype(np.float32),
        }
        models = {"stage1": ZeroModel(), "stage2": ZeroModel(), "stage3": ZeroModel()}
        predicted = predict_head_set(models, data, residual_scale=1.0)
        np.testing.assert_allclose(predicted, base, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(predicted.sum(axis=1), 1.0)


if __name__ == "__main__":
    unittest.main()
