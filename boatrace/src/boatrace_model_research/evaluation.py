from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .class_map import TrifectaClassMap, load_class_map
from .common import (
    atomic_write_json,
    open_deterministic_gzip_text,
    open_text,
    parse_bool,
    parse_int,
    read_json,
    sha256_file,
)
from .snapshot import (
    AUXILIARY_TARGET_COLUMNS,
    BOAT_FEATURE_COLUMNS,
    ELIGIBILITY_COLUMNS,
    RACE_FEATURE_COLUMNS,
    TOP3_TARGET_COLUMNS,
)


PROBABILITY_COLUMNS = [f"p_{class_id:03d}" for class_id in range(120)]
TARGET_STATUSES = ("unique_order", "tied", "void")


class EvaluationContractError(ValueError):
    """Raised when an input cannot be scored under evaluation contract v1.1."""


@dataclass
class _Checks:
    errors: list[str]
    maximum: int = 100

    def require(self, condition: bool, message: str) -> None:
        if not condition and len(self.errors) < self.maximum:
            self.errors.append(message)


@dataclass
class _Mean:
    total: float = 0.0
    correction: float = 0.0
    count: int = 0
    infinite: bool = False

    def add(self, value: float) -> None:
        self.count += 1
        if math.isinf(value):
            self.infinite = True
            return
        adjusted = value - self.correction
        updated = self.total + adjusted
        self.correction = (updated - self.total) - adjusted
        self.total = updated

    def value(self) -> float | str | None:
        if self.count == 0:
            return None
        if self.infinite:
            return "Infinity"
        return self.total / self.count


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _table_header(path: Path) -> list[str]:
    if path.suffix.lower() == ".parquet":
        try:
            import pyarrow.parquet as parquet  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                f"cannot read Parquet without PyArrow: {path}"
            ) from exc
        return list(parquet.ParquetFile(path).schema_arrow.names)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"empty table: {path}") from exc


def _table_rows(path: Path) -> Iterator[dict[str, str]]:
    if path.suffix.lower() == ".parquet":
        try:
            import pyarrow.parquet as parquet  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                f"cannot read Parquet without PyArrow: {path}"
            ) from exc
        source = parquet.ParquetFile(path)
        for batch in source.iter_batches(batch_size=65_536):
            for row in batch.to_pylist():
                yield {str(key): _text(value) for key, value in row.items()}
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _artifact_paths(
    snapshot_dir: Path,
    manifest: Mapping[str, Any],
    checks: _Checks,
) -> tuple[dict[str, Path], dict[str, Mapping[str, Any]]]:
    paths: dict[str, Path] = {}
    records: dict[str, Mapping[str, Any]] = {}
    for item in manifest.get("artifacts", []):
        name = str(item.get("name", ""))
        checks.require(bool(name), "manifest artifact has a blank name")
        checks.require(name not in paths, f"duplicate manifest artifact: {name}")
        path = snapshot_dir / str(item.get("file", ""))
        checks.require(path.is_file(), f"missing snapshot artifact: {path.name}")
        if path.is_file():
            checks.require(
                sha256_file(path) == item.get("sha256"),
                f"artifact SHA-256 mismatch: {path.name}",
            )
        paths[name] = path
        records[name] = item
    expected = {
        "race_features",
        "boat_features",
        "top3_targets",
        "auxiliary_targets",
        "eligibility",
        "dataset_profile",
        "feature_manifest",
    }
    checks.require(
        set(paths) == expected,
        f"artifact set mismatch: expected={sorted(expected)} actual={sorted(paths)}",
    )
    return paths, records


def _verify_recorded_files(
    project_root: Path,
    entries: Iterable[Mapping[str, Any]],
    group: str,
    checks: _Checks,
) -> None:
    for item in entries:
        relative = str(item.get("path", ""))
        path = project_root / relative
        checks.require(path.is_file(), f"{group} file missing: {relative}")
        if path.is_file():
            checks.require(
                sha256_file(path) == item.get("sha256"),
                f"{group} SHA-256 mismatch: {relative}",
            )


