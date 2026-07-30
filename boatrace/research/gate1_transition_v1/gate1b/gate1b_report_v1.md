# Gate 1-B final research snapshot validation v1

Gate 1-B passed. The snapshot was regenerated independently of research_v0.1 and promoted only after all checks passed.

1. Source release: `corpus_release_v1_200118_4f5554a4057e`
2. Release manifest SHA-256: `09ba1172dbd403aa4066e7934348fca5102df66618b73be26b506b72354fb6fe`
3. Final audit candidates: 219,240
4. Strict complete races: 200,118
5. Non-strict races: 19,122
6. Prediction-feature-eligible races: 213,016
7. Primary supervised candidates: 200,118
8. Normal unique outcomes: 200,118
9. Abnormal-tail unique outcomes: 0
10. Tied outcomes: 186 (178 have prediction-time features and remain tied-label candidates)
11. Auxiliary-only candidates: 12,720
12. Research-unavailable candidates: 6,224
13. Strict prediction-feature-eligible races: 200,118
14. Strict primary candidates: 200,118
15. Target mismatches: 0
16. Point-in-Time leakage findings: 0
17. Safe-core features: 49; forbidden features: 0
18. Snapshot ID: `research_v1_219240_1d586db9a15a`
19. Snapshot path: `results/boatrace_model_research/snapshots/research_v1_219240_1d586db9a15a`
20. Snapshot storage: UTF-8 CSV (no pre-existing Parquet writer was available)
21. Dataset manifest SHA-256: `eb2ddf85af16255dbc9d64f264ba0565da73949ccc957dda0b1de6d0bf48bf4c`
22. Snapshot logical SHA-256: recorded in `dataset_manifest.json`
23. Uniform sanity: passed (`ln(120)`, `ln(6)`, `ln(30)`, `ln(20)`, `ln(5)`, `ln(4)`, Brier `119/120`)
24. Oracle one-hot sanity: passed (log loss/Brier 0, hit@1 1)
25. Parser-regime blockers: 0
26. Protected-anchor differences: 0
27. Automation status: `PAUSED`
28. Data source status: Gate 1-A immutable release plus its fixed audit artifacts; strict rows re-transformed from release-pinned facts and non-strict rows reconstructed from archived originals where available.
29. Gate 1-B result: `passed=true`
30. Unresolved blockers: none

No collection, external web access, package change, Git action, Walk-forward split, final lock, model training, model evaluation, or experiment activation was performed.
