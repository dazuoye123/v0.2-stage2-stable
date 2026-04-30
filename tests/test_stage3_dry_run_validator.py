from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.dspy_modules.runner import run_stage3_dspy_schema_extraction


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_stage3_dry_run_validator_works_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = False
    settings.setdefault("stage3", {})
    settings["stage3"]["dry_run_validator"] = True
    settings["stage3"]["fixture_path"] = "resources/stage3_seed/extraction_lijianjun_full.schema_v2.json"

    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text("# dry run\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_stage3_dspy_schema_extraction(
        project_root=PROJECT_ROOT,
        settings=settings,
        paper_id="dry-run-paper",
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
    )
    assert result["stage3_mode"] == "dry_run_validator"
    assert "validation_report_path" in result
    report_path = Path(result["validation_report_path"])
    assert report_path.exists()
