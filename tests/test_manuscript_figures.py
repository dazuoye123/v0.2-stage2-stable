from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alumina_sol_extractor.manuscript_figures.data_logic import prepare_v2_payload
from alumina_sol_extractor.manuscript_figures.main_figures import build_fig1, build_fig2, build_fig4
from alumina_sol_extractor.manuscript_figures.runner import run_manuscript_figures


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_workspace(tmp_path: Path) -> tuple[Path, Path]:
    batch_root = tmp_path / "data" / "batch_validation" / "20260602_212510"
    diagnosis_dir = batch_root / "manuscript_figure_diagnosis"
    source_root = diagnosis_dir / "source_tables"
    atlas_root = batch_root / "figure_atlas" / "tables"
    v1_root = batch_root / "manuscript_figures_nature_v1" / "source_data"

    minimal_diag = pd.DataFrame([{"figure_id": "Fig1", "panel_id": "A", "source_table": "dummy.csv"}])
    for name in [
        "Fig1_dataset_coverage_source.csv",
        "Fig2_synthesis_parameter_landscape_source.csv",
        "Fig4_characterization_evidence_atlas_source.csv",
    ]:
        _write_csv(source_root / name, minimal_diag)

    stage3 = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "stage3_status": "success", "sample_count": 2, "process_steps_count": 3, "evidence_object_count": 2, "data_point_count": 4, "canonical_key_errors_count": 0, "rejected_parameter_records_count": 0, "process_steps_warning_count": 0, "process_steps_other_action_ratio": 0.0, "process_steps_missing_evidence_ratio": 0.0, "cleaned_body_chars": 1000, "input_truncated": False, "truncation_reason": "", "quality_flag": "ok"},
            {"category": "mechanism", "paper_id": "p2", "stage3_status": "success", "sample_count": 1, "process_steps_count": 2, "evidence_object_count": 1, "data_point_count": 3, "canonical_key_errors_count": 0, "rejected_parameter_records_count": 0, "process_steps_warning_count": 0, "process_steps_other_action_ratio": 0.0, "process_steps_missing_evidence_ratio": 0.0, "cleaned_body_chars": 900, "input_truncated": False, "truncation_reason": "", "quality_flag": "ok"},
        ]
    )
    stage4 = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "raw_candidate_count": 3, "candidate_count": 3, "success_count": 2, "failed_count": 1, "validation_error_count": 0, "validated_count": 2, "coverage_rate": 0.67, "figure_class_distribution": "{}"},
            {"category": "mechanism", "paper_id": "p2", "raw_candidate_count": 2, "candidate_count": 2, "success_count": 1, "failed_count": 1, "validation_error_count": 0, "validated_count": 1, "coverage_rate": 0.5, "figure_class_distribution": "{}"},
        ]
    )
    params = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "sample_id": "s1", "parameter_id": "pa1", "parameter_name": "pH", "parameter_key": "pH", "raw_value": "4.2", "numeric_value": 4.2, "raw_unit": "", "normalized_unit": "unitless", "parameter_family": "pH", "source_table": "normalized_parameters.csv", "has_sample_link": True, "has_evidence_link": True, "has_process_step_link": False, "has_spectra_link": True, "normalization_warning": ""},
            {"category": "uncategorized", "paper_id": "p2", "sample_id": "s2", "parameter_id": "pm1", "parameter_name": "calcination temperature", "parameter_key": "calcination_temperature_C", "raw_value": "900", "numeric_value": 900.0, "raw_unit": "°C", "normalized_unit": "°C", "parameter_family": "calcination temperature", "source_table": "normalized_parameters.csv", "has_sample_link": True, "has_evidence_link": True, "has_process_step_link": True, "has_spectra_link": False, "normalization_warning": ""},
            {"category": "applications", "paper_id": "p1", "sample_id": "s1", "parameter_id": "pa2", "parameter_name": "XRD peak", "parameter_key": "xrd_peak_position_2theta_deg", "raw_value": "25.5", "numeric_value": 25.5, "raw_unit": "2theta_deg", "normalized_unit": "2theta_deg", "parameter_family": "XRD peak", "source_table": "normalized_parameters.csv", "has_sample_link": False, "has_evidence_link": False, "has_process_step_link": False, "has_spectra_link": True, "normalization_warning": ""},
            {"category": "mechanism", "paper_id": "p2", "sample_id": "s2", "parameter_id": "pm2", "parameter_name": "aging time", "parameter_key": "aging_time_h", "raw_value": "12", "numeric_value": 12.0, "raw_unit": "h", "normalized_unit": "h", "parameter_family": "aging time", "source_table": "normalized_parameters.csv", "has_sample_link": True, "has_evidence_link": False, "has_process_step_link": False, "has_spectra_link": False, "normalization_warning": ""},
            {"category": "mechanism", "paper_id": "p2", "sample_id": "s2", "parameter_id": "pm3", "parameter_name": "aluminum source", "parameter_key": "aluminum_source", "raw_value": "boehmite", "numeric_value": "", "raw_unit": "", "normalized_unit": "", "parameter_family": "other", "source_table": "normalized_parameters.csv", "has_sample_link": False, "has_evidence_link": False, "has_process_step_link": False, "has_spectra_link": False, "normalization_warning": ""},
            {"category": "mechanism", "paper_id": "p2", "sample_id": "s2", "parameter_id": "pm4", "parameter_name": "holding time", "parameter_key": "holding_time_min", "raw_value": "30", "numeric_value": 30.0, "raw_unit": "min", "normalized_unit": "min", "parameter_family": "holding time", "source_table": "normalized_parameters.csv", "has_sample_link": False, "has_evidence_link": False, "has_process_step_link": True, "has_spectra_link": False, "normalization_warning": ""},
        ]
    )
    process_steps = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "process_step_id": "st1", "process_step_name": "drying", "process_step_family": "drying", "raw_text": "drying", "source_table": "normalized_process_steps.csv"},
            {"category": "mechanism", "paper_id": "p2", "process_step_id": "st2", "process_step_name": "calcination", "process_step_family": "calcination", "raw_text": "calcination", "source_table": "normalized_process_steps.csv"},
        ]
    )
    spectra = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "figure_id": "f1", "spectra_id": "sp1", "raw_spectra_type": "FTIR", "normalized_spectra_type": "FTIR", "figure_class": "generic_chart_or_plot", "technique": "FTIR", "caption": "", "source_table": "normalized_stage4_spectra.csv"},
            {"category": "mechanism", "paper_id": "p2", "figure_id": "f2", "spectra_id": "sp2", "raw_spectra_type": "XRD", "normalized_spectra_type": "XRD", "figure_class": "generic_chart_or_plot", "technique": "XRD", "caption": "", "source_table": "normalized_stage4_spectra.csv"},
            {"category": "mechanism", "paper_id": "p2", "figure_id": "f3", "spectra_id": "sp3", "raw_spectra_type": "Unknown", "normalized_spectra_type": "Unknown", "figure_class": "generic_chart_or_plot", "technique": "Unknown", "caption": "", "source_table": "normalized_stage4_spectra.csv"},
        ]
    )
    peaks = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "figure_id": "f1", "normalized_spectra_type": "FTIR", "peak_source_field": "peaks", "peak_value": 467.0, "peak_unit": "cm^-1", "peak_label": "", "source_table": "normalized_stage4_peaks.csv"},
            {"category": "mechanism", "paper_id": "p2", "figure_id": "f2", "normalized_spectra_type": "XRD", "peak_source_field": "peaks", "peak_value": 25.5, "peak_unit": "2θ degree", "peak_label": "", "source_table": "normalized_stage4_peaks.csv"},
            {"category": "mechanism", "paper_id": "p2", "figure_id": "f2", "normalized_spectra_type": "NMR", "peak_source_field": "peaks", "peak_value": 63.0, "peak_unit": "ppm", "peak_label": "", "source_table": "normalized_stage4_peaks.csv"},
            {"category": "mechanism", "paper_id": "p2", "figure_id": "f2", "normalized_spectra_type": "TG/DSC", "peak_source_field": "events", "peak_value": 800.0, "peak_unit": "°C", "peak_label": "", "source_table": "normalized_stage4_peaks.csv"},
        ]
    )
    links = pd.DataFrame(
        [
            {"category": "applications", "paper_id": "p1", "link_family": "sample", "source_id": "s1", "target_id": "pa1", "parameter_id": "pa1", "raw_source_type": "sample", "raw_target_type": "parameter", "normalized_spectra_type": "", "normalized_parameter_family": "pH", "normalized_process_step_family": "", "link_count_or_weight": 1, "source_table": "normalized_stage5_links.csv", "match_method": "sample_link"},
            {"category": "applications", "paper_id": "p1", "link_family": "evidence", "source_id": "e1", "target_id": "pa1", "parameter_id": "pa1", "raw_source_type": "evidence_object", "raw_target_type": "parameter", "normalized_spectra_type": "", "normalized_parameter_family": "pH", "normalized_process_step_family": "", "link_count_or_weight": 1, "source_table": "normalized_stage5_links.csv", "match_method": "direct_evidence_refs"},
            {"category": "mechanism", "paper_id": "p2", "link_family": "process_step", "source_id": "st2", "target_id": "pm1", "parameter_id": "pm1", "raw_source_type": "process_step", "raw_target_type": "parameter", "normalized_spectra_type": "", "normalized_parameter_family": "calcination temperature", "normalized_process_step_family": "calcination", "link_count_or_weight": 1, "source_table": "normalized_stage5_links.csv", "match_method": "deterministic_process_step_value_match"},
            {"category": "mechanism", "paper_id": "p2", "link_family": "spectra", "source_id": "sp2", "target_id": "pm1", "parameter_id": "pm1", "raw_source_type": "", "raw_target_type": "xrd_pattern", "normalized_spectra_type": "XRD", "normalized_parameter_family": "calcination temperature", "normalized_process_step_family": "", "link_count_or_weight": 1, "source_table": "normalized_stage5_links.csv", "match_method": "deterministic_spectra_peak_value_match"},
        ]
    )

    _write_csv(atlas_root / "stage3_paper_summary.csv", stage3)
    _write_csv(atlas_root / "stage4_paper_summary.csv", stage4)
    _write_csv(atlas_root / "normalized_parameters.csv", params)
    _write_csv(atlas_root / "normalized_process_steps.csv", process_steps)
    _write_csv(atlas_root / "normalized_stage4_spectra.csv", spectra)
    _write_csv(atlas_root / "normalized_stage4_peaks.csv", peaks)
    _write_csv(atlas_root / "normalized_stage5_links.csv", links)

    v1_fig1 = pd.DataFrame(
        [
            {"source_table": "category_summary.csv", "panel_id": "A", "metric": "paper_count", "entity_type": "category", "paper_id": "", "category": "uncategorized", "value": 10},
            {"source_table": "normalized_parameters.csv", "panel_id": "C", "metric": "linked_parameter_ratio", "entity_type": "link_family", "paper_id": "", "category": "uncategorized", "value": 1.0},
        ]
    )
    _write_csv(v1_root / "Fig1_dataset_coverage_source_data.csv", v1_fig1)

    _write_json(
        diagnosis_dir / "manuscript_figure_plan.json",
        [
            {"figure_id": "Fig1", "scientific_question": "How broad is the dataset coverage?", "expected_claim": "The dataset supports downstream analysis.", "panels": "A;B;C;D"},
            {"figure_id": "Fig2", "scientific_question": "Which parameters dominate the literature?", "expected_claim": "A structured synthesis landscape emerges.", "panels": "A;B;C;D;E;F"},
            {"figure_id": "Fig4", "scientific_question": "Which techniques dominate the evidence structure?", "expected_claim": "Complementary evidence fingerprints emerge.", "panels": "A;B;C;D"},
        ],
    )
    _write_csv(
        diagnosis_dir / "manuscript_figure_plan.csv",
        pd.DataFrame(
            [
                {"figure_id": "Fig1", "scientific_question": "How broad is the dataset coverage?", "expected_claim": "The dataset supports downstream analysis."},
                {"figure_id": "Fig2", "scientific_question": "Which parameters dominate the literature?", "expected_claim": "A structured synthesis landscape emerges."},
                {"figure_id": "Fig4", "scientific_question": "Which techniques dominate the evidence structure?", "expected_claim": "Complementary evidence fingerprints emerge."},
            ]
        ),
    )
    _write_json(diagnosis_dir / "data_quality_summary.json", {"ok": True})
    (diagnosis_dir / "diagnosis_report.md").write_text("# diagnosis\n", encoding="utf-8")
    return diagnosis_dir, batch_root


