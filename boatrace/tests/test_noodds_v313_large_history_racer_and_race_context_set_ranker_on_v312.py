import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v313_large_history_racer_and_race_context_set_ranker_on_v312 as v313


def _config():
    return json.loads(v313.PREREGISTRATION.read_text(encoding="utf-8"))


def _architecture():
    return {
        "runner_projection_width": 12,
        "attention_heads": 3,
        "feedforward_width": 24,
        "dropout": 0.0,
        "self_attention_layers": 1,
    }


def _model():
    torch.manual_seed(313)
    model = v313.RacerContextStagewiseSetRanker(
        5,
        3,
        [20],
        [24, 12],
        {"embedding_widths": {"racer_code": 4}},
        {"embedding_widths": {"venue_code": 3, "race_no": 2}},
        _architecture(),
    )
    model.eval()
    return model


def test_preregistration_fixes_parent_context_and_protocols():
    cfg = _config()
    assert cfg["policy"]["active_parent"] == (
        "v312_large_history_racer_identity_set_ranker_on_v295"
    )
    assert cfg["race_context_features"]["race_columns"] == {
        "venue_code": 0,
        "race_no": 1,
    }
    assert cfg["race_context_features"]["embedding_widths"] == {
        "venue_code": 6,
        "race_no": 4,
    }
    assert cfg["training"]["seed"] == 31301
    assert cfg["screen_protocol"].endswith(
        "noodds_candidate_acceleration_v4_matched_v312.json"
    )
    assert cfg["final_protocol"].endswith(
        "noodds_evaluation_protocol_v9.json"
    )


def test_context_vocabulary_is_training_only_and_unseen_maps_to_zero():
    raw = np.asarray([[1, 1], [2, 2], [24, 12]], dtype=np.float64)
    vocabulary = v313.fit_context_vocabulary(raw, np.asarray([0, 1]))
    encoded, audit = v313.encode_context(
        raw, np.asarray([2]), vocabulary
    )
    assert 24 not in vocabulary[0]
    assert np.all(encoded == 0)
    assert audit["venue_code"]["unknown_rate"] == 1.0
    assert audit["race_no"]["unknown_rate"] == 1.0


def test_context_rejects_fractional_category():
    raw = np.asarray([[1.5, 1]], dtype=np.float64)
    with pytest.raises(ValueError, match="not integer encoded"):
        v313.fit_context_vocabulary(raw, np.asarray([0]))


def test_model_masks_and_normalizes_120_probabilities():
    model = _model()
    runner = torch.randn(3, 6, 5)
    race = torch.randn(3, 3)
    identity = torch.randint(0, 20, (3, 6, 1))
    context = torch.stack(
        [torch.randint(0, 24, (3,)), torch.randint(0, 12, (3,))],
        dim=1,
    )
    stage1, stage2, stage3 = model(
        runner, race, identity, context
    )
    for lane in range(6):
        assert torch.all(stage2[:, lane, lane] < -1e8)
    probability = v313.v310.joint_probabilities(
        (stage1, stage2, stage3)
    )
    assert probability.shape == (3, 120)
    assert torch.allclose(
        probability.sum(dim=1), torch.ones(3), atol=1e-6
    )


def test_model_is_equivariant_when_runner_inputs_move_together():
    model = _model()
    runner = torch.randn(2, 6, 5)
    race = torch.randn(2, 3)
    identity = torch.randint(0, 20, (2, 6, 1))
    context = torch.stack(
        [torch.randint(0, 24, (2,)), torch.randint(0, 12, (2,))],
        dim=1,
    )
    permutation = torch.tensor([2, 5, 1, 0, 4, 3])
    original = model(runner, race, identity, context)
    moved = model(
        runner[:, permutation],
        race,
        identity[:, permutation],
        context,
        lane_ids=torch.arange(6)[permutation],
    )
    assert torch.allclose(moved[0], original[0][:, permutation], atol=1e-6)
    expected2 = original[1][:, permutation][:, :, permutation]
    assert torch.allclose(moved[1], expected2, atol=1e-5)
    expected3 = original[2][:, permutation][:, :, permutation][
        :, :, :, permutation
    ]
    assert torch.allclose(moved[2], expected3, atol=1e-5)


def test_train_predict_saves_context_vocabulary(tmp_path):
    rng = np.random.default_rng(313)
    runner = rng.normal(size=(12, 6, 4)).astype(np.float32)
    race = rng.normal(size=(12, 3)).astype(np.float32)
    identity = np.asarray(
        [
            [[100 + race_index * 6 + lane] for lane in range(6)]
            for race_index in range(12)
        ],
        dtype=np.float64,
    )
    v313._CONTEXT_RAW = np.asarray(
        [[1 + i % 3, 1 + i % 6] for i in range(12)],
        dtype=np.float64,
    )
    targets = np.asarray(
        [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]] * 3,
        dtype=np.int64,
    )
    prereg = {
        "identity_features": {
            "embedding_widths": {"racer_code": 4}
        },
        "race_context_features": {
            "embedding_widths": {"venue_code": 3, "race_no": 2}
        },
        "architecture": _architecture(),
        "training": {
            "epochs_screen": 1,
            "epochs_full": 1,
            "seed": 31301,
            "threads": 1,
            "learning_rate": 0.0003,
            "weight_decay": 0.001,
            "batch_races": 4,
            "gradient_clip": 1.0,
        },
    }
    path = tmp_path / "model.pt"
    probability, diagnostics = v313.train_and_predict(
        runner,
        race,
        identity,
        targets,
        np.arange(8),
        np.arange(8, 12),
        prereg,
        "screen",
        "d6",
        path,
    )
    saved = torch.load(path, weights_only=False)
    assert path.exists()
    assert probability.shape == (4, 120)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)
    assert len(saved["context_vocabulary"]) == 2
    assert diagnostics["train_context"]["venue_code"][
        "vocabulary_size"
    ] == 3


def test_matched_parent_reads_standalone_and_checks_alignment(tmp_path):
    fold_dir = tmp_path / "matched"
    fold_dir.mkdir()
    folds = {}
    for offset, fold in enumerate(v313.v310.FOLDS):
        indices = np.asarray([10 + offset], dtype=np.int64)
        dates = np.asarray([20260101 + offset], dtype=np.int32)
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
            "dates": v313.normalized_dates(dates),
            "target": target,
        }
    result = v313.load_matched_parents(
        SimpleNamespace(matched_parent_dir=fold_dir), folds
    )
    assert set(result) == set(v313.v310.FOLDS)
    assert np.allclose(result["d6"].sum(axis=1), 1.0)


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
