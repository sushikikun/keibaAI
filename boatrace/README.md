# Boat-race AI research foundation

This directory is an independent, sanitized research foundation. The existing horse-racing MVP remains untouched.

## GitHub scope

Only contracts, minimal reusable source code, one synthetic-fixture unit test, current research status, model-family specifications, and provenance manifests are public. Local-only data, raw source material, odds/payout tables, predictions, models, databases, caches, and machine-specific artifacts are deliberately excluded.

## Canonical current files

- `configs/boatrace_model_dataset_contract_v1.json`
- `configs/boatrace_model_evaluation_v1_1.json`
- `configs/boatrace_model_outcome_audit_v0_1.json`
- `configs/trifecta_class_map_v1.json`
- `research/current_research_status_v1.md`
- `manifests/local_data_registry_v1.json`

Historical configurations and local integration tests are represented by `manifests/historical_config_registry_v1.csv` and `manifests/local_integration_test_registry_v1.csv`; they are not executable in a GitHub clone because their local dependencies are intentionally excluded.

## Continue from another PC

Use the following documents as the canonical handoff:

1. `docs/next_steps_and_external_host_handoff_v1.md`
2. `research/gate2_b3_winner_residual_v1/portable_execution_runbook_v1.md`
3. `research/gate2_b3_winner_residual_v1/portable_bundle_manifest_public_v1.json`
4. GitHub Issue `#2 Complete Gate 2-F winner residual screening`

A Git clone alone is not enough to execute Gate 2-F. The trusted operator must also obtain the local-only `gate2f_portable_execution_bundle_v1.zip` and verify its SHA-256 before extraction. The handoff document records the expected ZIP and manifest hashes, fixed runtime, resource admission gate, serial execution order, failure policy, result publication workflow, and the roadmap after Screening.

## Validation and CI

`tests/test_boatrace_model_research_v0.py` is a synthetic-fixture unit test and runs without local data or network access. GitHub Actions runs compilation, JSON/CSV/secret/path/size checks, and this retained test on changes below `boatrace/**`.

Gate 2-F remains `resource_blocked`; this import does not claim a formal champion or reproduce WR-S/WR-H metrics. Confirmation and Final-lock artifacts were not accessed. Future model work must use the portable, guarded workflow documented above.
