# Boat-race AI: next steps and external-host handoff v1

> Superseded for current operations after Gate 2-F Screening completion. This remains the historical portable-execution contract. Use `next_steps_after_gate2f_screening_v1.md` and `../research/gate2_b3_winner_residual_v1/portable_screening_result_v2/run_report_v2.md` for the current next action. Confirmation and Final lock remain sealed.

This document is the canonical public handoff for continuing the boat-race AI research from a different PC. It is written so that a fresh operator or Codex session can understand the current state, obtain the local-only execution bundle, run the next experiment without changing the scientific contract, and return only safe public summaries to GitHub.

## 1. Project objective

The research target is a **no-odds trifecta probability model**. For every eligible race, the model must output a valid probability distribution over all 120 ordered trifecta outcomes.

Primary evaluation:

- future, time-separated trifecta Log Loss
- identical evaluation race keys across compared models
- paired per-race loss comparison
- calibration evaluated separately from raw probabilities

Never use the following as inference features:

- odds
- popularity
- payouts
- future information
- same-day previous-race results that were not available at the prediction timestamp

## 2. Current authoritative state

GitHub repository:

- `sushikikun/keibaAI`
- canonical public area: `boatrace/`
- tracking issue: `#2 Complete Gate 2-F winner residual screening`

Current model-research state:

- Gate 1-A through Gate 1-E: completed locally
- Gate 2-A: runtime record completed
- Gate 2-B: statistical baseline completed
- Gate 2-E: B3 residual atlas passed
- Gate 2-F optimizer canary: passed
- Gate 2-F probability canary: passed
- Gate 2-F full WR-S / WR-H screening: **not executed successfully**
- Gate 2-F performance status: `unresolved`
- formal Champion: not selected
- Confirmation access: 0
- Final-lock access/unlock: 0
- automation: `PAUSED`

The previous local host failed the resource-only admission check. No clean Gate 2-F fit, prediction, partial metric, or model ranking was started from that attempt.

## 3. Fixed reference values

These values identify the portable execution package and protected baseline. A new host must verify them before reading supervised data.

| Item | Expected value |
|---|---|
| Bundle file name | `gate2f_portable_execution_bundle_v1.zip` |
| Bundle ZIP SHA-256 | `0355c1f20b736fcc996e2707ede2d1657e811ec74104a69b8d4cded1377c4c6f` |
| Public bundle manifest SHA-256 | `92ccca26cc4ae08b764a8b72c73ac9444e27a2349f667be5613c912b1d0e1b3a` |
| Private bundle manifest SHA-256 | `386e6531d55fd43284a4c9b8ec4ef2ca52713f2c3ca0dadbfd1e78fe60156bdb` |
| Protected B3 baseline manifest SHA-256 | `f3eb62dc643c9f2561f5ec1827e3d070b63fd85952425ea69b39dc0f73a8c6e3` |
| Screening bundle race count | `126,978` |
| Existing B3 evaluation race count | `51,232` |
| Existing B3 raw pooled trifecta Log Loss | `4.151575557651773` |
| Existing B3 calibrated pooled trifecta Log Loss | `4.151932308088278` |

`126,978` is the total portable Screening population across the required roles. It must not be confused with the `51,232` evaluation races used for the existing B3 pooled metric.

## 4. Public GitHub data versus local-only data

### Stored in GitHub

GitHub contains sanitized contracts, public manifests, model-family definitions, audit summaries, current status, and small metrics.

Important public files:

- `boatrace/research/current_research_status_v1.md`
- `boatrace/research/gate2_b3_winner_residual_v1/gate2f_execution_status_v2.json`
- `boatrace/research/gate2_b3_winner_residual_v1/gate2f_execution_report_v2.md`
- `boatrace/research/gate2_b3_winner_residual_v1/portable_bundle_manifest_public_v1.json`
- `boatrace/research/gate2_b3_winner_residual_v1/portable_execution_runbook_v1.md`
- `boatrace/research/gate2_b3_winner_residual_v1/resource_preflight_attempt_v2_public.json`

### Never stored in GitHub

The following must be transferred privately between trusted hosts:

