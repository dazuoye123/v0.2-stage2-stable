"""Load settings.yaml together with config defaults from ``configs/``.

The refactor keeps ``settings.yaml`` as the user-facing entry point. Defaults
live under ``configs/`` and are merged first; values from ``settings.yaml``
override them so existing behavior stays stable.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILES = [
    "stage1_mineru.yaml",
    "stage2_figures.yaml",
    "dspy.yaml",
    "caption_rules.yaml",
    "review_rules.yaml",
    "output_schema.yaml",
]


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty mapping when missing."""
    path = Path(path)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML at {path}")
    return data


def resolve_project_path(project_root: Path, path_value: str | Path) -> Path:
    """Resolve a path from settings relative to the project root."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return Path(project_root) / path


def build_runtime_settings(project_root: Path, settings_path: Path | None = None) -> dict[str, Any]:
    """Build effective settings by merging config defaults with settings.yaml."""
    project_root = Path(project_root)
    configs_dir = project_root / "configs"
    merged: dict[str, Any] = {}
    for config_name in CONFIG_FILES:
        merged = _deep_merge(merged, load_yaml_file(configs_dir / config_name))
    settings_file = settings_path or (project_root / "settings.yaml")
    merged = _deep_merge(merged, load_yaml_file(settings_file))
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dictionaries without mutating the inputs."""
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
