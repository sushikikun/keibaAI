import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_v293_large_history_pairwise_ranker_on_v283 import (
    ORDER_I,
    ORDER_J,
    anchored_probability,
    known_pair_indices,
    pair_features,
)


class LargeHistoryPairwiseRankerTests(unittest.TestCase):
    def test_known_pairs_are_exactly_twelve(self):
        pairs = known_pair_indices([0, 1, 2])
        self.assertEqual(tuple(pairs.shape), (12, 2))
        self.assertEqual(len(set(map(tuple, pairs))), 12)

    def test_bottom_three_order_is_never_invented(self):
        pairs = set(map(tuple, known_pair_indices([0, 1, 2])))
        for left in (3, 4, 5):
            for right in (3, 4, 5):
                if left != right:
                    self.assertNotIn((left, right), pairs)

    def test_pair_labels_follow_partial_top3_order(self):
        pairs = set(map(tuple, known_pair_indices([2, 5, 1])))
        self.assertTrue(all((2, lane) in pairs for lane in range(6) if lane != 2))
        self.assertTrue(all((5, lane) in pairs for lane in (0, 1, 3, 4)))
        self.assertTrue(all((1, lane) in pairs for lane in (0, 3, 4)))

    def test_reverse_pair_negates_signed_features_only(self):
        left = np.array([[3.0, np.nan]], dtype=np.float32)
        right = np.array([[1.0, 2.0]], dtype=np.float32)
        context = np.array([[7.0]], dtype=np.float32)
        forward = pair_features(left, right, context)
        reverse = pair_features(right, left, context)
        self.assertEqual(forward[0, 0], -reverse[0, 0])
        self.assertTrue(np.isnan(forward[0, 1]) and np.isnan(reverse[0, 1]))
        self.assertEqual(forward[0, 2], reverse[0, 2])
        self.assertEqual(forward[0, -1], reverse[0, -1])

    def test_all_ordered_prediction_pairs_exist_once(self):
        pairs = list(zip(ORDER_I.tolist(), ORDER_J.tolist()))
        self.assertEqual(len(pairs), 30)
        self.assertEqual(len(set(pairs)), 30)
        self.assertTrue(all(left != right for left, right in pairs))

    def test_fixed_anchor_probability_is_normalized(self):
        rng = np.random.default_rng(3)
        parent = rng.random((5, 120))
        parent /= parent.sum(axis=1, keepdims=True)
        score = rng.normal(size=(5, 6))
        score -= score.mean(axis=1, keepdims=True)
        actual = anchored_probability(parent, score, 0.15, [1.0, 0.5, 0.25])
        self.assertTrue(np.all(actual > 0))
        self.assertTrue(np.allclose(actual.sum(axis=1), 1.0, atol=1e-12))

    def test_zero_runner_score_reproduces_parent(self):
        rng = np.random.default_rng(4)
        parent = rng.random((3, 120))
        parent /= parent.sum(axis=1, keepdims=True)
        actual = anchored_probability(parent, np.zeros((3, 6)), 0.15, [1.0, 0.5, 0.25])
        self.assertTrue(np.allclose(actual, parent, atol=1e-12, rtol=1e-10))


if __name__ == "__main__":
    unittest.main()
