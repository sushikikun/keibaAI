from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v213_censored_listwise import censored_relevance


class CensoredListwiseV213Tests(unittest.TestCase):
    def test_top_three_order_and_tied_tail(self):
        targets = np.asarray([[0, 2, 5], [3, 1, 4]], dtype=np.int8)
        relevance = censored_relevance(targets)
        np.testing.assert_array_equal(
            relevance,
            np.asarray(
                [
                    [3, 0, 2, 0, 0, 1],
                    [0, 2, 0, 3, 1, 0],
                ],
                dtype=np.int8,
            ),
        )

    def test_rejects_invalid_lane(self):
        with self.assertRaises(ValueError):
            censored_relevance(
                np.asarray([[0, 1, 6]], dtype=np.int8)
            )


if __name__ == "__main__":
    unittest.main()
