from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .plot_utils import annotate_empty, safe_heatmap, save_figure_bundle
from .style import DOUBLE_COLUMN_WIDTH_IN, OBJECT_TYPE_COLORS, PARAMETER_GROUP_COLORS, add_panel_label, configure_style


def build_fig1(frame: pd.DataFrame, output_stem: Path, *, context: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    context = context or {}
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 6.9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], width_ratios=[1.08, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    _fig1_panel_a(ax_a, frame[frame["panel_id"] == "A"])
    _fig1_panel_b(ax_b, frame[frame["panel_id"] == "B"])
    _fig1_panel_c(ax_c, frame[frame["panel_id"] == "C"])
    _fig1_panel_d(ax_d, frame[frame["panel_id"] == "D"])

    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D"],
        "panel_descriptions": context.get("panel_descriptions", []),
        "filters_applied": context.get("filters_applied", []),
        "unknown_other_handling": context.get("unknown_other_handling", ""),
        "unit_handling": context.get("unit_handling", ""),
        "category_handling": context.get("category_handling", ""),
        "limitations": context.get("limitations", []),
        "row_counts": _row_counts_by_panel(frame),
        "excluded_row_counts": context.get("excluded_row_counts", {}),
        "extra_metadata": {
            "official_categories": context.get("official_categories", []),
            "uncategorized_excluded_count": context.get("uncategorized_excluded_count", 0),
            "link_completeness_formula": context.get("link_completeness_formula", ""),
            "join_key_used": context.get("join_key_used", ""),
            "completeness_value_range": context.get("completeness_value_range", [0.0, 1.0]),
            "normalization_method": context.get("normalization_method_panel_d", ""),
        },
    }
    return fig_paths, meta


def build_fig2(frame: pd.DataFrame, output_stem: Path, *, context: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    context = context or {}
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 9.1))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.05], width_ratios=[1.0, 1.0])
    axes = [fig.add_subplot(gs[i, j]) for i in range(3) for j in range(2)]

    _fig2_panel_a(axes[0], frame[frame["panel_id"] == "A"])
    _fig2_panel_b(axes[1], frame[frame["panel_id"] == "B"])
    _fig2_panel_c(axes[2], frame[frame["panel_id"] == "C"])
    _fig2_panel_d(axes[3], frame[frame["panel_id"] == "D"])
    _fig2_panel_e(axes[4], frame[frame["panel_id"] == "E"])
    _fig2_panel_f(axes[5], frame[frame["panel_id"] == "F"])

    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D", "E", "F"],
        "panel_descriptions": context.get("panel_descriptions", []),
        "filters_applied": context.get("filters_applied", []),
        "unknown_other_handling": context.get("unknown_other_handling", ""),
        "unit_handling": context.get("unit_handling", ""),
        "category_handling": context.get("category_handling", ""),
        "limitations": context.get("limitations", []),
        "row_counts": _row_counts_by_panel(frame),
        "excluded_row_counts": context.get("excluded_row_counts", {}),
        "extra_metadata": {
            "excluded_characterization_families": context.get("excluded_characterization_families", []),
            "manuscript_parameter_group_mapping": context.get("manuscript_parameter_group_mapping", {}),
            "temperature_unit_conversion": context.get("temperature_unit_conversion", {}),
            "time_unit_conversion": context.get("time_unit_conversion", {}),
            "temperature_filter_range": context.get("temperature_filter_range", []),
            "time_filter_range": context.get("time_filter_range", []),
            "number_of_rows_excluded_by_unit": context.get("number_of_rows_excluded_by_unit", 0),
            "number_of_rows_excluded_by_range": context.get("number_of_rows_excluded_by_range", 0),
        },
    }
    return fig_paths, meta


def build_fig4(frame: pd.DataFrame, output_stem: Path, *, context: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, Any]]:
    context = context or {}
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 7.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.95], width_ratios=[1.0, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    _fig4_panel_a(ax_a, frame[frame["panel_id"] == "A"])
    _fig4_panel_b(ax_b, frame[frame["panel_id"] == "B"])
    _fig4_panel_c(ax_c, frame[frame["panel_id"] == "C"])
    _fig4_panel_d(ax_d, frame[frame["panel_id"] == "D"])

    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D"],
        "panel_descriptions": context.get("panel_descriptions", []),
        "filters_applied": context.get("filters_applied", []),
        "unknown_other_handling": context.get("unknown_other_handling", ""),
        "unit_handling": context.get("unit_handling", ""),
        "category_handling": context.get("category_handling", ""),
        "limitations": context.get("limitations", []),
        "row_counts": _row_counts_by_panel(frame),
        "excluded_row_counts": context.get("excluded_row_counts", {}),
        "extra_metadata": {
            "peak_bin_definitions": context.get("peak_bin_definitions", {}),
            "raw_peak_count": context.get("raw_peak_count", 0),
            "binned_peak_count": context.get("binned_peak_count", 0),
            "excluded_peak_count": context.get("excluded_peak_count", 0),
            "accepted_units": context.get("accepted_units", {}),
            "accepted_ranges": context.get("accepted_ranges", {}),
            "statement_that_bins_are_approximate": context.get("statement_that_bins_are_approximate", ""),
        },
    }
    return fig_paths, meta


