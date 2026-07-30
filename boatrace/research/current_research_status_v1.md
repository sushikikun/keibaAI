# Current boat-race research status

- Gate 1-A through Gate 1-E: completed local research records.
- Gate 2-A: completed local research record.
- Gate 2-B: statistical baseline screening reference.
- Gate 2-E: residual atlas validation passed locally.
- Gate 2-F: `resource_blocked`; no full WR-S / WR-H metrics, ranking, or formal champion.
- Confirmation access: 0.
- Final lock access: 0 in the migrated research record.
- Automation: paused.

The repository contains sanitized contracts and audit records, not the local corpus or model artifacts.

## Gate 2-F execution readiness v2

A resource-only preflight collected 13 samples at five-second intervals and failed the sustained 3,072 MiB admission gate (minimum 450.3 MiB; first sample 1,085.9 MiB). No clean Gate 2-F run, supervised fit, prediction, partial metric, or Champion selection was started.

A portable execution bundle is ready for a higher-memory host. Its local-only supervised-data component is not committed here. Gate 2-F remains performance-unresolved; Confirmation and Final-lock access/unlock remain zero and automation remains PAUSED.

## Canonical next action

Continue on a trusted higher-memory host using:

1. `boatrace/docs/next_steps_and_external_host_handoff_v1.md`
2. `boatrace/research/gate2_b3_winner_residual_v1/portable_execution_runbook_v1.md`
3. `boatrace/research/gate2_b3_winner_residual_v1/portable_bundle_manifest_public_v1.json`
4. GitHub Issue `#2 Complete Gate 2-F winner residual screening`

The next scientific result must come from a complete, hash-verified, fully serial WR-S / WR-H Screening Fold 1–4 run. Until that run completes, Gate 2-F performance remains unresolved and no Confirmation or Final-lock access is authorized.