- the ZIP bundle itself
- the supervised-data portion of the bundle
- the private manifest
- models and preprocessors
- race-level predictions
- full per-race loss ledgers
- local paths, credentials, tokens, or secrets
- raw source data, databases, and caches

A Git clone alone is intentionally insufficient to run Gate 2-F. The verified local-only ZIP is also required.

## 5. Required assets on a new host

Before starting, the new host must have:

1. access to `sushikikun/keibaAI`
2. a byte-identical copy of `gate2f_portable_execution_bundle_v1.zip`
3. enough free disk space for the extracted bundle, runtime, temporary files, models, and predictions
4. Python 3.12
5. a stable high-memory environment
6. Git and GitHub authentication for publishing sanitized results

Operational recommendation, not a scientific contract:

- 32 GiB physical RAM or more
- 64 GiB preferred when other services must remain active
- SSD storage
- no concurrent model training during the run

The formal admission rule remains the resource preflight defined below.

## 6. First 15 minutes on a new PC

Perform these steps in order.

1. Clone or update the repository.
2. Open this document and Issue #2.
3. Obtain the local-only ZIP through a private transfer channel.
4. Verify the ZIP SHA-256 before extraction.
5. Extract into a new empty directory outside the Git repository.
6. Verify both public and private manifests and every file listed by them.
7. Confirm the bundle contains zero Confirmation rows and zero Final-lock rows.
8. Create an isolated Python 3.12 virtual environment.
9. Install only the fixed dependencies.
10. Run import, optimizer, and probability canaries.
11. Run the resource-only preflight without opening supervised data.
12. Start Gate 2-F only if all admission checks pass.

Do not improvise around a failed check.

## 7. Safe workspace layout

Recommended logical layout:

```text
<WORK_ROOT>/
├─ repo/                         # Git clone of sushikikun/keibaAI
├─ bundle-source/                # original ZIP, read-only
├─ bundle-extracted/             # extracted portable bundle
├─ runtime/                      # isolated venv
├─ staging/                      # current incomplete run
├─ results/                      # completed local artifacts
└─ public-export/                # sanitized files proposed for GitHub
```

Rules:

- do not extract over an existing run
- do not put the supervised bundle inside the Git clone
- do not modify the source ZIP
- do not use a cloud-synced folder for active model writes when avoidable
- do not share one staging directory between attempts

## 8. ZIP and manifest verification

### PowerShell

```powershell
Get-FileHash .\gate2f_portable_execution_bundle_v1.zip -Algorithm SHA256
```

### Linux

```bash
sha256sum gate2f_portable_execution_bundle_v1.zip
```

The result must be:

```text
0355c1f20b736fcc996e2707ede2d1657e811ec74104a69b8d4cded1377c4c6f
```

After extraction, locate the public and private manifests from the bundle inventory. Verify:

- manifest file hashes
- all listed file hashes
- no missing file
- no unlisted supervised-data file
- no path traversal or external symlink
- no duplicate race keys inside a role
- exact Fold and role counts
- exact class map
- exact B3 baseline hash

Stop before supervised access if any hash or count differs.

## 9. Runtime contract

Use an isolated environment. Do not alter system Python.

Fixed core versions:

```text
Python 3.12.x
numpy==2.3.5
pandas==3.0.1
scipy==1.18.0
scikit-learn==1.9.0
```

### PowerShell example

```powershell
py -3.12 -m venv .\runtime\.venv
.\runtime\.venv\Scripts\python.exe -m pip install --upgrade pip
.\runtime\.venv\Scripts\python.exe -m pip install numpy==2.3.5 pandas==3.0.1 scipy==1.18.0 scikit-learn==1.9.0
.\runtime\.venv\Scripts\python.exe -m pip check
```

### Linux example

```bash
python3.12 -m venv runtime/.venv
runtime/.venv/bin/python -m pip install --upgrade pip
runtime/.venv/bin/python -m pip install numpy==2.3.5 pandas==3.0.1 scipy==1.18.0 scikit-learn==1.9.0
runtime/.venv/bin/python -m pip check
```

If the bundle runtime contract conflicts with these versions, stop and document the discrepancy. Do not silently select newer packages.

