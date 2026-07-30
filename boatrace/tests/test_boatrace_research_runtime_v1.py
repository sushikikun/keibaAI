import json
from pathlib import Path

def test_gate2a_is_synthetic_only():
    p=Path(__file__).resolve().parents[1]/"research"/"runtime_v1"/"runtime_smoke_test_v1.json"
    d=json.loads(p.read_text(encoding="utf-8"))
    assert d["actual_training_data_opened"] is False
    assert d["actual_target_data_opened"] is False
    assert d["metrics_computed"] is False
