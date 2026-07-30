import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_noodds_rolling_origin_splits_v337 import build_splits, validate_contract


def test_build_splits_is_strictly_prior_and_has_disjoint_validation():
    dates = np.asarray(["2025-06-30", "2025-07-01", "2025-07-01", "2025-07-31", "2025-08-01"], dtype="datetime64[D]")
    splits = build_splits(dates, [{"id": "a", "start": "2025-07-01", "end": "2025-07-31"}, {"id": "b", "start": "2025-08-01", "end": "2025-08-01"}], minimum_train_races=1)
    assert splits[0]["train_indices"].tolist() == [0]
    assert splits[0]["validation_indices"].tolist() == [1, 2, 3]
    assert splits[1]["train_indices"].tolist() == [0, 1, 2, 3]
    assert splits[1]["validation_indices"].tolist() == [4]


def test_build_splits_rejects_overlapping_windows():
    dates = np.asarray(["2025-06-30", "2025-07-01", "2025-07-02"], dtype="datetime64[D]")
    with pytest.raises(ValueError, match="validation overlaps"):
        build_splits(dates, [{"id": "a", "start": "2025-07-01", "end": "2025-07-02"}, {"id": "b", "start": "2025-07-02", "end": "2025-07-02"}], minimum_train_races=1)


def test_validate_contract_rejects_odds_enabled():
    contract = {"policy": {"odds_used": False, "payout_used": False, "same_day_results_used_for_features": False, "future_results_used": False}, "allowed_prediction_inputs": [{"name": "racer_code"}], "label_update_rule": "Finish-order labels may update state only after features are emitted."}
    with pytest.raises(ValueError, match="odds_used"):
        validate_contract(contract, {"odds_used": True, "payout_used": False})


def test_validate_contract_accepts_no_odds_manifest():
    contract_path = ROOT / "configs" / "noodds_feature_availability_contract_v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract, {"odds_used": False, "payout_used": False})