def _forbidden_feature_columns(
    columns: Sequence[str],
    contract: Mapping[str, Any],
) -> list[str]:
    policy = contract["forbidden_feature_policy"]
    exact = {str(value).casefold() for value in policy["exact_inference_forbidden_columns"]}
    tokens = [str(value).casefold() for value in policy["case_insensitive_name_tokens"]]
    violations: list[str] = []
    for column in columns:
        normalized = column.casefold()
        if normalized in exact:
            violations.append(f"exact:{column}")
        for token in tokens:
            if token in normalized:
                violations.append(f"token:{token}:{column}")
    return violations


def _load_eligibility(
    path: Path,
    checks: _Checks,
) -> tuple[dict[str, dict[str, Any]], Counter[str], Counter[str]]:
    eligibility: dict[str, dict[str, Any]] = {}
    statuses = Counter[str]({status: 0 for status in TARGET_STATUSES})
    reasons = Counter[str]()
    checks.require(
        _table_header(path) == ELIGIBILITY_COLUMNS,
        "eligibility columns differ from the dataset contract",
    )
    for row_number, row in enumerate(_table_rows(path), start=1):
        race_key = row.get("race_key", "")
        checks.require(bool(race_key), f"eligibility blank race_key at row {row_number}")
        checks.require(
            race_key not in eligibility,
            f"eligibility duplicate race_key: {race_key}",
        )
        status = row.get("target_status", "")
        checks.require(
            status in TARGET_STATUSES,
            f"eligibility invalid target_status for {race_key}: {status}",
        )
        try:
            prediction = parse_bool(row.get("prediction_input_eligible", ""))
            main = parse_bool(row.get("main_evaluation_eligible", ""))
        except ValueError as exc:
            checks.require(False, f"eligibility boolean error for {race_key}: {exc}")
            prediction = main = False
        checks.require(
            main == (prediction and status == "unique_order"),
            f"eligibility main flag is inconsistent for {race_key}",
        )
        for reason in filter(None, row.get("exclusion_reasons", "").split("|")):
            reasons[reason] += 1
        if status in TARGET_STATUSES:
            statuses[status] += 1
        eligibility[race_key] = {
            "prediction": prediction,
            "main": main,
            "status": status,
            "source_batch": row.get("source_batch", ""),
        }
    return eligibility, statuses, reasons


def _load_top3_targets(
    path: Path,
    eligibility: Mapping[str, Mapping[str, Any]],
    class_map: TrifectaClassMap,
    checks: _Checks,
) -> dict[str, int]:
    targets: dict[str, int] = {}
    seen: set[str] = set()
    checks.require(
        _table_header(path) == TOP3_TARGET_COLUMNS,
        "top3_targets columns differ from the dataset contract",
    )
    for row_number, row in enumerate(_table_rows(path), start=1):
        race_key = row.get("race_key", "")
        checks.require(bool(race_key), f"top3_targets blank race_key at row {row_number}")
        checks.require(race_key not in seen, f"top3_targets duplicate race_key: {race_key}")
        seen.add(race_key)
        status = row.get("target_status", "")
        checks.require(
            race_key in eligibility,
            f"top3_targets key absent from eligibility: {race_key}",
        )
        if race_key in eligibility:
            checks.require(
                status == eligibility[race_key]["status"],
                f"top3_targets status differs from eligibility for {race_key}",
            )
        if status == "unique_order":
            try:
                class_id = parse_int(
                    row.get("target_class_id", ""), minimum=0, maximum=119
                )
                order = tuple(
                    parse_int(row.get(column, ""), minimum=1, maximum=6)
                    for column in ("first_lane", "second_lane", "third_lane")
                )
                checks.require(
                    len(set(order)) == 3,
                    f"top3 target contains repeated lanes for {race_key}",
                )
                checks.require(
                    class_map.decode(class_id) == order,
                    f"top3 class_id/order mismatch for {race_key}",
                )
                checks.require(
                    class_map.encode(order) == class_id,
                    f"top3 encode round-trip mismatch for {race_key}",
                )
                checks.require(
                    row.get("target_label", "")
                    == "-".join(str(value) for value in order),
                    f"top3 label mismatch for {race_key}",
                )
                targets[race_key] = class_id
            except ValueError as exc:
                checks.require(False, f"invalid unique target for {race_key}: {exc}")
        elif status in {"tied", "void"}:
            for column in (
                "target_class_id",
                "first_lane",
                "second_lane",
                "third_lane",
                "target_label",
            ):
                checks.require(
                    row.get(column, "") == "",
                    f"{status} target must have blank {column}: {race_key}",
                )
    checks.require(
        seen == set(eligibility),
        "top3_targets keys differ from eligibility keys",
    )
    return targets


