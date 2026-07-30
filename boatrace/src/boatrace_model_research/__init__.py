"""Auditable no-odds boatrace research dataset and evaluation primitives."""

from .class_map import (
    CLASS_COUNT,
    TrifectaClassMap,
    build_class_map_payload,
    load_class_map,
)

__all__ = [
    "CLASS_COUNT",
    "TrifectaClassMap",
    "build_class_map_payload",
    "load_class_map",
]