def _fig1_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No official-category counts")
        return
    pivot = data.pivot_table(index="category", columns="entity_label", values="value", aggfunc="sum", fill_value=0)
    plot_values = np.log10(pivot.to_numpy(dtype=float) + 1.0)
    x = np.arange(len(pivot.index))
    width = 0.12
    for idx, object_type in enumerate(pivot.columns.tolist()):
        ax.bar(
            x + (idx - (len(pivot.columns) - 1) / 2) * width,
            plot_values[:, idx],
            width=width,
            color=OBJECT_TYPE_COLORS.get(f"{object_type}_count", "#888888"),
            label=object_type,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index.tolist(), rotation=18, ha="right")
    ax.set_ylabel("log10(count + 1)")
    ax.set_title("Dataset object counts by category", loc="left")
    ax.legend(ncol=3, fontsize=5.6, handlelength=1.0)


def _fig1_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No coverage fractions")
        return
    paper_stage = data[data["metric"] == "paper_stage_completion"].copy()
    figure_stage = data[data["metric"] == "stage4_extraction_rate"].copy()
    labels = paper_stage["entity_label"].tolist() + [""] + figure_stage["entity_label"].tolist()
    values = paper_stage["value"].tolist() + [np.nan] + figure_stage["value"].tolist()
    colors = ["#4E9A51"] * len(paper_stage) + ["#FFFFFF"] + ["#B56576"] * len(figure_stage)
    y = np.arange(len(labels))
    ax.barh(y, [0 if pd.isna(v) else v for v in values], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([label.replace("_", " ") for label in labels])
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Fraction of papers or candidate figures")
    ax.set_title("Stage coverage summary", loc="left")
    ax.axvline(1.0, color="#cccccc", lw=0.8, ls="--")


def _fig1_panel_c(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "C")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No completeness fractions")
        return
    safe_heatmap(
        ax,
        data,
        row_col="category",
        col_col="entity_label",
        value_col="value",
        cmap="Greens",
        colorbar_label="Fraction of parameters linked",
        value_range=(0.0, 1.0),
    )
    ax.set_title("Link completeness by category", loc="left")


def _fig1_panel_d(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "D")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No availability values")
        return
    safe_heatmap(
        ax,
        data,
        row_col="category",
        col_col="entity_label",
        value_col="value",
        cmap="Blues",
        colorbar_label="Normalized per-paper mean",
        value_range=(0.0, 1.0),
    )
    ax.set_title("Data availability matrix", loc="left")


def _fig2_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No synthesis groups")
        return
    plot = data.copy()
    plot["plot_value"] = np.log10(plot["value"].astype(float) + 1.0)
    safe_heatmap(
        ax,
        plot,
        row_col="category",
        col_col="entity_label",
        value_col="plot_value",
        cmap="Blues",
        colorbar_label="log10(count + 1)",
    )
    ax.set_title("Category x manuscript parameter group", loc="left")


def _fig2_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    data = frame[frame["included_in_main_plot"].fillna(False)].sort_values("value", ascending=True).copy()
    if data.empty:
        annotate_empty(ax, "No filtered parameter families")
        return
    ax.barh(
        data["entity_label"],
        data["value"],
        color=[PARAMETER_GROUP_COLORS.get(group, PARAMETER_GROUP_COLORS["other"]) for group in data["manuscript_parameter_group"]],
    )
    ax.set_xlabel("Unique parameter count")
    ax.set_title("Top synthesis and process parameter families", loc="left")


def _fig2_panel_c(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "C")
    pH_rows = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if pH_rows.empty:
        annotate_empty(ax, "No unit-safe pH rows")
        return
    values = pd.to_numeric(pH_rows["numeric_value"], errors="coerce").dropna()
    ax.hist(values, bins=20, color="#4E9A51", edgecolor="white")
    ax.set_xlabel("pH")
    ax.set_ylabel("Count")
    ax.set_title("Solution chemistry distributions", loc="left")
    ax.text(
        0.98,
        0.97,
        "Al concentration and solid content\nretained as availability-only rows\nbecause units remain mixed.",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=5.7,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "boxstyle": "round,pad=0.25"},
    )


def _fig2_panel_d(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "D")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No filtered temperature rows")
        return
    grouped, labels = _collect_boxplot_data(data)
    if not grouped:
        annotate_empty(ax, "No filtered temperature rows")
        return
    ax.boxplot(
        grouped,
        tick_labels=labels,
        patch_artist=True,
        boxprops={"facecolor": "#D8A25E", "edgecolor": "#8E5A24"},
        medianprops={"color": "#6B2C2C"},
    )
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Temperature (deg C)")
    ax.set_title("Temperature condition windows", loc="left")


