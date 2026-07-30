import math
import unittest

import numpy as np
import torch

from train_noodds_raw_v230_exact_top3_pl import trifecta_probs
from train_noodds_raw_v233_set_attention import (
    SetAttentionModel,
    exact_top3_loss,
)


class SetAttentionV233Tests(unittest.TestCase):
    def test_uniform_loss_matches_six_five_four_choices(self):
        scores = [torch.zeros((3, 6)) for _ in range(3)]
        targets = torch.tensor(
            [[0, 1, 2], [5, 4, 3], [2, 0, 5]],
            dtype=torch.long,
        )

        loss = exact_top3_loss(scores, targets)

        expected = (math.log(6) + math.log(5) + math.log(4)) / 3
        self.assertAlmostEqual(float(loss), expected, places=6)

    def test_model_outputs_three_lane_score_matrices(self):
        model = SetAttentionModel(7, 5)
        runner = torch.randn(4, 6, 7)
        race = torch.randn(4, 5)
        venue = torch.tensor([1, 2, 3, 4])
        weather = torch.tensor([1, 1, 2, 2])

        scores = model(runner, race, venue, weather)

        self.assertEqual(len(scores), 3)
        self.assertTrue(all(value.shape == (4, 6) for value in scores))
        self.assertTrue(all(torch.isfinite(value).all() for value in scores))

        probs = trifecta_probs(
            [value.detach().numpy() for value in scores], 1.0
        )
        np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
