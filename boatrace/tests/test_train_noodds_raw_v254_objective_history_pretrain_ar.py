from __future__ import annotations

import numpy as np
import torch

from train_noodds_raw_v254_objective_history_pretrain_ar import ObjectiveHistoryEncoder, auxiliary_targets


def test_encoder_does_not_accept_current_targets():
    model = ObjectiveHistoryEncoder()
    sequence = torch.zeros((4, 12, 13), dtype=torch.float32)
    mask = torch.zeros((4, 12), dtype=torch.bool)
    state = model.encode(sequence, mask)
    assert state.shape == (4, 8)
    assert torch.equal(state, torch.zeros_like(state))


def test_auxiliary_roles_are_derived_only_from_top3_labels():
    names = ["start_st", "start_st_missing", "exhibition_time"]
    runner = np.zeros((1, 6, 3), dtype=np.float32)
    runner[:, :, 0] = 0.15
    runner[:, :, 2] = 6.75
    data = {
        "manifest": {"runner_feature_names": names},
        "runner": runner,
        "targets": np.asarray([[2, 0, 5]], dtype=np.int64),
    }
    role, start, start_valid, exhibition, exhibition_valid = auxiliary_targets(data)
    assert role.tolist() == [[1, 3, 0, 3, 3, 2]]
    assert start_valid.all()
    assert exhibition_valid.all()
    assert np.allclose(start, 0.15)
    assert np.allclose(exhibition, 6.75)


if __name__ == "__main__":
    test_encoder_does_not_accept_current_targets()
    test_auxiliary_roles_are_derived_only_from_top3_labels()
    print("ok")
