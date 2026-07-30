from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_noodds_raw_v242_openskill_contextual import (
    append_runner_features,
    load_skill_sidecar,
)


class NooddsRawV242OpenSkillContextualTests(unittest.TestCase):
    def test_append_preserves_race_lane_alignment(self):
        base = np.arange(12, dtype=np.float32).reshape(6, 2)
        skill = np.arange(18, dtype=np.float32).reshape(1, 6, 3)
        result = append_runner_features(base, skill)
        self.assertEqual(result.shape, (6, 5))
        np.testing.assert_array_equal(result[:, :2], base)
        np.testing.assert_array_equal(result[:, 2:], skill[0])

    def test_append_rejects_row_mismatch(self):
        with self.assertRaisesRegex(ValueError, "base rows"):
            append_runner_features(
                np.zeros((5, 2), dtype=np.float32),
                np.zeros((1, 6, 3), dtype=np.float32),
            )

    def test_load_sidecar_checks_feature_order_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ["mu", "sigma"]
            values = np.ones((2, 6, 2), dtype=np.float32)
            np.save(root / "runner_skill_features.npy", values)
            (root / "manifest.json").write_text(
                json.dumps({
                    "feature_names": names,
                    "shape": list(values.shape),
                }),
                encoding="utf-8",
            )
            loaded, manifest = load_skill_sidecar(root, 2, names)
            np.testing.assert_array_equal(loaded, values)
            self.assertEqual(manifest["feature_names"], names)

    def test_load_sidecar_rejects_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            values = np.ones((1, 6, 1), dtype=np.float32)
            values[0, 0, 0] = np.nan
            np.save(root / "runner_skill_features.npy", values)
            (root / "manifest.json").write_text(
                json.dumps({"feature_names": ["mu"], "shape": [1, 6, 1]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_skill_sidecar(root, 1, ["mu"])
