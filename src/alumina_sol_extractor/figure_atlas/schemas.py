from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class FigureArtifact:
    figure_id: str
    title: str
    tier: str
    recommendation: str
    feasibility: str
    svg: str | None
    png: str | None
    source_csv: str
    source_json: str
    input_tables: list[str]
    warnings: list[str] = field(default_factory=list)
    empty_data_note: str | None = None


@dataclass
class FigureSpec:
    figure_id: str
    title: str
    tier: str
    required_tables: list[str]
    optional_tables: list[str]
    recommendation: str = "supplementary"


def planned_figure_specs() -> list[FigureSpec]:
    specs: list[FigureSpec] = []
    specs.extend(
        FigureSpec(f"main_fig{i}_{suffix}", title, "main", ["normalized_parameters", "normalized_stage4_spectra", "normalized_stage5_links"], [])
        for i, suffix, title in [
            (1, "dataset_overview", "Dataset overview"),
            (2, "parameter_landscape", "Parameter landscape"),
            (3, "spectroscopic_fingerprint_atlas", "Spectroscopic fingerprint atlas"),
            (4, "synthesis_process_atlas", "Synthesis process atlas"),
            (5, "linked_evidence_map", "Linked evidence map"),
            (6, "category_research_patterns", "Category research patterns"),
            (7, "stage4_characterization_coverage", "Stage4 characterization coverage"),
            (8, "process_spectra_parameter_relationship", "Process-spectra-parameter relationship"),
            (9, "knowledge_graph_overview", "Knowledge graph overview"),
            (10, "research_atlas_summary", "Research atlas summary"),
        ]
    )
    specs.extend(FigureSpec(f"stage3_fig{i}_{suffix}", title, "stage3", ["normalized_parameters"], ["normalized_process_steps"]) for i, suffix, title in [
        (1, "object_counts_by_category", "Stage3 object counts by category"),
        (2, "parameter_family_coverage", "Stage3 parameter family coverage"),
        (3, "parameter_family_by_category", "Stage3 parameter family by category"),
        (4, "ph_distribution", "Stage3 pH distribution"),
        (5, "temperature_distributions", "Stage3 temperature distributions"),
        (6, "time_distributions", "Stage3 time distributions"),
        (7, "size_distributions", "Stage3 size distributions"),
        (8, "concentration_solid_content", "Stage3 concentration and solid content"),
        (9, "bet_mass_loss_mechanical", "Stage3 BET / mass loss / mechanical"),
        (10, "parameter_cooccurrence_matrix", "Stage3 parameter cooccurrence matrix"),
        (11, "parameter_cooccurrence_network", "Stage3 parameter cooccurrence network"),
        (12, "sample_parameter_matrix_top", "Stage3 sample parameter matrix top"),
        (13, "paper_parameter_coverage", "Stage3 paper parameter coverage"),
        (14, "process_step_frequency", "Stage3 process step frequency"),
        (15, "process_step_by_category", "Stage3 process step by category"),
        (16, "process_route_simple", "Stage3 process route simple"),
        (17, "numeric_value_availability_by_family", "Stage3 numeric value availability by family"),
        (18, "parameter_missingness_by_category", "Stage3 parameter missingness by category"),
        (19, "top_parameter_examples", "Stage3 top parameter examples"),
        (20, "category_parameter_density", "Stage3 category parameter density"),
    ])
    specs.extend(FigureSpec(f"stage4_fig{i}_{suffix}", title, "stage4", ["normalized_stage4_spectra"], ["normalized_stage4_peaks"]) for i, suffix, title in [
        (1, "extraction_overview", "Stage4 extraction overview"),
        (2, "per_paper_success_rate", "Stage4 per-paper success rate"),
        (3, "candidate_count_distribution", "Stage4 candidate count distribution"),
        (4, "success_failure_distribution", "Stage4 success/failure distribution"),
        (5, "full_figure_class_distribution", "Stage4 full figure class distribution"),
        (6, "characterization_family_distribution", "Stage4 characterization family distribution"),
        (7, "spectra_type_by_category", "Stage4 spectra type by category"),
        (8, "ftir_peak_distribution", "Stage4 FTIR peak distribution"),
        (9, "xrd_peak_distribution", "Stage4 XRD peak distribution"),
        (10, "nmr_shift_distribution", "Stage4 NMR shift distribution"),
        (11, "raman_peak_distribution", "Stage4 Raman peak distribution"),
        (12, "thermal_event_distribution", "Stage4 thermal event distribution"),
        (13, "microscopy_distribution", "Stage4 microscopy distribution"),
        (14, "ferron_distribution", "Stage4 ferron distribution"),
        (15, "unknown_other_breakdown", "Stage4 unknown/other breakdown"),
        (16, "failure_reason_distribution", "Stage4 failure reason distribution"),
        (17, "validation_error_summary", "Stage4 validation error summary"),
        (18, "peak_value_availability", "Stage4 peak value availability"),
        (19, "spectra_extraction_density_by_paper", "Stage4 spectra extraction density by paper"),
        (20, "characterization_coverage_by_category", "Stage4 characterization coverage by category"),
    ])
    specs.extend(FigureSpec(f"stage5_fig{i}_{suffix}", title, "stage5", ["normalized_stage5_links"], ["normalized_sample_matrix"]) for i, suffix, title in [
        (1, "link_family_counts", "Stage5 link family counts"),
        (2, "link_family_by_category", "Stage5 link family by category"),
        (3, "evidence_links_by_parameter_family", "Stage5 evidence links by parameter family"),
        (4, "process_links_by_parameter_family", "Stage5 process links by parameter family"),
        (5, "spectra_links_by_parameter_family", "Stage5 spectra links by parameter family"),
        (6, "spectra_type_parameter_matrix", "Stage5 spectra type-parameter matrix"),
        (7, "process_step_parameter_matrix", "Stage5 process step-parameter matrix"),
        (8, "sample_matrix_coverage", "Stage5 sample matrix coverage"),
        (9, "unlinked_parameter_distribution", "Stage5 unlinked parameter distribution"),
        (10, "representative_paper_graph", "Stage5 representative paper graph"),
        (11, "category_link_density", "Stage5 category link density"),
        (12, "showcase_table_summary", "Stage5 showcase table summary"),
        (13, "parameters_with_any_link_by_category", "Stage5 parameters with any link by category"),
        (14, "link_completeness_heatmap", "Stage5 link completeness heatmap"),
        (15, "top_linked_parameter_families", "Stage5 top linked parameter families"),
    ])
    specs.extend(FigureSpec(f"cross_fig{i}_{suffix}", title, "cross_stage", ["normalized_parameters", "normalized_stage4_spectra", "normalized_stage5_links"], []) for i, suffix, title in [
        (1, "stage3_stage4_coverage", "Cross-stage Stage3/Stage4 coverage"),
        (2, "stage4_success_vs_parameter_count", "Cross-stage Stage4 success vs parameter count"),
        (3, "spectra_links_vs_stage4_success", "Cross-stage spectra links vs Stage4 success"),
        (4, "category_integrated_coverage", "Cross-stage category integrated coverage"),
        (5, "parameter_spectra_process_triangle", "Cross-stage parameter-spectra-process triangle"),
        (6, "research_pattern_cluster_preview", "Cross-stage research pattern cluster preview"),
        (7, "parameter_family_vs_characterization_family", "Cross-stage parameter vs characterization family"),
        (8, "process_step_vs_spectra_type", "Cross-stage process step vs spectra type"),
        (9, "stage3_parameter_vs_stage5_link_completeness", "Cross-stage Stage3 parameter vs Stage5 link completeness"),
        (10, "stage4_characterization_vs_stage5_spectra_links", "Cross-stage characterization vs spectra links"),
        (11, "paper_level_data_density_map", "Cross-stage paper-level data density map"),
        (12, "category_end_to_end_pipeline_map", "Cross-stage category end-to-end pipeline map"),
    ])
    specs.extend(FigureSpec(f"qa_fig{i}_{suffix}", title, "qa", ["normalized_parameters", "normalized_stage4_spectra", "normalized_stage5_links"], []) for i, suffix, title in [
        (1, "stage3_raw_object_counts", "QA Stage3 raw object counts"),
        (2, "stage3_parameter_raw_coverage", "QA Stage3 parameter raw coverage"),
        (3, "stage3_numeric_extraction_qa", "QA Stage3 numeric extraction"),
        (4, "stage3_missing_parameter_family", "QA Stage3 missing parameter family"),
        (5, "stage3_process_step_raw_distribution", "QA Stage3 process step raw distribution"),
        (6, "stage3_category_balance", "QA Stage3 category balance"),
        (7, "stage4_candidate_count_distribution", "QA Stage4 candidate count distribution"),
        (8, "stage4_success_failure_distribution", "QA Stage4 success/failure distribution"),
        (9, "stage4_full_figure_class_distribution", "QA Stage4 full figure class distribution"),
        (10, "stage4_unknown_other_qa", "QA Stage4 unknown/other"),
        (11, "stage4_validation_error_summary", "QA Stage4 validation error summary"),
        (12, "stage4_failed_record_summary", "QA Stage4 failed record summary"),
        (13, "stage4_per_paper_success_rate_full", "QA Stage4 per-paper success rate full"),
        (14, "stage5_success_partial_summary", "QA Stage5 success/partial summary"),
        (15, "stage5_warning_distribution", "QA Stage5 warning distribution"),
        (16, "evidence_link_coverage_qa", "QA evidence link coverage"),
        (17, "spectra_link_coverage_qa", "QA spectra link coverage"),
        (18, "process_step_link_coverage_qa", "QA process step link coverage"),
        (19, "sample_matrix_missingness", "QA sample matrix missingness"),
        (20, "category_object_density", "QA category object density"),
        (21, "unlinked_parameters_qa", "QA unlinked parameters"),
        (22, "unknown_spectra_type_examples", "QA unknown spectra examples"),
        (23, "other_parameter_family_examples", "QA other parameter family examples"),
        (24, "source_table_row_counts", "QA source table row counts"),
        (25, "data_availability_dashboard", "QA data availability dashboard"),
    ])
    return specs