## 10. Pre-execution canaries

Before opening full supervised data, verify:

- runner imports without error
- contract files parse
- class map has all 120 valid ordered outcomes
- optimizer analytic gradient matches finite differences within the registered tolerance
- `beta = 0` reproduces the B3 winner prior
- `beta = 0` reproduces the B3 120-class raw distribution
- all generated probabilities are finite and non-negative
- probability sums are within `1e-12`
- no fallback distribution is used

A canary failure is a code or portability blocker, not a model-performance result.

## 11. Resource-only preflight

The resource preflight must not read:

- supervised features
- targets
- B3 predictions
- the private race table

Measure available physical memory for 60 seconds at five-second intervals: 13 samples total.

Admission requires all of the following:

- every sample is at least 3,072 MiB
- the final sample is at least 3,072 MiB
- the final sample is not more than 512 MiB below the first sample
- no other project training process is active
- no existing Gate 2-F, CatBoost, SAR, or S120 runner is active

Do not terminate unrelated processes automatically.

If preflight fails:

- supervised-data access count remains 0
- model-fit count remains 0
- no run attempt is consumed
- save the preflight report
- keep Issue #2 open
- do not produce performance claims

## 12. Gate 2-F scientific contract

Control:

- B3 autoregressive hierarchical frequency baseline

Treatment WR-S:

- B3 winner probability
- racer official snapshot residual correction

Treatment WR-H:

- WR-S inputs
- F1 as-of racer history residual correction

Final trifecta probability:

```text
Q(i,j,k) = Q1(i) × P2_B3(j | i) × P3_B3(k | i,j)
```

Only `Q1` may change. `P2_B3` and `P3_B3` must remain unchanged.

Fixed lambda grid:

```text
0.01
0.1
1.0
10.0
100.0
```

The bundle contracts are the source of truth for optimizer, preprocessing, selection, refit, calibration, seed, class order, and artifact schemas.

## 13. Execution order

Run completely serially:

1. Fold 1 WR-S
2. Fold 1 WR-H
3. Fold 2 WR-S
4. Fold 2 WR-H
5. Fold 3 WR-S
6. Fold 3 WR-H
7. Fold 4 WR-S
8. Fold 4 WR-H

At any moment:

- one Fold
- one arm
- one lambda
- one fit process

After each candidate:

1. save required artifacts
2. ensure the child process exits
3. release temporary objects
4. run garbage collection
5. measure available memory
6. wait up to 60 seconds for recovery

The next candidate may start only when available memory is at least 2,048 MiB.

## 14. Runtime memory safety

Monitor available physical memory once per second.

Warning threshold:

- below 1,024 MiB

Hard-stop threshold:

- below 512 MiB

At warning:

- the current candidate may continue
- do not start another candidate
- record the timestamp and minimum memory

At hard stop:

- stop only the current Gate 2-F child process
- preserve staging
- do not stop unrelated processes
- do not publish partial metrics as formal
- do not automatically retry with changed parameters

## 15. Formal result requirements

Formal Screening metrics may be produced only when both WR-S and WR-H complete all four Folds.

Required primary outputs:

- B3 calibrated pooled trifecta Log Loss
- WR-S raw pooled trifecta Log Loss
- WR-S calibrated pooled trifecta Log Loss
- WR-H raw pooled trifecta Log Loss
- WR-H calibrated pooled trifecta Log Loss
- WR-S versus B3 paired delta
- WR-H versus B3 paired delta
- WR-H versus WR-S paired delta

Required stability and diagnostics:

- Fold-level Log Loss
- number of improved Folds
- worst-Fold delta
- winner Log Loss
- exacta Log Loss
- top-3-set Log Loss
- second-given-first Log Loss
- third-given-first-second Log Loss
- trifecta Brier
- Hit@1, 3, 5, 10, 20
- MRR
- loss P90, P95, P99
- catastrophic-underweight rate
- normal-unique and abnormal-tail Log Loss
- cold-start subset
- selected lambda
- selected calibrator
- coefficient table and Fold stability
- peak memory and elapsed time
- prediction coverage

The second- and third-stage conditional losses must remain unchanged except for numerical tolerance.

