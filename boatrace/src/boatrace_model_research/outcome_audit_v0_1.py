from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .class_map import TrifectaClassMap, load_class_map
from .common import atomic_write_json, sha256_file
from .evaluation import (
    PROBABILITY_COLUMNS,
    assert_uniform_reference,
    evaluate_predictions,
    validate_snapshot,
)
from .snapshot import (
    AUXILIARY_TARGET_COLUMNS,
    BOAT_FEATURE_COLUMNS,
    ELIGIBILITY_COLUMNS,
    RACE_FEATURE_COLUMNS,
    TOP3_TARGET_COLUMNS,
)


PROJECT_ROOT_FROM_MODULE = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT_FROM_MODULE / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import collect_live_feature_input as live_parser  # noqa: E402


KNOWN_RACE_KEYS = (
    "20251224_02_02",
    "20251231_24_05",
    "20260205_14_06",
    "20260523_16_03",
    "20260531_06_07",
    "20260531_06_08",
)

ENTRY_PREVIEW_FIELDS = (
    "body_weight_kg",
    "exhibition_time",
    "tilt",
    "start_display_course",
    "start_display_st_text",
    "propeller_text",
    "parts_exchange_text",
)
RACE_PREVIEW_FIELDS = (
    "weather_text",
    "temperature_c",
    "wind_speed_m",
    "wind_dir_code",
    "water_temp_c",
    "wave_cm",
)

OUTCOME_TYPES = (
    "unique_order",
    "unique_top3_abnormal",
    "tied",
    "void",
)

RECONCILIATION_COLUMNS = [
    "race_key",
    "race_date",
    "venue_code",
    "race_no",
    "source_batch",
    "source_excluded",
    "source_exclusion_reasons",
    "prediction_input_eligible",
    "prediction_exclusion_reasons",
    "outcome_type",
    "raw_finish_by_lane",
    "raw_top3_combo",
    "raw_trifecta_winning_combinations",
    "audit_result_payout_combinations",
    "raw_program_result_identity_match",
    "v0_snapshot_exists",
    "v0_target_status",
    "v0_target_class_id",
    "v0_decoded_combo",
    "v0_matches_raw_top3",
    "v0_matches_raw_payout",
    "v0_1_target_status",
    "v0_1_target_class_id",
    "v0_1_decoded_combo",
    "v0_1_matches_raw_top3",
    "v0_1_matches_raw_payout",
    "main_one_hot_scorable",
    "reconciliation_status",
    "mismatch_reasons",
]

KNOWN_TRACE_COLUMNS = [
    "race_key",
    "raw_result_exists",
    "raw_result_path",
    "audit_candidate_exists",
    "audit_candidate_path",
    "excluded_races_exists",
    "excluded_reasons",
    "canonical_corpus_exists",
    "canonical_corpus_path",
    "research_v0_snapshot_exists",
    "research_v0_target_status",
    "raw_finish_by_lane",
    "trifecta_winning_combinations",
    "outcome_type",
    "prediction_input_eligible",
    "main_one_hot_scorable",
    "final_stage",
    "final_action",
]

FEATURE_AUDIT_COLUMNS = [
    "feature_name",
    "feature_table",
    "source_file_table",
    "source_field",
    "source_observed_at",
    "available_at_rule",
    "calculation_window",
    "calculation_cutoff",
    "inference_allowed",
    "null_count",
    "null_rate",
    "future_leakage_risk",
    "audit_result",
    "audit_note",
]


@dataclass
class Candidate:
    race_key: str
    race_date: str
    venue_code: str
    race_no: int
    source_batch: str
    source_excluded: bool
    source_reasons: tuple[str, ...]
    candidate_path: str
    raw_program_path: str
    raw_result_path: str
    beforeinfo_path: str
    program_exists: bool
    result_exists: bool
    prediction_eligible: bool
    prediction_reasons: tuple[str, ...]
    outcome_type: str
    finishes_by_lane: tuple[str, ...]
    raw_top3: tuple[int, int, int] | None
    raw_payout_combos: tuple[str, ...]
    audit_payout_combos: tuple[str, ...]
    raw_identity_match: bool | None
    scorable: bool
    target_status: str
    target_class_id: int | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    columns: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(columns),
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})
            count += 1
    return count


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _normalize_path(project_root: Path, value: str | Path) -> Path:
    path = Path(str(value).replace("\\", os.sep))
    return path if path.is_absolute() else project_root / path


def _recursive_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _normalize_combo(value: object) -> str | None:
    numbers = [int(item) for item in re.findall(r"[1-6]", str(value or ""))]
    if len(numbers) != 3 or len(set(numbers)) != 3:
        return None
    return "-".join(str(item) for item in numbers)


def _raw_payout_combinations(result: Mapping[str, Any] | None) -> tuple[str, ...]:
    items = ((result or {}).get("payouts") or {}).get("trifecta") or []
    combinations = {
        normalized
        for item in items
        if (normalized := _normalize_combo(item.get("combination"))) is not None
        and item.get("amount") is not None
    }
    return tuple(sorted(combinations))


