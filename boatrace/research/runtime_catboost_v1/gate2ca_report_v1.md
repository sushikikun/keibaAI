# Gate 2-C-A CatBoost runtime追加・合成smoke test v1

- status: PASSED
- runtime_id: boatrace_research_runtime_catboost_v1
- Python: 3.12.13 / CPython 3.12 / Windows x86-64
- CatBoost: 1.2.10 / CPU / thread_count=1
- wheel: catboost-1.2.10-cp312-cp312-win_amd64.whl
- official PyPI SHA-256 match: True
- pip check: PASS
- synthetic 120-class fit: PASS
- predict_proba shape: [480, 120]
- save/load: True
- seed determinism: True
- row-order invariance: True
- unknown category: True
- real feature/target access: 0
- screening/confirmation/final-lock metrics: 0
- final-lock unlock_count: 0
- automation: PAUSED

Real-data training and metric computation remain unauthorized; Gate 2-C-B requires explicit approval.