def test_prepare_v2_payload_filters_uncategorized_and_characterization_rows(tmp_path: Path) -> None:
    diagnosis_dir, _ = _build_workspace(tmp_path)
    payload = prepare_v2_payload(diagnosis_dir)

    fig1 = payload["figures"]["Fig1"]
    fig2 = payload["figures"]["Fig2"]
    fig4 = payload["figures"]["Fig4"]

    assert not fig1[(fig1["panel_id"] == "A") & (fig1["included_in_main_plot"]) & (fig1["category"] == "uncategorized")].any().any()
    assert fig1[(fig1["panel_id"] == "C") & (fig1["included_in_main_plot"])].value.between(0, 1).all()
    assert "XRD peak" not in fig2[(fig2["panel_id"] == "B") & (fig2["included_in_main_plot"])]["entity_label"].astype(str).tolist()
    assert set(fig2[(fig2["panel_id"] == "D") & (fig2["included_in_main_plot"])]["unit"].dropna().unique().tolist()) <= {"deg C"}
    assert set(fig2[(fig2["panel_id"] == "E") & (fig2["included_in_main_plot"])]["unit"].dropna().unique().tolist()) <= {"h"}
    assert set(fig4[(fig4["panel_id"] == "D") & (fig4["included_in_main_plot"])]["bin_family"].dropna().unique().tolist()) <= {"FTIR", "XRD", "NMR", "TG/DSC"}


