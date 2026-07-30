from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "<CODEX_HOME>_deps"))
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v245_tabm_autoregressive import (
    TabMAutoregressive,
    exact_top3_loss,
    predict_distribution,
)


class TabMAutoregressiveTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(24501)
        self.runner_num = torch.randn(4, 6, 7)
        self.runner_cat = torch.stack(
            [
                torch.randint(0, 9, (4, 6)),
                torch.randint(0, 5, (4, 6)),
                torch.randint(0, 8, (4, 6)),
                torch.randint(0, 7, (4, 6)),
            ],
            dim=2,
        )
        self.race_num = torch.randn(4, 3)
        self.race_cat = torch.stack(
            [
                torch.randint(0, 4, (4,)),
                torch.randint(0, 3, (4,)),
            ],
            dim=1,
        )
        self.targets = torch.tensor(
            [[0, 1, 2], [1, 3, 5], [5, 4, 3], [2, 0, 4]]
        )
        self.model = TabMAutoregressive(
            7, 3, [9, 5, 8, 7], [4, 3]
        )

    def test_branches_are_distinct_and_selected_lanes_are_masked(self):
        self.model.eval()
        tokens, context = self.model.encode(
            self.runner_num,
            self.runner_cat,
            self.race_num,
            self.race_cat,
        )
        self.assertEqual(tuple(context.shape), (4, 8, 192))
        self.assertFalse(torch.equal(context[:, 0], context[:, 1]))
        first = self.targets[:, 0]
        second = self.targets[:, 1]
        stage2 = self.model.stage2(tokens, context, first)
        stage3 = self.model.stage3(
            tokens, context, first, second
        )
        rows = torch.arange(4)[:, None]
        branches = torch.arange(8)[None, :]
        self.assertTrue(
            torch.all(stage2[rows, branches, first[:, None]] < -1e8)
        )
        self.assertTrue(
            torch.all(stage3[rows, branches, first[:, None]] < -1e8)
        )
        self.assertTrue(
            torch.all(stage3[rows, branches, second[:, None]] < -1e8)
        )

    def test_loss_backpropagates_and_distribution_is_normalized(self):
        self.model.train()
        tokens, context = self.model.encode(
            self.runner_num,
            self.runner_cat,
            self.race_num,
            self.race_cat,
        )
        loss = exact_top3_loss(
            self.model, tokens, context, self.targets
        )
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        gradients = [
            parameter.grad
            for parameter in self.model.parameters()
            if parameter.requires_grad
        ]
        self.assertTrue(any(
            grad is not None and torch.any(grad != 0)
            for grad in gradients
        ))
        probabilities = predict_distribution(
            self.model,
            (
                self.runner_num,
                self.runner_cat,
                self.race_num,
                self.race_cat,
                self.targets,
            ),
            batch_races=2,
        )
        self.assertEqual(probabilities.shape, (4, 120))
        self.assertTrue(np.all(np.isfinite(probabilities)))
        np.testing.assert_allclose(
            probabilities.sum(axis=1), 1.0, atol=1e-6
        )


if __name__ == "__main__":
    unittest.main()
