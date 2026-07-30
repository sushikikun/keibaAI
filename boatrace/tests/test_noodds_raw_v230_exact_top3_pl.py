import unittest

import numpy as np

from train_noodds_raw_v230_exact_top3_pl import (
    conditional_softmax_objective,
    stage_labels,
    trifecta_probs,
)


class ExactTop3PlTests(unittest.TestCase):
    def test_stage_labels_exclude_prior_finishers(self):
        targets = np.asarray([[0, 2, 4], [5, 3, 1]], dtype=np.int64)

        first = stage_labels(targets, 0)
        second = stage_labels(targets, 1)
        third = stage_labels(targets, 2)

        self.assertEqual(first[0, 0], 1.0)
        self.assertEqual(second[0, 0], -1.0)
        self.assertEqual(second[0, 2], 1.0)
        self.assertEqual(third[0, 0], -1.0)
        self.assertEqual(third[0, 2], -1.0)
        self.assertEqual(third[0, 4], 1.0)

    def test_conditional_objective_conserves_gradient(self):
        targets = np.asarray([[0, 2, 4], [5, 3, 1]], dtype=np.int64)
        labels = stage_labels(targets, 2)
        predictions = np.zeros(labels.size, dtype=np.float64)

        gradient, hessian = conditional_softmax_objective(
            labels.ravel(), predictions
        )
        gradient = gradient.reshape(-1, 6)
        hessian = hessian.reshape(-1, 6)

        np.testing.assert_allclose(gradient.sum(axis=1), 0.0, atol=1e-12)
        self.assertEqual(gradient[0, 0], 0.0)
        self.assertEqual(gradient[0, 2], 0.0)
        self.assertEqual(hessian[0, 0], 0.0)
        self.assertTrue((hessian[labels >= 0] > 0.0).all())

    def test_trifecta_probabilities_are_exactly_normalized(self):
        rng = np.random.default_rng(230)
        scores = [
            rng.normal(size=(5, 6)),
            rng.normal(size=(5, 6)),
            rng.normal(size=(5, 6)),
        ]

        probs = trifecta_probs(scores, 1.4)

        self.assertEqual(probs.shape, (5, 120))
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-12)
        self.assertTrue((probs > 0.0).all())


if __name__ == "__main__":
    unittest.main()
