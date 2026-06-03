from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_nature_skills(explicit_dir: Path | None = None) -> dict[str, Any]:
    candidates = []
    if explicit_dir:
        candidates.append(explicit_dir)
    candidates.extend(
        [
            Path.cwd() / "nature-skills",
            Path.cwd() / "skills" / "nature-skills",
            Path.home() / ".codex" / "skills" / "nature-skills",
            Path.home() / ".codex" / "skills" / "nature-figure",
            Path.cwd().parent / "nature-skills",
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            mode = "style_guide"
            helper_paths = list(candidate.glob("*.py")) + list((candidate / "helpers").glob("*.py")) if candidate.is_dir() else []
            if helper_paths:
                mode = "python_helper"
            return {
                "nature_skills_used": True,
                "nature_skills_path": str(candidate),
                "adapter_mode": mode,
                "fallback_used": False,
                "fallback_reason": "",
            }
    return {
        "nature_skills_used": False,
        "nature_skills_path": "",
        "adapter_mode": "fallback_matplotlib_profile",
        "fallback_used": True,
        "fallback_reason": "No local nature-skills directory was found.",
    }
