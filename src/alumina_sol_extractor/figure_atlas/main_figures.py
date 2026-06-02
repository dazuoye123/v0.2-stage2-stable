from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .plot_utils import bar_figure, heatmap_figure, hist_figure, multi_panel_overview
from .source_data import artifact_paths, write_figure_bundle


def generate_main_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    specs = [
        ("main_fig1_dataset_overview", "Dataset overview", _dataset_overview, "overview"),
        ("main_fig2_parameter_landscape", "Parameter landscape", _parameter_landscape, "heatmap"),
        ("main_fig3_spectroscopic_fingerprint_atlas", "Spectroscopic fingerprint atlas", _spectra_atlas, "heatmap"),
        ("main_fig4_synthesis_process_atlas", "Synthesis process atlas", _process_atlas, "heatmap"),
        ("main_fig5_linked_evidence_map", "Linked evidence map", _evidence_map, "heatmap"),
        ("main_fig6_category_research_patterns", "Category research patterns", _category_patterns, "heatmap"),
        ("main_fig7_stage4_characterization_coverage", "Stage4 characterization coverage", _stage4_coverage, "bar"),
        ("main_fig8_process_spectra_parameter_relationship", "Process-spectra-parameter relationship", _process_spectra_parameter, "heatmap"),
        ("main_fig9_knowledge_graph_overview", "Knowledge graph overview", _knowledge_graph_overview, "overview"),
        ("main_fig10_research_atlas_summary", "Research atlas summary", _research_summary, "overview"),
    ]
    for figure_id, title, builder, mode in specs:
        frame = builder(tables)
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="main", figure_id=figure_id)
        if mode == "heatmap" and len(frame.columns) >= 3:
            svg, png = heatmap_figure(
                paths["figure_stem"],
                frame,
                index_col=frame.columns[0] if not frame.empty else "row",
                column_col=frame.columns[1] if not frame.empty else "col",
                value_col=frame.columns[2] if not frame.empty else "count",
                title=title,
                top_n_rows=10,
                top_n_cols=10,
            )
        elif mode == "bar":
            svg, png = bar_figure(
                paths["figure_stem"],
                frame,
                label_col=frame.columns[0] if not frame.empty else "label",
                value_col=frame.columns[1] if len(frame.columns) >= 2 and not frame.empty else "count",
                title=title,
                top_n=12,
                compress_other=True,
            )
        elif mode == "heatmap":
            svg, png = bar_figure(
                paths["figure_stem"],
                frame,
                label_col=frame.columns[0] if not frame.empty else "label",
                value_col=frame.columns[1] if len(frame.columns) >= 2 and not frame.empty else "count",
                title=title,
                top_n=12,
                compress_other=True,
            )
        else:
            panels = _overview_panels(tables)
            svg, png = multi_panel_overview(paths["figure_stem"], panels, title=title)
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="main",
            recommendation="main",
            feasibility="ready" if not frame.empty else "partial",
            source_df=frame,
            input_tables=_infer_input_tables(frame),
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not frame.empty else "No data available for this main figure.",
        )
        artifacts.append(_artifact_row(artifact))
    return artifacts


def _dataset_overview(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    category = tables["category_summary"]
    if category.empty:
        return pd.DataFrame(columns=["metric", "count"])
    rows = [
        {"metric": "papers", "count": int(category["paper_count"].sum())},
        {"metric": "parameters", "count": int(category["parameter_count"].sum())},
        {"metric": "process_steps", "count": int(category["process_step_count"].sum())},
        {"metric": "spectra", "count": int(category["spectra_count"].sum())},
        {"metric": "links", "count": int(category["link_count"].sum())},
    ]
    return pd.DataFrame(rows)


def _parameter_landscape(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["parameter_family_by_category"].copy()


def _spectra_atlas(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["spectra_type_by_category"].copy()


def _process_atlas(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["process_step_by_category"].copy()


def _evidence_map(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["evidence_parameter_matrix"].copy()


def _category_patterns(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["category_summary"][["category", "parameter_count"]].copy()


def _stage4_coverage(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage4_paper_summary"]
    if frame.empty:
        return pd.DataFrame(columns=["metric", "count"])
    return pd.DataFrame(
        [
            {"metric": "candidates", "count": int(frame["candidate_count"].sum())},
            {"metric": "success", "count": int(frame["success_count"].sum())},
            {"metric": "failed", "count": int(frame["failed_count"].sum())},
            {"metric": "validated", "count": int(frame["validated_count"].sum())},
        ]
    )


def _process_spectra_parameter(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["spectra_parameter_matrix"].copy()


def _knowledge_graph_overview(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    links = tables["normalized_stage5_links"]
    if links.empty:
        return pd.DataFrame(columns=["metric", "count"])
    return links.groupby("link_family").size().reset_index(name="count").rename(columns={"link_family": "metric"})


def _research_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["category_summary"].copy()


def _overview_panels(tables: dict[str, pd.DataFrame]) -> list[tuple[pd.DataFrame, dict[str, Any]]]:
    return [
        (tables["parameter_family_by_category"].groupby("parameter_family")["count"].sum().reset_index().rename(columns={"parameter_family": "label"}), {"kind": "barh", "label_col": "label", "value_col": "count", "title": "A. Parameters"}),
        (tables["spectra_type_by_category"].groupby("normalized_spectra_type")["count"].sum().reset_index().rename(columns={"normalized_spectra_type": "label"}), {"kind": "bar", "label_col": "label", "value_col": "count", "title": "B. Spectra"}),
        (tables["process_step_by_category"].groupby("process_step_family")["count"].sum().reset_index().rename(columns={"process_step_family": "label"}), {"kind": "barh", "label_col": "label", "value_col": "count", "title": "C. Process"}),
        (tables["parameter_family_by_category"], {"kind": "heatmap", "index_col": "category", "column_col": "parameter_family", "value_col": "count", "title": "D. Category x family"}),
    ]


def _artifact_row(artifact: Any) -> dict[str, Any]:
    return artifact.__dict__


def _infer_input_tables(frame: pd.DataFrame) -> list[str]:
    return sorted(set(frame["source_table"].dropna().astype(str).tolist())) if "source_table" in frame.columns else []
