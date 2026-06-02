from __future__ import annotations

from typing import Any

import pandas as pd

from .tables import (
    build_category_summary,
    build_normalized_links,
    build_normalized_parameters,
    build_normalized_process_steps,
    build_normalized_sample_matrix,
    build_normalized_stage4_peaks,
    build_normalized_stage4_spectra,
    link_matrix,
)


def build_normalized_tables(payload: dict[str, Any]) -> dict[str, pd.DataFrame]:
    stage3 = payload["stage3"]
    stage4 = payload["stage4"]
    stage5 = payload["stage5"]

    normalized_parameters = build_normalized_parameters(stage5["final_parameters_linked"])
    normalized_process_steps = build_normalized_process_steps(stage5["process_steps_table"])
    normalized_stage4_spectra = build_normalized_stage4_spectra(stage4["spectra"])
    normalized_stage4_peaks = build_normalized_stage4_peaks(stage4["peaks"])
    normalized_stage5_links = build_normalized_links(
        stage5["evidence_parameter_links"],
        stage5["process_step_parameter_links"],
        stage5["spectra_parameter_links"],
        normalized_parameters,
        normalized_process_steps,
        normalized_stage4_spectra,
        stage5["sample_parameter_matrix"],
    )
    normalized_sample_matrix = build_normalized_sample_matrix(stage5["sample_parameter_matrix"])

    parameter_family_by_category = (
        normalized_parameters.groupby(["category", "parameter_family"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    spectra_type_by_category = (
        normalized_stage4_spectra.groupby(["category", "normalized_spectra_type"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    process_step_by_category = (
        normalized_process_steps.groupby(["category", "process_step_family"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    spectra_parameter_matrix = link_matrix(
        normalized_stage5_links,
        link_family="spectra",
        row_col="normalized_spectra_type",
        col_col="normalized_parameter_family",
    )
    process_parameter_matrix = link_matrix(
        normalized_stage5_links,
        link_family="process_step",
        row_col="normalized_process_step_family",
        col_col="normalized_parameter_family",
    )
    evidence_parameter_matrix = link_matrix(
        normalized_stage5_links,
        link_family="evidence",
        row_col="raw_source_type",
        col_col="normalized_parameter_family",
    )
    category_summary = build_category_summary(
        normalized_parameters,
        normalized_process_steps,
        normalized_stage4_spectra,
        normalized_stage5_links,
    )

    return {
        "normalized_parameters": normalized_parameters,
        "normalized_process_steps": normalized_process_steps,
        "normalized_stage4_spectra": normalized_stage4_spectra,
        "normalized_stage4_peaks": normalized_stage4_peaks,
        "normalized_stage5_links": normalized_stage5_links,
        "normalized_sample_matrix": normalized_sample_matrix,
        "parameter_family_by_category": parameter_family_by_category,
        "spectra_type_by_category": spectra_type_by_category,
        "process_step_by_category": process_step_by_category,
        "spectra_parameter_matrix": spectra_parameter_matrix,
        "process_parameter_matrix": process_parameter_matrix,
        "evidence_parameter_matrix": evidence_parameter_matrix,
        "category_summary": category_summary,
        "stage4_paper_summary": stage4["paper_summary"],
        "stage4_failed": stage4["failed"],
        "stage4_quality": stage4["quality"],
        "stage3_parameter_distribution": stage3["parameter_distribution"],
        "stage3_sample_parameter_long": stage3["sample_parameter_long"],
        "stage3_paper_summary": stage3["paper_stage3_summary"],
        "stage3_coverage_matrix_plotting_data": stage3["coverage_matrix_plotting_data"],
        "stage3_paper_metadata_plotting_data": stage3["paper_metadata_plotting_data"],
        "stage5_final_showcase_table": stage5["final_showcase_table"],
    }
