from __future__ import annotations

import pandas as pd

from alumina_sol_extractor.figure_atlas.table_builder import build_normalized_tables


def test_table_builder_creates_core_normalized_tables() -> None:
    payload = {
        "stage3": {
            "parameter_distribution": pd.DataFrame(),
            "sample_parameter_long": pd.DataFrame(),
            "paper_stage3_summary": pd.DataFrame(),
            "coverage_matrix_plotting_data": pd.DataFrame(),
            "paper_metadata_plotting_data": pd.DataFrame(),
        },
        "stage4": {
            "paper_summary": pd.DataFrame([{"paper_id": "p1", "candidate_count": 2, "success_count": 1, "failed_count": 1, "validated_count": 1, "validation_error_count": 0}]),
            "spectra": pd.DataFrame([{"category": "applications", "paper_id": "p1", "figure_id": "f1", "spectra_id": "s1", "raw_spectra_type": "xrd_pattern", "normalized_spectra_type": "XRD", "figure_class": "generic_chart_or_plot", "technique": "XRD", "caption": "", "source_table": "spectra_extractions.jsonl"}]),
            "failed": pd.DataFrame(),
            "quality": pd.DataFrame(),
            "peaks": pd.DataFrame([{"category": "applications", "paper_id": "p1", "figure_id": "f1", "raw_spectra_type": "xrd_pattern", "normalized_spectra_type": "XRD", "figure_class": "generic_chart_or_plot", "peak_source_field": "peaks", "peak_value": 25.5, "peak_unit": "2theta_deg", "peak_label": "", "source_table": "spectra_extractions.jsonl"}]),
        },
        "stage5": {
            "final_parameters_linked": pd.DataFrame([{"paper_id": "p1", "category": "applications", "parameter_id": "param-1", "canonical_key": "calcination_temperature_C", "zh_name": "", "en_name": "", "resolved_sample_id": "smp-1", "sample_id_original": "smp-1", "value_raw": "800", "value_num": 800.0, "value_text": "", "unit": "C", "link_types": "sample;spectra", "linked_evidence_ids": "", "linked_spectra_ids": "spectra-1", "normalization_note": ""}]),
            "evidence_parameter_links": pd.DataFrame([{"paper_id": "p1", "category": "applications", "source_type": "evidence", "source_id": "e1", "parameter_id": "param-1", "canonical_key": "calcination_temperature_C", "created_by": "manual"}]),
            "process_step_parameter_links": pd.DataFrame([{"paper_id": "p1", "category": "applications", "source_type": "process_step", "source_id": "step-1", "parameter_id": "param-1", "canonical_key": "calcination_temperature_C", "created_by": "manual"}]),
            "spectra_parameter_links": pd.DataFrame([{"paper_id": "p1", "category": "applications", "source_type": "spectra", "source_id": "spectra-1", "figure_id": "f1", "figure_type": "xrd_pattern", "parameter_id": "param-1", "canonical_key": "calcination_temperature_C", "created_by": "manual"}]),
            "process_steps_table": pd.DataFrame([{"paper_id": "p1", "category": "applications", "step_id": "step-1", "action": "calcination", "action_zh": "煅烧", "section": "", "product_or_outcome": "", "reagent_name": "", "condition_key": "", "evidence_text": ""}]),
            "sample_parameter_matrix": pd.DataFrame([{"paper_id": "p1", "category": "applications", "sample_id": "smp-1", "sample_name": "Sample 1", "parameter_count": 3, "linked_parameter_count": 2, "spectra_count": 1}]),
            "final_showcase_table": pd.DataFrame([{"paper_id": "p1", "category": "applications"}]),
        },
    }
    tables = build_normalized_tables(payload)
    assert "normalized_parameters" in tables
    assert "normalized_stage5_links" in tables
    assert not tables["normalized_parameters"].empty
    assert not tables["normalized_stage5_links"].empty