def _validate_race_features(
    path: Path,
    eligible_keys: set[str],
    contract: Mapping[str, Any],
    checks: _Checks,
) -> int:
    header = _table_header(path)
    checks.require(header == RACE_FEATURE_COLUMNS, "race_features columns mismatch")
    violations = _forbidden_feature_columns(header, contract)
    checks.require(
        not violations,
        f"race_features contains forbidden columns: {violations}",
    )
    required = contract["feature_tables"]["race_features"]["required_non_null_columns"]
    seen: set[str] = set()
    count = 0
    for row in _table_rows(path):
        count += 1
        race_key = row.get("race_key", "")
        checks.require(bool(race_key), f"race_features blank race_key at row {count}")
        checks.require(race_key not in seen, f"race_features duplicate race_key: {race_key}")
        seen.add(race_key)
        for column in required:
            checks.require(
                bool(row.get(column, "").strip()),
                f"race_features blank required {column}: {race_key}",
            )
    checks.require(
        seen == eligible_keys,
        "race_features keys differ from prediction-input-eligible keys",
    )
    return count


def _validate_boat_features(
    path: Path,
    eligible_keys: set[str],
    contract: Mapping[str, Any],
    checks: _Checks,
) -> int:
    header = _table_header(path)
    checks.require(header == BOAT_FEATURE_COLUMNS, "boat_features columns mismatch")
    violations = _forbidden_feature_columns(header, contract)
    checks.require(
        not violations,
        f"boat_features contains forbidden columns: {violations}",
    )
    required = contract["feature_tables"]["boat_features"]["required_non_null_columns"]
    lanes: dict[str, set[int]] = defaultdict(set)
    count = 0
    for row in _table_rows(path):
        count += 1
        race_key = row.get("race_key", "")
        checks.require(bool(race_key), f"boat_features blank race_key at row {count}")
        for column in required:
            checks.require(
                bool(row.get(column, "").strip()),
                f"boat_features blank required {column}: {race_key}",
            )
        try:
            lane = parse_int(row.get("lane", ""), minimum=1, maximum=6)
            checks.require(
                lane not in lanes[race_key],
                f"boat_features duplicate lane {lane}: {race_key}",
            )
            lanes[race_key].add(lane)
        except ValueError as exc:
            checks.require(False, f"boat_features invalid lane for {race_key}: {exc}")
    checks.require(
        set(lanes) == eligible_keys,
        "boat_features keys differ from prediction-input-eligible keys",
    )
    for race_key in eligible_keys:
        checks.require(
            lanes.get(race_key) == set(range(1, 7)),
            f"boat_features lanes are not exactly 1..6 for {race_key}",
        )
    return count


