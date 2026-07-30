from __future__ import annotations

import numpy as np
import torch

from train_noodds_raw_v257_missingness_experts_ar import (
    PARTIAL_EXHIBITION_LANES,
    PARTIAL_START_LANES,
    deterministic_view,
    routing_experts,
)


RUNNER_NAMES = [
    "body_weight_kg", "adjust_weight_kg", "exhibition_time", "tilt",
    "propeller_new", "parts_count", "part_ring", "part_piston", "part_carb",
    "part_gear", "part_carrier", "part_electric", "part_shaft",
    "part_cylinder", "start_st", "start_st_f", "start_st_l",
    "start_st_missing", "start_display_left_pct", "rel_body_weight_kg_diff",
    "rel_exhibition_time_diff", "rel_tilt_diff", "rel_start_st_diff",
    "rel_start_display_left_pct_diff",
]
RACE_NAMES = [
    "exhibition_coverage", "start_st_coverage",
    "exhibition_spread", "start_st_spread",
]


def fixture():
    layout = {
        "runner_numeric_names": RUNNER_NAMES,
        "race_numeric_names": RACE_NAMES,
    }
    stats = {
        "runner_mean": np.zeros(len(RUNNER_NAMES), dtype=np.float32),
        "runner_std": np.ones(len(RUNNER_NAMES), dtype=np.float32),
        "race_mean": np.zeros(len(RACE_NAMES), dtype=np.float32),
        "race_std": np.ones(len(RACE_NAMES), dtype=np.float32),
    }
    tensors = (
        torch.ones((2, 6, len(RUNNER_NAMES))),
        torch.zeros((2, 6, 0), dtype=torch.long),
        torch.ones((2, len(RACE_NAMES))),
        torch.zeros((2, 0), dtype=torch.long),
        torch.zeros((2, 3), dtype=torch.long),
    )
    return tensors, layout, stats


def test_partial_view_is_fixed_and_does_not_mutate_complete():
    tensors, layout, stats = fixture()
    view = deterministic_view(tensors, layout, stats, 1)
    exhibition = RUNNER_NAMES.index("exhibition_time")
    start = RUNNER_NAMES.index("start_st")
    missing = RUNNER_NAMES.index("start_st_missing")
    assert torch.all(tensors[0] == 1.0)
    assert torch.all(view[0][:, list(PARTIAL_EXHIBITION_LANES), exhibition] == 0.0)
    assert torch.all(view[0][:, list(PARTIAL_START_LANES), start] == 0.0)
    assert torch.all(view[0][:, list(PARTIAL_START_LANES), missing] == 1.0)
    assert torch.all(view[0][:, :, RUNNER_NAMES.index("rel_start_st_diff")] == 0.0)
    assert torch.all(view[2][:, :2] == 0.5)
    assert torch.all(view[2][:, 2:] == 0.0)


def test_preinfo_view_removes_all_current_beforeinfo():
    tensors, layout, stats = fixture()
    view = deterministic_view(tensors, layout, stats, 2)
    missing = RUNNER_NAMES.index("start_st_missing")
    kept = view[0].clone()
    kept[:, :, missing] = 0.0
    assert torch.all(kept == 0.0)
    assert torch.all(view[0][:, :, missing] == 1.0)
    assert torch.all(view[2] == 0.0)


def test_routing_is_exhaustive_and_fixed():
    race = np.asarray(
        [
            [1.0, 1.0],
            [0.5, 1.0],
            [1.0, 0.0],
            [0.0, 0.0],
            [np.nan, np.nan],
        ],
        dtype=np.float32,
    )
    data = {
        "manifest": {
            "race_feature_names": ["exhibition_coverage", "start_st_coverage"]
        },
        "race": race,
    }
    routes = routing_experts(data, np.arange(len(race)))
    assert np.array_equal(routes, np.asarray([0, 1, 1, 2, 1]))


if __name__ == "__main__":
    test_partial_view_is_fixed_and_does_not_mutate_complete()
    test_preinfo_view_removes_all_current_beforeinfo()
    test_routing_is_exhaustive_and_fixed()
    print("ok")
