import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v315_large_history_racer_identity_seed_ensemble_on_v312 as v315
import audit_noodds_parent_family_v314 as v314


def _config():
    return json.loads(v315.PREREGISTRATION.read_text(encoding="utf-8"))


def test_preregistration_freezes_three_sequential_equal_weight_members():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["ensemble"]["members"] == 3
    assert cfg["ensemble"]["seeds"] == [31501, 31502, 31503]
    assert cfg["ensemble"]["execution"].startswith("strictly sequential")
    assert np.isclose(sum(cfg["ensemble"]["weights"]), 1.0)
    assert cfg["screen_protocol"].endswith(
        "noodds_candidate_acceleration_v4_matched_v312.json"
    )
    assert cfg["final_protocol"].endswith("noodds_evaluation_protocol_v9.json")


def test_geometric_mean_is_normalized_and_member_order_invariant():
    rng = np.random.default_rng(315)
    members = rng.random((3, 5, 120))
    members /= members.sum(axis=2, keepdims=True)
    weights = np.full(3, 1.0 / 3.0)
    combined = v315.geometric_mean_probabilities(members, weights)
    reversed_combined = v315.geometric_mean_probabilities(
        members[::-1], weights[::-1]
    )
    assert combined.shape == (5, 120)
    assert np.allclose(combined.sum(axis=1), 1.0)
    assert np.allclose(combined, reversed_combined)


def test_geometric_mean_reproduces_identical_member():
    rng = np.random.default_rng(316)
    member = rng.random((4, 120))
    member /= member.sum(axis=1, keepdims=True)
    combined = v315.geometric_mean_probabilities(
        np.stack([member, member, member]), [1 / 3, 1 / 3, 1 / 3]
    )
    assert np.allclose(combined, member)


def test_geometric_mean_rejects_invalid_weights():
    member = np.full((3, 1, 120), 1.0 / 120)
    with pytest.raises(ValueError, match="sum to one"):
        v315.geometric_mean_probabilities(member, [0.5, 0.5, 0.5])


def test_members_train_strictly_sequentially_and_are_saved(tmp_path, monkeypatch):
    calls = []

    def fake_train(
        runner_numeric,
        race_numeric,
        identity_raw,
        target_lanes,
        train_indices,
        validation_indices,
        prereg,
        mode,
        fold,
        model_path,
    ):
        seed = prereg["training"]["seed"]
        calls.append(seed)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"seed": seed}, model_path)
        probability = np.full((len(validation_indices), 120), 1.0 / 120)
        return probability, {"seed_seen": seed}

    monkeypatch.setattr(v315, "_BASE_TRAIN_AND_PREDICT", fake_train)
    prereg = {
        "ensemble": {
            "members": 3,
            "seeds": [31501, 31502, 31503],
            "weights": [1 / 3, 1 / 3, 1 / 3],
        },
        "training": {"seed": 31501},
    }
    model_path = tmp_path / "models" / "d7.pt"
    probability, diagnostics = v315.train_and_predict(
        None,
        None,
        None,
        None,
        np.arange(3),
        np.arange(2),
        prereg,
        "screen",
        "d7",
        model_path,
    )
    assert calls == [31501, 31502, 31503]
    assert probability.shape == (2, 120)
    assert diagnostics["execution"] == "strictly_sequential"
    assert model_path.exists()
    assert all(
        (model_path.with_suffix("") / f"member_{index}.pt").exists()
        for index in (1, 2, 3)
    )


def test_matched_parent_reads_v312_standalone(tmp_path):
    fold_dir = tmp_path / "matched"
    fold_dir.mkdir()
    folds = {}
    for offset, fold in enumerate(v315.v310.FOLDS):
        indices = np.asarray([20 + offset], dtype=np.int64)
        dates = np.asarray([20260110 + offset], dtype=np.int32)
        target = np.asarray([offset], dtype=np.int64)
        probability = np.full((1, 120), 1.0 / 120, dtype=np.float32)
        np.savez_compressed(
            fold_dir / f"fold_{fold}_predictions.npz",
            standalone=probability,
            race_indices=indices,
            race_dates=dates,
            true_combo=target,
        )
        folds[fold] = {
            "indices": indices,
            "dates": v315.v313.normalized_dates(dates),
            "target": target,
        }
    result = v315.v313.load_matched_parents(
        SimpleNamespace(matched_parent_dir=fold_dir), folds
    )
    assert set(result) == set(v315.v310.FOLDS)
    assert np.allclose(result["d8"].sum(axis=1), 1.0)


def test_v9_and_v4_are_frozen_to_v312():
    v9 = json.loads(
        (ROOT / "configs" / "noodds_evaluation_protocol_v9.json").read_text(
            encoding="utf-8"
        )
    )
    v4 = json.loads(
        (
            ROOT
            / "configs"
            / "noodds_candidate_acceleration_v4_matched_v312.json"
        ).read_text(encoding="utf-8")
    )
    assert v9["references"]["active_parent"]["model_id"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert v4["matched_parent"]["prediction_key"] == "standalone"
    assert v4["policy"]["screen_never_promotes"] is True

def test_parent_family_status_uses_v312_not_old_v295():
    deltas = {
        "v312": np.asarray([-0.2, -0.1]),
        "v295": np.asarray([0.4, 0.5]),
    }
    assert v314.active_parent_mean(deltas) < 0.0
    assert any("v315" in replacement for _, replacement in v314.ALIASES)
