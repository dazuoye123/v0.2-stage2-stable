from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_full_pipeline.py"
SPEC = importlib.util.spec_from_file_location("run_full_pipeline_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_run_full_pipeline_safe_mode_exports_without_models(monkeypatch, tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    markdown_dir.mkdir()
    outputs_dir.mkdir()
    (markdown_dir / "paper-a.md").write_text("content", encoding="utf-8")
    (outputs_dir / "paper-a" / "final_dataset").mkdir(parents=True)

    monkeypatch.setattr(
        MODULE,
        "run_stage6c_full_resume",
        lambda **kwargs: {
            "full_resume_summary": {"completed_after": 1, "partial_after": 0, "failed_papers": 0},
            "per_paper_summary": [{"paper_id": "paper-a", "status_before": "complete", "status_after": "complete", "completed_stages_after": ["stage2", "stage3", "stage4a", "stage5", "stage55"]}],
        },
    )
    monkeypatch.setattr(
        MODULE,
        "generate_link_aware_exports",
        lambda *args, **kwargs: {"paper_id": "paper-a", "summary": {"parameters_with_any_link": 1, "parameters_with_evidence_link": 1, "parameters_with_spectra_link": 0}},
    )
    monkeypatch.setattr(
        MODULE,
        "export_batch_link_aware_dataset",
        lambda *args, **kwargs: {"output_dir": str(tmp_path / "_batch"), "summary": {"showcase_rows": 0}},
    )

    result = MODULE.run_full_pipeline(
        pdf_dir=None,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        paper_ids=["paper-a"],
        max_papers=1,
        auto_complete=False,
        allow_stage1=False,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4=False,
        live_linking=False,
        force_stage3=False,
        force_stage4=False,
        force_stage5=False,
        force_linking=True,
        export_link_aware=True,
        dry_run=False,
        safe=True,
        max_stage3_papers=0,
        max_stage4_papers=0,
        max_stage4_figures_per_paper=0,
        max_total_model_calls=0,
        stage4_figure_types=["ftir_spectrum"],
        stage4_figure_ids=None,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        stage4_routing_mode="universal_compact",
        stage4_candidate_source="stage2-selected",
        include_showcase=False,
        output_dir=tmp_path / "batch",
    )
    assert result["paper_ids"] == ["paper-a"]
    assert result["exports"][0]["paper_id"] == "paper-a"


def test_run_full_pipeline_can_force_linking_and_skip_completed_stages(monkeypatch, tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    markdown_dir.mkdir()
    outputs_dir.mkdir()
    (markdown_dir / "paper-a.md").write_text("content", encoding="utf-8")
    (outputs_dir / "paper-a" / "final_dataset").mkdir(parents=True)

    captured: dict[str, object] = {}

    def fake_resume(**kwargs):
        captured["resume_kwargs"] = kwargs
        return {
            "full_resume_summary": {"completed_after": 1, "partial_after": 0, "failed_papers": 0},
            "per_paper_summary": [{"paper_id": "paper-a", "status_before": "complete", "status_after": "complete", "completed_stages_after": ["stage2", "stage3", "stage4a", "stage5", "stage55"]}],
        }

    monkeypatch.setattr(MODULE, "run_stage6c_full_resume", fake_resume)
    monkeypatch.setattr(MODULE, "generate_link_aware_exports", lambda *args, **kwargs: {"paper_id": "paper-a", "summary": {}})
    monkeypatch.setattr(MODULE, "export_batch_link_aware_dataset", lambda *args, **kwargs: {"output_dir": str(tmp_path / "_batch"), "summary": {}})

    MODULE.run_full_pipeline(
        pdf_dir=None,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        paper_ids=["paper-a"],
        max_papers=1,
        auto_complete=True,
        allow_stage1=False,
        allow_stage2_refresh=False,
        live_stage3=True,
        live_stage4=True,
        live_linking=False,
        force_stage3=False,
        force_stage4=False,
        force_stage5=True,
        force_linking=True,
        export_link_aware=True,
        dry_run=False,
        safe=False,
        max_stage3_papers=1,
        max_stage4_papers=1,
        max_stage4_figures_per_paper=0,
        max_total_model_calls=2,
        stage4_figure_types=["ftir_spectrum"],
        stage4_figure_ids=["fig-1"],
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        stage4_routing_mode="universal_compact",
        stage4_candidate_source="stage2-selected",
        include_showcase=True,
        output_dir=tmp_path / "batch",
    )

    assert captured["resume_kwargs"]["force_stage5"] is True
    assert captured["resume_kwargs"]["force_linking"] is True
    assert captured["resume_kwargs"]["paper_ids"] == ["paper-a"]
    assert captured["resume_kwargs"]["stage4_subdir"] == "stage4_vision_spectra_universal"
    assert captured["resume_kwargs"]["stage4_figure_ids"] == ["fig-1"]


def test_parse_args_keeps_stage4a_aliases(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_full_pipeline.py",
            "--outputs-dir",
            "tmp",
            "--live-stage4a",
            "--force-stage4a",
            "--max-stage4a-figures-per-paper",
            "7",
        ],
    )
    args = MODULE.parse_args()
    assert args.live_stage4 is True
    assert args.force_stage4 is True
    assert args.max_stage4_figures_per_paper == 7
