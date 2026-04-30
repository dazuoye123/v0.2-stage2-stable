from __future__ import annotations

from pathlib import Path

import pytest

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.dspy_modules.runner import run_stage3_dspy_smoke_test


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_smoke_test_requires_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        run_stage3_dspy_smoke_test(
            project_root=PROJECT_ROOT,
            settings=settings,
            paper_id="smoke-paper",
            cleaned_markdown_path=markdown_path,
            output_dir=output_dir,
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

    with pytest.raises(RuntimeError, match="dspy-ai is not installed"):
        run_stage3_dspy_smoke_test(
            project_root=PROJECT_ROOT,
            settings=settings,
            paper_id="smoke-paper",
            cleaned_markdown_path=markdown_path,
            output_dir=output_dir,
        )
