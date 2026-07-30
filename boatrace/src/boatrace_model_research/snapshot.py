from __future__ import annotations

import csv
import importlib.util
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .class_map import TrifectaClassMap, load_class_map
from .common import (
    SNAPSHOT_ID_PATTERN,
    atomic_write_json,
    canonical_json_bytes,
    ensure_relative_to,
    read_json,
    relative_posix,
    sha256_bytes,
    sha256_file,
)


RACE_FEATURE_COLUMNS = [
    "race_key",
    "race_date",
    "venue_code",
    "race_no",
    "closed_at",
    "beforeinfo_time",
    "distance",
    "grade_number",
    "preview_air_temperature",
    "preview_water_temperature",
    "preview_wave_height",
    "preview_weather",
    "preview_wind_direction_number",
    "preview_wind_speed",
    "subtitle",
    "title",
]

BOAT_FEATURE_COLUMNS = [
    "race_key",
    "lane",
    "race_date",
    "venue_code",
    "race_no",
    "racer_id",
    "racer_name",
    "racer_age",
    "racer_branch_number",
    "racer_class_number",
    "average_start_timing",
    "national_top_1_percent",
    "national_top_2_percent",
    "national_top_3_percent",
    "local_top_1_percent",
    "local_top_2_percent",
    "local_top_3_percent",
    "motor_no",
    "motor_top_2_percent",
    "motor_top_3_percent",
    "boat_no",
    "boat_top_2_percent",
    "boat_top_3_percent",
    "program_weight",
    "body_weight",
    "weight_adjustment",
    "exhibition_course",
    "exhibition_start_timing",
    "exhibition_time",
    "tilt",
    "propeller_new",
    "propeller_status",
    "parts_exchange_status",
]

TOP3_TARGET_COLUMNS = [
    "race_key",
    "race_date",
    "venue_code",
    "race_no",
    "target_status",
    "target_class_id",
    "first_lane",
    "second_lane",
    "third_lane",
    "target_label",
]

AUXILIARY_TARGET_COLUMNS = [
    "race_key",
    "lane",
    "race_date",
    "venue_code",
    "race_no",
    "target_status",
    "actual_finish",
    "actual_course",
    "actual_start_timing",
    "winning_technique_number",
]

ELIGIBILITY_COLUMNS = [
    "race_key",
    "race_date",
    "venue_code",
    "race_no",
    "source_batch",
    "target_status",
    "prediction_input_eligible",
    "main_evaluation_eligible",
    "exclusion_reasons",
]

IMPLEMENTATION_FILES = [
    "src/boatrace_model_research/__init__.py",
    "src/boatrace_model_research/common.py",
    "src/boatrace_model_research/class_map.py",
    "src/boatrace_model_research/snapshot.py",
    "src/boatrace_model_research/validation.py",
    "src/boatrace_model_research/evaluation.py",

]

CONFIG_FILES = [
    "configs/boatrace_model_evaluation_v1_1.json",
    "configs/trifecta_class_map_v1.json",
    "configs/boatrace_model_dataset_contract_v1.json",
]

DOCUMENTATION_FILES = [
    "docs/boatrace_model_evaluation_v1_1.md",
]


@dataclass(frozen=True)
class SourceState:
    owners_by_batch: dict[str, tuple[str, ...]]
    batch_records: dict[str, dict[str, Any]]
    status: dict[str, Any]
    status_sha256: str
    registry_logical_sha256: str
    registry_metadata: dict[str, str]

    @property
    def owner_count(self) -> int:
        return sum(len(keys) for keys in self.owners_by_batch.values())


