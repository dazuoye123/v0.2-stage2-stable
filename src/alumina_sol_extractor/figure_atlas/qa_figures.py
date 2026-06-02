from __future__ import annotations

from pathlib import Path

import pandas as pd

from .plot_utils import bar_figure, heatmap_figure, hist_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_qa_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame], availability: pd.DataFrame) -> list[dict[str, object]]:
    frames = {
        "qa_fig1_stage3_raw_object_counts": tables["category_summary"][["category", "parameter_count"]].rename(columns={"parameter_count": "count"}),
        "qa_fig2_stage3_parameter_raw_coverage": _group_count(tables["parameter_family_by_category"], "parameter_family", sum_col="count"),
        "qa_fig3_stage3_numeric_extraction_qa": tables["normalized_parameters"][["numeric_value"]].copy(),
        "qa_fig4_stage3_missing_parameter_family": _group_count(
            tables["normalized_parameters"][tables["normalized_parameters"]["parameter_family"].isin(["other", "Unknown"])],
            "parameter_family",
        ),
        "qa_fig5_stage3_process_step_raw_distribution": _group_count(tables["normalized_process_steps"], "process_step_family"),
        "qa_fig6_stage3_category_balance": tables["category_summary"][["category", "paper_count"]].copy(),
        "qa_fig7_stage4_candidate_count_distribution": tables["stage4_paper_summary"][["candidate_count"]].copy(),
        "qa_fig8_stage4_success_failure_distribution": tables["stage4_paper_summary"][["success_count", "failed_count"]].sum().reset_index(name="count"),
        "qa_fig9_stage4_full_figure_class_distribution": _group_count(tables["normalized_stage4_spectra"], "figure_class"),
        "qa_fig10_stage4_unknown_other_qa": _group_count(
            tables["normalized_stage4_spectra"][tables["normalized_stage4_spectra"]["normalized_spectra_type"].isin(["Unknown", "Other"])],
            "normalized_spectra_type",
        ),
        "qa_fig11_stage4_validation_error_summary": tables["stage4_paper_summary"][["validation_error_count"]].copy(),
        "qa_fig12_stage4_failed_record_summary": _group_count(tables["stage4_failed"], "paper_id"),
        "qa_fig13_stage4_per_paper_success_rate_full": tables["stage4_paper_summary"][["coverage_rate"]].copy(),
        "qa_fig14_stage5_success_partial_summary": _link_family_counts(tables),
        "qa_fig15_stage5_warning_distribution": _warning_distribution(tables),
        "qa_fig16_evidence_link_coverage_qa": _group_count(
            tables["normalized_stage5_links"][tables["normalized_stage5_links"]["link_family"] == "evidence"],
            "normalized_parameter_family",
        ),
        "qa_fig17_spectra_link_coverage_qa": _group_count(
            tables["normalized_stage5_links"][tables["normalized_stage5_links"]["link_family"] == "spectra"],
            "normalized_parameter_family",
        ),
        "qa_fig18_process_step_link_coverage_qa": _group_count(
            tables["normalized_stage5_links"][tables["normalized_stage5_links"]["link_family"] == "process_step"],
            "normalized_parameter_family",
        ),
        "qa_fig19_sample_matrix_missingness": _sample_missingness(tables),
        "qa_fig20_category_object_density": tables["category_summary"][["category", "parameter_count"]].copy(),
        "qa_fig21_unlinked_parameters_qa": _group_count(
            tables["normalized_parameters"][
                ~(tables["normalized_parameters"]["has_evidence_link"] | tables["normalized_parameters"]["has_process_step_link"] | tables["normalized_parameters"]["has_spectra_link"])
            ],
            "parameter_family",
        ),
        "qa_fig22_unknown_spectra_type_examples": _group_count(
            tables["normalized_stage4_spectra"][tables["normalized_stage4_spectra"]["normalized_spectra_type"] == "Unknown"],
            "raw_spectra_type",
        ).head(20),
        "qa_fig23_other_parameter_family_examples": _group_count(
            tables["normalized_parameters"][tables["normalized_parameters"]["parameter_family"] == "other"],
            "parameter_key",
        ).head(20),
        "qa_fig24_source_table_row_counts": _group_count(availability, "data_source", sum_col="row_count"),
        "qa_fig25_data_availability_dashboard": _group_count(availability, ["data_source", "usable_for_figures"]),
    }
    heatmaps = {"qa_fig25_data_availability_dashboard"}
    histograms = {"qa_fig3_stage3_numeric_extraction_qa", "qa_fig7_stage4_candidate_count_distribution", "qa_fig11_stage4_validation_error_summary", "qa_fig13_stage4_per_paper_success_rate_full"}
    artifacts: list[dict[str, object]] = []
    for figure_id, frame in frames.items():
        title = figure_id.replace("_", " ")
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="qa", figure_id=figure_id)
        if figure_id in heatmaps:
            svg, png = heatmap_figure(paths["figure_stem"], frame, index_col=frame.columns[0] if not frame.empty else "row", column_col=frame.columns[1] if not frame.empty else "col", value_col=frame.columns[2] if not frame.empty else "count", title=title, top_n_rows=10, top_n_cols=10)
        elif figure_id in histograms:
            value_col = frame.columns[-1] if not frame.empty else "count"
            svg, png = hist_figure(paths["figure_stem"], frame, value_col=value_col, title=title)
        else:
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=frame.columns[0] if not frame.empty else "label", value_col=frame.columns[1] if frame.shape[1] > 1 else "count", title=title, top_n=15, compress_other=True)
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="qa",
            recommendation="qa",
            feasibility="ready" if not frame.empty else "partial",
            source_df=frame,
            input_tables=[],
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not frame.empty else "No QA data available.",
        )
        artifacts.append(artifact.__dict__)
    return artifacts


def _link_family_counts(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return _group_count(tables["normalized_stage5_links"], "link_family")


def _warning_distribution(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"]
    return _group_count(frame, "normalization_warning")


def _sample_missingness(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_sample_matrix"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["category", "metric", "count"])
    rows = []
    for _, row in frame.iterrows():
        rows.append({"category": row.get("category"), "metric": "parameter_gap", "count": max(float(row.get("parameter_count", 0)) - float(row.get("linked_parameter_count", 0)), 0)})
    return pd.DataFrame(rows)


def _group_count(frame: pd.DataFrame, group_cols: str | list[str], *, sum_col: str | None = None) -> pd.DataFrame:
    columns = [group_cols] if isinstance(group_cols, str) else list(group_cols)
    if frame.empty or any(column not in frame.columns for column in columns):
        output_columns = columns + ["count"]
        return pd.DataFrame(columns=output_columns)
    if sum_col is not None:
        if sum_col not in frame.columns:
            return pd.DataFrame(columns=columns + ["count"])
        return frame.groupby(columns, dropna=False)[sum_col].sum().reset_index(name="count")
    return frame.groupby(columns, dropna=False).size().reset_index(name="count")
