from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.dspy_modules.runner import run_stage3_dspy_smoke_test
from alumina_sol_extractor.dspy_modules.settings import (
    DASHSCOPE_COMPATIBLE_BASE_URL,
    load_project_dotenv,
    normalize_openai_compatible_model_name,
    resolve_dspy_runtime_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_smoke_test_requires_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)

    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = True
    settings.setdefault("stage3", {})
    settings["stage3"]["dry_run_validator"] = False

    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text("# smoke test\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY or DASHSCOPE_API_KEY"):
        run_stage3_dspy_smoke_test(
            project_root=PROJECT_ROOT,
            settings=settings,
            paper_id="smoke-paper",
            cleaned_markdown_path=markdown_path,
            output_dir=output_dir,
            paper_text_limit_chars=1000,
            max_experiment_series=1,
        )


def test_smoke_test_reports_missing_dspy_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("MODEL_NAME", "dummy-model")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = True
    settings.setdefault("stage3", {})
    settings["stage3"]["dry_run_validator"] = False

    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text("# smoke test\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "dspy":
            raise ImportError("mock missing dspy")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        with pytest.raises(RuntimeError, match="dspy-ai is not installed"):
            run_stage3_dspy_smoke_test(
                project_root=PROJECT_ROOT,
                settings=settings,
                paper_id="smoke-paper",
                cleaned_markdown_path=markdown_path,
                output_dir=output_dir,
                paper_text_limit_chars=1000,
                max_experiment_series=1,
            )


def test_resolve_runtime_config_prefers_openai_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_NAME", "custom-model")

    config = resolve_dspy_runtime_config({})
    assert config["api_key"] == "openai-key"
    assert config["api_key_env"] == "OPENAI_API_KEY"
    assert config["base_url"] == "https://example.com/v1"
    assert config["model_name"] == "openai/custom-model"


def test_resolve_runtime_config_falls_back_to_dashscope(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)

    config = resolve_dspy_runtime_config({})
    assert config["api_key"] == "dashscope-key"
    assert config["api_key_env"] == "DASHSCOPE_API_KEY"
    assert config["base_url"] == DASHSCOPE_COMPATIBLE_BASE_URL
    assert config["model_name"] == "openai/qwen3.6-max-preview"


def test_load_project_dotenv_uses_project_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=from-dotenv\nMODEL_NAME=dotenv-model\n", encoding="utf-8")

    loaded_path = load_project_dotenv(tmp_path)
    assert loaded_path == env_path
    config = resolve_dspy_runtime_config({})
    assert config["api_key"] == "from-dotenv"
    assert config["model_name"] == "dotenv-model"


def test_load_project_dotenv_missing_file_is_safe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert load_project_dotenv(tmp_path) is None


def test_missing_key_error_does_not_echo_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    with pytest.raises(RuntimeError) as exc_info:
        resolve_dspy_runtime_config({})
    assert "OPENAI_API_KEY or DASHSCOPE_API_KEY" in str(exc_info.value)
    assert "dashscope.aliyuncs.com" not in str(exc_info.value)


def test_normalize_openai_compatible_model_name() -> None:
    assert normalize_openai_compatible_model_name("qwen3.6-max-preview", base_url="https://example.com/v1") == "openai/qwen3.6-max-preview"
    assert normalize_openai_compatible_model_name("openai/qwen3.6-max-preview", base_url="https://example.com/v1") == "openai/qwen3.6-max-preview"
    assert normalize_openai_compatible_model_name("qwen3.6-max-preview", base_url=None) == "qwen3.6-max-preview"
