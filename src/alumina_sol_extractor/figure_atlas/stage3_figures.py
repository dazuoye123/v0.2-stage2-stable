from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .plot_utils import bar_figure, box_figure, heatmap_figure, hist_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_stage3_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    frames = {
        "stage3_fig1_object_counts_by_category": _object_counts_by_category(tables),
        "stage3_fig2_parameter_family_coverage": _parameter_family_coverage(tables),
        "stage3_fig3_parameter_family_by_category": tables["parameter_family_by_category"].copy(),
        "stage3_fig4_ph_distribution": _family_numeric(tables, ["pH"]),
        "stage3_fig5_temperature_distributions": _family_numeric(tables, ["hydrolysis temperature", "aging temperature", "drying temperature", "calcination temperature"]),
        "stage3_fig6_time_distributions": _family_numeric(tables, ["hydrolysis time", "aging time", "drying time", "holding time"]),
        "stage3_fig7_size_distributions": _family_numeric(tables, ["fiber diameter", "particle size"]),
        "stage3_fig8_concentration_solid_content": _family_numeric(tables, ["Al concentration", "solid content"]),
        "stage3_fig9_bet_mass_loss_mechanical": _family_numeric(tables, ["BET surface area", "mass loss", "mechanical property"]),
        "stage3_fig10_parameter_cooccurrence_matrix": _parameter_cooccurrence(tables),
        "stage3_fig11_parameter_cooccurrence_network": _parameter_cooccurrence(tables),
        "stage3_fig12_sample_parameter_matrix_top": _sample_matrix_top(tables),
        "stage3_fig13_paper_parameter_coverage": _paper_parameter_coverage(tables),
        "stage3_fig14_process_step_frequency": _process_frequency(tables),
        "stage3_fig15_process_step_by_category": tables["process_step_by_category"].copy(),
        "stage3_fig16_process_route_simple": _process_frequency(tables),
        "stage3_fig17_numeric_value_availability_by_family": _numeric_availability(tables),
        "stage3_fig18_parameter_missingness_by_category": _missingness_by_category(tables),
        "stage3_fig19_top_parameter_examples": _top_parameters(tables),
        "stage3_fig20_category_parameter_density": tables["category_summary"][["category", "parameter_count"]].copy(),
    }
    heatmaps = {
        "stage3_fig3_parameter_family_by_category",
        "stage3_fig10_parameter_cooccurrence_matrix",
        "stage3_fig12_sample_parameter_matrix_top",
        "stage3_fig15_process_step_by_category",
    }
    boxplots = {
        "stage3_fig5_temperature_distributions",
        "stage3_fig6_time_distributions",
        "stage3_fig7_size_distributions",
        "stage3_fig8_concentration_solid_content",
        "stage3_fig9_bet_mass_loss_mechanical",
    }
    artifacts: list[dict[str, Any]] = []
    for figure_id, frame in frames.items():
        title = figure_id.replace("_", " ")
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="stage3", figure_id=figure_id)
        if figure_id in heatmaps:
            if figure_id == "stage3_fig12_sample_parameter_matrix_top":
                svg, png = heatmap_figure(paths["figure_stem"], _sample_matrix_long(frame), index_col="sample_id", column_col="parameter", value_col="value", title=title, top_n_rows=25, top_n_cols=25)
                source_df = _sample_matrix_long(frame)
            else:
                svg, png = heatmap_figure(paths["figure_stem"], frame, index_col=frame.columns[0] if not frame.empty else "row", column_col=frame.columns[1] if not frame.empty else "col", value_col=frame.columns[2] if not frame.empty else "count", title=title, top_n_rows=15, top_n_cols=15)
                source_df = frame
        elif figure_id in boxplots:
            svg, png = box_figure(paths["figure_stem"], frame, group_col="parameter_family", value_col="numeric_value", title=title, top_n=10)
            source_df = frame
        elif figure_id in {"stage3_fig4_ph_distribution"}:
            svg, png = hist_figure(paths["figure_stem"], frame, value_col="numeric_value", title=title)
            source_df = frame
        else:
            label_col = frame.columns[0] if not frame.empty else "label"
            value_col = _bar_value_column(frame)
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=label_col, value_col=value_col, title=title, top_n=12, compress_other=True, horizontal=value_col != "count" and label_col != "category")
            source_df = frame
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="stage3",
            recommendation="supplementary",
            feasibility="ready" if not source_df.empty else "partial",
            source_df=source_df,
            input_tables=[],
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not source_df.empty else "No Stage3 data available.",
        )
        artifacts.append(artifact.__dict__)
    return artifacts


def _object_counts_by_category(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["category_summary"][["category", "parameter_count"]].rename(columns={"parameter_count": "count"}).copy()


def _parameter_family_coverage(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_parameters"].groupby("parameter_family").size().reset_index(name="count")


def _family_numeric(tables: dict[str, pd.DataFrame], families: list[str]) -> pd.DataFrame:
    frame = tables["normalized_parameters"]
    return frame[frame["parameter_family"].isin(families)][["parameter_family", "numeric_value", "paper_id", "category"]].dropna(subset=["numeric_value"]).copy()


def _parameter_cooccurrence(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"][["paper_id", "sample_id", "parameter_family"]].dropna().copy()
    if frame.empty:
        return pd.DataFrame(columns=["row_family", "col_family", "count"])
    pairs: list[dict[str, Any]] = []
    for (_, _), group in frame.groupby(["paper_id", "sample_id"]):
        families = sorted(set(group["parameter_family"].tolist()))
        for row_family in families:
            for col_family in families:
                pairs.append({"row_family": row_family, "col_family": col_family, "count": 1})
    return pd.DataFrame(pairs).groupby(["row_family", "col_family"]).sum().reset_index()


def _sample_matrix_top(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage3_coverage_matrix_plotting_data"].copy()
    if not frame.empty:
        label_col = frame.columns[0]
        return frame.rename(columns={label_col: "sample_id"})
    return pd.DataFrame()


def _sample_matrix_long(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["sample_id", "parameter", "value"])
    return frame.melt(id_vars=[frame.columns[0]], var_name="parameter", value_name="value")


def _paper_parameter_coverage(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_parameters"].groupby("paper_id").size().reset_index(name="count").sort_values("count", ascending=False).head(30)


def _process_frequency(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_process_steps"].groupby("process_step_family").size().reset_index(name="count")


def _numeric_availability(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"].copy()
    grouped = frame.groupby("parameter_family").agg(total=("parameter_id", "size"), numeric=("numeric_value", lambda s: int(s.notna().sum()))).reset_index()
    grouped["count"] = grouped["numeric"] / grouped["total"].clip(lower=1)
    return grouped[["parameter_family", "count"]]


def _missingness_by_category(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_parameters"].copy()
    grouped = frame.groupby("category").agg(total=("parameter_id", "size"), missing=("numeric_value", lambda s: int(s.isna().sum()))).reset_index()
    grouped["count"] = grouped["missing"] / grouped["total"].clip(lower=1)
    return grouped[["category", "count"]]


def _top_parameters(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_parameters"].groupby("parameter_name").size().reset_index(name="count").sort_values("count", ascending=False).head(20)


def _bar_value_column(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "count"
    numeric_columns = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    if numeric_columns:
        return numeric_columns[-1]
    return frame.columns[1] if frame.shape[1] > 1 else "count"
