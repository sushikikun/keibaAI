# Gate 2-F portable screening result v1

## Status

`resource_blocked_on_target_host`

The target-host preflight collected 13 samples at five-second intervals. Available physical memory ranged from 2,207 MiB to 2,469 MiB (mean 2,317.2 MiB), below the required sustained minimum of 3,072 MiB.

No supervised-data rows were accessed. No WR-S or WR-H fit, selection, refit, calibration, prediction, metrics, partial staging, or partial metrics were started. No retry was performed.

## Verified before the resource stop

- Portable ZIP SHA-256 matched: `0355c1f20b736fcc996e2707ede2d1657e811ec74104a69b8d4cded1377c4c6f`.
- Public-manifest SHA-256 matched the supplied value.
- Private-manifest content is not included in this repository.
- Python 3.12.13 runtime validation passed.
- Runtime package versions: numpy 2.3.5, pandas 3.0.1, scipy 1.18.0, scikit-learn 1.9.0.
- Runner import, synthetic optimizer canary, and synthetic probability canary passed.
- Confirmation access count: 0; Final-lock access/unlock count: 0.

## Follow-up

Run only on a host whose available physical memory is at least 3,072 MiB for the full 60-second preflight. This is a screening-only record, not a formal Champion decision.
