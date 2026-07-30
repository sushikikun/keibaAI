import inspect
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_noodds_v304_full_history_pointer_set_exact_top3_on_v295 as v304
torch = v304.torch


def _config():
    return json.loads(
        (ROOT / "configs" / "noodds_v304_full_history_pointer_set_exact_top3_on_v295_preregistered.json").read_text()
    )


def _prob(rows, seed):
    rng = np.random.default_rng(seed)
    values = rng.random((rows, 120))
    return values / values.sum(axis=1, keepdims=True)


def test_preregistered_full_history_budget_is_fixed():
    cfg = _config()
    assert cfg["training"]["full_train_races"] == {"d6": 50788, "d7": 55225, "d8": 59840}
    assert cfg["training"]["epochs_full"] == 8
    assert cfg["training"]["epochs_screen"] == 3
    assert cfg["architecture"]["width"] == 48
    assert cfg["forbidden"].count("parent probability as training input") == 1


def test_train_only_preprocessing_and_missing_masks():
    runner = np.arange(4 * 6 * 2, dtype=np.float32).reshape(4, 6, 2)
    race = np.arange(4 * 2, dtype=np.float32).reshape(4, 2)
    runner[0, 0, 0] = np.nan
    race[0, 0] = np.nan
    stats = v304.fit_preprocessing(runner, race, np.asarray([0, 1]))
    transformed_runner, transformed_race = v304.transform_features(
        runner, race, np.asarray([2, 3]), stats
    )
    assert transformed_runner.shape == (2, 6, 10)
    assert transformed_race.shape == (2, 4)
    assert np.isfinite(transformed_runner).all()
    assert np.isfinite(transformed_race).all()
    assert stats["runner_mean"][0] < runner[3, :, 0].mean()


def test_teacher_forcing_masks_selected_runners():
    cfg = _config()["architecture"]
    model = v304.PointerSetExactTop3(10, 4, cfg)
    runner = torch.zeros((3, 6, 10), dtype=torch.float32)
    race = torch.zeros((3, 4), dtype=torch.float32)
    target = torch.tensor([[0, 1, 2], [2, 4, 1], [5, 3, 0]], dtype=torch.long)
    first, second, third = model.teacher_logits(runner, race, target)
    rows = torch.arange(3)
    assert torch.isneginf(second[rows, target[:, 0]]).all()
    assert torch.isneginf(third[rows, target[:, 0]]).all()
    assert torch.isneginf(third[rows, target[:, 1]]).all()
    assert torch.isfinite(first).all()


def test_pointer_enumerates_normalized_exact_top3_probabilities():
    cfg = _config()["architecture"]
    torch.manual_seed(1)
    model = v304.PointerSetExactTop3(10, 4, cfg)
    model.eval()
    with torch.no_grad():
        probability = model.probabilities(
            torch.randn(4, 6, 10), torch.randn(4, 4)
        ).numpy()
    assert probability.shape == (4, 120)
    assert np.isfinite(probability).all()
    assert np.all(probability > 0)
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-6)


def test_gamma_zero_reproduces_parent():
    parent = _prob(5, 1)
    standalone = _prob(5, 2)
    result = v304.anchored_probability(parent, standalone, 0.0)
    assert np.allclose(result, parent, atol=1e-12)


def test_training_does_not_accept_parent_probability_input():
    signature = inspect.signature(v304.train_pointer)
    assert "parent" not in signature.parameters
    source = inspect.getsource(v304.train_pointer)
    assert '["base"]' not in source
    assert "parent_probability" not in source


def test_fold_loader_retains_full_train_indices():
    source = inspect.getsource(v304.load_fold)
    assert 'f"{prefix}_train_indices"' in source
    assert '"train_indices": train' in source
