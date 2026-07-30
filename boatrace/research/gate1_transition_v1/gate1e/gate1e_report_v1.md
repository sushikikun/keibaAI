# Gate 1-E report

1. Gate 1-D inputs verified: snapshot research_v1_219240_1d586db9a15a, dataset manifest and sidecar feature_sidecar_v1_213016_6fa39ceeb32f.
2. Gate 1-D manifest SHA-256 is 75b5756e2b764912fdf110733813add08543132af2279666e56ae11d43912db7; sidecar manifest SHA-256 is 2a4d0549e1763ac37dc4904bd2e118142051f8058a24e61f7b36d0f4ecaff87d.
3. Gate 1-A/B/C/D passed values and protected anchors were reverified.
4. Candidate/U0/U1 counts are 219240/200118/178; prediction entries are 1278096.
5. Same-day, future, equipment C/D and Gate 1-D protected-anchor differences are zero.
6. Automation remains PAUSED and model training count is zero.
7. Final lock candidate is 2025-07-28 through 2026-07-27 (365 calendar days).
8. Final lock U0 count is 50802 with 24 venues and 12 months.
9. Final lock per-venue U0 range is 1788 to 2401; duplicate race keys are zero.
10. Final lock status is sealed; performance_viewed=false; unlock_count=0; immutable_after_creation=true.
11. Final lock logical SHA-256 is 9294f86b36fef245acfd1a142ddca85ed69efa97a03aac990eebbd945b12eaa2.
12. Screening folds fixed: 4; confirmation folds fixed: 2.
13. Screening Fold 1 train/selection/calibration/evaluation counts are 42619/13190/12149/12822.
14. Screening Fold 2 train/selection/calibration/evaluation counts are 55809/12149/12822/12953.
15. Screening Fold 3 train/selection/calibration/evaluation counts are 67958/12822/12953/13169.
16. Screening Fold 4 train/selection/calibration/evaluation counts are 80780/12953/13169/12288.
17. Confirmation Fold 1 train/selection/calibration/evaluation counts are 93733/13169/12288/12727.
18. Confirmation Fold 2 train/selection/calibration/evaluation counts are 106902/12288/12727/17399.
19. Every evaluation period has at least 8000 U0 entries and 24-venue coverage.
20. Split membership SHA-256 is d3318c40504b34f163cf3db12ce9469002aa21804659f250574305978864b8bc; split ID is split_v1_d3318c40504b.
21. Confirmation lock ID is confirmation_lock_v1_287f0917ecce; final lock ID is final_lock_v1_365d_9294f86b36fe.
22. Split guard dry-run rejects cross-stage and unknown-key access.
23. Final lock guard dry-run rejects missing unlock, wrong hash, double unlock and manifest mutation.
24. Fold preprocessing contracts isolate fit, refit, calibration and evaluation scopes.
25. Screening uniform dry-run passes; synthetic trifecta log loss equals ln(120).
26. Confirmation and final-lock metrics/predictions were not viewed or created.
27. F3/F5 remain not_materialized; dependent programs remain blocked or conditional.
28. Experiment, checkpoint, prediction and class-map contracts are fixed.
29. Seed policy is deterministic SHA-256-derived; best-seed post-selection is forbidden.
30. Environment inventory is complete; GPU is unavailable in the current runtime.
31. Missing Wave 1 dependencies are scipy, scikit-learn; no install was performed.
32. Gate 1-E protocol status is protocol_passed_runtime_blocked; formal_model_research_ready=false.
33. Gate 2 requires explicit authorization for venv, package install, runner, artifact storage and screening metrics.
34. Gate 1-E did not unlock final lock, start training, or start Gate 2; unresolved item is runtime dependency approval.