def _validate_auxiliary(
    path: Path,
    eligible_keys: set[str],
    all_keys: set[str],
    checks: _Checks,
) -> int:
    checks.require(
        _table_header(path) == AUXILIARY_TARGET_COLUMNS,
        "auxiliary_targets columns mismatch",
    )
    lanes: dict[str, set[int]] = defaultdict(set)
    counts = Counter[str]()
    rows = 0
    for row in _table_rows(path):
        rows += 1
        race_key = row.get("race_key", "")
        checks.require(
            race_key in all_keys,
            f"auxiliary target key absent from eligibility: {race_key}",
        )
        counts[race_key] += 1
        try:
            lane = parse_int(row.get("lane", ""), minimum=1, maximum=6)
            checks.require(
                lane not in lanes[race_key],
                f"auxiliary target duplicate lane {lane}: {race_key}",
            )
            lanes[race_key].add(lane)
        except ValueError as exc:
            checks.require(False, f"auxiliary target invalid lane for {race_key}: {exc}")
    for race_key in eligible_keys:
        checks.require(
            counts[race_key] == 6 and lanes[race_key] == set(range(1, 7)),
            f"auxiliary targets are not exactly six lanes for {race_key}",
        )
    return rows


def _normalized_status_counts(value: Mapping[str, Any]) -> dict[str, int]:
    return {status: int(value.get(status, 0)) for status in TARGET_STATUSES}