## 16. Screening decision policy

A treatment is Screening-supported only when its pooled calibrated delta versus the registered control is negative.

Additional stability diagnostics:

- improvement in at least three of four Folds
- worst-Fold deterioration no greater than 0.01

These conditions do not select a formal Champion. They only determine the next research action.

### Branch A: WR-H or WR-S is clearly supported

1. freeze the exact arm, lambda-selection rule, preprocessing, and calibration policy
2. publish sanitized Screening summaries through a Draft PR
3. update Issue #2 with exact metrics
4. create a separate explicit authorization item for Confirmation
5. do not open Confirmation data yet

### Branch B: pooled improvement exists but Fold stability is weak

1. keep the result as exploratory Screening evidence
2. diagnose the unstable Fold or regime
3. allow at most one pre-registered follow-up Screening experiment
4. do not progress to Confirmation

### Branch C: neither arm improves B3

1. record that winner-only linear residual correction was not supported in this form
2. do not claim that racer history is scientifically useless
3. return to Gate 2-E evidence
4. prioritize a pre-registered second-stage or ordering-focused correction
5. keep B3 as the Screening reference

### Branch D: host or portability failure

1. preserve staging and validation records
2. publish no partial performance result
3. keep Issue #2 open
4. fix only portability or resource orchestration
5. do not change the scientific model to make it fit

## 17. Confirmation phase after a supported Screening result

Confirmation is a separate gated phase. It requires explicit authorization after the Screening configuration is frozen.

Before Confirmation:

- select one candidate without viewing Confirmation metrics
- freeze all model and preprocessing choices
- freeze calibration and metric code
- freeze artifact hashes
- create a confirmation run manifest
- verify Confirmation access remains 0 until the authorized atomic run

During Confirmation:

- no hyperparameter tuning
- no feature changes
- no candidate switching based on partial results
- no Final-lock access

After Confirmation:

- assess the pre-registered success criteria
- either reject progression, request one justified redesign, or freeze the final candidate

## 18. Final lock policy

The Final lock remains sealed until all of the following are complete:

- Screening completed
- Confirmation completed
- final candidate frozen
- code and runtime frozen
- final reporting contract frozen
- explicit one-shot authorization issued

Final lock must never be used for iteration. Unlock count must remain 0 until the authorized final run.

## 19. GitHub publication workflow

Never commit private bundle data to GitHub.

For a completed or failed external-host run:

1. update local `main`
2. create a fresh branch from `origin/main`
3. use branch name `research/gate2f-portable-screening-result-v1` for the first result
4. add only sanitized small artifacts
5. update `boatrace/research/current_research_status_v1.md`
6. run the public GitHub validation workflow
7. create a Draft PR
8. use `Closes #2` only if all required Gate 2-F outputs completed
9. otherwise use `Tracks #2`
10. do not merge until review is complete

Allowed public artifacts:

- sanitized report
- sanitized validation summary
- pooled and Fold metrics
- paired-delta summary
- coefficient summary
- resource summary
- public run manifest
- guard summary

Forbidden public artifacts:

- ZIP
- private manifest
- supervised data
- models and preprocessors
- full predictions
- full race-level loss ledger
- machine-specific paths
- credentials or host identity

## 20. Required result directory

Recommended local result structure:

```text
results/gate2f_portable_screening_run_v1/
├─ models/
├─ preprocessors/
├─ predictions_raw/
├─ predictions_calibrated/
├─ selection_results/
├─ calibration_parameters/
├─ coefficient_tables/
├─ metrics_by_arm_fold_v1.csv
├─ metrics_pooled_v1.csv
├─ paired_loss_differences_v1.csv
├─ paired_daily_loss_summary_v1.csv
├─ coefficient_stability_v1.csv
├─ resource_profile_v1.csv
├─ run_manifest_v1.json
├─ run_manifest_v1.sha256
└─ run_report_v1.md
```

Validation structure:

