from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alumina_sol_extractor.manuscript_figures.main_figures import build_fig1, build_fig2, build_fig4
from alumina_sol_extractor.manuscript_figures.runner import run_manuscript_figures


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_diagnosis_dir(tmp_path: Path) -> Path:
    diagnosis_dir = tmp_path / "diagnosis"
    source_root = diagnosis_dir / "source_tables"

    fig1 = pd.DataFrame(
        [
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "paper_count", "value": 5, "entity_label": "paper_count", "source_table": "category_summary.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "sample_count", "value": 7, "entity_label": "sample_count", "source_table": "category_summary.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "parameter_count", "value": 9, "entity_label": "parameter_count", "source_table": "category_summary.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "process_step_count", "value": 4, "entity_label": "process_step_count", "source_table": "category_summary.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "spectra_count", "value": 3, "entity_label": "spectra_count", "source_table": "category_summary.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "metric": "link_count", "value": 2, "entity_label": "link_count", "source_table": "category_summary.csv"},
            {"panel_id": "B", "included_in_main_plot": True, "category": "applications", "metric": "coverage", "value": 5, "entity_label": "stage3_objects", "source_table": "stage3_paper_summary.csv"},
            {"panel_id": "C", "included_in_main_plot": True, "category": "applications", "metric": "ratio", "value": 0.8, "entity_label": "sample_links", "source_table": "normalized_stage5_links.csv"},
            {"panel_id": "D", "included_in_main_plot": True, "category": "applications", "metric": "availability", "value": 0.9, "entity_label": "spectra_available", "source_table": "normalized_sample_matrix.csv"},
        ]
    )
    fig2 = pd.DataFrame(
        [
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "entity_label": "pH", "value": 12, "source_table": "parameter_family_by_category.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "entity_label": "calcination temperature", "value": 8, "source_table": "parameter_family_by_category.csv"},
            {"panel_id": "B", "included_in_main_plot": True, "category": "applications", "entity_label": "pH", "value": 12, "source_table": "normalized_parameters.csv"},
            {"panel_id": "B", "included_in_main_plot": True, "category": "applications", "entity_label": "calcination temperature", "value": 8, "source_table": "normalized_parameters.csv"},
            {"panel_id": "C", "included_in_main_plot": True, "category": "applications", "entity_label": "pH", "value": 4.1, "source_table": "normalized_parameters.csv"},
            {"panel_id": "C", "included_in_main_plot": False, "category": "applications", "entity_label": "Al concentration", "value": 0.5, "source_table": "normalized_parameters.csv"},
            {"panel_id": "C", "included_in_main_plot": False, "category": "applications", "entity_label": "solid content", "value": 20.0, "source_table": "normalized_parameters.csv"},
            {"panel_id": "D", "included_in_main_plot": True, "category": "applications", "entity_label": "aging temperature", "value": 80, "source_table": "normalized_parameters.csv"},
            {"panel_id": "D", "included_in_main_plot": True, "category": "applications", "entity_label": "aging time", "value": 12, "source_table": "normalized_parameters.csv"},
            {"panel_id": "E", "included_in_main_plot": True, "category": "applications", "entity_label": "pH -> calcination temperature", "value": 3, "source_table": "normalized_parameters.csv"},
            {"panel_id": "E", "included_in_main_plot": True, "category": "applications", "entity_label": "calcination temperature -> pH", "value": 2, "source_table": "normalized_parameters.csv"},
        ]
    )
    fig4 = pd.DataFrame(
        [
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "entity_label": "FTIR", "value": 10, "source_table": "spectra_type_by_category.csv"},
            {"panel_id": "A", "included_in_main_plot": True, "category": "applications", "entity_label": "XRD", "value": 9, "source_table": "spectra_type_by_category.csv"},
            {"panel_id": "B", "included_in_main_plot": True, "category": "applications", "entity_label": "FTIR -> pH", "value": 4, "source_table": "spectra_parameter_matrix.csv"},
            {"panel_id": "B", "included_in_main_plot": True, "category": "applications", "entity_label": "XRD -> calcination temperature", "value": 3, "source_table": "spectra_parameter_matrix.csv"},
            {"panel_id": "C", "included_in_main_plot": True, "category": "applications", "entity_label": "FTIR peak", "value": 467, "source_table": "normalized_stage4_peaks.csv"},
            {"panel_id": "D", "included_in_main_plot": True, "category": "applications", "entity_label": "XRD peak", "value": 25.5, "source_table": "normalized_stage4_peaks.csv"},
            {"panel_id": "E", "included_in_main_plot": True, "category": "applications", "entity_label": "NMR peak", "value": 65.2, "source_table": "normalized_stage4_peaks.csv"},
            {"panel_id": "F", "included_in_main_plot": True, "category": "applications", "entity_label": "TG event", "value": 800, "source_table": "normalized_stage4_peaks.csv"},
        ]
    )

    _write_csv(source_root / "Fig1_dataset_coverage_source.csv", fig1)
    _write_csv(source_root / "Fig2_synthesis_parameter_landscape_source.csv", fig2)
    _write_csv(source_root / "Fig4_characterization_evidence_atlas_source.csv", fig4)
    _write_json(
        diagnosis_dir / "manuscript_figure_plan.json",
        [
            {
                "figure_id": "Fig1",
                "scientific_question": "How broad is the dataset coverage?",
                "expected_claim": "The dataset supports downstream analysis.",
                "panels": "A object counts by category; B coverage summary; C link completeness; D availability matrix",
            },
            {
                "figure_id": "Fig2",
                "scientific_question": "Which parameters dominate the literature?",
                "expected_claim": "A small set of families dominates reporting.",
                "panels": "A heatmap; B top families; C pH distribution; D condition windows; E co-occurrence matrix",
            },
            {
                "figure_id": "Fig4",
                "scientific_question": "Which techniques dominate the evidence structure?",
                "expected_claim": "A few characterization families dominate evidence generation.",
                "panels": "A type x category; B spectra x parameter; C FTIR; D XRD; E NMR; F TG/DSC",
            },
        ],
    )
    _write_csv(
        diagnosis_dir / "manuscript_figure_plan.csv",
        pd.DataFrame(
            [
                {"figure_id": "Fig1", "scientific_question": "How broad is the dataset coverage?", "expected_claim": "The dataset supports downstream analysis."},
                {"figure_id": "Fig2", "scientific_question": "Which parameters dominate the literature?", "expected_claim": "A small set of families dominates reporting."},
                {"figure_id": "Fig4", "scientific_question": "Which techniques dominate the evidence structure?", "expected_claim": "A few characterization families dominate evidence generation."},
            ]
        ),
    )
    _write_json(diagnosis_dir / "data_quality_summary.json", {"ok": True})
    (diagnosis_dir / "diagnosis_report.md").write_text("# diagnosis\n", encoding="utf-8")
    return diagnosis_dir