def validate_snapshot(
    *,
    project_root: Path,
    snapshot_dir: Path,
    verify_environment_hashes: bool = True,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    snapshot_dir = snapshot_dir.resolve()
    checks = _Checks(errors=[])
    manifest_path = snapshot_dir / "dataset_manifest.json"
    if not manifest_path.is_file():
        return {
            "valid": False,
            "errors": ["dataset_manifest.json is missing"],
            "snapshot_dir": str(snapshot_dir),
        }
    manifest = read_json(manifest_path)
    checks.require(
        manifest.get("manifest_id") == "boatrace_model_dataset_manifest_v1",
        "unexpected dataset manifest_id",
    )
    checks.require(
        manifest.get("snapshot_id") == snapshot_dir.name,
        "snapshot directory name differs from manifest snapshot_id",
    )
    artifacts, artifact_records = _artifact_paths(snapshot_dir, manifest, checks)

    if verify_environment_hashes:
        _verify_recorded_files(project_root, manifest.get("configs", []), "config", checks)
        _verify_recorded_files(
            project_root, manifest.get("implementation_files", []), "implementation", checks
        )
        _verify_recorded_files(
            project_root, manifest.get("documentation", []), "documentation", checks
        )

    try:
        contract = read_json(
            project_root / "configs/boatrace_model_dataset_contract_v1.json"
        )
        evaluation_contract = read_json(
            project_root / "configs/boatrace_model_evaluation_v1_1.json"
        )
        class_map = load_class_map(
            project_root / "configs/trifecta_class_map_v1.json"
        )
    except (OSError, ValueError, KeyError) as exc:
        checks.require(False, f"contract loading failed: {exc}")
        return {
            "valid": False,
            "errors": checks.errors,
            "snapshot_dir": str(snapshot_dir),
        }
    checks.require(
        class_map.mapping_sha256 == evaluation_contract["class_map"]["mapping_sha256"],
        "evaluation contract and class map mapping SHA differ",
    )
    checks.require(
        class_map.mapping_sha256
        == manifest.get("class_map", {}).get("mapping_sha256"),
        "dataset manifest and class map mapping SHA differ",
    )
    checks.require(
        manifest.get("class_map", {}).get("class_count") == 120,
        "dataset manifest class_count is not 120",
    )

    eligibility, statuses, reasons = _load_eligibility(
        artifacts["eligibility"], checks
    )
    prediction_keys = {
        key for key, value in eligibility.items() if value["prediction"]
    }
    main_keys = {key for key, value in eligibility.items() if value["main"]}
    targets = _load_top3_targets(
        artifacts["top3_targets"], eligibility, class_map, checks
    )
    checks.require(
        set(targets) == main_keys,
        "unique top3 targets differ from main-evaluation-eligible keys",
    )
    race_rows = _validate_race_features(
        artifacts["race_features"], prediction_keys, contract, checks
    )
    boat_rows = _validate_boat_features(
        artifacts["boat_features"], prediction_keys, contract, checks
    )
    auxiliary_rows = _validate_auxiliary(
        artifacts["auxiliary_targets"],
        prediction_keys,
        set(eligibility),
        checks,
    )

    feature_manifest = read_json(artifacts["feature_manifest"])
    checks.require(
        feature_manifest.get("class_map_mapping_sha256") == class_map.mapping_sha256,
        "feature manifest class-map mapping SHA differs",
    )
    for table, expected_columns in (
        ("race_features", RACE_FEATURE_COLUMNS),
        ("boat_features", BOAT_FEATURE_COLUMNS),
    ):
        declared = [
            item.get("name")
            for item in feature_manifest.get("tables", {})
            .get(table, {})
            .get("columns", [])
        ]
        checks.require(
            declared == expected_columns,
            f"feature manifest {table} columns mismatch",
        )
        violations = _forbidden_feature_columns(declared, contract)
        checks.require(
            not violations,
            f"feature manifest {table} contains forbidden columns: {violations}",
        )

    expected_rows = {
        "race_features": race_rows,
        "boat_features": boat_rows,
        "top3_targets": len(eligibility),
        "auxiliary_targets": auxiliary_rows,
        "eligibility": len(eligibility),
    }
    profile = read_json(artifacts["dataset_profile"])
    checks.require(
        profile.get("rows") == expected_rows,
        f"dataset profile row counts mismatch: {profile.get('rows')} != {expected_rows}",
    )
    profile_eligibility = profile.get("eligibility", {})
    checks.require(
        int(profile_eligibility.get("prediction_input_eligible", -1))
        == len(prediction_keys),
        "dataset profile prediction eligible count mismatch",
    )
    checks.require(
        int(profile_eligibility.get("prediction_input_excluded", -1))
        == len(eligibility) - len(prediction_keys),
        "dataset profile prediction excluded count mismatch",
    )
    checks.require(
        int(profile_eligibility.get("main_evaluation_eligible", -1)) == len(main_keys),
        "dataset profile main eligible count mismatch",
    )
    checks.require(
        int(profile_eligibility.get("main_evaluation_excluded", -1))
        == len(eligibility) - len(main_keys),
        "dataset profile main excluded count mismatch",
    )
    checks.require(
        _normalized_status_counts(profile_eligibility.get("target_status_counts", {}))
        == dict(statuses),
        "dataset profile target status counts mismatch",
    )
    checks.require(
        profile_eligibility.get("exclusion_reason_counts", {})
        == dict(sorted(reasons.items())),
        "dataset profile exclusion reason counts mismatch",
    )
    checks.require(
        manifest.get("source", {}).get("canonical_race_count") == len(eligibility),
        "manifest canonical_race_count differs from eligibility rows",
    )
    source_batch_sum = sum(
        int(item.get("canonical_races", 0))
        for item in manifest.get("source", {}).get("batches", [])
    )
    checks.require(
        source_batch_sum == len(eligibility),
        "source batch counts do not sum to canonical race count",
    )
    for name, row_count in expected_rows.items():
        record = artifact_records.get(name, {})
        checks.require(
            record.get("rows") == row_count,
            f"manifest row count mismatch for {name}",
        )

    return {
        "valid": not checks.errors,
        "errors": checks.errors,
        "snapshot_id": manifest.get("snapshot_id"),
        "snapshot_dir": str(snapshot_dir),
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "class_map_mapping_sha256": class_map.mapping_sha256,
        "counts": {
            "canonical_races": len(eligibility),
            "prediction_input_eligible": len(prediction_keys),
            "main_evaluation_eligible": len(main_keys),
            "target_status_counts": dict(statuses),
            "exclusion_reason_counts": dict(sorted(reasons.items())),
            "race_feature_rows": race_rows,
            "boat_feature_rows": boat_rows,
            "auxiliary_target_rows": auxiliary_rows,
        },
    }


def _validated_dataset(
    project_root: Path,
    snapshot_dir: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Path],
    dict[str, dict[str, Any]],
    dict[str, int],
    TrifectaClassMap,
]:
    validation = validate_snapshot(
        project_root=project_root,
        snapshot_dir=snapshot_dir,
        verify_environment_hashes=True,
    )
    if not validation["valid"]:
        raise EvaluationContractError(
            "snapshot validation failed: " + " | ".join(validation["errors"][:10])
        )
    manifest = read_json(snapshot_dir / "dataset_manifest.json")
    paths = {
        str(item["name"]): snapshot_dir / str(item["file"])
        for item in manifest["artifacts"]
    }
    checks = _Checks(errors=[])
    eligibility, _, _ = _load_eligibility(paths["eligibility"], checks)
    class_map = load_class_map(project_root / "configs/trifecta_class_map_v1.json")
    targets = _load_top3_targets(
        paths["top3_targets"], eligibility, class_map, checks
    )
    if checks.errors:
        raise EvaluationContractError("dataset reload failed: " + " | ".join(checks.errors))
    return manifest, paths, eligibility, targets, class_map


