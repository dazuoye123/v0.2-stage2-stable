"""Canonical key normalization based on ontology aliases."""

from __future__ import annotations

from pathlib import Path

from .ontology_loader import get_ontology_entry_map


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
        aliases = [canonical_key]
        aliases.extend(entry.get("en_aliases") or [])
        aliases.extend(entry.get("zh_aliases") or [])
        aliases.extend([entry.get("zh_name")])
        for alias in aliases:
            if not alias:
                continue
            alias_text = str(alias).strip()
            if candidate == alias_text or normalized_candidate == alias_text.casefold():
                return canonical_key
    return None
