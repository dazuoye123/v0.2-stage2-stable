"""DSPy settings helpers with lazy initialization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config import build_runtime_settings

DASHSCOPE_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def load_dspy_settings(project_root: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Load merged DSPy settings from configs and runtime settings."""
    runtime_settings = build_runtime_settings(Path(project_root), Path(project_root) / "settings.yaml")
    merged = dict(runtime_settings.get("dspy", {}))
    merged.update(settings.get("dspy", {}))
    return merged


def load_project_dotenv(project_root: Path) -> Path | None:
    """Load a project-local ``.env`` file without overriding system env vars."""
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return None
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - dependency issue is rare and explicit
        raise RuntimeError(
            "Smoke test .env support requires python-dotenv. "
            "Install it with `pip install python-dotenv>=1.0.1`."
        ) from exc
    load_dotenv(env_path, override=False)
    return env_path


def resolve_dspy_runtime_config(dspy_settings: dict[str, Any]) -> dict[str, Any]:
    """Resolve DSPy runtime configuration from environment variables."""
    api_key_env = dspy_settings.get("api_key_env", "OPENAI_API_KEY")
    base_url_env = dspy_settings.get("base_url_env", "OPENAI_BASE_URL")
    model_name_env = dspy_settings.get("model_name_env", "MODEL_NAME")

    api_key = os.getenv(api_key_env)
    api_key_source = api_key_env if api_key else None
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        api_key_source = "DASHSCOPE_API_KEY" if api_key else None
    if not api_key:
        raise RuntimeError(
            "Stage 3 DSPy smoke test requires OPENAI_API_KEY or DASHSCOPE_API_KEY. "
            "Set one of them in your system environment or project .env before running the smoke test script."
        )

    base_url = os.getenv(base_url_env)
    if not base_url and api_key_source == "DASHSCOPE_API_KEY":
        base_url = DASHSCOPE_COMPATIBLE_BASE_URL

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model_name": os.getenv(model_name_env, "qwen3.6-max-preview"),
        "api_key_env": api_key_source or api_key_env,
        "base_url_env": base_url_env,
        "model_name_env": model_name_env,
    }


def configure_dspy_lm(dspy_settings: dict[str, Any]):
    """Configure a DSPy LM lazily for OpenAI-compatible endpoints."""
    runtime_config = resolve_dspy_runtime_config(dspy_settings)
    try:
        import dspy  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised by tests without package
        raise RuntimeError(
            "Stage 3 DSPy is enabled, but dspy-ai is not installed. "
            "Install it with `pip install dspy-ai>=2.4.0`."
        ) from exc

    lm_kwargs: dict[str, Any] = {
        "model": runtime_config["model_name"],
        "api_key": runtime_config["api_key"],
    }
    if runtime_config["base_url"]:
        lm_kwargs["api_base"] = runtime_config["base_url"]

    lm = dspy.LM(**lm_kwargs)
    dspy.settings.configure(lm=lm)
    return lm
