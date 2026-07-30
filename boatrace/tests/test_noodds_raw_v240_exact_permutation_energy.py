from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v240_exact_permutation_energy import (
    BOTTOM_LOSS_WEIGHT,
    ExactPermutationEnergyModel,
    PERMUTATIONS,
    TOP3_TO_PERMUTATIONS,
    TRANSITION_RANK,
    combo_indices_from_targets,
    energies_to_trifecta,
    exact_permutation_loss,
    full_permutation_labels,
)


class NooddsRawV240ExactPermutationEnergyTests(unittest.TestCase):
    def test_permutation_and_top3_partition_are_exact(self):
        self.assertEqual(PERMUTATIONS.shape, (720, 6))
        self.assertEqual(
            len({tuple(row) for row in PERMUTATIONS.tolist()}), 720
        )
        self.assertEqual(TOP3_TO_PERMUTATIONS.shape, (120, 6))
        flattened = np.sort(TOP3_TO_PERMUTATIONS.ravel())
        np.testing.assert_array_equal(flattened, np.arange(720))

    def test_full_finish_positions_map_to_true_permutation(self):
        positions = np.array(
            [
                [1, 2, 3, 4, 5, 6],
                [6, 5, 4, 3, 2, 1],
                [1, 2, 3, 0, 0, 0],
            ],
            dtype=np.int8,
        )
        labels = full_permutation_labels(
            positions, np.array([True, True, False])
        )
        np.testing.assert_array_equal(
            PERMUTATIONS[labels[:2]],
            np.array(
                [[0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0]]
            ),
        )
        self.assertEqual(labels[2], -1)

    def test_uniform_energy_has_exact_analytic_loss(self):
        energies = torch.zeros((2, 720), dtype=torch.float32)
        targets = torch.tensor(
            [[0, 1, 2], [5, 4, 3]], dtype=torch.long
        )
        combos = combo_indices_from_targets(targets)
        full = torch.tensor([0, -1], dtype=torch.long)
        total, top3, bottom = exact_permutation_loss(
            energies, combos, full
        )
        self.assertAlmostEqual(float(top3), math.log(120.0), places=5)
        self.assertAlmostEqual(float(bottom), math.log(6.0), places=5)
        self.assertAlmostEqual(
            float(total),
            math.log(120.0) + BOTTOM_LOSS_WEIGHT * math.log(6.0),
            places=5,
        )

    def test_uniform_energy_produces_uniform_trifecta(self):
        probabilities = energies_to_trifecta(
            torch.zeros((3, 720), dtype=torch.float32)
        )
        np.testing.assert_allclose(
            probabilities.detach().numpy(),
            np.full((3, 120), 1.0 / 120.0),
            rtol=1.0e-6,
            atol=1.0e-7,
        )
        np.testing.assert_allclose(
            probabilities.sum(dim=1).detach().numpy(), 1.0
        )

    def test_model_outputs_finite_energy_for_all_permutations(self):
        torch.manual_seed(1)
        model = ExactPermutationEnergyModel(4, 3)
        model.eval()
        with torch.no_grad():
            energies = model(
                torch.zeros((2, 6, 4), dtype=torch.float32),
                torch.zeros((2, 3), dtype=torch.float32),
                torch.zeros(2, dtype=torch.long),
                torch.zeros(2, dtype=torch.long),
            )
        self.assertEqual(tuple(energies.shape), (2, 720))
        self.assertTrue(bool(torch.isfinite(energies).all()))

    def test_vectorized_energy_matches_reference_indexing(self):
        torch.manual_seed(2)
        model = ExactPermutationEnergyModel(4, 3)
        model.eval()
        runner = torch.randn((2, 6, 4))
        race = torch.randn((2, 3))
        venue = torch.zeros(2, dtype=torch.long)
        weather = torch.zeros(2, dtype=torch.long)
        with torch.no_grad():
            actual = model(runner, race, venue, weather)
            hidden = model.encode(runner, race, venue, weather)
            position = model.position_head(hidden)
            expected = torch.zeros_like(actual)
            for finish_position in range(6):
                boat = model.permutations[:, finish_position]
                expected += position[:, boat, finish_position]
            left = model.transition_left(hidden).reshape(
                2, 6, 5, TRANSITION_RANK
            ).permute(0, 2, 1, 3)
            right = model.transition_right(hidden).reshape(
                2, 6, 5, TRANSITION_RANK
            ).permute(0, 2, 1, 3)
            pair = torch.einsum(
                "btir,btjr->btij", left, right
            ) / math.sqrt(TRANSITION_RANK)
            for transition in range(5):
                first = model.permutations[:, transition]
                second = model.permutations[:, transition + 1]
                expected += pair[:, transition, first, second]
        torch.testing.assert_close(actual, expected)

if __name__ == "__main__":
    unittest.main()
