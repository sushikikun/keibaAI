from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from train_noodds_raw_v258_multiperiod_fixed_ensemble import (
    component_masks,
    component_view,
)


def fixture():
    layout = {
        "runner_numeric_names": [
            "hist_win_rate", "recent5_win_rate", "single_race_day",
            "start_st_missing", "exhibition_time", "unknown_feature",
        ],
        "runner_categorical_names": [
            "racer_code", "branch_code", "venue_motor_code", "venue_boat_code",
        ],
        "race_numeric_names": [
            "race_no", "temperature_c", "exhibition_coverage", "unknown_race",
        ],
        "race_categorical_names": ["venue_code_cat", "weather_code"],
    }
    config = json.loads(
        Path("configs/noodds_v258_multiperiod_fixed_ensemble_design.json").read_text(
            encoding="utf-8"
        )
    )
    return layout, config


def test_component_masks_are_disjoint_by_period_and_keep_availability():
    layout, config = fixture()
    masks = component_masks(layout, config, skill_width=2)
    assert masks["long_term"]["runner_numeric"].tolist() == [
        True, False, False, True, False, False, True, True
    ]
    assert masks["recent_form"]["runner_numeric"].tolist() == [
        False, True, False, True, True, False, False, False
    ]
    assert masks["meeting_state"]["runner_numeric"].tolist() == [
        False, False, True, True, True, False, False, False
    ]
    assert masks["long_term"]["runner_categorical"].all()
    assert masks["recent_form"]["runner_categorical"].tolist() == [
        True, True, False, False
    ]
    assert masks["meeting_state"]["race_categorical"].tolist() == [True, False]
    assert masks["recent_form"]["race_categorical"].tolist() == [False, True]


def test_component_view_masks_without_mutating_source():
    layout, config = fixture()
    masks = component_masks(layout, config, skill_width=2)
    tensors = (
        torch.ones((2, 6, 8)),
        torch.ones((2, 6, 4), dtype=torch.long),
        torch.ones((2, 4)),
        torch.ones((2, 2), dtype=torch.long),
        torch.zeros((2, 3), dtype=torch.long),
    )
    view = component_view(tensors, masks["recent_form"])
    assert torch.all(tensors[0] == 1.0)
    assert torch.all(view[0][:, :, masks["recent_form"]["runner_numeric"]] == 1.0)
    assert torch.all(view[0][:, :, ~masks["recent_form"]["runner_numeric"]] == 0.0)
    assert torch.all(view[1][:, :, 2:] == 0)
    assert torch.all(view[3][:, 0] == 0)
    assert torch.all(view[3][:, 1] == 1)


if __name__ == "__main__":
    test_component_masks_are_disjoint_by_period_and_keep_availability()
    test_component_view_masks_without_mutating_source()
    print("ok")
