# Gate 2-F portable Screening result v2

## Outcome

Gate 2-F Screening is complete with validated post-fit reporting recovery.

WR-S and WR-H both improved the registered B3 baseline in all four Screening Folds. WR-H also improved on WR-S in every Fold and is the sole recommended candidate for a separately reviewed Confirmation freeze.

This is Screening evidence only. No formal Champion is selected, Confirmation access remains zero, Final-lock access/unlock remains zero, and automation remains `PAUSED`.

## Primary result

| Model | Raw pooled trifecta Log Loss | Calibrated pooled trifecta Log Loss | Calibrated paired delta vs B3 |
|---|---:|---:|---:|
| B3 | 4.151575557651773 | 4.151932308088278 | — |
| WR-S | 4.036482276373360 | 4.035359545645713 | -0.116572762442565 |
| WR-H | 4.030231240628925 | 4.028538529624236 | -0.123393778464042 |

WR-H versus WR-S calibrated paired delta was `-0.006821016021477`. Its 95% paired interval was `[-0.007794655709581, -0.005847376333372]`. WR-H improved on WR-S on 267 of 366 evaluation days.

Lower Log Loss is better.

## Fold stability

| Fold | B3 calibrated | WR-S calibrated | WR-S delta | WR-H calibrated | WR-H delta |
|---|---:|---:|---:|---:|---:|
| 1 | 4.157478310559472 | 4.033883928153435 | -0.123594382406036 | 4.024952799146472 | -0.132525511413000 |
| 2 | 4.135915402064670 | 4.017401630894845 | -0.118513771169824 | 4.010286820664735 | -0.125628581399935 |
| 3 | 4.180640507492863 | 4.062161229284395 | -0.118479278208469 | 4.057197088104019 | -0.123443419388843 |
| 4 | 4.132262537749672 | 4.027105791203671 | -0.105156746546001 | 4.020806275857804 | -0.111456261891869 |

Both arms meet all registered Screening diagnostics:

- pooled calibrated delta is negative
- four of four Folds improve
- worst-Fold deterioration is at most `0.01`; neither arm deteriorated in any Fold
- prediction coverage is 100%

## Diagnostics

WR-H calibrated pooled diagnostics were:

- winner Log Loss: `1.205850494353336`
- exacta Log Loss: `2.677440532130644`
- top-3-set Log Loss: `2.532262534888000`
- trifecta Brier: `0.971396523035708`
- Hit@1 / 3 / 5 / 10 / 20: `0.0702100 / 0.1811758 / 0.2697728 / 0.4321323 / 0.6262687`
- mean reciprocal rank: `0.181158011620273`
- loss P90 / P95 / P99: `5.5748262 / 6.0565461 / 6.9709639`
- true-probability below `1e-4`: `0.000019519050593`
- abnormal-tail evaluation rows: `0`

The any-lane cold-start subset contained only 55 races. WR-S and WR-H both improved its descriptive Log Loss versus B3, but the subset is too small for a candidate decision. There were no evaluation races in which the winning lane itself had the cold-start flag.

## Model-contract validation

All 24 B3/WR prediction files passed exact-key, duplicate, finite-value, non-negativity, upper-bound, 120-class-length, and probability-sum checks across 51,232 evaluation races.

For raw predictions, the maximum absolute difference from B3 was:

- second-stage conditional distribution: `4.440892098500626e-16`
- third-stage conditional distribution: `2.220446049250313e-16`

This passes the winner-only residual contract at numerical precision. Scalar temperature calibration is evaluated separately because it acts on the full 120-class distribution.

Every Fold and arm selected lambda `0.01`; all optimizers reported success. The public coefficient artifact contains aggregated Fold-stability summaries, not row-level training data. Coefficient signs are descriptive and should not be interpreted causally.

## Execution and reporting recovery

The bundle, public manifest, private manifest, and all 28 private-manifest payload hashes passed. The fixed runtime was Python 3.12 with numpy 2.3.5, pandas 3.0.1, scipy 1.18.0, and scikit-learn 1.9.0. Import, class-map, gradient, beta-zero, probability, and guard canaries passed.

The resource preflight passed with 13 samples and a minimum of 20,911 MiB available. The serial run took 1,170 seconds; minimum available memory during execution was 16,928 MiB, and no warning or hard-stop threshold was reached.

All eight model computations and raw prediction exports completed. The source runner then exited while writing `selected_lambda_v1.csv` because its `DictWriter` schema omitted fields present in the metric dictionaries. The original source run was preserved.

Recovery performed no model fit. It regenerated all eight calibrated files deterministically from complete raw probabilities and the recorded Fold/arm temperatures. Six complete originals matched the regenerated files byte-for-byte; the two originals interrupted during reporting were replaced in the recovered copy. Formal pooled metrics were recomputed over individual races, avoiding the source runner's unweighted mean of Fold means. The recovered result passed full validation.

## Decision and next action

Gate 2-F follows supported Branch A:

1. review this sanitized result
2. freeze WR-H as the sole Confirmation candidate, including exact hashes, preprocessing, lambda rule, and calibration policy
3. create a separate explicit Confirmation authorization item
4. keep Confirmation sealed until that approval
5. keep Final lock sealed and automation paused

The required authorization contract is described in `boatrace/docs/next_steps_after_gate2f_screening_v1.md`.
