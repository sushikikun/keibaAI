# Gate 2-F B3 Winner Residual Correction — Screening Report

## Result

The Fold 1–4 screening run was **resource_blocked**. Available physical memory fell to **356.5 MiB**, below the Gate 2-F hard-stop threshold of 512 MiB. The runner was stopped without destroying existing inputs or partial staging.

The optimizer/probability canary passed, but the full WR-S and WR-H arm fits, predictions, calibration, and fold metrics did not complete. Therefore this report makes no claim about arm ranking, improvement, or a formal champion. No Confirmation or Final lock was accessed.

## Preserved guards

- Gate 2-E validation remained passed.
- The protected B3 baseline manifest SHA-256 remained `f3eb62dc643c9f2561f5ec1827e3d070b63fd85952425ea69b39dc0f73a8c6e3`.
- The B3 factorization contract and the P2/P3 unchanged policy were preserved.
- Automation remained `PAUSED`.

See `gate2f_validation_v1.json` and the staging `resource_profile_v1.json` for the machine-readable record.
