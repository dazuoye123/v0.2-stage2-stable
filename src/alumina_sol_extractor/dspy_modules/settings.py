"""DSPy settings helpers with lazy initialization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config import build_runtime_settings


def load_dspy_settings(project_root: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Load merged DSPy settings from configs and runtime settings."""
    runtime_settings = build_runtime_settings(Path(project_root), Path(project_root) / "settings.yaml")
    merged = dict(runtime_settings.get("dspy", {}))
    merged.update(settings.get("dspy", {}))
    return merged


def configure_dspy_lm(dspy_settings: dict[str, Any]):
    """Configure a DSPy LM lazily for OpenAI-compatible endpoints."""
    try:
        import dspy  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised by tests without package
        raise RuntimeError(
            "Stage 3 DSPy is enabled, but dspy-ai is not installed. "
            "Install it with `pip install dspy-ai>=2.4.0`."
        ) from exc

    api_key_env = dspy_settings.get("api_key_env", "OPENAI_API_KEY")
    base_url_env = dspy_settings.get("base_url_env", "OPENAI_BASE_URL")
    model_name_env = dspy_settings.get("model_name_env", "MODEL_NAME")

    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Stage 3 DSPy is enabled, but environment variable {api_key_env} is missing."
        )

    base_url = os.getenv(base_url_env)
    model_name = os.getenv(model_name_env, "gpt-4o-mini")

    lm_kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
    }
    if base_url:
        lm_kwargs["api_base"] = base_url

    lm = dspy.LM(**lm_kwargs)
    dspy.settings.configure(lm=lm)
    return lm
