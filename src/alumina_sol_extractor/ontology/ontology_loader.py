"""Load canonical ontology configuration from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_ontology_path(project_root: Path | None = None) -> Path:
    return Path(project_root or _default_project_root()) / "configs" / "ontology.yaml"


@lru_cache(maxsize=4)
def load_ontology_config(project_root: str | Path | None = None) -> dict[str, Any]:
    """Load ``configs/ontology.yaml`` as the source of truth for canonical keys."""
    ontology_path = _default_ontology_path(Path(project_root) if project_root is not None else None)
    if not ontology_path.exists():
        raise FileNotFoundError(
            f"Ontology config not found: {ontology_path}. "
            "Expected configs/ontology.yaml copied from resources/stage3_seed/ontology.yaml."
        )
    data = yaml.safe_load(ontology_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Ontology YAML must be a mapping: {ontology_path}")
    return data


def get_canonical_keys(project_root: str | Path | None = None) -> list[str]:
    """Return ontology canonical keys in declaration order."""
    data = load_ontology_config(project_root)
    parameters = data.get("parameters") or []
    return [item.get("canonical_key") for item in parameters if isinstance(item, dict) and item.get("canonical_key")]


def get_ontology_entry_map(project_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Return canonical key -> metadata mapping."""
    data = load_ontology_config(project_root)
    result: dict[str, dict[str, Any]] = {}
    for item in data.get("parameters") or []:
        if not isinstance(item, dict):
            continue
        canonical_key = item.get("canonical_key")
        if canonical_key:
            result[str(canonical_key)] = item
    return result
