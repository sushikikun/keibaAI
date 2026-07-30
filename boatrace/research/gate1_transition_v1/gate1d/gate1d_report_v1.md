# Gate 1-D report

1. Gate 1-D snapshot research_v1_219240_1d586db9a15a and Gate 1-C manifest 379f459cff4d7e9327c478c9ff6b2a3069c48604c05ca67af9cf8b0a9f64b8d3 were reverified.
2. Gate 1-A release corpus_release_v1_200118_4f5554a4057e and Gate 1-B snapshot were retained read-only.
3. Gate 1-C counts are candidates 219240, U0 200118, U1 178, H 109, programs 15.
4. Gate 1-C equipment C/D generation assignments are 0; only official A/B evidence is eligible.
5. Automation is PAUSED and no collection runner was started.
6. F0_safe_core_49 was reused unchanged.
7. F1_asof_racer_history was materialized for 213016 target races and 1278096 entries.
8. F1 source dates are strictly earlier than target dates; target and same-day rows are excluded.
9. F1 cold-start entries are null with a flag: 2731 (0.002137).
10. F1 lineage preserves source dates, hashes, and point-in-time status.
11. F2 motor history contains official A/B verified entries and unresolved nulls.
12. F2 boat history contains official A/B verified entries and unresolved nulls.
13. F2 generation starts must be strictly earlier than target dates.
14. F2 same-day, future, C/D, pre-boundary, and cross-generation counts are all zero.
15. F3 relative features remain not_materialized; no placeholder files were created.
16. F4 auxiliary targets remain separate and are not inference inputs.
17. F5 temporal features remain not_materialized because meeting evidence is absent.
18. F6 external/late-stage features remain blocked and not_materialized.
19. Scope registry covers F0 through F6 with rules and ownership.
20. Deferred preprocessing registry covers scaling, imputation, encoding, PCA, selection, winsorization, embeddings, and learned expectations.
21. All deferred preprocessing has train_fold_only fit and apply scope.
22. Snapshot/universe join audit passed for six entries per target race.
23. Feature sidecar ID is feature_sidecar_v1_213016_6fa39ceeb32f and final storage is under results/boatrace_model_research/feature_sidecars.
24. Sidecar storage is CSV+JSON and includes racer/equipment lineage and profiles.
25. All seven leakage canaries were rejected with zero accepted sources.
26. Feature quality is diagnostic-only; no corrective mutation was applied.
27. Input-order, chunk-size, and idempotent rebuild checks passed.
28. Protected anchor before and after Gate 1-D is unchanged.
29. Unregistered and forbidden feature counts are zero.
30. No walk-forward, final lock, training, evaluation, or champion output was created.
31. Validation errors are empty; warnings document only deferred/unresolved scope.
32. Gate 1-D validation passed with U0/U1 accounting complete and automation paused.
33. Gate 1-D sidecar migration is complete; Gate 2 requires separate authorization.
