from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import atomic_write_json, canonical_json_bytes, read_json, sha256_bytes


CLASS_COUNT = 120
LANES = tuple(range(1, 7))
CLASS_MAP_CONTRACT_ID = "trifecta_class_map_v1"


def enumerate_orders() -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (first, second, third)
        for first in LANES
        for second in LANES
        if second != first
        for third in LANES
        if third not in (first, second)
    )


def classes_payload() -> list[dict[str, Any]]:
    return [
        {
            "class_id": class_id,
            "order": list(order),
            "label": "-".join(str(lane) for lane in order),
        }
        for class_id, order in enumerate(enumerate_orders())
    ]


def classes_sha256(classes: Sequence[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(classes))


def build_class_map_payload() -> dict[str, Any]:
    classes = classes_payload()
    return {
        "contract_id": CLASS_MAP_CONTRACT_ID,
        "version": "1.0.0",
        "boat_identity": "lane_number_1_through_6",
        "class_count": CLASS_COUNT,
        "class_id_range": [0, CLASS_COUNT - 1],
        "enumeration_rule": (
            "ascending nested loops: first=1..6, second=1..6 except first, "
            "third=1..6 except first and second"
        ),
        "mapping_sha256_algorithm": (
            "sha256(UTF-8 canonical JSON of classes; keys sorted; separators ',' ':'; "
            "ensure_ascii=false)"
        ),
        "mapping_sha256": classes_sha256(classes),
        "classes": classes,
    }


@dataclass(frozen=True)
class TrifectaClassMap:
    orders: tuple[tuple[int, int, int], ...]
    mapping_sha256: str

    def encode(self, order: Iterable[int]) -> int:
        normalized = tuple(int(value) for value in order)
        if len(normalized) != 3 or len(set(normalized)) != 3:
            raise ValueError(f"trifecta order must contain three distinct lanes: {normalized}")
        if any(value not in LANES for value in normalized):
            raise ValueError(f"trifecta lanes must be in 1..6: {normalized}")
        try:
            return self.orders.index(normalized)
        except ValueError as exc:
            raise ValueError(f"unknown trifecta order: {normalized}") from exc

    def decode(self, class_id: int) -> tuple[int, int, int]:
        if isinstance(class_id, bool) or not isinstance(class_id, int):
            raise ValueError(f"class_id must be an integer: {class_id!r}")
        if not 0 <= class_id < len(self.orders):
            raise ValueError(f"class_id outside 0..{len(self.orders) - 1}: {class_id}")
        return self.orders[class_id]


def validate_class_map_payload(payload: dict[str, Any]) -> TrifectaClassMap:
    if payload.get("contract_id") != CLASS_MAP_CONTRACT_ID:
        raise ValueError("unexpected class-map contract_id")
    classes = payload.get("classes")
    if not isinstance(classes, list):
        raise ValueError("class-map classes must be an array")
    expected = classes_payload()
    if classes != expected:
        raise ValueError("class-map classes differ from the frozen v1 enumeration")
    if payload.get("class_count") != CLASS_COUNT:
        raise ValueError(f"class_count must be {CLASS_COUNT}")
    actual_mapping_sha = classes_sha256(classes)
    if payload.get("mapping_sha256") != actual_mapping_sha:
        raise ValueError("class-map mapping_sha256 mismatch")
    orders = tuple(tuple(int(value) for value in item["order"]) for item in classes)
    class_map = TrifectaClassMap(orders=orders, mapping_sha256=actual_mapping_sha)
    for class_id, order in enumerate(orders):
        if class_map.encode(order) != class_id or class_map.decode(class_id) != order:
            raise ValueError(f"class-map round-trip failed at class_id={class_id}")
    return class_map


def load_class_map(path: Path) -> TrifectaClassMap:
    return validate_class_map_payload(read_json(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the frozen trifecta class map v1.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    atomic_write_json(args.out, build_class_map_payload())
    validated = load_class_map(args.out)
    print(
        f"wrote {args.out} classes={len(validated.orders)} "
        f"mapping_sha256={validated.mapping_sha256}"
    )


if __name__ == "__main__":
    main()