def test_run_manuscript_figures_writes_v2_outputs_and_qc_tables(tmp_path: Path) -> None:
    diagnosis_dir, batch_root = _build_workspace(tmp_path)
    out_dir = batch_root / "manuscript_figures_nature_v2"

    result = run_manuscript_figures(
        diagnosis_dir=diagnosis_dir,
        output_dir=out_dir,
        figures=["Fig1", "Fig2", "Fig4"],
    )

    assert Path(result["manifest"]).exists()
    assert Path(result["index"]).exists()
    assert Path(result["contact_sheet"]).exists()
    assert Path(result["qc_summary"]).exists()
    assert (out_dir / "qc" / "uncategorized_source_audit.csv").exists()
    assert (out_dir / "qc" / "Fig2_unit_filter_audit.csv").exists()
    assert (out_dir / "qc" / "Fig4_peak_bin_audit.csv").exists()
    assert (out_dir / "main_figures" / "Fig1_dataset_coverage" / "Fig1_dataset_coverage.png").exists()
    assert (out_dir / "main_figures" / "Fig2_synthesis_parameter_landscape" / "Fig2_synthesis_parameter_landscape_source_data.csv").exists()
    assert (out_dir / "main_figures" / "Fig4_characterization_evidence_atlas" / "Fig4_characterization_evidence_atlas_figure_data.json").exists()

    manifest = json.loads((out_dir / "manuscript_figures_manifest.json").read_text(encoding="utf-8"))
    assert manifest["figure_count"] == 3
    assert manifest["data_safety"]["stage3_rerun"] is False
    assert manifest["data_safety"]["stage4_rerun"] is False
    assert manifest["data_safety"]["stage5_rerun"] is False
    assert manifest["data_safety"]["llm_or_vlm_called"] is False
    assert len(manifest["qc_audits"]) == 3

    figure_json = json.loads((out_dir / "figure_data" / "Fig4_characterization_evidence_atlas_figure_data.json").read_text(encoding="utf-8"))
    assert figure_json["figure_id"] == "Fig4"
    assert "statement_that_bins_are_approximate" in figure_json
    assert figure_json["row_counts"]["D"]["included_count"] >= 1