```text
execution_validation/
├─ bundle_integrity_validation_v1.json
├─ bundle_file_hash_validation_v1.csv
├─ split_and_role_validation_v1.json
├─ prohibited_column_validation_v1.json
├─ runtime_inventory_v1.json
├─ installed_packages_v1.csv
├─ pip_check_v1.txt
├─ runner_import_test_v1.json
├─ optimizer_canary_v1.json
├─ probability_canary_v1.json
├─ target_host_resource_preflight_v1.json
├─ data_access_audit_v1.json
├─ leakage_validation_v1.json
├─ confirmation_guard_v1.json
├─ final_lock_guard_v1.json
└─ execution_validation_v1.json
```

## 21. Failure statuses

Use one clear final status:

- `gate2f_screening_completed`
- `target_host_resource_preflight_failed`
- `resource_blocked_on_target_host`
- `memory_not_recovered_after_candidate`
- `bundle_integrity_failed`
- `runtime_contract_failed`
- `optimizer_canary_failed`
- `probability_contract_failed`
- `failed_for_non_memory_reason`

Only `gate2f_screening_completed` permits formal Gate 2-F metrics.

## 22. Troubleshooting rules

### ZIP or manifest hash mismatch

- stop
- do not extract or run
- obtain a fresh byte-identical copy

### Runtime package mismatch

- recreate the isolated venv
- do not upgrade the scientific stack

### Canary failure

- stop before full data access
- report the exact failing contract
- do not treat it as a model result

### Preflight failure

- keep supervised access and fit count at 0
- close memory-consuming applications manually
- rerun only after the host is stable

### Candidate hard stop

- preserve staging
- no automatic parameter reduction
- no partial formal metrics

### Cross-platform path failure

- patch path handling only
- do not alter model math, data values, split, or evaluation
- record the code hash change and rerun canaries

## 23. Operator handoff record

Every new host or operator should record:

- date and operator
- OS and architecture
- total physical memory
- Python version
- package versions
- ZIP and manifest hashes
- bundle integrity result
- Fold and role counts
- preflight samples
- run ID
- completed Fold count per arm
- final status
- formal metrics availability
- Confirmation and Final-lock access counts
- Git branch, commit, PR, and Issue update

## 24. Ready-to-use Codex instruction

Use the following as the starting instruction on the external host:

```text
Open the cloned sushikikun/keibaAI repository and read, in order:

1. boatrace/docs/next_steps_and_external_host_handoff_v1.md
2. boatrace/research/gate2_b3_winner_residual_v1/portable_execution_runbook_v1.md
3. boatrace/research/gate2_b3_winner_residual_v1/portable_bundle_manifest_public_v1.json
4. GitHub Issue #2

Locate gate2f_portable_execution_bundle_v1.zip outside the Git repository. Verify the ZIP SHA-256 is 0355c1f20b736fcc996e2707ede2d1657e811ec74104a69b8d4cded1377c4c6f. Verify the public manifest SHA-256 is 92ccca26cc4ae08b764a8b72c73ac9444e27a2349f667be5613c912b1d0e1b3a, the private manifest SHA-256 is 386e6531d55fd43284a4c9b8ec4ef2ca52713f2c3ca0dadbfd1e78fe60156bdb, and the protected B3 baseline manifest SHA-256 is f3eb62dc643c9f2561f5ec1827e3d070b63fd85952425ea69b39dc0f73a8c6e3.

Do not read supervised data until all bundle, runtime, canary, guard, and resource-preflight checks pass. Execute WR-S and WR-H across Screening Folds 1–4 completely serially using only the bundle contracts. Never access Confirmation or Final lock. Never use odds, popularity, payout, F2, future information, or same-day previous-race outcomes. Do not publish the ZIP, private manifest, data, models, preprocessors, or full predictions.

When finished, create a sanitized Draft PR from a fresh branch. Use Closes #2 only if both arms completed all four Folds with formal metrics; otherwise use Tracks #2. Do not merge the PR.
```

## 25. Definition of project continuity

The project is portable when a new trusted host can:

1. clone GitHub
2. obtain the private ZIP
3. verify all hashes
4. recreate the fixed runtime
5. pass canaries and resource admission
6. execute Gate 2-F without consulting the original PC
7. publish a sanitized Draft PR linked to Issue #2

Until the private ZIP is stored in a durable trusted location with verified backup, GitHub alone is not a complete recovery mechanism.