def generate_uniform_predictions(
    *,
    project_root: Path,
    snapshot_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    snapshot_dir = snapshot_dir.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"prediction output already exists: {output_path}")
    manifest_path = output_path.with_name(output_path.name + ".manifest.json")
    if manifest_path.exists():
        raise FileExistsError(f"prediction manifest already exists: {manifest_path}")
    dataset_manifest, _, eligibility, _, class_map = _validated_dataset(
        project_root, snapshot_dir
    )
    race_keys = sorted(
        key for key, value in eligibility.items() if value["prediction"]
    )
    probability = format(1.0 / 120.0, ".17g")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".gz":
        handle = open_deterministic_gzip_text(output_path)
    else:
        handle = output_path.open("w", encoding="utf-8", newline="")
    try:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["race_key", *PROBABILITY_COLUMNS])
        probability_row = [probability] * 120
        for race_key in race_keys:
            writer.writerow([race_key, *probability_row])
    finally:
        handle.close()
    prediction_hash = sha256_file(output_path)
    payload = {
        "manifest_id": "boatrace_uniform_predictions_v1",
        "model_id": "uniform_1_over_120",
        "snapshot_id": dataset_manifest["snapshot_id"],
        "dataset_manifest_sha256": sha256_file(
            snapshot_dir / "dataset_manifest.json"
        ),
        "class_map_mapping_sha256": class_map.mapping_sha256,
        "prediction_file": output_path.name,
        "prediction_file_sha256": prediction_hash,
        "race_count": len(race_keys),
        "probability_array_length": 120,
        "probability_per_class": 1.0 / 120.0,
    }
    atomic_write_json(manifest_path, payload)
    return {
        **payload,
        "prediction_path": str(output_path),
        "prediction_manifest_path": str(manifest_path),
    }


def _loss(probability: float) -> float:
    return math.inf if probability <= 0.0 else -math.log(probability)


def _metric_indices(
    class_map: TrifectaClassMap,
) -> tuple[
    dict[int, tuple[int, ...]],
    dict[tuple[int, int], tuple[int, ...]],
    dict[frozenset[int], tuple[int, ...]],
]:
    winners: dict[int, list[int]] = defaultdict(list)
    exactas: dict[tuple[int, int], list[int]] = defaultdict(list)
    sets: dict[frozenset[int], list[int]] = defaultdict(list)
    for class_id, order in enumerate(class_map.orders):
        winners[order[0]].append(class_id)
        exactas[(order[0], order[1])].append(class_id)
        sets[frozenset(order)].append(class_id)
    return (
        {key: tuple(value) for key, value in winners.items()},
        {key: tuple(value) for key, value in exactas.items()},
        {key: tuple(value) for key, value in sets.items()},
    )


