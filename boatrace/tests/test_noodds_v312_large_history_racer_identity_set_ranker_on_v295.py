import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v311_large_history_identity_set_ranker_on_v295 as v311
import train_noodds_v312_large_history_racer_identity_set_ranker_on_v295 as v312


def _config():
    return json.loads(v312.PREREGISTRATION.read_text(encoding="utf-8"))


def test_preregistration_fixes_racer_only_before_results():
    cfg = _config()
    assert cfg["model_id"] == v312.MODEL_ID
    assert cfg["identity_features"]["runner_columns"] == {"racer_code": 0}
    assert cfg["identity_features"]["embedding_widths"] == {"racer_code": 16}
    assert cfg["training"]["seed"] == 31201
    assert cfg["training"]["search"] is False
    assert cfg["anchoring"]["gamma_bounds"] == [0.0, 0.25]


def test_wrapper_configures_only_stable_racer_identity():
    v312.configure_v311_core()
    assert v311.MODEL_ID == v312.MODEL_ID
    assert v311.IDENTITY_COLUMNS == (0,)
    assert v311.IDENTITY_NAMES == ("racer_code",)


def test_racer_vocabulary_is_fold_training_only():
    v312.configure_v311_core()
    raw = np.asarray(
        [[[10]] * 6, [[20]] * 6, [[999]] * 6],
        dtype=np.float64,
    )
    vocabulary = v311.fit_identity_vocabulary(raw, np.asarray([0, 1]))
    encoded, audit = v311.encode_identity(
        raw, np.asarray([2]), vocabulary
    )
    assert 999 not in vocabulary[0]
    assert np.all(encoded == 0)
    assert audit["racer_code"]["unknown_rate"] == 1.0


def test_racer_only_model_outputs_normalized_120_probabilities():
    v312.configure_v311_core()
    cfg = {
        "embedding_widths": {"racer_code": 4},
    }
    architecture = {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }
    model = v311.IdentityStagewiseSetRanker(
        5, 3, [20], cfg, architecture
    )
    model.eval()
    runner = torch.randn(2, 6, 5)
    race = torch.randn(2, 3)
    identity = torch.randint(0, 20, (2, 6, 1))
    probability = v311.v310.joint_probabilities(
        model(runner, race, identity)
    )
    assert probability.shape == (2, 120)
    assert torch.allclose(
        probability.sum(dim=1), torch.ones(2), atol=1e-6
    )


def test_policy_keeps_v295_parent_and_forbids_leakage():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v295_large_history_exact_top3_with_proven_history_on_v283"
    )
    assert cfg["policy"]["same_day_validation_result_used"] is False
    assert cfg["policy"]["future_information_used"] is False
    assert cfg["policy"]["posthoc_search"] is False