def test_manuscript_figure_builders_render_empty_data_fallbacks(tmp_path: Path) -> None:
    empty_fig1 = pd.DataFrame([{"panel_id": panel, "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "count"} for panel in ["A", "B", "C", "D"]])
    empty_fig2 = pd.DataFrame([{"panel_id": panel, "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "count"} for panel in ["A", "B", "C", "D", "E", "F"]])
    empty_fig4 = pd.DataFrame([{"panel_id": panel, "included_in_main_plot": False, "entity_label": "placeholder", "value": 0, "category": "applications", "metric": "count"} for panel in ["A", "B", "C", "D"]])

    fig1_paths, fig1_meta = build_fig1(empty_fig1, tmp_path / "fig1_empty")
    fig2_paths, fig2_meta = build_fig2(empty_fig2, tmp_path / "fig2_empty")
    fig4_paths, fig4_meta = build_fig4(empty_fig4, tmp_path / "fig4_empty")

    for bundle in (fig1_paths, fig2_paths, fig4_paths):
        assert Path(bundle["png"]).exists()
        assert Path(bundle["svg"]).exists()
        assert Path(bundle["pdf"]).exists()

    assert fig1_meta["row_counts"]["A"]["included_count"] == 0
    assert fig2_meta["row_counts"]["F"]["excluded_count"] == 1
    assert fig4_meta["row_counts"]["D"]["raw_count"] == 1
