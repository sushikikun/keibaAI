# Dependency gap report

Wave 1 missing: scipy, scikit-learn. Later-wave missing: catboost, lightgbm, xgboost, torch, pyarrow, duckdb, optuna. No package was installed or substituted. Gate 2 authorization must explicitly cover local venv creation, required package installation, training runner execution, artifact storage, and screening metric viewing.
