# Boat-race AI: next steps after Gate 2-F Screening

## Current decision boundary

Gate 2-F Screening is complete. Both winner-residual arms improved the registered B3 baseline in all four Screening Folds. WR-H also improved on WR-S in every Fold and is the sole recommended candidate for a future Confirmation freeze.

This result does not authorize Confirmation access and does not select a formal Champion.

## Frozen recommendation pending review

- candidate arm: WR-H
- model form: B3 winner prior plus official snapshot and F1 as-of racer-history residual
- lambda selection grid: `0.01, 0.1, 1.0, 10.0, 100.0`
- selected lambda: `0.01` in every Screening Fold
- preprocessing: train-only median imputation, missing indicator, and z-score normalization
- calibration: Fold-specific scalar temperature selected on the calibration role
- class distribution: 120 ordered trifecta outcomes
- protected conditionals: B3 second- and third-stage raw conditionals remain unchanged
- odds, popularity, payout, future, F2, and same-day previous-result features: prohibited

The exact executable hashes, preprocessing state, calibration implementation, and reporting code must be frozen in a separate Confirmation manifest before any Confirmation row is opened.

## Required next authorization

Create a separate issue or task that explicitly authorizes one atomic WR-H Confirmation run. Before approval, the item must contain:

1. the exact candidate and artifact hashes
2. the fixed runtime and package versions
3. the immutable feature and leakage contracts
4. the fixed calibration and metric code
5. the Confirmation success criteria
6. the no-tuning and no-candidate-switching rule
7. the required resource and guard preflight
8. the rule that Final lock remains inaccessible

Until that item is reviewed and approved:

- Confirmation access count stays `0`
- Final-lock access/unlock count stays `0`
- automation stays `PAUSED`
- no live selection, betting, ROI claim, or production promotion is allowed

## Screening evidence to review

Use the sanitized artifacts in:

```text
boatrace/research/gate2_b3_winner_residual_v1/portable_screening_result_v2/
```

The key result is calibrated pooled trifecta Log Loss of `4.028538529624236` for WR-H versus `4.151932308088278` for B3, a paired improvement of `-0.12339377846404213` across 51,232 evaluation races.
