"""Canonical key normalization based on ontology aliases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .ontology_loader import get_ontology_entry_map


def _iter_aliases(canonical_key: str, entry: dict[str, Any]) -> Iterable[str]:
    """Yield ontology aliases while staying compatible with legacy field names."""
    yield canonical_key
    for field_name in ("aliases_en", "aliases_zh", "en_aliases", "zh_aliases"):
        for alias in entry.get(field_name) or []:
            if alias:
                yield str(alias)
    for field_name in ("zh_name", "en_name"):
        alias = entry.get(field_name)
        if alias:
            yield str(alias)


def normalize_key(raw_name: str, project_root: str | Path | None = None) -> str | None:
    """Normalize a raw parameter name to a canonical ontology key.

    Matching is intentionally conservative for now:
    - exact canonical key match
    - exact alias match
    - lowercase alias match
    """

    if not raw_name:
        return None
    candidate = raw_name.strip()
    if not candidate:
        return None

    normalized_candidate = candidate.casefold()
    for canonical_key, entry in get_ontology_entry_map(project_root).items():
        if candidate == canonical_key or normalized_candidate == canonical_key.casefold():
            return canonical_key
        for alias in _iter_aliases(canonical_key, entry):
            alias_text = str(alias).strip()
            if not alias_text:
                continue
            if candidate == alias_text or normalized_candidate == alias_text.casefold():
                return canonical_key
    return None
