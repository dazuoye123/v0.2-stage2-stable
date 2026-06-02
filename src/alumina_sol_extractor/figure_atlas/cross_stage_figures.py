from __future__ import annotations

from pathlib import Path

import pandas as pd

from .plot_utils import bar_figure, heatmap_figure, hist_figure, scatter_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_cross_stage_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    base = _paper_cross_base(tables)
    frames = {
        "cross_fig1_stage3_stage4_coverage": base[["parameter_count", "success_count"]].rename(columns={"parameter_count": "x", "success_count": "y"}),
        "cross_fig2_stage4_success_vs_parameter_count": base[["success_count", "parameter_count"]].rename(columns={"success_count": "x", "parameter_count": "y"}),
        "cross_fig3_spectra_links_vs_stage4_success": base[["spectra_link_count", "success_count"]].rename(columns={"spectra_link_count": "x", "success_count": "y"}),
        "cross_fig4_category_integrated_coverage": tables["category_summary"].copy(),
        "cross_fig5_parameter_spectra_process_triangle": _triangle_summary(tables),
        "cross_fig6_research_pattern_cluster_preview": tables["parameter_family_by_category"].copy(),
        "cross_fig7_parameter_family_vs_characterization_family": tables["spectra_parameter_matrix"].copy(),
        "cross_fig8_process_step_vs_spectra_type": _process_vs_spectra(tables),
        "cross_fig9_stage3_parameter_vs_stage5_link_completeness": base[["parameter_count", "link_count"]].rename(columns={"parameter_count": "x", "link_count": "y"}),
        "cross_fig10_stage4_characterization_vs_stage5_spectra_links": base[["spectra_count", "spectra_link_count"]].rename(columns={"spectra_count": "x", "spectra_link_count": "y"}),
        "cross_fig11_paper_level_data_density_map": base[["paper_id", "data_density"]].copy(),
        "cross_fig12_category_end_to_end_pipeline_map": _pipeline_map(tables),
    }
    artifacts: list[dict[str, object]] = []
    for figure_id, frame in frames.items():
        title = figure_id.replace("_", " ")
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="cross_stage", figure_id=figure_id)
        if figure_id in {"cross_fig1_stage3_stage4_coverage", "cross_fig2_stage4_success_vs_parameter_count", "cross_fig3_spectra_links_vs_stage4_success", "cross_fig9_stage3_parameter_vs_stage5_link_completeness", "cross_fig10_stage4_characterization_vs_stage5_spectra_links"}:
            svg, png = scatter_figure(paths["figure_stem"], frame, x_col="x", y_col="y", title=title)
        elif figure_id in {"cross_fig6_research_pattern_cluster_preview", "cross_fig7_parameter_family_vs_characterization_family", "cross_fig8_process_step_vs_spectra_type"}:
            svg, png = heatmap_figure(paths["figure_stem"], frame, index_col=frame.columns[0] if not frame.empty else "row", column_col=frame.columns[1] if not frame.empty else "col", value_col=frame.columns[2] if not frame.empty else "count", title=title, top_n_rows=15, top_n_cols=15)
        else:
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=frame.columns[0] if not frame.empty else "label", value_col=frame.columns[1] if frame.shape[1] > 1 else "count", title=title, top_n=15, compress_other=True)
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="cross_stage",
            recommendation="supplementary",
            feasibility="ready" if not frame.empty else "partial",
            source_df=frame,
            input_tables=[],
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not frame.empty else "No cross-stage data available.",
        )
        artifacts.append(artifact.__dict__)
    return artifacts


def _paper_cross_base(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    param_counts = tables["normalized_parameters"].groupby("paper_id").size().reset_index(name="parameter_count")
    stage4 = tables["stage4_paper_summary"][["paper_id", "success_count", "candidate_count"]].copy()
    spectra_count = tables["normalized_stage4_spectra"].groupby("paper_id").size().reset_index(name="spectra_count")
    link_count = tables["normalized_stage5_links"].groupby("paper_id").size().reset_index(name="link_count")
    spectra_link_count = tables["normalized_stage5_links"][tables["normalized_stage5_links"]["link_family"] == "spectra"].groupby("paper_id").size().reset_index(name="spectra_link_count")
    base = param_counts.merge(stage4, on="paper_id", how="outer").merge(spectra_count, on="paper_id", how="outer").merge(link_count, on="paper_id", how="outer").merge(spectra_link_count, on="paper_id", how="outer").fillna(0)
    base["data_density"] = base[["parameter_count", "success_count", "spectra_count", "link_count"]].sum(axis=1)
    return base


def _triangle_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"component": "parameters", "count": int(len(tables["normalized_parameters"]))},
            {"component": "spectra", "count": int(len(tables["normalized_stage4_spectra"]))},
            {"component": "links", "count": int(len(tables["normalized_stage5_links"]))},
        ]
    )


def _process_vs_spectra(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    links = tables["normalized_stage5_links"]
    subset = links[links["link_family"] == "spectra"].copy()
    return subset.groupby(["normalized_process_step_family", "normalized_spectra_type"]).size().reset_index(name="count")


def _pipeline_map(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["category_summary"][["category", "paper_count", "parameter_count", "spectra_count", "link_count"]].copy()