def evaluate_predictions(
    *,
    project_root: Path,
    snapshot_dir: Path,
    prediction_path: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    snapshot_dir = snapshot_dir.resolve()
    prediction_path = prediction_path.resolve()
    if not prediction_path.is_file():
        raise FileNotFoundError(prediction_path)
    dataset_manifest, _, eligibility, targets, class_map = _validated_dataset(
        project_root, snapshot_dir
    )
    contract = read_json(project_root / "configs/boatrace_model_evaluation_v1_1.json")
    sum_tolerance = float(
        contract["prediction_schema"]["constraints"]["sum_absolute_tolerance"]
    )
    expected_keys = {
        key for key, value in eligibility.items() if value["prediction"]
    }
    main_keys = {key for key, value in eligibility.items() if value["main"]}
    winners, exactas, top3_sets = _metric_indices(class_map)
    accumulators = {
        name: _Mean()
        for name in (
            "trifecta_log_loss",
            "winner_log_loss",
            "exacta_log_loss",
            "top3_set_log_loss",
            "second_given_first_log_loss",
            "third_given_first_second_log_loss",
            "trifecta_brier",
        )
    }
    errors: list[str] = []
    seen: set[str] = set()
    valid_rows = 0
    with open_text(prediction_path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        expected_header = ["race_key", *PROBABILITY_COLUMNS]
        if header != expected_header:
            errors.append(
                f"prediction columns mismatch: expected 121 frozen columns, got {len(header)}"
            )
        else:
            for row_number, row in enumerate(reader, start=2):
                if len(row) != 121:
                    if len(errors) < 100:
                        errors.append(
                            f"row {row_number} has {len(row) - 1} probabilities; expected 120"
                        )
                    continue
                race_key = row[0]
                if not race_key:
                    if len(errors) < 100:
                        errors.append(f"row {row_number} has blank race_key")
                    continue
                if race_key in seen:
                    if len(errors) < 100:
                        errors.append(f"duplicate prediction race_key: {race_key}")
                    continue
                seen.add(race_key)
                if race_key not in expected_keys:
                    if len(errors) < 100:
                        errors.append(f"extra prediction race_key: {race_key}")
                    continue
                probabilities: list[float] = []
                row_valid = True
                for class_id, text in enumerate(row[1:]):
                    try:
                        value = float(text)
                    except ValueError:
                        value = math.nan
                    if not math.isfinite(value):
                        if len(errors) < 100:
                            errors.append(
                                f"non-finite probability at {race_key} class {class_id}"
                            )
                        row_valid = False
                    elif value < 0.0 or value > 1.0:
                        if len(errors) < 100:
                            errors.append(
                                f"probability outside [0,1] at {race_key} class {class_id}"
                            )
                        row_valid = False
                    probabilities.append(value)
                if not row_valid:
                    continue
                probability_sum = math.fsum(probabilities)
                if abs(probability_sum - 1.0) > sum_tolerance:
                    if len(errors) < 100:
                        errors.append(
                            f"probability sum mismatch at {race_key}: {probability_sum}"
                        )
                    continue
                valid_rows += 1
                if race_key not in main_keys:
                    continue
                class_id = targets[race_key]
                first, second, third = class_map.decode(class_id)
                trifecta_probability = probabilities[class_id]
                winner_probability = math.fsum(
                    probabilities[index] for index in winners[first]
                )
                exacta_probability = math.fsum(
                    probabilities[index] for index in exactas[(first, second)]
                )
                set_probability = math.fsum(
                    probabilities[index]
                    for index in top3_sets[frozenset((first, second, third))]
                )
                second_given_first = (
                    exacta_probability / winner_probability
                    if winner_probability > 0.0
                    else 0.0
                )
                third_given_first_second = (
                    trifecta_probability / exacta_probability
                    if exacta_probability > 0.0
                    else 0.0
                )
                brier = (
                    math.fsum(value * value for value in probabilities)
                    - 2.0 * trifecta_probability
                    + 1.0
                )
                values = {
                    "trifecta_log_loss": _loss(trifecta_probability),
                    "winner_log_loss": _loss(winner_probability),
                    "exacta_log_loss": _loss(exacta_probability),
                    "top3_set_log_loss": _loss(set_probability),
                    "second_given_first_log_loss": _loss(second_given_first),
                    "third_given_first_second_log_loss": _loss(
                        third_given_first_second
                    ),
                    "trifecta_brier": brier,
                }
                for name, value in values.items():
                    accumulators[name].add(value)

    missing = sorted(expected_keys - seen)
    if missing:
        errors.append(
            f"missing prediction race_key count={len(missing)} examples={missing[:10]}"
        )
    coverage = len(seen & expected_keys) / len(expected_keys) if expected_keys else 1.0
    if valid_rows != len(expected_keys):
        errors.append(
            f"valid prediction rows {valid_rows} differ from expected {len(expected_keys)}"
        )
    if any(accumulator.count != len(main_keys) for accumulator in accumulators.values()):
        errors.append("metric row count differs from main-evaluation population")

    status_counts = Counter[str]({status: 0 for status in TARGET_STATUSES})
    for value in eligibility.values():
        status_counts[value["status"]] += 1
    report = {
        "report_id": "boatrace_model_evaluation_report_v1_1",
        "qualification_status": "passed" if not errors else "disqualified",
        "errors": errors[:100],
        "snapshot_id": dataset_manifest["snapshot_id"],
        "dataset_manifest_sha256": sha256_file(
            snapshot_dir / "dataset_manifest.json"
        ),
        "evaluation_contract_sha256": sha256_file(
            project_root / "configs/boatrace_model_evaluation_v1_1.json"
        ),
        "class_map_file_sha256": sha256_file(
            project_root / "configs/trifecta_class_map_v1.json"
        ),
        "class_map_mapping_sha256": class_map.mapping_sha256,
        "prediction_file": str(prediction_path),
        "prediction_file_sha256": sha256_file(prediction_path),
        "coverage": {
            "required_races": len(expected_keys),
            "submitted_unique_races": len(seen),
            "valid_races": valid_rows,
            "missing_races": len(expected_keys - seen),
            "extra_races": len(seen - expected_keys),
            "coverage": coverage,
            "required_coverage": 1.0,
        },
        "populations": {
            "target_status_counts": dict(status_counts),
            "prediction_input_eligible": len(expected_keys),
            "main_evaluation_eligible": len(main_keys),
        },
        "metrics": {
            name: accumulator.value() for name, accumulator in accumulators.items()
        },
        "metric_log_base": "e",
    }
    if report_path is not None:
        report_path = report_path.resolve()
        if report_path.exists():
            raise FileExistsError(f"evaluation report already exists: {report_path}")
        atomic_write_json(report_path, report)
        report["report_path"] = str(report_path)
        report["report_sha256"] = sha256_file(report_path)
    return report


def assert_uniform_reference(
    report: Mapping[str, Any],
    evaluation_contract: Mapping[str, Any],
) -> None:
    if report.get("qualification_status") != "passed":
        raise AssertionError(f"uniform predictions were disqualified: {report.get('errors')}")
    reference = evaluation_contract["uniform_reference"]
    tolerance = float(reference["test_absolute_tolerance"])
    metric_to_reference = {
        "trifecta_log_loss": "trifecta_log_loss",
        "winner_log_loss": "winner_log_loss",
        "exacta_log_loss": "exacta_log_loss",
        "top3_set_log_loss": "top3_set_log_loss",
        "second_given_first_log_loss": "second_given_first_log_loss",
        "third_given_first_second_log_loss": "third_given_first_second_log_loss",
        "trifecta_brier": "trifecta_brier",
    }
    for metric, reference_name in metric_to_reference.items():
        actual = report["metrics"][metric]
        expected = float(reference[reference_name])
        if not isinstance(actual, (int, float)) or abs(float(actual) - expected) > tolerance:
            raise AssertionError(
                f"uniform {metric} mismatch: actual={actual} expected={expected} "
                f"tolerance={tolerance}"
            )
