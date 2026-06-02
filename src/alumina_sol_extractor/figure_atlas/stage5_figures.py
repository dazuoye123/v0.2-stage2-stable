from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .plot_utils import bar_figure, heatmap_figure, hist_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_stage5_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    frames = {
        "stage5_fig1_link_family_counts": _link_family_counts(tables),
        "stage5_fig2_link_family_by_category": _link_family_by_category(tables),
        "stage5_fig3_evidence_links_by_parameter_family": _links_by_parameter_family(tables, "evidence"),
        "stage5_fig4_process_links_by_parameter_family": _links_by_parameter_family(tables, "process_step"),
        "stage5_fig5_spectra_links_by_parameter_family": _links_by_parameter_family(tables, "spectra"),
        "stage5_fig6_spectra_type_parameter_matrix": tables["spectra_parameter_matrix"].copy(),
        "stage5_fig7_process_step_parameter_matrix": tables["process_parameter_matrix"].copy(),
        "stage5_fig8_sample_matrix_coverage": _sample_matrix_coverage(tables),
        "stage5_fig9_unlinked_parameter_distribution": _unlinked_parameters(tables),
        "stage5_fig10_representative_paper_graph": _paper_link_counts(tables),
        "stage5_fig11_category_link_density": tables["category_summary"][["category", "link_count"]].copy(),
        "stage5_fig12_showcase_table_summary": _showcase_summary(tables),
        "stage5_fig13_parameters_with_any_link_by_category": _parameter_link_rate(tables),
        "stage5_fig14_link_completeness_heatmap": _link_completeness_heatmap(tables),
        "stage5_fig15_top_linked_parameter_families": _top_linked_parameter_families(tables),
    }
    heatmaps = {"stage5_fig2_link_family_by_category", "stage5_fig6_spectra_type_parameter_matrix", "stage5_fig7_process_step_parameter_matrix", "stage5_fig14_link_completeness_heatmap"}
    histograms = {"stage5_fig8_sample_matrix_coverage"}
    artifacts: list[dict[str, Any]] = []
    for figure_id, frame in frames.items():
        title = figure_id.replace("_", " ")
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="stage5", figure_id=figure_id)
        if figure_id in heatmaps:
            svg, png = heatmap_figure(paths["figure_stem"], frame, index_col=frame.columns[0] if not frame.empty else "row", column_col=frame.columns[1] if not frame.empty else "col", value_col=frame.columns[2] if not frame.empty else "count", title=title, top_n_rows=15, top_n_cols=15)
        elif figure_id in histograms:
            svg, png = hist_figure(paths["figure_stem"], frame, value_col=frame.columns[-1] if not frame.empty else "count", title=title)
        else:
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=frame.columns[0] if not frame.empty else "label", value_col=frame.columns[1] if frame.shape[1] > 1 else "count", title=title, top_n=15, compress_other=True)
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="stage5",
            recommendation="supplementary",
            feasibility="ready" if not frame.empty else "partial",
            source_df=frame,
            input_tables=[],
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not frame.empty else "No Stage5 data available.",
        )
        artifacts.append(artifact.__dict__)
    return artifacts


def _link_family_counts(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_stage5_links"].groupby("link_family").size().reset_index(name="count").sort_values("count", ascending=False)


def _link_family_by_category(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_stage5_links"].groupby(["category", "link_family"]).size().reset_index(name="count")


def _links_by_parameter_family(tables: dict[str, pd.DataFrame], family: str) -> pd.DataFrame:
    frame = tables["normalized_stage5_links"]
    subset = frame[frame["link_family"] == family]
    return subset.groupby("normalized_parameter_family").size().reset_index(name="count").sort_values("count", ascending=False)


def _sample_matrix_coverage(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_sample_matrix"]
    cols = [column for column in ("parameter_count", "linked_parameter_count", "spectra_count") if column in frame.columns]
    return frame[cols].copy() if cols else pd.DataFrame(columns=["parameter_count"])


def _unlinked_parameters(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"]
    mask = ~(frame["has_evidence_link"] | frame["has_process_step_link"] | frame["has_spectra_link"])
    return frame[mask].groupby("parameter_family").size().reset_index(name="count").sort_values("count", ascending=False)


def _paper_link_counts(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_stage5_links"].groupby("paper_id").size().reset_index(name="count").sort_values("count", ascending=False).head(20)


def _showcase_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage5_final_showcase_table"]
    if frame.empty:
        return pd.DataFrame(columns=["category", "count"])
    category_col = "category" if "category" in frame.columns else frame.columns[0]
    return frame.groupby(category_col).size().reset_index(name="count")


def _parameter_link_rate(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"].copy()
    frame["has_any_link"] = frame["has_evidence_link"] | frame["has_process_step_link"] | frame["has_spectra_link"]
    grouped = frame.groupby("category").agg(count=("has_any_link", lambda s: int(s.sum()))).reset_index()
    return grouped


def _link_completeness_heatmap(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"].copy()
    rows: list[dict[str, Any]] = []
    flags = {
        "sample": "has_sample_link",
        "evidence": "has_evidence_link",
        "process_step": "has_process_step_link",
        "spectra": "has_spectra_link",
    }
    for category, group in frame.groupby("category"):
        for label, column in flags.items():
            rows.append({"category": category, "link_type": label, "count": int(group[column].sum())})
    return pd.DataFrame(rows)


def _top_linked_parameter_families(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_stage5_links"]
    return frame.groupby("normalized_parameter_family").size().reset_index(name="count").sort_values("count", ascending=False).head(20)
