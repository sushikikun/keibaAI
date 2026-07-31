# Current boat-race research status

- Gate 1-A through Gate 1-E: completed local research records.
- Gate 2-A: completed local research record.
- Gate 2-B: statistical baseline screening reference.
- Gate 2-E: residual atlas validation passed locally.
- Gate 2-F: Screening completed on a higher-memory host with post-fit reporting recovery; WR-S and WR-H are both Screening-supported across all four Folds.
- Confirmation access: 0.
- Final lock access: 0 in the migrated research record.
- Automation: paused.

The repository contains sanitized contracts and audit records, not the local corpus or model artifacts.

## Gate 2-F Screening result v2

A higher-memory host passed the 13-sample resource preflight with a minimum of 20,911 MiB available. The fixed Python 3.12 runtime, bundle hashes, canaries, protected-data guards, and all 28 private-manifest payload hashes passed before execution.

All eight serial Fold/arm computations completed. The source runner then failed in post-fit CSV reporting because a `DictWriter` received fields outside its declared schema. The source run was preserved. Missing reporting artifacts and two truncated calibrated-prediction files were reconstructed from the complete raw predictions and recorded temperatures without another model fit. A full 51,232-race validation passed for all 24 B3/WR prediction files.

Calibrated pooled trifecta Log Loss:

- B3: `4.151932308088278`
- WR-S: `4.035359545645713` (paired delta `-0.11657276244256537`)
- WR-H: `4.028538529624236` (paired delta `-0.12339377846404213`)
- WR-H versus WR-S: `-0.00682101602147674`

Both arms improved B3 in four of four Folds. WR-H is the recommended sole candidate to freeze for a separately authorized Confirmation run. This is not a formal Champion selection. Confirmation and Final-lock access remain zero, and automation remains `PAUSED`.

## Canonical next action

Review the sanitized Screening result and prepare a separate explicit Confirmation authorization using:

1. `boatrace/research/gate2_b3_winner_residual_v1/portable_screening_result_v2/run_report_v2.md`
2. `boatrace/docs/next_steps_after_gate2f_screening_v1.md`
3. GitHub Issue `#2 Complete Gate 2-F winner residual screening`

Do not open Confirmation data from this result alone. First review and freeze the exact WR-H configuration, hashes, preprocessing, calibration policy, and success criteria in a new explicit authorization item. Final lock remains sealed.
