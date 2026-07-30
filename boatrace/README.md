# Boat-race AI research foundation

This directory is an independent boat-race AI research project inside `keibaAI`. The existing keibaAI horse-racing project is not moved or rewritten.

## Scope

- Research-only code, contracts, validation, audit, and sanitized Gate 1 / Gate 2 artifacts.
- No raw HTML/JSON, complete-corpus bodies, snapshots, feature rows, odds/payout tables, models, checkpoints, databases, virtual environments, caches, secrets, or local machine paths.
- Large research files over 10 MiB are excluded from the public import. The complete inclusion/exclusion ledger is `manifests/github_import_inventory_v1.csv`.

## Current public status

- Strict complete race count: 200,118 (local-only source artifact; not included here).
- Audit candidate count: 219,240 (local-only source artifact; not included here).
- Primary supervised U0 scope: 200,118 races.
- Main target: future trifecta log loss without odds leakage.
- B3 calibrated screening log loss reference: 4.151932308088278.
- Current Gate 2-F status: `resource_blocked`; available physical memory reached 356.5 MiB, below the 512 MiB hard-stop threshold. No arm ranking or formal champion is claimed.
- Confirmation and Final lock access: 0 in the migrated research record.

## Layout

`configs/`, `docs/`, `research/`, `src/`, `scripts/`, `tests/`, `schemas/`, and `manifests/` contain sanitized project material. Local data release IDs and hashes are recorded in `manifests/local_data_registry_v1.json`; those local artifacts remain local-only and are not committed here.

## Reproducibility

Run tests from the repository root with the project's supported Python environment. Public files use placeholders such as `<PROJECT_ROOT>` instead of local absolute paths. No dependency installation or data download is performed by this import.