def _fig2_panel_e(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "E")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No filtered time rows")
        return
    grouped, labels = _collect_boxplot_data(data)
    if not grouped:
        annotate_empty(ax, "No filtered time rows")
        return
    ax.boxplot(
        grouped,
        tick_labels=labels,
        patch_artist=True,
        boxprops={"facecolor": "#8FB7D8", "edgecolor": "#4B6A88"},
        medianprops={"color": "#C7675C"},
    )
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Time (h)")
    ax.set_title("Time condition windows", loc="left")


def _fig2_panel_f(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "F")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No filtered co-occurrence rows")
        return
    plot = data.copy()
    plot["row_family"] = plot["entity_label"].str.split(" -> ").str[0]
    plot["col_family"] = plot["entity_label"].str.split(" -> ").str[1]
    safe_heatmap(
        ax,
        plot,
        row_col="row_family",
        col_col="col_family",
        value_col="value",
        cmap="Purples",
        colorbar_label="Co-occurrence count",
    )
    ax.set_title("Parameter co-occurrence", loc="left")


def _fig4_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No filtered characterization rows")
        return
    plot = data.copy()
    plot["plot_value"] = np.log10(plot["value"].astype(float) + 1.0)
    safe_heatmap(
        ax,
        plot,
        row_col="category",
        col_col="entity_label",
        value_col="plot_value",
        cmap="Blues",
        colorbar_label="log10(count + 1)",
    )
    ax.set_title("Characterization family x category", loc="left")


def _fig4_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No deterministic spectra links")
        return
    plot = data.copy()
    plot["spectra_type"] = plot["entity_label"].str.split(" -> ").str[0]
    plot["parameter_family"] = plot["entity_label"].str.split(" -> ").str[1]
    safe_heatmap(
        ax,
        plot,
        row_col="spectra_type",
        col_col="parameter_family",
        value_col="value",
        cmap="Oranges",
        colorbar_label="Deterministic link count",
    )
    ax.set_title("Spectra type x parameter family", loc="left")


def _fig4_panel_c(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "C")
    data = frame[frame["included_in_main_plot"].fillna(False)].sort_values("value", ascending=True).copy()
    if data.empty:
        annotate_empty(ax, "No linked-parameter contributions")
        return
    ax.barh(data["entity_label"], data["value"], color="#B56576")
    ax.set_xlabel("Unique linked parameters")
    ax.set_title("Contribution to linked parameters", loc="left")
    for idx, row in enumerate(data.to_dict(orient="records")):
        if pd.notna(row.get("numeric_value")):
            ax.text(float(row["value"]) + 0.5, idx, f"{float(row['numeric_value']) * 100:.1f}%", va="center", fontsize=5.6)


def _fig4_panel_d(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "D")
    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    if data.empty:
        annotate_empty(ax, "No binned peak or event rows")
        return
    plot = data.copy()
    plot["spectra_type"] = plot["entity_label"].str.split(" -> ").str[0]
    plot["bin_label"] = plot["entity_label"].str.split(" -> ").str[1]
    pivot = plot.pivot_table(index="spectra_type", columns="bin_label", values="value", aggfunc="sum", fill_value=0)
    if pivot.empty:
        annotate_empty(ax, "No binned peak or event rows")
        return
    left = np.zeros(len(pivot.index))
    palette = ["#7BA77F", "#A8C686", "#DCC48E", "#C7675C", "#7D8CC4", "#A68AC0", "#D48FAD", "#B7B7B7"]
    for idx, column in enumerate(pivot.columns.tolist()):
        values = pivot[column].to_numpy(dtype=float)
        ax.barh(pivot.index.tolist(), values, left=left, color=palette[idx % len(palette)], label=column)
        left += values
    ax.set_xlabel("Peak or event count")
    ax.set_title("Approximate peak and event group summary", loc="left")
    ax.legend(fontsize=5.0, loc="lower right")


def _collect_boxplot_data(frame: pd.DataFrame) -> tuple[list[list[float]], list[str]]:
    grouped: list[list[float]] = []
    labels: list[str] = []
    for family, group in frame.groupby("entity_label"):
        values = pd.to_numeric(group["numeric_value"], errors="coerce").dropna()
        if len(values) > 0:
            grouped.append(values.tolist())
            labels.append(str(family))
    return grouped, labels


def _row_counts_by_panel(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    payload: dict[str, dict[str, int]] = {}
    for panel_id, group in frame.groupby("panel_id"):
        included = group["included_in_main_plot"].fillna(False).astype(bool)
        payload[str(panel_id)] = {
            "raw_count": int(len(group)),
            "included_count": int(included.sum()),
            "excluded_count": int((~included).sum()),
        }
    return payload
