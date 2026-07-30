# Gate 2-F portable execution runbook

This is the execution entry point for continuing Gate 2-F on another trusted PC. Read the full canonical handoff first:

- `boatrace/docs/next_steps_and_external_host_handoff_v1.md`
- GitHub Issue `#2 Complete Gate 2-F winner residual screening`

## Current state

- Gate 2-F performance is unresolved.
- WR-S and WR-H have no complete four-Fold metrics.
- The optimizer and probability canaries passed on the source host.
- The source host failed the sustained-memory admission gate.
- No clean supervised run was started from that failed preflight.
- Confirmation access is 0.
- Final-lock access/unlock is 0.
- Automation is `PAUSED`.

## Required private asset

The Git repository does not contain the supervised execution package. Obtain this file privately:

```text
gate2f_portable_execution_bundle_v1.zip
```

Expected SHA-256:

```text
0355c1f20b736fcc996e2707ede2d1657e811ec74104a69b8d4cded1377c4c6f
```

Additional fixed hashes:

```text
public manifest:  92ccca26cc4ae08b764a8b72c73ac9444e27a2349f667be5613c912b1d0e1b3a
private manifest: 386e6531d55fd43284a4c9b8ec4ef2ca52713f2c3ca0dadbfd1e78fe60156bdb
B3 baseline:      f3eb62dc643c9f2561f5ec1827e3d070b63fd85952425ea69b39dc0f73a8c6e3
```

## Mandatory order of operations

1. Clone or update `sushikikun/keibaAI`.
2. Place the ZIP outside the Git clone.
3. Verify the ZIP SHA before extraction.
4. Extract into a new empty directory.
5. Verify public and private manifests and every listed file.
6. Confirm the package contains 126,978 Screening races, four Folds, zero Confirmation rows, and zero Final-lock rows.
7. Confirm odds, popularity, payout, F2, future, and same-day previous-result columns are absent.
8. Create an isolated Python 3.12 environment.
9. Install only the fixed scientific stack.
10. Run import, optimizer, probability, class-map, and guard canaries.
11. Run the 13-sample resource-only preflight without opening supervised data.
12. Start training only after every admission condition passes.
13. Execute one Fold, one arm, one lambda, and one fit process at a time.
14. Produce formal metrics only after WR-S and WR-H both complete all four Folds.
15. Publish only sanitized small summaries through a Draft PR linked to Issue #2.

## Fixed runtime

```text
Python 3.12.x
numpy==2.3.5
pandas==3.0.1
scipy==1.18.0
scikit-learn==1.9.0
```

Do not silently upgrade or substitute packages.

## Resource admission

Collect 13 available-memory samples at five-second intervals over 60 seconds.

All must be true:

- every sample is at least 3,072 MiB
- final available memory is at least 3,072 MiB
- final memory is not more than 512 MiB below the first sample
- no other training process is active
- no Gate 2-F, CatBoost, SAR, or S120 process is active

If this check fails, supervised-data access and model-fit count must stay at 0.

## Serial execution order

```text
Fold 1 WR-S
Fold 1 WR-H
Fold 2 WR-S
Fold 2 WR-H
Fold 3 WR-S
Fold 3 WR-H
Fold 4 WR-S
Fold 4 WR-H
```

The next candidate starts only after available memory recovers to at least 2,048 MiB.

Warning threshold:

```text
1,024 MiB
```

Hard-stop threshold:

```text
512 MiB
```

At hard stop, terminate only the current Gate 2-F child process, preserve staging, and do not formalize partial metrics.

## Model contract

```text
Q(i,j,k) = Q1(i) × P2_B3(j | i) × P3_B3(k | i,j)
```

Only the winner distribution `Q1` may be corrected. B3 second- and third-stage conditional distributions remain fixed.

Arms:

- WR-S: B3 winner prior plus official racer snapshot residual
- WR-H: WR-S plus F1 as-of racer-history residual

Lambda grid:

```text
0.01, 0.1, 1.0, 10.0, 100.0
```

The bundle contracts are authoritative for preprocessing, selection, refit, calibration, seed, and output schema.

## Completion rule

Formal Gate 2-F metrics exist only if:

- WR-S completes four of four Folds
- WR-H completes four of four Folds
- prediction coverage is 100%
- all 120-class distributions pass the probability contract
- leakage checks pass
- Confirmation and Final-lock access remain 0
- the protected B3 hash remains unchanged

The result remains Screening evidence. It does not automatically select a formal Champion.

## GitHub return path

Use a fresh branch from `origin/main`:

```text
research/gate2f-portable-screening-result-v1
```

Create a Draft PR.

- use `Closes #2` only after full successful completion
- otherwise use `Tracks #2`
- never commit the ZIP, private manifest, supervised data, models, preprocessors, or full predictions
- do not merge without review

For detailed validation, output schemas, failure statuses, troubleshooting, and the post-Screening roadmap, follow `boatrace/docs/next_steps_and_external_host_handoff_v1.md`.