class CsvTableWriter:
    def __init__(self, path: Path, columns: Sequence[str]):
        self.path = path
        self.columns = list(columns)
        self.row_count = 0
        self.missing = Counter[str]()
        self._handle = path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._handle,
            fieldnames=self.columns,
            extrasaction="raise",
            lineterminator="\n",
        )
        self._writer.writeheader()

    def write(self, row: Mapping[str, object]) -> None:
        normalized: dict[str, object] = {}
        for column in self.columns:
            value = row.get(column, "")
            if value is None:
                value = ""
            if value == "":
                self.missing[column] += 1
            normalized[column] = value
        self._writer.writerow(normalized)
        self.row_count += 1

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "CsvTableWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _read_stable_source_state(corpus_root: Path, attempts: int = 20) -> SourceState:
    registry_path = corpus_root / "integrity_registry.sqlite"
    status_path = corpus_root / "status.json"
    if not registry_path.is_file() or not status_path.is_file():
        raise FileNotFoundError("formal complete corpus registry or status.json is missing")

    last_error = ""
    for _ in range(attempts):
        status_before_bytes = status_path.read_bytes()
        status = json.loads(status_before_bytes.decode("utf-8-sig"))
        connection = sqlite3.connect(_sqlite_uri(registry_path), uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            batch_rows = connection.execute(
                """
                SELECT batch, manifest_sha256, integrity_status, hash_status,
                       complete_races, entry_rows, odds_rows, payout_rows,
                       errors_json, candidates, excluded, reasons_json
                FROM batches
                ORDER BY batch
                """
            ).fetchall()
            owner_rows = connection.execute(
                "SELECT race_key, batch FROM race_owners ORDER BY race_key"
            ).fetchall()
            metadata_rows = connection.execute(
                "SELECT key, value FROM metadata ORDER BY key"
            ).fetchall()
            connection.rollback()
        finally:
            connection.close()

        status_after_bytes = status_path.read_bytes()
        if status_before_bytes != status_after_bytes:
            last_error = "status.json changed during registry read"
            time.sleep(0.05)
            continue

        batch_records: dict[str, dict[str, Any]] = {}
        for row in batch_rows:
            batch_records[str(row[0])] = {
                "batch": str(row[0]),
                "manifest_sha256": str(row[1]),
                "integrity_status": str(row[2]),
                "hash_status": str(row[3]),
                "complete_races": int(row[4]),
                "entry_rows": int(row[5]),
                "odds_rows": int(row[6]),
                "payout_rows": int(row[7]),
                "errors": json.loads(row[8]),
                "candidates": int(row[9]),
                "excluded": int(row[10]),
                "reasons": json.loads(row[11]),
            }

        owners: dict[str, list[str]] = defaultdict(list)
        for race_key, batch in owner_rows:
            owners[str(batch)].append(str(race_key))
        owner_count = len(owner_rows)
        if int(status.get("complete_races", -1)) != owner_count:
            last_error = (
                f"status/registry count mismatch: status={status.get('complete_races')} "
                f"registry={owner_count}"
            )
            time.sleep(0.05)
            continue
        if int(status.get("batch_count", -1)) != len(batch_records):
            last_error = (
                f"status/registry batch mismatch: status={status.get('batch_count')} "
                f"registry={len(batch_records)}"
            )
            time.sleep(0.05)
            continue

        logical_payload = {
            "metadata": metadata_rows,
            "batches": batch_rows,
            "race_owners": owner_rows,
        }
        return SourceState(
            owners_by_batch={
                batch: tuple(keys) for batch, keys in sorted(owners.items())
            },
            batch_records=batch_records,
            status=status,
            status_sha256=sha256_bytes(status_before_bytes),
            registry_logical_sha256=sha256_bytes(canonical_json_bytes(logical_payload)),
            registry_metadata={str(key): str(value) for key, value in metadata_rows},
        )
    raise RuntimeError(f"could not obtain a stable formal corpus state: {last_error}")


def _read_selected_rows(
    path: Path,
    expected_columns: Sequence[str],
    selected_keys: set[str],
) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(expected_columns):
            raise ValueError(
                f"source schema mismatch for {path}: "
                f"expected={list(expected_columns)} actual={reader.fieldnames}"
            )
        for row in reader:
            race_key = row.get("race_key", "")
            if race_key in selected_keys:
                rows[race_key].append(row)
    return rows


def _int_or_none(value: object, minimum: int, maximum: int) -> int | None:
    text = str(value or "").strip()
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if minimum <= parsed <= maximum else None


def _target_status(
    race: Mapping[str, str] | None,
    entries: Sequence[Mapping[str, str]],
) -> tuple[str, tuple[int, int, int] | None]:
    if race is None or race.get("result_status") != "settled_standard_six_boat":
        return "void", None
    if len(entries) != 6:
        return "void", None
    lanes = [_int_or_none(row.get("lane"), 1, 6) for row in entries]
    finishes = [_int_or_none(row.get("actual_finish"), 1, 6) for row in entries]
    if sorted(value for value in lanes if value is not None) != list(range(1, 7)):
        return "void", None
    if any(value is None for value in finishes):
        return "void", None
    normalized_finishes = [int(value) for value in finishes if value is not None]
    if len(set(normalized_finishes)) != 6:
        return "tied", None
    if sorted(normalized_finishes) != list(range(1, 7)):
        return "void", None
    finish_to_lane = {
        int(finish): int(lane)
        for finish, lane in zip(normalized_finishes, lanes)
        if lane is not None
    }
    return "unique_order", (
        finish_to_lane[1],
        finish_to_lane[2],
        finish_to_lane[3],
    )


def _prediction_exclusion_reasons(
    race_rows: Sequence[Mapping[str, str]],
    entries: Sequence[Mapping[str, str]],
) -> list[str]:
    reasons: list[str] = []
    if len(race_rows) == 0:
        reasons.append("missing_race_facts")
    elif len(race_rows) > 1:
        reasons.append("duplicate_race_facts")
    race = race_rows[0] if len(race_rows) == 1 else None
    if race is not None:
        for column in ("race_key", "race_date", "venue_code", "race_no", "closed_at"):
            if not str(race.get(column, "")).strip():
                reasons.append(f"missing_required_race_field:{column}")
    if len(entries) != 6:
        reasons.append("entry_count_not_six")
    lanes = [_int_or_none(row.get("lane"), 1, 6) for row in entries]
    if len(entries) == 6 and sorted(value for value in lanes if value is not None) != list(
        range(1, 7)
    ):
        reasons.append("lane_set_not_1_to_6")
    if any(not str(row.get("racer_id", "")).strip() for row in entries):
        reasons.append("missing_racer_id")
    if race is not None:
        identity_columns = ("race_key", "race_date", "venue_code", "race_no")
        if any(
            any(str(row.get(column, "")) != str(race.get(column, "")) for column in identity_columns)
            for row in entries
        ):
            reasons.append("race_entry_identity_mismatch")
    return sorted(set(reasons))


def _identity(
    race_key: str,
    race: Mapping[str, str] | None,
    entries: Sequence[Mapping[str, str]],
) -> dict[str, str]:
    fallback = entries[0] if entries else {}
    return {
        "race_key": race_key,
        "race_date": str((race or {}).get("race_date") or fallback.get("race_date") or ""),
        "venue_code": str((race or {}).get("venue_code") or fallback.get("venue_code") or ""),
        "race_no": str((race or {}).get("race_no") or fallback.get("race_no") or ""),
    }


def _verify_batch_source(
    project_root: Path,
    corpus_root: Path,
    batch: str,
    record: Mapping[str, Any],
) -> tuple[Path, Path, dict[str, Any], dict[str, str]]:
    batch_dir = corpus_root / "batches" / batch
    manifest_path = batch_dir / "batch_manifest.json"
    race_path = batch_dir / "race_facts.csv"
    entry_path = batch_dir / "entry_facts.csv"
    if record.get("integrity_status") != "passed":
        raise ValueError(f"source batch {batch} is not integrity_status=passed")
    if record.get("hash_status") != "verified":
        raise ValueError(f"source batch {batch} is not hash_status=verified")
    if not manifest_path.is_file() or not race_path.is_file() or not entry_path.is_file():
        raise FileNotFoundError(f"source batch {batch} is missing a required artifact")
    manifest_hash = sha256_file(manifest_path)
    if manifest_hash != record.get("manifest_sha256"):
        raise ValueError(f"source batch {batch} manifest differs from integrity registry")
    manifest = read_json(manifest_path)
    declared = manifest.get("artifact_sha256") or {}
    actual = {
        "manifest": manifest_hash,
        "race_facts": sha256_file(race_path),
        "entry_facts": sha256_file(entry_path),
    }
    for name in ("race_facts", "entry_facts"):
        if not declared.get(name):
            raise ValueError(f"source batch {batch} has no declared hash for {name}")
        if actual[name] != declared[name]:
            raise ValueError(f"source batch {batch} {name} hash mismatch")
    return race_path, entry_path, manifest, actual


def _parquet_availability() -> dict[str, Any]:
    available = importlib.util.find_spec("pyarrow") is not None
    return {
        "available": available,
        "writer_engine": "pyarrow" if available else None,
        "reason": (
            None
            if available
            else "PyArrow is not installed; CSV fallback used without installing dependencies."
        ),
    }


def _convert_csv_to_parquet(csv_path: Path) -> Path:
    import pyarrow.csv as arrow_csv  # type: ignore[import-not-found]
    import pyarrow.parquet as arrow_parquet  # type: ignore[import-not-found]

    parquet_path = csv_path.with_suffix(".parquet")
    reader = arrow_csv.open_csv(csv_path)
    writer = None
    try:
        for batch in reader:
            if writer is None:
                writer = arrow_parquet.ParquetWriter(
                    parquet_path,
                    batch.schema,
                    compression="zstd",
                )
            writer.write_batch(batch)
        if writer is None:
            raise ValueError(f"cannot convert empty CSV without a schema: {csv_path}")
    finally:
        if writer is not None:
            writer.close()
    csv_path.unlink()
    return parquet_path


def _role_for_feature(column: str, table: str) -> str:
    if column == "race_key":
        return "identifier"
    if table == "boat_features" and column in {"lane", "racer_id", "racer_name"}:
        return "identifier"
    if column in {"race_date", "venue_code", "race_no"}:
        return "official_race_context"
    if column == "closed_at":
        return "official_cutoff_boundary"
    return "official_prediction_input"


def _feature_manifest(
    dataset_contract: Mapping[str, Any],
    table_writers: Mapping[str, CsvTableWriter],
    table_files: Mapping[str, Path],
    class_map: TrifectaClassMap,
) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    for table in ("race_features", "boat_features"):
        writer = table_writers[table]
        tables[table] = {
            "file": table_files[table].name,
            "grain": dataset_contract["feature_tables"][table]["grain"],
            "columns": [
                {
                    "name": column,
                    "role": _role_for_feature(column, table),
                    "availability": "official_at_or_before_prediction_cutoff",
                    "nullable": (
                        column
                        not in dataset_contract["feature_tables"][table][
                            "required_non_null_columns"
                        ]
                    ),
                    "missing_count": int(writer.missing[column]),
                }
                for column in writer.columns
            ],
        }
    return {
        "manifest_id": "boatrace_model_feature_manifest_v1",
        "created_at": _now(),
        "prediction_cutoff_contract": "boatrace_model_evaluation_v1_1",
        "dataset_contract": "boatrace_model_dataset_contract_v1",
        "class_map_mapping_sha256": class_map.mapping_sha256,
        "inference_forbidden_exact_columns": dataset_contract[
            "forbidden_feature_policy"
        ]["exact_inference_forbidden_columns"],
        "inference_forbidden_name_tokens": dataset_contract[
            "forbidden_feature_policy"
        ]["case_insensitive_name_tokens"],
        "tables": tables,
    }


def _resolve_snapshot_id(
    requested: str | None,
    source: SourceState,
) -> str:
    snapshot_id = requested or (
        f"research_v0_{source.owner_count}_{source.registry_logical_sha256[:12]}"
    )
    if not SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise ValueError(
            "snapshot_id must start with an alphanumeric character and contain only "
            "letters, digits, dot, underscore, or hyphen (maximum 128 characters)"
        )
    return snapshot_id


def build_snapshot(
    *,
    project_root: Path,
    corpus_root: Path,
    snapshots_root: Path,
    snapshot_id: str | None = None,
    storage_format: str = "auto",
) -> dict[str, Any]:
    project_root = project_root.resolve()
    corpus_root = corpus_root.resolve()
    snapshots_root = snapshots_root.resolve()
    dataset_contract_path = project_root / "configs/boatrace_model_dataset_contract_v1.json"
    evaluation_contract_path = project_root / "configs/boatrace_model_evaluation_v1_1.json"
    class_map_path = project_root / "configs/trifecta_class_map_v1.json"
    dataset_contract = read_json(dataset_contract_path)
    evaluation_contract = read_json(evaluation_contract_path)
    class_map = load_class_map(class_map_path)
    expected_mapping_hash = evaluation_contract["class_map"]["mapping_sha256"]
    if class_map.mapping_sha256 != expected_mapping_hash:
        raise ValueError("evaluation contract and class map mapping_sha256 differ")

    if corpus_root == snapshots_root or corpus_root in snapshots_root.parents:
        raise ValueError("snapshot output must not be inside the protected complete corpus")
    source = _read_stable_source_state(corpus_root)
    resolved_id = _resolve_snapshot_id(snapshot_id, source)
    final_dir = snapshots_root / resolved_id
    building_dir = snapshots_root / f".building-{resolved_id}-{os.getpid()}"
    if final_dir.exists() or building_dir.exists():
        raise FileExistsError(f"snapshot output already exists: {final_dir}")
    snapshots_root.mkdir(parents=True, exist_ok=True)
    ensure_relative_to(building_dir, snapshots_root)

    parquet = _parquet_availability()
    if storage_format not in {"auto", "csv", "parquet"}:
        raise ValueError("storage_format must be one of: auto, csv, parquet")
    if storage_format == "parquet" and not parquet["available"]:
        raise RuntimeError(
            "Parquet output requested but PyArrow is not installed. "
            "No dependency was installed; use --format csv or install PyArrow separately."
        )
    resolved_format = (
        "parquet"
        if storage_format == "parquet" or (storage_format == "auto" and parquet["available"])
        else "csv"
    )

    building_dir.mkdir()
    csv_paths = {
        "race_features": building_dir / "race_features.csv",
        "boat_features": building_dir / "boat_features.csv",
        "top3_targets": building_dir / "top3_targets.csv",
        "auxiliary_targets": building_dir / "auxiliary_targets.csv",
        "eligibility": building_dir / "eligibility.csv",
    }
    writers = {
        "race_features": CsvTableWriter(csv_paths["race_features"], RACE_FEATURE_COLUMNS),
        "boat_features": CsvTableWriter(csv_paths["boat_features"], BOAT_FEATURE_COLUMNS),
        "top3_targets": CsvTableWriter(csv_paths["top3_targets"], TOP3_TARGET_COLUMNS),
        "auxiliary_targets": CsvTableWriter(
            csv_paths["auxiliary_targets"], AUXILIARY_TARGET_COLUMNS
        ),
        "eligibility": CsvTableWriter(csv_paths["eligibility"], ELIGIBILITY_COLUMNS),
    }
    target_counts = Counter[str]()
    reason_counts = Counter[str]()
    prediction_eligible_count = 0
    main_eligible_count = 0
    date_values: list[str] = []
    source_batches: list[dict[str, Any]] = []
    try:
        race_source_columns = dataset_contract["source_schema"]["race_facts_columns"]
        entry_source_columns = dataset_contract["source_schema"]["entry_facts_columns"]
        for batch, race_keys in source.owners_by_batch.items():
            record = source.batch_records.get(batch)
            if record is None:
                raise ValueError(f"canonical owner references unknown batch: {batch}")
            race_path, entry_path, _, source_hashes = _verify_batch_source(
                project_root, corpus_root, batch, record
            )
            selected = set(race_keys)
            race_rows_by_key = _read_selected_rows(
                race_path, race_source_columns, selected
            )
            entry_rows_by_key = _read_selected_rows(
                entry_path, entry_source_columns, selected
            )
            if sha256_file(race_path) != source_hashes["race_facts"]:
                raise ValueError(f"source race_facts changed while reading batch {batch}")
            if sha256_file(entry_path) != source_hashes["entry_facts"]:
                raise ValueError(f"source entry_facts changed while reading batch {batch}")
            source_batches.append(
                {
                    "batch": batch,
                    "canonical_races": len(race_keys),
                    "batch_manifest_sha256": source_hashes["manifest"],
                    "race_facts_sha256": source_hashes["race_facts"],
                    "entry_facts_sha256": source_hashes["entry_facts"],
                }
            )

            for race_key in race_keys:
                race_rows = race_rows_by_key.get(race_key, [])
                entries = entry_rows_by_key.get(race_key, [])
                race = race_rows[0] if len(race_rows) == 1 else None
                identity = _identity(race_key, race, entries)
                if identity["race_date"]:
                    date_values.append(identity["race_date"])
                prediction_reasons = _prediction_exclusion_reasons(race_rows, entries)
                prediction_eligible = not prediction_reasons
                target_status, top3 = _target_status(race, entries)
                target_counts[target_status] += 1
                main_eligible = prediction_eligible and target_status == "unique_order"
                if prediction_eligible:
                    prediction_eligible_count += 1
                if main_eligible:
                    main_eligible_count += 1

                reasons = list(prediction_reasons)
                if target_status == "tied":
                    reasons.append("target_tied")
                elif target_status == "void":
                    reasons.append("target_void")
                for reason in sorted(set(reasons)):
                    reason_counts[reason] += 1

                writers["eligibility"].write(
                    {
                        **identity,
                        "source_batch": batch,
                        "target_status": target_status,
                        "prediction_input_eligible": str(prediction_eligible).lower(),
                        "main_evaluation_eligible": str(main_eligible).lower(),
                        "exclusion_reasons": "|".join(sorted(set(reasons))),
                    }
                )

                class_id: int | str = ""
                first: int | str = ""
                second: int | str = ""
                third: int | str = ""
                label = ""
                if target_status == "unique_order" and top3 is not None:
                    first, second, third = top3
                    class_id = class_map.encode(top3)
                    label = f"{first}-{second}-{third}"
                writers["top3_targets"].write(
                    {
                        **identity,
                        "target_status": target_status,
                        "target_class_id": class_id,
                        "first_lane": first,
                        "second_lane": second,
                        "third_lane": third,
                        "target_label": label,
                    }
                )

                def entry_sort_key(row: Mapping[str, str]) -> tuple[int, str]:
                    lane = _int_or_none(row.get("lane"), 1, 6)
                    return (lane if lane is not None else 99, str(row.get("lane", "")))

                sorted_entries = sorted(entries, key=entry_sort_key)
                for entry in sorted_entries:
                    writers["auxiliary_targets"].write(
                        {
                            **identity,
                            "lane": entry.get("lane", ""),
                            "target_status": target_status,
                            "actual_finish": entry.get("actual_finish", ""),
                            "actual_course": entry.get("actual_course", ""),
                            "actual_start_timing": entry.get("actual_start_timing", ""),
                            "winning_technique_number": (
                                race.get("winning_technique_number", "") if race else ""
                            ),
                        }
                    )

                if prediction_eligible and race is not None:
                    writers["race_features"].write(
                        {column: race.get(column, "") for column in RACE_FEATURE_COLUMNS}
                    )
                    for entry in sorted_entries:
                        writers["boat_features"].write(
                            {column: entry.get(column, "") for column in BOAT_FEATURE_COLUMNS}
                        )
    finally:
        for writer in writers.values():
            writer.close()

    table_files: dict[str, Path] = dict(csv_paths)
    if resolved_format == "parquet":
        for table, csv_path in csv_paths.items():
            table_files[table] = _convert_csv_to_parquet(csv_path)

    feature_manifest_payload = _feature_manifest(
        dataset_contract, writers, table_files, class_map
    )
    feature_manifest_path = building_dir / "feature_manifest.json"
    atomic_write_json(feature_manifest_path, feature_manifest_payload)

    source_exclusion_reasons = source.status.get("exclusion_reasons") or {}
    profile_payload = {
        "profile_id": "boatrace_model_dataset_profile_v1",
        "snapshot_id": resolved_id,
        "created_at": _now(),
        "contracts": {
            "evaluation": evaluation_contract["contract_id"],
            "dataset": dataset_contract["contract_id"],
            "class_map": "trifecta_class_map_v1",
        },
        "storage": {
            "requested": storage_format,
            "resolved": resolved_format,
            "parquet": parquet,
        },
        "source": {
            "corpus_root": relative_posix(corpus_root, project_root),
            "status_created_at": source.status.get("created_at"),
            "status_sha256": source.status_sha256,
            "registry_logical_sha256": source.registry_logical_sha256,
            "canonical_races": source.owner_count,
            "batch_count": len(source.owners_by_batch),
            "candidate_races_audited": source.status.get("candidate_races_audited"),
            "excluded_before_snapshot": source.status.get("excluded_races"),
            "exclusion_reasons_before_snapshot": source_exclusion_reasons,
        },
        "date_range": {
            "minimum": min(date_values) if date_values else None,
            "maximum": max(date_values) if date_values else None,
        },
        "rows": {table: writer.row_count for table, writer in writers.items()},
        "eligibility": {
            "prediction_input_eligible": prediction_eligible_count,
            "prediction_input_excluded": source.owner_count - prediction_eligible_count,
            "main_evaluation_eligible": main_eligible_count,
            "main_evaluation_excluded": source.owner_count - main_eligible_count,
            "target_status_counts": dict(sorted(target_counts.items())),
            "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        },
        "feature_missing_counts": {
            table: dict(sorted(writer.missing.items()))
            for table, writer in writers.items()
            if table in {"race_features", "boat_features"}
        },
    }
    profile_path = building_dir / "dataset_profile.json"
    atomic_write_json(profile_path, profile_payload)

    artifact_paths = {
        **table_files,
        "dataset_profile": profile_path,
        "feature_manifest": feature_manifest_path,
    }
    config_hashes = []
    for relative in CONFIG_FILES:
        path = project_root / relative
        config_hashes.append(
            {"path": relative, "sha256": sha256_file(path)}
        )
    implementation_hashes = []
    for relative in IMPLEMENTATION_FILES:
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"implementation file missing at snapshot time: {path}")
        implementation_hashes.append(
            {"path": relative, "sha256": sha256_file(path)}
        )
    documentation_hashes = []
    for relative in DOCUMENTATION_FILES:
        path = project_root / relative
        documentation_hashes.append(
            {"path": relative, "sha256": sha256_file(path)}
        )
    manifest_payload = {
        "manifest_id": "boatrace_model_dataset_manifest_v1",
        "snapshot_id": resolved_id,
        "created_at": _now(),
        "storage_format": resolved_format,
        "class_map": {
            "path": "configs/trifecta_class_map_v1.json",
            "mapping_sha256": class_map.mapping_sha256,
            "class_count": len(class_map.orders),
        },
        "source": {
            "corpus_root": relative_posix(corpus_root, project_root),
            "status_sha256": source.status_sha256,
            "registry_logical_sha256": source.registry_logical_sha256,
            "registry_metadata": source.registry_metadata,
            "canonical_race_count": source.owner_count,
            "batches": source_batches,
        },
        "artifacts": [
            {
                "name": name,
                "file": path.name,
                "sha256": sha256_file(path),
                "rows": writers[name].row_count if name in writers else None,
                "columns": writers[name].columns if name in writers else None,
            }
            for name, path in artifact_paths.items()
        ],
        "configs": config_hashes,
        "documentation": documentation_hashes,
        "implementation_files": implementation_hashes,
        "self_hash_policy": (
            "dataset_manifest.json is omitted from its own artifact hash list to avoid "
            "an impossible circular self-reference; validators hash it externally."
        ),
    }
    manifest_path = building_dir / "dataset_manifest.json"
    atomic_write_json(manifest_path, manifest_payload)
    os.replace(building_dir, final_dir)
    return {
        "snapshot_id": resolved_id,
        "snapshot_dir": str(final_dir),
        "storage_format": resolved_format,
        "dataset_manifest_sha256": sha256_file(final_dir / "dataset_manifest.json"),
        "canonical_races": source.owner_count,
        "prediction_input_eligible": prediction_eligible_count,
        "main_evaluation_eligible": main_eligible_count,
        "target_status_counts": dict(sorted(target_counts.items())),
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "source_excluded_before_snapshot": source.status.get("excluded_races"),
        "source_exclusion_reasons": source_exclusion_reasons,
        "parquet": parquet,
    }
