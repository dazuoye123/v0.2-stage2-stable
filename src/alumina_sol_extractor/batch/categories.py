from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


CANONICAL_BATCH_CATEGORIES = [
    "applications",
    "fiber_process",
    "mechanism",
    "rheology",
]
CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED = [
    *CANONICAL_BATCH_CATEGORIES,
    "uncategorized",
]
BATCH_CATEGORY_PRIORITY = [
    "fiber_process",
    "mechanism",
    "rheology",
    "applications",
    "uncategorized",
]

_CATEGORY_ALIASES = {
    "applications": "applications",
    "application": "applications",
    "apps": "applications",
    "fiberprocess": "fiber_process",
    "fibers": "fiber_process",
    "fiber": "fiber_process",
    "fibreprocess": "fiber_process",
    "fibres": "fiber_process",
    "fibre": "fiber_process",
    "mechanism": "mechanism",
    "mechanisms": "mechanism",
    "rheology": "rheology",
    "rheological": "rheology",
    "uncategorized": "uncategorized",
}


def normalize_batch_category(value: str | None) -> str:
    if not value:
        return "uncategorized"
    normalized_token = _normalize_alias_token(value)
    return _CATEGORY_ALIASES.get(normalized_token, "uncategorized")


def infer_batch_category_from_path(path: Path, root_dir: Path) -> str:
    try:
        relative_parts = path.relative_to(root_dir).parts
    except ValueError:
        return "uncategorized"
    return infer_batch_category_from_parts(relative_parts[:-1])


def infer_batch_category_from_parts(parts: Iterable[str]) -> str:
    for part in parts:
        category = normalize_batch_category(part)
        if category != "uncategorized":
            return category
    return "uncategorized"


def _normalize_alias_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())
