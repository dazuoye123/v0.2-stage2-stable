from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_full_pipeline.py"
SPEC = importlib.util.spec_from_file_location("run_full_pipeline_script_stage5_only", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_run_full_pipeline_stage5_only_without_markdown_dir(monkeypatch, tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    (outputs_dir / "paper-a" / "final_dataset").mkdir(parents=True)

    captured: dict[str, object] = {}

    def fake_stage5_only(**kwargs):
        captured["stage5_only_kwargs"] = kwargs
        return (
            {
                "full_resume_summary": {"completed_after": 1, "partial_after": 0, "failed_papers": 0},
                "per_paper_summary": [
                    {
                        "paper_id": "paper-a",
                        "status_before": "existing_final_dataset",
                        "status_after": "complete",
                        "completed_stages_after": ["stage5", "stage55"],
                    }
                ],
            },
            [{"paper_id": "paper-a", "summary": {"parameters_with_any_link": 2}}],
            {"output_dir": str(tmp_path / "_batch"), "summary": {"showcase_rows": 0}},
        )

    monkeypatch.setattr(MODULE, "_run_stage5_and_stage55_dry_run", fake_stage5_only)

    result = MODULE.run_full_pipeline(
        pdf_dir=None,
        markdown_dir=None,
        outputs_dir=outputs_dir,
        paper_ids=["paper-a"],
        max_papers=1,
        auto_complete=False,
        allow_stage1=False,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=True,
        force_linking=True,
        export_link_aware=True,
        dry_run=False,
        safe=True,
        max_stage3_papers=0,
        max_stage4a_papers=0,
        max_stage4a_figures_per_paper=4,
        max_total_model_calls=0,
        stage4a_figure_types=["ftir_spectrum"],
        include_showcase=False,
        output_dir=tmp_path / "batch",
    )

    assert result["paper_ids"] == ["paper-a"]
    assert captured["stage5_only_kwargs"]["paper_ids"] == ["paper-a"]
    assert captured["stage5_only_kwargs"]["include_showcase"] is False