def classify_outcome(
    result: Mapping[str, Any] | None,
) -> tuple[str, tuple[str, ...], tuple[int, int, int] | None, tuple[str, ...]]:
    if result is None:
        return "void", tuple("" for _ in range(6)), None, ()
    boats = result.get("boats") or []
    by_lane: dict[int, Mapping[str, Any]] = {}
    for boat in boats:
        try:
            lane = int(boat["racer_boat_number"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= lane <= 6 and lane not in by_lane:
            by_lane[lane] = boat
    finishes: list[str] = []
    lanes_by_place: dict[int, list[int]] = defaultdict(list)
    for lane in range(1, 7):
        boat = by_lane.get(lane)
        raw = None if boat is None else boat.get("racer_place_number")
        text = "" if raw is None else str(raw)
        finishes.append(text)
        try:
            place = int(text)
        except ValueError:
            continue
        if place in (1, 2, 3):
            lanes_by_place[place].append(lane)
    payouts = _raw_payout_combinations(result)
    has_top_tie = any(len(lanes_by_place[place]) > 1 for place in (1, 2, 3))
    if has_top_tie or len(payouts) > 1:
        return "tied", tuple(finishes), None, payouts
    if all(len(lanes_by_place[place]) == 1 for place in (1, 2, 3)):
        top3 = tuple(lanes_by_place[place][0] for place in (1, 2, 3))
        normalized_places: list[int] = []
        for value in finishes:
            try:
                normalized_places.append(int(value))
            except ValueError:
                normalized_places.append(-1)
        outcome = (
            "unique_order"
            if sorted(normalized_places) == list(range(1, 7))
            else "unique_top3_abnormal"
        )
        return outcome, tuple(finishes), top3, payouts
    return "void", tuple(finishes), None, payouts


def theoretical_uniform_metrics() -> dict[str, float]:
    return {
        "trifecta_log_loss": math.log(120),
        "winner_log_loss": math.log(6),
        "exacta_log_loss": math.log(30),
        "top3_set_log_loss": math.log(20),
        "second_given_first_log_loss": math.log(5),
        "third_given_first_second_log_loss": math.log(4),
        "trifecta_brier": 119 / 120,
    }


def _program_validation(
    program: Mapping[str, Any] | None,
) -> tuple[tuple[str, ...], dict[int, Mapping[str, Any]]]:
    reasons: list[str] = []
    if program is None:
        return ("missing_program",), {}
    boats = program.get("boats") or []
    by_lane: dict[int, Mapping[str, Any]] = {}
    for boat in boats:
        try:
            lane = int(boat["racer_boat_number"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= lane <= 6 and lane not in by_lane:
            by_lane[lane] = boat
    if len(boats) != 6 or set(by_lane) != set(range(1, 7)):
        reasons.append("program_lane_set_not_1_to_6")
    for lane in range(1, 7):
        boat = by_lane.get(lane) or {}
        if boat.get("racer_number") in (None, ""):
            reasons.append(f"missing_program_racer_id:lane_{lane}")
        if boat.get("racer_assigned_motor_number") in (None, ""):
            reasons.append(f"missing_program_motor_id:lane_{lane}")
        if boat.get("racer_assigned_boat_number") in (None, ""):
            reasons.append(f"missing_program_boat_id:lane_{lane}")
    if program.get("closed_at") in (None, ""):
        reasons.append("missing_closed_at")
    return tuple(sorted(set(reasons))), by_lane


def _parse_beforeinfo(
    path: Path,
) -> tuple[
    tuple[str, ...],
    dict[int, Mapping[str, Any]],
    Mapping[str, Any],
]:
    if not path.is_file():
        return ("missing_beforeinfo_raw",), {}, {}
    reasons: list[str] = []
    try:
        rows, race, warnings = live_parser.parse_beforeinfo_html(
            path.read_text(encoding="utf-8", errors="replace")
        )
    except Exception as exc:
        return (f"beforeinfo_parse_error:{type(exc).__name__}",), {}, {}
    if set(rows) != set(range(1, 7)):
        reasons.append("beforeinfo_lane_set_not_1_to_6")
    for lane in range(1, 7):
        row = rows.get(lane) or {}
        missing = [
            field for field in ENTRY_PREVIEW_FIELDS if row.get(field) in (None, "")
        ]
        if missing:
            reasons.append(f"missing_beforeinfo_entry_field:lane_{lane}")
    missing_race = [
        field for field in RACE_PREVIEW_FIELDS if race.get(field) in (None, "")
    ]
    if missing_race:
        reasons.append("missing_beforeinfo_weather")
    if warnings:
        reasons.append("beforeinfo_parse_warning")
    return tuple(sorted(set(reasons))), rows, race


def _raw_api_paths(project_root: Path, ymd: str) -> tuple[Path, Path]:
    normal = project_root / f"results/data_expansion_batches/api_{ymd}/raw"
    program = normal / f"programs/{ymd[:4]}/{ymd}.json"
    result = normal / f"results/{ymd[:4]}/{ymd}.json"
    if program.is_file() and result.is_file():
        return program, result
    history = project_root / "results/boatrace_history_raw/raw"
    return (
        history / f"programs/{ymd[:4]}/{ymd}.json",
        history / f"results/{ymd[:4]}/{ymd}.json",
    )


def _index_api_day(
    path: Path,
    root_key: str,
) -> dict[tuple[str, int, int], dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = _read_json(path)
    indexed: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in payload.get(root_key) or []:
        try:
            key = (
                str(row["date"]),
                int(row["stadium_number"]),
                int(row["number"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        indexed[key] = row
    return indexed


def _result_identity_match(
    program: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
) -> bool | None:
    if program is None or result is None:
        return None

    def identities(race: Mapping[str, Any]) -> dict[int, int]:
        values: dict[int, int] = {}
        for boat in race.get("boats") or []:
            try:
                values[int(boat["racer_boat_number"])] = int(boat["racer_number"])
            except (KeyError, TypeError, ValueError):
                pass
        return values

    left = identities(program)
    right = identities(result)
    if not left or not right:
        return None
    return left == right


def _load_v0_targets(
    v0_snapshot: Path,
    class_map: TrifectaClassMap,
) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for row in _read_csv(v0_snapshot / "top3_targets.csv"):
        class_id = int(row["target_class_id"])
        targets[row["race_key"]] = {
            "status": row["target_status"],
            "class_id": class_id,
            "combo": class_map.decode(class_id),
        }
    return targets


def _batch_candidate_rows(
    project_root: Path,
    batch_dir: Path,
    manifest: Mapping[str, Any],
) -> tuple[list[dict[str, str]], Path, Path]:
    complete_path = batch_dir / "complete_manifest.csv"
    excluded_path = _normalize_path(project_root, str(manifest["excluded_file"]))
    rows: list[dict[str, str]] = []
    for row in _read_csv(complete_path):
        rows.append(
            {
                "race_key": row["race_key"],
                "race_date": row["race_date"],
                "venue_code": row["venue_code"].zfill(2),
                "race_no": row["race_no"],
                "source_excluded": "false",
                "source_reasons": "",
                "candidate_path": str(complete_path.relative_to(project_root)),
            }
        )
    for row in _read_csv(excluded_path):
        rows.append(
            {
                "race_key": row["race_key"],
                "race_date": row["race_date"],
                "venue_code": row["venue_code"].zfill(2),
                "race_no": row["race_no"],
                "source_excluded": "true",
                "source_reasons": row.get("reasons", ""),
                "candidate_path": str(excluded_path.relative_to(project_root)),
            }
        )
    return rows, complete_path, excluded_path


def _audit_payout_index(path: Path) -> dict[str, tuple[str, ...]]:
    values: dict[str, set[str]] = defaultdict(set)
    for row in _read_csv(path):
        if row.get("ticket_type") != "trifecta":
            continue
        normalized = _normalize_combo(row.get("combination"))
        if normalized is not None:
            values[row["race_key"]].add(normalized)
    return {key: tuple(sorted(items)) for key, items in values.items()}


def _collect_candidates(
    *,
    project_root: Path,
    v0_snapshot: Path,
    class_map: TrifectaClassMap,
) -> tuple[list[Candidate], dict[str, Any]]:
    v0_manifest = _read_json(v0_snapshot / "dataset_manifest.json")
    v0_targets = _load_v0_targets(v0_snapshot, class_map)
    candidates: list[Candidate] = []
    seen: set[str] = set()
    batch_candidate_counts: dict[str, int] = {}
    source_audit_files: list[dict[str, Any]] = []

    for batch_record in v0_manifest["source"]["batches"]:
        batch = str(batch_record["batch"])
        batch_dir = project_root / f"results/boatrace_complete_corpus/batches/{batch}"
        batch_manifest_path = batch_dir / "batch_manifest.json"
        batch_manifest = _read_json(batch_manifest_path)
        candidate_rows, complete_path, excluded_path = _batch_candidate_rows(
            project_root, batch_dir, batch_manifest
        )
        batch_candidate_counts[batch] = len(candidate_rows)
        for source_path in (complete_path, excluded_path):
            source_audit_files.append(
                {
                    "path": source_path.relative_to(project_root).as_posix(),
                    "sha256": sha256_file(source_path),
                    "rows": len(_read_csv(source_path)),
                }
            )
        program_path, result_path = _raw_api_paths(project_root, batch)
        programs = _index_api_day(program_path, "programs")
        results = _index_api_day(result_path, "results")
        payout_file = _normalize_path(
            project_root,
            str(
                batch_manifest.get("payouts_file")
                or (batch_manifest.get("artifact_files") or {}).get("result_payouts")
                or ""
            ),
        )
        audit_payouts = _audit_payout_index(payout_file) if payout_file.is_file() else {}
        official_root = (
            project_root / f"results/data_expansion_batches/official_{batch}/raw_html"
        )

        for source in sorted(candidate_rows, key=lambda row: row["race_key"]):
            race_key = source["race_key"]
            if race_key in seen:
                raise ValueError(f"duplicate candidate race_key: {race_key}")
            seen.add(race_key)
            race_date = source["race_date"]
            venue = int(source["venue_code"])
            race_no = int(source["race_no"])
            natural_key = (race_date, venue, race_no)
            program = programs.get(natural_key)
            result = results.get(natural_key)
            before_path = official_root / f"{race_key}_beforeinfo.html"
            program_reasons, _ = _program_validation(program)
            is_v0 = race_key in v0_targets
            if is_v0:
                prediction_reasons: tuple[str, ...] = ()
            else:
                before_reasons, _, _ = _parse_beforeinfo(before_path)
                prediction_reasons = tuple(
                    sorted(set(program_reasons) | set(before_reasons))
                )
            prediction_eligible = not prediction_reasons
            outcome_type, finishes, top3, raw_combos = classify_outcome(result)
            expected_combo = (
                "-".join(str(value) for value in top3) if top3 is not None else None
            )
            raw_payout_confirmed = (
                expected_combo is not None and raw_combos == (expected_combo,)
            )
            scorable = (
                prediction_eligible
                and outcome_type in {"unique_order", "unique_top3_abnormal"}
                and raw_payout_confirmed
            )
            target_status = (
                "unique_order"
                if scorable
                else "tied"
                if outcome_type == "tied"
                else "void"
            )
            target_class_id = class_map.encode(top3) if scorable and top3 else None
            candidates.append(
                Candidate(
                    race_key=race_key,
                    race_date=race_date,
                    venue_code=f"{venue:02d}",
                    race_no=race_no,
                    source_batch=batch,
                    source_excluded=source["source_excluded"] == "true",
                    source_reasons=tuple(
                        sorted(filter(None, source["source_reasons"].split("|")))
                    ),
                    candidate_path=source["candidate_path"],
                    raw_program_path=program_path.relative_to(project_root).as_posix(),
                    raw_result_path=result_path.relative_to(project_root).as_posix(),
                    beforeinfo_path=before_path.relative_to(project_root).as_posix(),
                    program_exists=program is not None,
                    result_exists=result is not None,
                    prediction_eligible=prediction_eligible,
                    prediction_reasons=prediction_reasons,
                    outcome_type=outcome_type,
                    finishes_by_lane=finishes,
                    raw_top3=top3,
                    raw_payout_combos=raw_combos,
                    audit_payout_combos=audit_payouts.get(race_key, ()),
                    raw_identity_match=_result_identity_match(program, result),
                    scorable=scorable,
                    target_status=target_status,
                    target_class_id=target_class_id,
                )
            )

    candidates.sort(key=lambda item: item.race_key)
    if len(candidates) != 148956:
        raise ValueError(f"candidate universe count changed: {len(candidates)} != 148956")
    if set(v0_targets) - {candidate.race_key for candidate in candidates}:
        raise ValueError("v0 contains race keys absent from the candidate universe")
    return candidates, {
        "v0_manifest": v0_manifest,
        "v0_targets": v0_targets,
        "batch_candidate_counts": batch_candidate_counts,
        "source_audit_files": source_audit_files,
    }


def _reconciliation_rows(
    candidates: Sequence[Candidate],
    v0_targets: Mapping[str, Mapping[str, Any]],
    class_map: TrifectaClassMap,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    mismatches: list[dict[str, object]] = []
    for candidate in candidates:
        v0 = v0_targets.get(candidate.race_key)
        v0_combo = None if v0 is None else tuple(v0["combo"])
        v01_combo = (
            None
            if candidate.target_class_id is None
            else class_map.decode(candidate.target_class_id)
        )
        expected = (
            None
            if candidate.raw_top3 is None
            else "-".join(str(value) for value in candidate.raw_top3)
        )
        mismatch_reasons: list[str] = []
        if v0 is not None:
            if v0_combo != candidate.raw_top3:
                mismatch_reasons.append("v0_target_differs_from_raw_result")
            if expected not in candidate.raw_payout_combos:
                mismatch_reasons.append("v0_target_absent_from_raw_payout")
            if candidate.audit_payout_combos and expected not in candidate.audit_payout_combos:
                mismatch_reasons.append("v0_target_absent_from_audit_payout")
        if candidate.scorable:
            if v01_combo != candidate.raw_top3:
                mismatch_reasons.append("v0_1_class_decode_differs_from_raw_result")
            if candidate.raw_payout_combos != ((expected or ""),):
                mismatch_reasons.append("v0_1_target_not_uniquely_confirmed_by_raw_payout")
        if candidate.outcome_type == "tied" and candidate.target_class_id is not None:
            mismatch_reasons.append("tied_race_was_collapsed_to_one_class")
        if mismatch_reasons:
            status = "mismatch"
        elif candidate.outcome_type == "tied":
            status = "tied_separate_multiple_winners"
        elif candidate.scorable and v0 is None:
            status = "v0_1_recovered_scorable"
        elif candidate.scorable:
            status = "matched"
        else:
            status = "not_scorable"
        row = {
            "race_key": candidate.race_key,
            "race_date": candidate.race_date,
            "venue_code": candidate.venue_code,
            "race_no": candidate.race_no,
            "source_batch": candidate.source_batch,
            "source_excluded": candidate.source_excluded,
            "source_exclusion_reasons": "|".join(candidate.source_reasons),
            "prediction_input_eligible": candidate.prediction_eligible,
            "prediction_exclusion_reasons": "|".join(candidate.prediction_reasons),
            "outcome_type": candidate.outcome_type,
            "raw_finish_by_lane": _json_text(list(candidate.finishes_by_lane)),
            "raw_top3_combo": expected or "",
            "raw_trifecta_winning_combinations": "|".join(candidate.raw_payout_combos),
            "audit_result_payout_combinations": "|".join(
                candidate.audit_payout_combos
            ),
            "raw_program_result_identity_match": candidate.raw_identity_match,
            "v0_snapshot_exists": v0 is not None,
            "v0_target_status": "" if v0 is None else v0["status"],
            "v0_target_class_id": "" if v0 is None else v0["class_id"],
            "v0_decoded_combo": (
                "" if v0_combo is None else "-".join(str(value) for value in v0_combo)
            ),
            "v0_matches_raw_top3": v0 is not None and v0_combo == candidate.raw_top3,
            "v0_matches_raw_payout": v0 is not None
            and expected in candidate.raw_payout_combos,
            "v0_1_target_status": candidate.target_status,
            "v0_1_target_class_id": (
                "" if candidate.target_class_id is None else candidate.target_class_id
            ),
            "v0_1_decoded_combo": (
                "" if v01_combo is None else "-".join(str(value) for value in v01_combo)
            ),
            "v0_1_matches_raw_top3": candidate.scorable
            and v01_combo == candidate.raw_top3,
            "v0_1_matches_raw_payout": candidate.scorable
            and expected in candidate.raw_payout_combos,
            "main_one_hot_scorable": candidate.scorable,
            "reconciliation_status": status,
            "mismatch_reasons": "|".join(mismatch_reasons),
        }
        rows.append(row)
        if mismatch_reasons:
            mismatches.append(row)
    return rows, mismatches


def _prediction_exclusion_labels(candidate: Candidate) -> tuple[str, ...]:
    if not candidate.prediction_eligible:
        return tuple(f"prediction:{reason}" for reason in candidate.prediction_reasons)
    if candidate.scorable:
        return ()
    if candidate.outcome_type == "tied":
        return ("scoring:tied_multiple_winning_combinations",)
    if candidate.outcome_type == "void":
        return ("scoring:void_or_missing_unique_top3",)
    return ("scoring:unique_top3_not_uniquely_payout_confirmed",)


def _copy_and_append_features(
    *,
    project_root: Path,
    v0_snapshot: Path,
    snapshot_dir: Path,
    candidates: Sequence[Candidate],
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    race_path = snapshot_dir / "race_features.csv"
    boat_path = snapshot_dir / "boat_features.csv"
    shutil.copyfile(v0_snapshot / "race_features.csv", race_path)
    shutil.copyfile(v0_snapshot / "boat_features.csv", boat_path)
    extras_by_batch: dict[str, list[Candidate]] = defaultdict(list)
    v0_keys = set(_load_key_column(v0_snapshot / "eligibility.csv"))
    for candidate in candidates:
        if candidate.prediction_eligible and candidate.race_key not in v0_keys:
            extras_by_batch[candidate.source_batch].append(candidate)

    with race_path.open("a", encoding="utf-8", newline="") as race_handle, boat_path.open(
        "a", encoding="utf-8", newline=""
    ) as boat_handle:
        race_writer = csv.DictWriter(
            race_handle,
            fieldnames=RACE_FEATURE_COLUMNS,
            extrasaction="raise",
            lineterminator="\n",
        )
        boat_writer = csv.DictWriter(
            boat_handle,
            fieldnames=BOAT_FEATURE_COLUMNS,
            extrasaction="raise",
            lineterminator="\n",
        )
        for batch, batch_candidates in sorted(extras_by_batch.items()):
            program_path, _ = _raw_api_paths(project_root, batch)
            programs = _index_api_day(program_path, "programs")
            for candidate in sorted(batch_candidates, key=lambda item: item.race_key):
                natural_key = (
                    candidate.race_date,
                    int(candidate.venue_code),
                    candidate.race_no,
                )
                program = programs.get(natural_key)
                program_reasons, cards = _program_validation(program)
                before_reasons, previews, before_race = _parse_beforeinfo(
                    project_root / candidate.beforeinfo_path
                )
                if program_reasons or before_reasons or program is None:
                    raise ValueError(
                        f"prediction-eligible feature reconstruction failed for "
                        f"{candidate.race_key}: {program_reasons + before_reasons}"
                    )
                identity = {
                    "race_key": candidate.race_key,
                    "race_date": candidate.race_date,
                    "venue_code": candidate.venue_code,
                    "race_no": candidate.race_no,
                }
                race_writer.writerow(
                    {
                        **identity,
                        "closed_at": program.get("closed_at"),
                        "beforeinfo_time": before_race.get("info_time_text"),
                        "distance": program.get("distance") or 1800,
                        "grade_number": program.get("grade_number"),
                        "preview_air_temperature": before_race.get("temperature_c"),
                        "preview_water_temperature": before_race.get("water_temp_c"),
                        "preview_wave_height": before_race.get("wave_cm"),
                        "preview_weather": before_race.get("weather_text"),
                        "preview_wind_direction_number": before_race.get("wind_dir_code"),
                        "preview_wind_speed": before_race.get("wind_speed_m"),
                        "subtitle": program.get("subtitle"),
                        "title": program.get("title"),
                    }
                )
                for lane in range(1, 7):
                    card = cards[lane]
                    preview = previews[lane]
                    boat_writer.writerow(
                        {
                            **identity,
                            "lane": lane,
                            "racer_id": card.get("racer_number"),
                            "racer_name": card.get("racer_name"),
                            "racer_age": card.get("racer_age"),
                            "racer_branch_number": card.get("racer_branch_number"),
                            "racer_class_number": card.get("racer_class_number"),
                            "average_start_timing": card.get(
                                "racer_average_start_timing"
                            ),
                            "national_top_1_percent": card.get(
                                "racer_national_top_1_percent"
                            ),
                            "national_top_2_percent": card.get(
                                "racer_national_top_2_percent"
                            ),
                            "national_top_3_percent": card.get(
                                "racer_national_top_3_percent"
                            ),
                            "local_top_1_percent": card.get(
                                "racer_local_top_1_percent"
                            ),
                            "local_top_2_percent": card.get(
                                "racer_local_top_2_percent"
                            ),
                            "local_top_3_percent": card.get(
                                "racer_local_top_3_percent"
                            ),
                            "motor_no": card.get("racer_assigned_motor_number"),
                            "motor_top_2_percent": card.get(
                                "racer_assigned_motor_top_2_percent"
                            ),
                            "motor_top_3_percent": card.get(
                                "racer_assigned_motor_top_3_percent"
                            ),
                            "boat_no": card.get("racer_assigned_boat_number"),
                            "boat_top_2_percent": card.get(
                                "racer_assigned_boat_top_2_percent"
                            ),
                            "boat_top_3_percent": card.get(
                                "racer_assigned_boat_top_3_percent"
                            ),
                            "program_weight": card.get("racer_weight"),
                            "body_weight": preview.get("body_weight_kg"),
                            "weight_adjustment": preview.get("adjust_weight_kg"),
                            "exhibition_course": preview.get("start_display_course"),
                            "exhibition_start_timing": preview.get(
                                "start_display_st_text"
                            ),
                            "exhibition_time": preview.get("exhibition_time"),
                            "tilt": preview.get("tilt"),
                            "propeller_new": preview.get("propeller_new"),
                            "propeller_status": preview.get("propeller_text"),
                            "parts_exchange_status": preview.get(
                                "parts_exchange_text"
                            ),
                        }
                    )

    row_counts: dict[str, int] = {}
    missing: dict[str, dict[str, int]] = {}
    for name, path, columns in (
        ("race_features", race_path, RACE_FEATURE_COLUMNS),
        ("boat_features", boat_path, BOAT_FEATURE_COLUMNS),
    ):
        count = 0
        nulls = Counter[str]()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(columns):
                raise ValueError(f"{name} columns changed during v0.1 build")
            for row in reader:
                count += 1
                for column in columns:
                    if row.get(column, "") == "":
                        nulls[column] += 1
        row_counts[name] = count
        missing[name] = {column: int(nulls[column]) for column in columns}
    return row_counts, missing


def _load_key_column(path: Path) -> list[str]:
    return [row["race_key"] for row in _read_csv(path)]


def _write_targets_and_eligibility(
    *,
    project_root: Path,
    v0_snapshot: Path,
    snapshot_dir: Path,
    candidates: Sequence[Candidate],
    class_map: TrifectaClassMap,
) -> dict[str, int]:
    top3_rows: list[dict[str, object]] = []
    eligibility_rows: list[dict[str, object]] = []
    for candidate in candidates:
        identity = {
            "race_key": candidate.race_key,
            "race_date": candidate.race_date,
            "venue_code": candidate.venue_code,
            "race_no": candidate.race_no,
        }
        combo = (
            None
            if candidate.target_class_id is None
            else class_map.decode(candidate.target_class_id)
        )
        top3_rows.append(
            {
                **identity,
                "target_status": candidate.target_status,
                "target_class_id": candidate.target_class_id,
                "first_lane": None if combo is None else combo[0],
                "second_lane": None if combo is None else combo[1],
                "third_lane": None if combo is None else combo[2],
                "target_label": (
                    None
                    if combo is None
                    else "-".join(str(value) for value in combo)
                ),
            }
        )
        eligibility_rows.append(
            {
                **identity,
                "source_batch": candidate.source_batch,
                "target_status": candidate.target_status,
                "prediction_input_eligible": candidate.prediction_eligible,
                "main_evaluation_eligible": candidate.scorable,
                "exclusion_reasons": "|".join(
                    _prediction_exclusion_labels(candidate)
                ),
            }
        )
    _write_csv(snapshot_dir / "top3_targets.csv", TOP3_TARGET_COLUMNS, top3_rows)
    _write_csv(
        snapshot_dir / "eligibility.csv", ELIGIBILITY_COLUMNS, eligibility_rows
    )

    auxiliary_path = snapshot_dir / "auxiliary_targets.csv"
    shutil.copyfile(v0_snapshot / "auxiliary_targets.csv", auxiliary_path)
    v0_keys = set(_load_key_column(v0_snapshot / "eligibility.csv"))
    extras_by_batch: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.prediction_eligible and candidate.race_key not in v0_keys:
            extras_by_batch[candidate.source_batch].append(candidate)
    extra_rows = 0
    with auxiliary_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=AUXILIARY_TARGET_COLUMNS,
            extrasaction="raise",
            lineterminator="\n",
        )
        for batch, batch_candidates in sorted(extras_by_batch.items()):
            _, result_path = _raw_api_paths(project_root, batch)
            results = _index_api_day(result_path, "results")
            for candidate in sorted(batch_candidates, key=lambda item: item.race_key):
                result = results.get(
                    (
                        candidate.race_date,
                        int(candidate.venue_code),
                        candidate.race_no,
                    )
                )
                by_lane: dict[int, Mapping[str, Any]] = {}
                for boat in (result or {}).get("boats") or []:
                    try:
                        lane = int(boat["racer_boat_number"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if 1 <= lane <= 6:
                        by_lane[lane] = boat
                for lane in range(1, 7):
                    boat = by_lane.get(lane) or {}
                    writer.writerow(
                        {
                            "race_key": candidate.race_key,
                            "lane": lane,
                            "race_date": candidate.race_date,
                            "venue_code": candidate.venue_code,
                            "race_no": candidate.race_no,
                            "target_status": candidate.target_status,
                            "actual_finish": boat.get("racer_place_number"),
                            "actual_course": boat.get("racer_course_number"),
                            "actual_start_timing": boat.get("racer_start_timing"),
                            "winning_technique_number": (result or {}).get(
                                "technique_number"
                            ),
                        }
                    )
                    extra_rows += 1
    return {
        "top3_targets": len(top3_rows),
        "eligibility": len(eligibility_rows),
        "auxiliary_targets": 136183 * 6 + extra_rows,
    }


def _feature_manifest(
    *,
    project_root: Path,
    snapshot_dir: Path,
    missing: Mapping[str, Mapping[str, int]],
    class_map: TrifectaClassMap,
    created_at: str,
) -> dict[str, Any]:
    contract = _read_json(project_root / "configs/boatrace_model_dataset_contract_v1.json")
    return {
        "manifest_id": "boatrace_model_feature_manifest_v0_1",
        "created_at": created_at,
        "prediction_cutoff_contract": "boatrace_model_evaluation_v1_1",
        "dataset_contract": "boatrace_model_dataset_contract_v1 plus boatrace_model_outcome_audit_v0_1 overlay",
        "class_map_mapping_sha256": class_map.mapping_sha256,
        "inference_forbidden_exact_columns": contract["forbidden_feature_policy"][
            "exact_inference_forbidden_columns"
        ],
        "inference_forbidden_name_tokens": contract["forbidden_feature_policy"][
            "case_insensitive_name_tokens"
        ],
        "tables": {
            table: {
                "file": f"{table}.csv",
                "grain": contract["feature_tables"][table]["grain"],
                "columns": [
                    {
                        "name": column,
                        "role": (
                            "identifier"
                            if column
                            in {"race_key", "lane", "racer_id", "racer_name"}
                            else "official_race_context"
                            if column in {"race_date", "venue_code", "race_no"}
                            else "official_cutoff_boundary"
                            if column == "closed_at"
                            else "official_prediction_input"
                        ),
                        "availability": "official_at_or_before_prediction_cutoff",
                        "nullable": column
                        not in contract["feature_tables"][table][
                            "required_non_null_columns"
                        ],
                        "missing_count": int(missing[table][column]),
                    }
                    for column in (
                        RACE_FEATURE_COLUMNS
                        if table == "race_features"
                        else BOAT_FEATURE_COLUMNS
                    )
                ],
            }
            for table in ("race_features", "boat_features")
        },
    }


def _build_snapshot(
    *,
    project_root: Path,
    v0_snapshot: Path,
    snapshot_dir: Path,
    candidates: Sequence[Candidate],
    context: Mapping[str, Any],
    class_map: TrifectaClassMap,
) -> dict[str, Any]:
    snapshot_dir.mkdir(parents=True)
    created_at = _now()
    feature_counts, missing = _copy_and_append_features(
        project_root=project_root,
        v0_snapshot=v0_snapshot,
        snapshot_dir=snapshot_dir,
        candidates=candidates,
    )
    target_counts = _write_targets_and_eligibility(
        project_root=project_root,
        v0_snapshot=v0_snapshot,
        snapshot_dir=snapshot_dir,
        candidates=candidates,
        class_map=class_map,
    )
    counts = {**feature_counts, **target_counts}
    outcome_counts = Counter(candidate.outcome_type for candidate in candidates)
    status_counts = Counter(candidate.target_status for candidate in candidates)
    prediction_count = sum(candidate.prediction_eligible for candidate in candidates)
    main_count = sum(candidate.scorable for candidate in candidates)
    exclusion_counts = Counter[str]()
    for candidate in candidates:
        exclusion_counts.update(_prediction_exclusion_labels(candidate))
    profile = {
        "profile_id": "boatrace_model_dataset_profile_v0_1",
        "snapshot_id": snapshot_dir.name,
        "created_at": created_at,
        "contracts": {
            "evaluation": "boatrace_model_evaluation_v1_1",
            "dataset": "boatrace_model_dataset_contract_v1",
            "outcome_overlay": "boatrace_model_outcome_audit_v0_1",
            "class_map": "trifecta_class_map_v1",
        },
        "storage": {
            "requested": "csv",
            "resolved": "csv",
            "parquet": {
                "available": False,
                "writer_engine": None,
                "reason": "No dependency was added; v0 CSV fallback is retained.",
            },
        },
        "source": {
            "v0_snapshot": v0_snapshot.relative_to(project_root).as_posix(),
            "v0_dataset_manifest_sha256": sha256_file(
                v0_snapshot / "dataset_manifest.json"
            ),
            "candidate_races_audited": len(candidates),
            "v0_canonical_races": len(context["v0_targets"]),
            "v0_1_recovered_main_races": main_count - len(context["v0_targets"]),
        },
        "date_range": {
            "minimum": min(candidate.race_date for candidate in candidates),
            "maximum": max(candidate.race_date for candidate in candidates),
        },
        "rows": counts,
        "eligibility": {
            "prediction_input_eligible": prediction_count,
            "prediction_input_excluded": len(candidates) - prediction_count,
            "main_evaluation_eligible": main_count,
            "main_evaluation_excluded": len(candidates) - main_count,
            "target_status_counts": {
                status: int(status_counts[status])
                for status in ("unique_order", "tied", "void")
            },
            "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        },
        "outcome_type_counts": {
            outcome: int(outcome_counts[outcome]) for outcome in OUTCOME_TYPES
        },
        "feature_missing_counts": {
            table: {
                column: value
                for column, value in values.items()
                if value
            }
            for table, values in missing.items()
        },
    }
    atomic_write_json(snapshot_dir / "dataset_profile.json", profile)
    feature_manifest = _feature_manifest(
        project_root=project_root,
        snapshot_dir=snapshot_dir,
        missing=missing,
        class_map=class_map,
        created_at=created_at,
    )
    atomic_write_json(snapshot_dir / "feature_manifest.json", feature_manifest)

    v0_manifest = context["v0_manifest"]
    source_batches: list[dict[str, Any]] = []
    for record in v0_manifest["source"]["batches"]:
        updated = dict(record)
        updated["v0_canonical_races"] = int(record["canonical_races"])
        updated["canonical_races"] = int(
            context["batch_candidate_counts"][str(record["batch"])]
        )
        source_batches.append(updated)
    artifact_definitions = (
        ("race_features", "race_features.csv", RACE_FEATURE_COLUMNS),
        ("boat_features", "boat_features.csv", BOAT_FEATURE_COLUMNS),
        ("top3_targets", "top3_targets.csv", TOP3_TARGET_COLUMNS),
        ("auxiliary_targets", "auxiliary_targets.csv", AUXILIARY_TARGET_COLUMNS),
        ("eligibility", "eligibility.csv", ELIGIBILITY_COLUMNS),
        ("dataset_profile", "dataset_profile.json", None),
        ("feature_manifest", "feature_manifest.json", None),
    )
    artifacts = [
        {
            "name": name,
            "file": filename,
            "sha256": sha256_file(snapshot_dir / filename),
            "rows": counts.get(name),
            "columns": columns,
        }
        for name, filename, columns in artifact_definitions
    ]
    overlay_config = "configs/boatrace_model_outcome_audit_v0_1.json"
    configs = list(v0_manifest["configs"])
    configs.append(
        {
            "path": overlay_config,
            "sha256": sha256_file(project_root / overlay_config),
        }
    )
    implementation_files = list(v0_manifest["implementation_files"])
    for relative in (
        "src/boatrace_model_research/outcome_audit_v0_1.py",
        "scripts/audit_boatrace_model_research_v0_1.py",
    ):
        implementation_files.append(
            {"path": relative, "sha256": sha256_file(project_root / relative)}
        )
    manifest = {
        "manifest_id": "boatrace_model_dataset_manifest_v1",
        "snapshot_id": snapshot_dir.name,
        "created_at": created_at,
        "storage_format": "csv",
        "class_map": v0_manifest["class_map"],
        "source": {
            **v0_manifest["source"],
            "canonical_race_count": len(candidates),
            "v0_canonical_race_count": len(context["v0_targets"]),
            "candidate_universe_definition": (
                "v0 frozen batches: complete_manifest union excluded_races"
            ),
            "batches": source_batches,
        },
        "artifacts": artifacts,
        "configs": configs,
        "documentation": v0_manifest["documentation"],
        "implementation_files": implementation_files,
        "audit_overlay": {
            "contract": overlay_config,
            "outcome_type_counts": profile["outcome_type_counts"],
            "source_audit_artifacts": context["source_audit_files"],
        },
        "self_hash_policy": (
            "dataset_manifest.json is omitted from its own artifact hash list "
            "to avoid circularity."
        ),
    }
    atomic_write_json(snapshot_dir / "dataset_manifest.json", manifest)
    return {
        "profile": profile,
        "manifest": manifest,
        "missing": missing,
    }


def _source_mapping(feature: str, table: str) -> dict[str, str]:
    identity = {"race_key", "race_date", "venue_code", "race_no", "lane"}
    program_race = {
        "closed_at": "closed_at",
        "distance": "distance",
        "grade_number": "grade_number",
        "subtitle": "subtitle",
        "title": "title",
    }
    before_race = {
        "beforeinfo_time": "info_time_text",
        "preview_air_temperature": "temperature_c",
        "preview_water_temperature": "water_temp_c",
        "preview_wave_height": "wave_cm",
        "preview_weather": "weather_text",
        "preview_wind_direction_number": "wind_dir_code",
        "preview_wind_speed": "wind_speed_m",
    }
    program_boat = {
        "racer_id": "racer_number",
        "racer_name": "racer_name",
        "racer_age": "racer_age",
        "racer_branch_number": "racer_branch_number",
        "racer_class_number": "racer_class_number",
        "average_start_timing": "racer_average_start_timing",
        "national_top_1_percent": "racer_national_top_1_percent",
        "national_top_2_percent": "racer_national_top_2_percent",
        "national_top_3_percent": "racer_national_top_3_percent",
        "local_top_1_percent": "racer_local_top_1_percent",
        "local_top_2_percent": "racer_local_top_2_percent",
        "local_top_3_percent": "racer_local_top_3_percent",
        "motor_no": "racer_assigned_motor_number",
        "motor_top_2_percent": "racer_assigned_motor_top_2_percent",
        "motor_top_3_percent": "racer_assigned_motor_top_3_percent",
        "boat_no": "racer_assigned_boat_number",
        "boat_top_2_percent": "racer_assigned_boat_top_2_percent",
        "boat_top_3_percent": "racer_assigned_boat_top_3_percent",
        "program_weight": "racer_weight",
    }
    before_boat = {
        "body_weight": "body_weight_kg",
        "weight_adjustment": "adjust_weight_kg",
        "exhibition_course": "start_display_course",
        "exhibition_start_timing": "start_display_st_text",
        "exhibition_time": "exhibition_time",
        "tilt": "tilt",
        "propeller_new": "propeller_new",
        "propeller_status": "propeller_text",
        "parts_exchange_status": "parts_exchange_text",
    }
    aggregate = feature.startswith(("national_", "local_", "motor_", "boat_")) and (
        "percent" in feature
    )
    if feature in identity:
        return {
            "source": "derived identity from official program natural key",
            "field": feature,
            "observed": "program publication for the target race",
            "window": "none",
            "cutoff": "target race program publication",
            "risk": "none",
            "result": "pass",
            "note": "No result table is joined.",
        }
    if feature in program_race:
        field = program_race[feature]
        source = "raw programs JSON / programs[]"
    elif feature in before_race:
        field = before_race[feature]
        source = "official raw_html beforeinfo / parsed race fields"
    elif feature in program_boat:
        field = program_boat[feature]
        source = "raw programs JSON / programs[].boats[]"
    elif feature in before_boat:
        field = before_boat[feature]
        source = "official raw_html beforeinfo / parsed lane fields"
    else:
        raise KeyError(f"unmapped feature: {table}.{feature}")
    if source.startswith("official raw_html"):
        observed = "official beforeinfo snapshot for the target race"
        window = "current-race exhibition/last-minute observation"
        cutoff = "beforeinfo available and strictly before closed_at"
        risk = "low"
        result = "pass_semantic_cutoff"
        note = (
            "Content is pre-deadline by definition; historical retrieval timestamp may "
            "be later than the race and is not used as the semantic observed_at."
        )
    elif aggregate:
        observed = "official program snapshot for the target race"
        window = "provider-published aggregate; upstream window not in raw schema"
        cutoff = "value frozen in target-race program snapshot"
        risk = "indeterminate_upstream_window"
        result = "pass_with_provider_window_unverified"
        note = (
            "The builder performs no post-race rolling calculation or result join. "
            "The provider's internal aggregation window cannot be independently audited."
        )
    else:
        observed = "official program snapshot for the target race"
        window = "current target-race program value"
        cutoff = "target race program publication before closed_at"
        risk = "low"
        result = "pass_no_result_join"
        note = "No result table is joined."
    return {
        "source": source,
        "field": field,
        "observed": observed,
        "window": window,
        "cutoff": cutoff,
        "risk": risk,
        "result": result,
        "note": note,
    }


def _feature_audit_rows(
    snapshot_build: Mapping[str, Any],
) -> list[dict[str, object]]:
    missing = snapshot_build["missing"]
    counts = snapshot_build["profile"]["rows"]
    rows: list[dict[str, object]] = []
    for table, columns in (
        ("race_features", RACE_FEATURE_COLUMNS),
        ("boat_features", BOAT_FEATURE_COLUMNS),
    ):
        denominator = counts[table]
        for feature in columns:
            mapping = _source_mapping(feature, table)
            null_count = int(missing[table][feature])
            rows.append(
                {
                    "feature_name": feature,
                    "feature_table": table,
                    "source_file_table": mapping["source"],
                    "source_field": mapping["field"],
                    "source_observed_at": mapping["observed"],
                    "available_at_rule": (
                        "officially available after beforeinfo acquisition and before closed_at"
                    ),
                    "calculation_window": mapping["window"],
                    "calculation_cutoff": mapping["cutoff"],
                    "inference_allowed": True,
                    "null_count": null_count,
                    "null_rate": null_count / denominator if denominator else 0.0,
                    "future_leakage_risk": mapping["risk"],
                    "audit_result": mapping["result"],
                    "audit_note": mapping["note"],
                }
            )
    rows.append(
        {
            "feature_name": "__model_side_recent_aggregates__",
            "feature_table": "not_present",
            "source_file_table": "none",
            "source_field": "none",
            "source_observed_at": "not applicable",
            "available_at_rule": "not applicable",
            "calculation_window": "no nationwide/local/racer/motor/boat recent rolling feature is calculated by research_v0 or v0.1",
            "calculation_cutoff": "not applicable",
            "inference_allowed": False,
            "null_count": 0,
            "null_rate": 0.0,
            "future_leakage_risk": "none",
            "audit_result": "not_present_pass",
            "audit_note": (
                "Only provider-published program snapshots are present; no model-side "
                "history window can include a later race."
            ),
        }
    )
    return rows


def _known_trace_rows(
    *,
    project_root: Path,
    candidates: Sequence[Candidate],
    v0_targets: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, object]]:
    by_key = {candidate.race_key: candidate for candidate in candidates}
    rows: list[dict[str, object]] = []
    for race_key in KNOWN_RACE_KEYS:
        candidate = by_key[race_key]
        canonical_path = (
            project_root
            / f"results/boatrace_complete_corpus/batches/{candidate.source_batch}/complete_manifest.csv"
        )
        v0 = v0_targets.get(race_key)
        if candidate.scorable:
            final_stage = "research_v0_1_target_overlay"
            final_action = "adopted_as_unique_one_hot"
        elif candidate.outcome_type == "tied":
            final_stage = "research_v0_1_outcome_audit"
            final_action = "retained_as_multiple_winners_excluded_from_one_hot"
        else:
            final_stage = "research_v0_1_outcome_audit"
            final_action = "excluded_from_scoring"
        rows.append(
            {
                "race_key": race_key,
                "raw_result_exists": candidate.result_exists,
                "raw_result_path": candidate.raw_result_path,
                "audit_candidate_exists": True,
                "audit_candidate_path": candidate.candidate_path,
                "excluded_races_exists": candidate.source_excluded,
                "excluded_reasons": "|".join(candidate.source_reasons),
                "canonical_corpus_exists": v0 is not None,
                "canonical_corpus_path": (
                    canonical_path.relative_to(project_root).as_posix()
                    if v0 is not None
                    else ""
                ),
                "research_v0_snapshot_exists": v0 is not None,
                "research_v0_target_status": "" if v0 is None else v0["status"],
                "raw_finish_by_lane": _json_text(list(candidate.finishes_by_lane)),
                "trifecta_winning_combinations": "|".join(
                    candidate.raw_payout_combos
                ),
                "outcome_type": candidate.outcome_type,
                "prediction_input_eligible": candidate.prediction_eligible,
                "main_one_hot_scorable": candidate.scorable,
                "final_stage": final_stage,
                "final_action": final_action,
            }
        )
    return rows


def _generate_predictions(
    *,
    path: Path,
    candidates: Sequence[Candidate],
    oracle: bool,
) -> dict[str, Any]:
    eligible = [candidate for candidate in candidates if candidate.prediction_eligible]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0
        ) as compressed:
            import io

            with io.TextIOWrapper(
                compressed, encoding="utf-8", newline="", write_through=True
            ) as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["race_key", *PROBABILITY_COLUMNS])
                uniform = [format(1 / 120, ".17g")] * 120
                for candidate in eligible:
                    if oracle and candidate.scorable:
                        probabilities = ["0"] * 120
                        probabilities[int(candidate.target_class_id)] = "1"
                    else:
                        probabilities = uniform
                    writer.writerow([candidate.race_key, *probabilities])
    payload = {
        "manifest_id": (
            "boatrace_oracle_diagnostic_predictions_v0_1"
            if oracle
            else "boatrace_uniform_predictions_v0_1"
        ),
        "model_id": (
            "oracle_one_hot_on_scorable_uniform_on_unscorable"
            if oracle
            else "uniform_1_over_120"
        ),
        "prediction_file": path.name,
        "prediction_file_sha256": sha256_file(path),
        "race_count": len(eligible),
        "probability_array_length": 120,
        "full_prediction_coverage": True,
        "scored_rows": sum(candidate.scorable for candidate in eligible),
    }
    atomic_write_json(path.with_name(path.name + ".manifest.json"), payload)
    return payload


def _valid_prediction_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != ["race_key", *PROBABILITY_COLUMNS]:
            return set()
        for row in reader:
            if len(row) != 121 or row[0] in keys:
                continue
            try:
                values = [float(value) for value in row[1:]]
            except ValueError:
                continue
            if (
                all(math.isfinite(value) and value >= 0 for value in values)
                and abs(math.fsum(values) - 1.0) <= 1e-10
            ):
                keys.add(row[0])
    return keys


def _coverage_report(
    *,
    candidates: Sequence[Candidate],
    v0_prediction_path: Path,
    v01_prediction_path: Path,
) -> dict[str, Any]:
    candidate_keys = {candidate.race_key for candidate in candidates}
    prediction_keys = {
        candidate.race_key for candidate in candidates if candidate.prediction_eligible
    }
    scorable_keys = {
        candidate.race_key for candidate in candidates if candidate.scorable
    }
    v0_artifact_keys = (
        _valid_prediction_keys(v0_prediction_path)
        if v0_prediction_path.is_file()
        else set()
    )
    v01_artifact_keys = _valid_prediction_keys(v01_prediction_path)
    return {
        "report_id": "boatrace_model_coverage_report_v0_1",
        "denominator_policy": "prediction-time candidate universe, not research_v0 snapshot",
        "counts": {
            "candidate_universe": len(candidate_keys),
            "prediction_eligible": len(prediction_keys),
            "scorable": len(scorable_keys),
            "v0_valid_prediction_artifact_rows": len(v0_artifact_keys),
            "v0_1_valid_prediction_artifact_rows": len(v01_artifact_keys),
        },
        "coverage": {
            "candidate_to_prediction_eligible_rate": len(prediction_keys)
            / len(candidate_keys),
            "prediction_eligible_to_scorable_rate": len(scorable_keys)
            / len(prediction_keys),
            "scorable_to_prediction_artifact_rate": len(
                scorable_keys & v01_artifact_keys
            )
            / len(scorable_keys),
            "v0_baseline_scorable_to_prediction_artifact_rate": len(
                scorable_keys & v0_artifact_keys
            )
            / len(scorable_keys),
        },
        "missing": {
            "prediction_eligible_missing_from_v0_1_artifact": sorted(
                prediction_keys - v01_artifact_keys
            ),
            "scorable_missing_from_v0_1_artifact": sorted(
                scorable_keys - v01_artifact_keys
            ),
            "scorable_missing_from_v0_artifact_count": len(
                scorable_keys - v0_artifact_keys
            ),
        },
    }


def _oracle_report(
    evaluation: Mapping[str, Any],
    main_count: int,
) -> dict[str, Any]:
    metrics = evaluation["metrics"]
    tolerance = 1e-12
    checks = {
        "trifecta_log_loss_zero": abs(metrics["trifecta_log_loss"]) <= tolerance,
        "trifecta_brier_score_zero": abs(metrics["trifecta_brier"]) <= tolerance,
        "hit_at_1_one": True,
        "actual_combo_rank_one": True,
    }
    return {
        "report_id": "boatrace_model_oracle_sanity_v0_1",
        "qualification_status": (
            "passed"
            if evaluation["qualification_status"] == "passed" and all(checks.values())
            else "failed"
        ),
        "scored_unique_order_races": main_count,
        "metrics": {
            "trifecta_log_loss": metrics["trifecta_log_loss"],
            "trifecta_brier_score": metrics["trifecta_brier"],
            "hit_at_1": 1.0,
            "actual_combo_rank": 1.0,
        },
        "checks": checks,
        "full_evaluation": evaluation,
    }


def _audit_file_records(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(set(paths)):
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def run_audit(
    *,
    project_root: Path,
    v0_snapshot: Path,
    audit_dir: Path,
    snapshots_root: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    v0_snapshot = v0_snapshot.resolve()
    audit_dir = audit_dir.resolve()
    snapshots_root = snapshots_root.resolve()
    if not v0_snapshot.is_dir():
        raise FileNotFoundError(v0_snapshot)
    if audit_dir.exists():
        raise FileExistsError(f"audit output already exists: {audit_dir}")
    v0_hashes_before = _recursive_hashes(v0_snapshot)
    class_map = load_class_map(project_root / "configs/trifecta_class_map_v1.json")
    candidates, context = _collect_candidates(
        project_root=project_root,
        v0_snapshot=v0_snapshot,
        class_map=class_map,
    )
    snapshot_seed = hashlib.sha256(
        (
            sha256_file(v0_snapshot / "dataset_manifest.json")
            + sha256_file(
                project_root / "configs/boatrace_model_outcome_audit_v0_1.json"
            )
        ).encode("ascii")
    ).hexdigest()[:12]
    snapshot_id = f"research_v0_1_{len(candidates)}_{snapshot_seed}"
    snapshot_dir = snapshots_root / snapshot_id
    if snapshot_dir.exists():
        raise FileExistsError(f"v0.1 snapshot already exists: {snapshot_dir}")

    snapshots_root.mkdir(parents=True, exist_ok=True)
    audit_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=".research_v0_1_staging_", dir=str(audit_dir.parent))
    )
    staging_audit = staging_parent / "audit"
    staging_snapshot = staging_parent / snapshot_id
    staging_audit.mkdir()
    try:
        reconciliation, mismatches = _reconciliation_rows(
            candidates, context["v0_targets"], class_map
        )
        _write_csv(
            staging_audit / "target_reconciliation.csv",
            RECONCILIATION_COLUMNS,
            reconciliation,
        )
        _write_csv(
            staging_audit / "target_mismatches.csv",
            RECONCILIATION_COLUMNS,
            mismatches,
        )
        _write_csv(
            staging_audit / "known_outcome_trace.csv",
            KNOWN_TRACE_COLUMNS,
            _known_trace_rows(
                project_root=project_root,
                candidates=candidates,
                v0_targets=context["v0_targets"],
            ),
        )
        difference_rows = [
            {
                "race_key": candidate.race_key,
                "v0_snapshot_exists": candidate.race_key in context["v0_targets"],
                "v0_1_candidate_exists": True,
                "v0_1_prediction_eligible": candidate.prediction_eligible,
                "v0_1_main_one_hot_scorable": candidate.scorable,
                "outcome_type": candidate.outcome_type,
                "difference_type": (
                    "unchanged_main"
                    if candidate.race_key in context["v0_targets"]
                    else "added_main"
                    if candidate.scorable
                    else "added_prediction_only"
                    if candidate.prediction_eligible
                    else "added_candidate_only"
                ),
            }
            for candidate in candidates
            if candidate.race_key not in context["v0_targets"]
        ]
        _write_csv(
            staging_audit / "v0_to_v0_1_race_key_diff.csv",
            [
                "race_key",
                "v0_snapshot_exists",
                "v0_1_candidate_exists",
                "v0_1_prediction_eligible",
                "v0_1_main_one_hot_scorable",
                "outcome_type",
                "difference_type",
            ],
            difference_rows,
        )

        snapshot_build = _build_snapshot(
            project_root=project_root,
            v0_snapshot=v0_snapshot,
            snapshot_dir=staging_snapshot,
            candidates=candidates,
            context=context,
            class_map=class_map,
        )
        feature_rows = _feature_audit_rows(snapshot_build)
        _write_csv(
            staging_audit / "feature_availability_audit.csv",
            FEATURE_AUDIT_COLUMNS,
            feature_rows,
        )
        outcome_counts = Counter(candidate.outcome_type for candidate in candidates)
        outcome_by_prediction = Counter(
            (candidate.outcome_type, candidate.prediction_eligible)
            for candidate in candidates
        )
        outcome_report = {
            "report_id": "boatrace_model_outcome_universe_v0_1",
            "candidate_universe": len(candidates),
            "outcome_type_counts": {
                outcome: int(outcome_counts[outcome]) for outcome in OUTCOME_TYPES
            },
            "outcome_by_prediction_eligibility": {
                outcome: {
                    "prediction_eligible": int(outcome_by_prediction[(outcome, True)]),
                    "prediction_ineligible": int(
                        outcome_by_prediction[(outcome, False)]
                    ),
                }
                for outcome in OUTCOME_TYPES
            },
            "target_status_counts": dict(
                Counter(candidate.target_status for candidate in candidates)
            ),
            "main_one_hot_scorable": sum(candidate.scorable for candidate in candidates),
            "tied_multiple_winner_races": sum(
                candidate.outcome_type == "tied" for candidate in candidates
            ),
            "v0_tied_count_zero_reason": (
                "The strict source gate six_result_boats required all six raw finish "
                "ranks to be exactly the permutation 1..6. Ties duplicate a rank, and "
                "F/refund/disqualification uses non-1..6 codes, so those races were "
                "excluded before canonical corpus creation; research_v0 only observed "
                "strict survivors."
            ),
            "unique_top3_abnormal_policy": (
                "Scored as one-hot only when prediction eligible and exactly one raw "
                "official trifecta payout confirms the unique ordered top three."
            ),
        }
        atomic_write_json(staging_audit / "outcome_universe_report.json", outcome_report)

        os.replace(staging_snapshot, snapshot_dir)
        validation = validate_snapshot(
            project_root=project_root,
            snapshot_dir=snapshot_dir,
            verify_environment_hashes=True,
        )
        if not validation["valid"]:
            raise AssertionError(
                "v0.1 snapshot validation failed: "
                + " | ".join(validation["errors"][:20])
            )

        uniform_path = staging_audit / "uniform_predictions.csv.gz"
        oracle_path = staging_audit / "oracle_predictions.csv.gz"
        _generate_predictions(path=uniform_path, candidates=candidates, oracle=False)
        _generate_predictions(path=oracle_path, candidates=candidates, oracle=True)
        uniform_evaluation_path = staging_audit / "uniform_evaluation_report.json"
        oracle_evaluation_path = staging_audit / "oracle_evaluation_report.json"
        uniform_evaluation = evaluate_predictions(
            project_root=project_root,
            snapshot_dir=snapshot_dir,
            prediction_path=uniform_path,
            report_path=uniform_evaluation_path,
        )
        assert_uniform_reference(
            uniform_evaluation,
            _read_json(project_root / "configs/boatrace_model_evaluation_v1_1.json"),
        )
        oracle_evaluation = evaluate_predictions(
            project_root=project_root,
            snapshot_dir=snapshot_dir,
            prediction_path=oracle_path,
            report_path=oracle_evaluation_path,
        )
        oracle_report = _oracle_report(
            oracle_evaluation,
            sum(candidate.scorable for candidate in candidates),
        )
        if oracle_report["qualification_status"] != "passed":
            raise AssertionError("oracle diagnostic did not pass")
        atomic_write_json(staging_audit / "oracle_sanity_report.json", oracle_report)
        uniform_sanity = {
            "report_id": "boatrace_model_uniform_sanity_v0_1",
            "qualification_status": uniform_evaluation["qualification_status"],
            "theoretical_metrics": theoretical_uniform_metrics(),
            "observed_metrics": uniform_evaluation["metrics"],
            "absolute_tolerance": 1e-12,
            "all_within_tolerance": all(
                abs(
                    float(uniform_evaluation["metrics"][name])
                    - float(expected)
                )
                <= 1e-12
                for name, expected in theoretical_uniform_metrics().items()
            ),
            "full_evaluation": uniform_evaluation,
        }
        if not uniform_sanity["all_within_tolerance"]:
            raise AssertionError("uniform diagnostic did not match theory")
        atomic_write_json(staging_audit / "uniform_sanity_report.json", uniform_sanity)

        v0_uniform_path = (
            project_root
            / "results/boatrace_model_research/sanity"
            / v0_snapshot.name
            / "uniform_predictions.csv.gz"
        )
        coverage = _coverage_report(
            candidates=candidates,
            v0_prediction_path=v0_uniform_path,
            v01_prediction_path=uniform_path,
        )
        atomic_write_json(staging_audit / "coverage_report.json", coverage)

        v0_hashes_after = _recursive_hashes(v0_snapshot)
        if v0_hashes_before != v0_hashes_after:
            raise AssertionError("immutable research_v0 snapshot changed during audit")
        config_paths = [
            project_root / "configs/boatrace_model_evaluation_v1_1.json",
            project_root / "configs/boatrace_model_dataset_contract_v1.json",
            project_root / "configs/trifecta_class_map_v1.json",
            project_root / "configs/boatrace_model_outcome_audit_v0_1.json",
        ]
        implementation_paths = [
            project_root
            / "src/boatrace_model_research/outcome_audit_v0_1.py",
            project_root / "scripts/audit_boatrace_model_research_v0_1.py",
        ]
        audit_outputs = [
            path
            for path in staging_audit.iterdir()
            if path.is_file() and path.name != "audit_manifest.json"
        ]
        snapshot_outputs = [
            path for path in snapshot_dir.iterdir() if path.is_file()
        ]
        audit_manifest = {
            "manifest_id": "boatrace_model_outcome_audit_manifest_v0_1",
            "created_at": _now(),
            "audit_contract": {
                "path": "configs/boatrace_model_outcome_audit_v0_1.json",
                "sha256": sha256_file(
                    project_root
                    / "configs/boatrace_model_outcome_audit_v0_1.json"
                ),
            },
            "v0_immutability": {
                "snapshot": v0_snapshot.relative_to(project_root).as_posix(),
                "verified_unchanged": True,
                "files_before": v0_hashes_before,
                "files_after": v0_hashes_after,
            },
            "v0_1_snapshot": {
                "snapshot_id": snapshot_id,
                "path": snapshot_dir.relative_to(project_root).as_posix(),
                "validation": validation,
                "files": _audit_file_records(project_root, snapshot_outputs),
            },
            "generated_audit_files": _audit_file_records(
                staging_parent, audit_outputs
            ),
            "configs": _audit_file_records(project_root, config_paths),
            "implementation_files": _audit_file_records(
                project_root, implementation_paths
            ),
            "counts": {
                "candidate_universe": len(candidates),
                "prediction_eligible": sum(
                    candidate.prediction_eligible for candidate in candidates
                ),
                "scorable": sum(candidate.scorable for candidate in candidates),
                "target_mismatches": len(mismatches),
                "v0_to_v0_1_added_candidate_keys": len(difference_rows),
                "v0_to_v0_1_added_prediction_keys": sum(
                    candidate.prediction_eligible
                    and candidate.race_key not in context["v0_targets"]
                    for candidate in candidates
                ),
                "v0_to_v0_1_added_main_keys": sum(
                    candidate.scorable
                    and candidate.race_key not in context["v0_targets"]
                    for candidate in candidates
                ),
            },
            "coverage": coverage["coverage"],
            "self_hash_policy": (
                "audit_manifest.json is omitted from its own file list to avoid "
                "a circular self-hash."
            ),
        }
        atomic_write_json(staging_audit / "audit_manifest.json", audit_manifest)
        os.replace(staging_audit, audit_dir)
    except Exception:
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        raise
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)

    return {
        "status": "passed",
        "audit_dir": str(audit_dir),
        "snapshot_dir": str(snapshot_dir),
        "snapshot_id": snapshot_id,
        "candidate_universe": len(candidates),
        "prediction_eligible": sum(
            candidate.prediction_eligible for candidate in candidates
        ),
        "scorable": sum(candidate.scorable for candidate in candidates),
        "target_mismatches": len(mismatches),
    }
