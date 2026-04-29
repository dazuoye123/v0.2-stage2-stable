from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.dspy_modules.runner import run_stage3_dspy_schema_extraction


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dspy_disabled_does_not_require_import_or_api_key(tmp_path: Path) -> None:
    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = False

    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text("# test\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_stage3_dspy_schema_extraction(
        project_root=PROJECT_ROOT,
        settings=settings,
        paper_id="test-paper",
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
    )
    assert result == {"stage3_dspy": "disabled"}