def test_run_manuscript_figures_writes_expected_batch_outputs(tmp_path: Path) -> None:
    diagnosis_dir = _build_diagnosis_dir(tmp_path)
    out_dir = tmp_path / "manuscript_figures_nature_v1"

    result = run_manuscript_figures(
        diagnosis_dir=diagnosis_dir,
        output_dir=out_dir,
        figures=["Fig1", "Fig2", "Fig4"],
    )

    assert Path(result["manifest"]).exists()
    assert Path(result["index"]).exists()
    assert Path(result["contact_sheet"]).exists()
    assert (out_dir / "main_figures" / "Fig1_dataset_coverage" / "Fig1_dataset_coverage.png").exists()
    assert (out_dir / "main_figures" / "Fig2_synthesis_parameter_landscape" / "Fig2_synthesis_parameter_landscape_source_data.csv").exists()
    assert (out_dir / "main_figures" / "Fig4_characterization_evidence_atlas" / "Fig4_characterization_evidence_atlas_figure_data.json").exists()
    assert (out_dir / "source_data" / "Fig1_dataset_coverage_source_data.csv").exists()
    assert (out_dir / "figure_data" / "Fig2_synthesis_parameter_landscape_figure_data.json").exists()
    assert (out_dir / "captions" / "Fig4_characterization_evidence_atlas_caption.md").exists()
    assert (out_dir / "qc" / "Fig1_dataset_coverage_qc.png").exists()

    manifest = json.loads((out_dir / "manuscript_figures_manifest.json").read_text(encoding="utf-8"))
    assert manifest["figure_count"] == 3
    assert manifest["data_safety"]["stage3_rerun"] is False
    assert manifest["data_safety"]["stage4_rerun"] is False
    assert manifest["data_safety"]["stage5_rerun"] is False
    assert manifest["data_safety"]["llm_or_vlm_called"] is False
    assert len(manifest["input_source_tables"]) == 3
    assert manifest["figures"][0]["figure_id"] in {"Fig1", "Fig2", "Fig4"}

    figure_json = json.loads((out_dir / "figure_data" / "Fig4_characterization_evidence_atlas_figure_data.json").read_text(encoding="utf-8"))
    assert figure_json["figure_id"] == "Fig4"
    assert figure_json["row_counts"]["C"]["included_count"] >= 1


def test_manuscript_figure_builders_render_empty_data_fallbacks(tmp_path: Path) -> None:
    empty_frame = pd.DataFrame(
        [
            {"panel_id": "A", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
            {"panel_id": "B", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
            {"panel_id": "C", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
            {"panel_id": "D", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
            {"panel_id": "E", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
            {"panel_id": "F", "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "paper_count"},
        ]
    )

    fig1_paths, fig1_meta = build_fig1(empty_frame[empty_frame["panel_id"].isin(["A", "B", "C", "D"])], tmp_path / "fig1_empty")
    fig2_paths, fig2_meta = build_fig2(empty_frame[empty_frame["panel_id"].isin(["A", "B", "C", "D", "E"])], tmp_path / "fig2_empty")
    fig4_paths, fig4_meta = build_fig4(empty_frame, tmp_path / "fig4_empty")

    for bundle in (fig1_paths, fig2_paths, fig4_paths):
        assert Path(bundle["png"]).exists()
        assert Path(bundle["svg"]).exists()
        assert Path(bundle["pdf"]).exists()

    assert fig1_meta["row_counts"]["A"]["included_count"] == 0
    assert fig2_meta["row_counts"]["C"]["excluded_count"] >= 1
    assert fig4_meta["row_counts"]["F"]["raw_count"] == 1
