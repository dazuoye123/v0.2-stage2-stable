from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .plot_utils import annotate_empty, safe_heatmap, save_figure_bundle
from .style import DOUBLE_COLUMN_WIDTH_IN, OBJECT_TYPE_COLORS, PARAMETER_GROUP_COLORS, add_panel_label, configure_style


def build_fig1(frame: pd.DataFrame, output_stem: Path) -> tuple[dict[str, str], dict[str, Any]]:
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 6.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], width_ratios=[1.15, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    data = frame[frame["included_in_main_plot"].fillna(False)].copy()
    _fig1_panel_a(ax_a, data[data["panel_id"] == "A"])
    _fig1_panel_b(ax_b, data[data["panel_id"] == "B"])
    _fig1_panel_c(ax_c, data[data["panel_id"] == "C"])
    _fig1_panel_d(ax_d, data[data["panel_id"] == "D"])
    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D"],
        "filters_applied": ["included_in_main_plot == true"],
        "unknown_other_handling": "No dominant Unknown/Other categories in this figure; counts were plotted directly.",
        "unit_handling": "Count- and ratio-based panels only.",
        "limitations": ["Coverage does not equal semantic perfection; Stage4 and linking quality still need caption context."],
        "row_counts": _row_counts_by_panel(frame),
    }
    return fig_paths, meta


def build_fig2(frame: pd.DataFrame, output_stem: Path) -> tuple[dict[str, str], dict[str, Any]]:
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 8.4))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 0.9, 1.0], width_ratios=[1.0, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])
    ax_e = fig.add_subplot(gs[2, :])

    data = frame.copy()
    included = data[data["included_in_main_plot"].fillna(False)]
    _fig2_panel_a(ax_a, included[included["panel_id"] == "A"])
    _fig2_panel_b(ax_b, included[included["panel_id"] == "B"])
    _fig2_panel_c(ax_c, data[data["panel_id"] == "C"])
    _fig2_panel_d(ax_d, included[included["panel_id"] == "D"])
    _fig2_panel_e(ax_e, included[included["panel_id"] == "E"])
    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D", "E"],
        "filters_applied": [
            "included_in_main_plot == true for plotted rows",
            "Other/Unknown removed from heatmaps and top-family panel",
            "Panel C downgraded to pH-only numeric distribution because concentration-related units remained mixed",
        ],
        "unknown_other_handling": "Unknown/Other rows were preserved in source data and excluded from main panels.",
        "unit_handling": "pH used unitless numeric rows only; temperature/time windows used unit-consistent numeric rows; mixed concentration units stayed excluded.",
        "limitations": [
            "Al concentration and solid-content families still need semantic/unit cleanup before quantitative main-panel plotting.",
        ],
        "row_counts": _row_counts_by_panel(frame),
    }
    return fig_paths, meta


def build_fig4(frame: pd.DataFrame, output_stem: Path) -> tuple[dict[str, str], dict[str, Any]]:
    configure_style()
    fig = plt.figure(figsize=(DOUBLE_COLUMN_WIDTH_IN, 8.6))
    gs = fig.add_gridspec(3, 2, height_ratios=[0.95, 1.0, 1.0], width_ratios=[1.0, 1.0])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])
    ax_e = fig.add_subplot(gs[2, 0])
    ax_f = fig.add_subplot(gs[2, 1])

    data = frame.copy()
    included = data[data["included_in_main_plot"].fillna(False)]
    _fig4_panel_a(ax_a, included[included["panel_id"] == "A"])
    _fig4_panel_b(ax_b, included[included["panel_id"] == "B"])
    _fig4_hist(ax_c, included[included["panel_id"] == "C"], xlabel="Wavenumber (cm$^{-1}$)", bins=30, title="FTIR peaks")
    _fig4_hist(ax_d, included[included["panel_id"] == "D"], xlabel="2theta (degree)", bins=28, title="XRD peaks")
    _fig4_hist(ax_e, included[included["panel_id"] == "E"], xlabel="Chemical shift (ppm)", bins=24, title="NMR shifts")
    _fig4_hist(ax_f, included[included["panel_id"] == "F"], xlabel="Event temperature (deg C)", bins=26, title="TG/DSC events")
    fig_paths = save_figure_bundle(fig, output_stem)
    meta = {
        "panels": ["A", "B", "C", "D", "E", "F"],
        "filters_applied": [
            "included_in_main_plot == true for plotted rows",
            "FTIR restricted to 400-4000 cm^-1",
            "XRD restricted to 5-90 degree 2theta",
            "NMR restricted to ppm rows in a plausible range",
            "TG/DSC restricted to temperature-like rows in a bounded thermal range",
        ],
        "unknown_other_handling": "Other/Unknown characterization families were retained in source data and excluded from the main heatmaps.",
        "unit_handling": "Each peak panel used unit-compatible subsets only; all excluded rows remain in the source-data CSV with filter reasons.",
        "limitations": [
            "Stage4 peak panels remain sensitive to upstream labeling quality and should be checked manually before submission.",
        ],
        "row_counts": _row_counts_by_panel(frame),
    }
    return fig_paths, meta


def _fig1_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    order = ["applications", "fiber_process", "mechanism", "rheology", "uncategorized"]
    metrics = ["paper_count", "sample_count", "parameter_count", "process_step_count", "spectra_count", "link_count"]
    pivot = frame.pivot_table(index="category", columns="metric", values="value", aggfunc="sum", fill_value=0).reindex(order).fillna(0)
    x = np.arange(len(pivot.index))
    width = 0.12
    for idx, metric in enumerate(metrics):
        ax.bar(
            x + (idx - 2.5) * width,
            pivot[metric].to_numpy(),
            width=width,
            color=OBJECT_TYPE_COLORS.get(metric, "#888888"),
            label=metric.replace("_count", ""),
        )
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index.tolist(), rotation=20, ha="right")
    ax.set_ylabel("Count")
    ax.set_title("Dataset objects by category", loc="left")
    ax.legend(ncol=3, fontsize=5.8, handlelength=1.0)


def _fig1_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    grouped = frame.groupby("entity_label")["value"].sum().sort_values(ascending=True)
    labels = [str(item).replace("_", " ") for item in grouped.index.tolist()]
    ax.barh(labels, grouped.to_numpy(), color="#5D87B1")
    ax.set_xlabel("Count")
    ax.set_title("Stage coverage summary", loc="left")


def _fig1_panel_c(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "C")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    safe_heatmap(ax, frame, row_col="category", col_col="entity_label", value_col="value", cmap="Greens")
    ax.set_title("Link completeness by category", loc="left")


def _fig1_panel_d(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "D")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    safe_heatmap(ax, frame, row_col="category", col_col="entity_label", value_col="value", cmap="Blues", normalize=True)
    ax.set_title("Data availability matrix", loc="left")


def _fig2_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    top_cols = frame.groupby("entity_label")["value"].sum().sort_values(ascending=False).head(14).index.tolist()
    panel = frame[frame["entity_label"].isin(top_cols)].copy()
    safe_heatmap(ax, panel, row_col="category", col_col="entity_label", value_col="value", cmap="Blues")
    ax.set_title("Category x parameter family", loc="left")


def _fig2_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    top = frame.sort_values("value", ascending=False).head(12).copy()
    top["group"] = top["entity_label"].apply(_parameter_group)
    ax.barh(
        top["entity_label"][::-1],
        top["value"][::-1],
        color=[PARAMETER_GROUP_COLORS.get(item, PARAMETER_GROUP_COLORS["other"]) for item in top["group"][::-1]],
    )
    ax.set_xlabel("Count")
    ax.set_title("Top parameter families", loc="left")


def _fig2_panel_c(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "C")
    included = frame[frame["included_in_main_plot"].fillna(False)].copy()
    ph = included[included["entity_label"] == "pH"].copy()
    if ph.empty:
        annotate_empty(ax, "No unit-safe numeric panel")
        return
    values = pd.to_numeric(ph["value"], errors="coerce").dropna()
    ax.hist(values, bins=20, color="#4E9A51", edgecolor="white")
    ax.set_xlabel("pH")
    ax.set_ylabel("Count")
    ax.set_title("pH distribution", loc="left")
    excluded_counts = frame.groupby("entity_label")["included_in_main_plot"].apply(lambda s: int((~s.fillna(False).astype(bool)).sum()))
    ax.text(
        0.98,
        0.97,
        f"Excluded numeric rows\nAl concentration: {excluded_counts.get('Al concentration', 0)}\nsolid content: {excluded_counts.get('solid content', 0)}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=5.8,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "boxstyle": "round,pad=0.25"},
    )


def _fig2_panel_d(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "D")
    if frame.empty:
        annotate_empty(ax, "No unit-safe window data")
        return
    subset = frame[
        frame["entity_label"].isin(
            [
                "aging temperature",
                "calcination temperature",
                "drying temperature",
                "hydrolysis temperature",
                "aging time",
                "holding time",
                "drying time",
                "hydrolysis time",
            ]
        )
    ]
    grouped = []
    labels = []
    for family, group in subset.groupby("entity_label"):
        values = pd.to_numeric(group["value"], errors="coerce").dropna()
        if not values.empty:
            grouped.append(values.tolist())
            labels.append(str(family).replace("temperature", "temp"))
    if not grouped:
        annotate_empty(ax, "No unit-safe window data")
        return
    ax.boxplot(
        grouped,
        tick_labels=labels,
        patch_artist=True,
        boxprops={"facecolor": "#8FB7D8", "edgecolor": "#4B6A88"},
        medianprops={"color": "#C7675C"},
    )
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Value")
    ax.set_title("Temperature/time windows", loc="left")


def _fig2_panel_e(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "E")
    if frame.empty:
        annotate_empty(ax, "No co-occurrence data")
        return
    panel = frame.copy()
    panel["row_family"] = panel["entity_label"].str.split(" -> ").str[0]
    panel["col_family"] = panel["entity_label"].str.split(" -> ").str[1]
    top = panel.groupby("row_family")["value"].sum().sort_values(ascending=False).head(12).index.tolist()
    filtered = panel[panel["row_family"].isin(top) & panel["col_family"].isin(top)]
    safe_heatmap(ax, filtered, row_col="row_family", col_col="col_family", value_col="value", cmap="Purples")
    ax.set_title("Parameter co-occurrence", loc="left")


def _fig4_panel_a(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "A")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    safe_heatmap(ax, frame, row_col="category", col_col="entity_label", value_col="value", cmap="Blues")
    ax.set_title("Characterization x category", loc="left")


def _fig4_panel_b(ax: plt.Axes, frame: pd.DataFrame) -> None:
    add_panel_label(ax, "B")
    if frame.empty:
        annotate_empty(ax, "No data")
        return
    panel = frame.copy()
    panel["spectra_type"] = panel["entity_label"].str.split(" -> ").str[0]
    panel["parameter_family"] = panel["entity_label"].str.split(" -> ").str[1]
    top_param = panel.groupby("parameter_family")["value"].sum().sort_values(ascending=False).head(10).index.tolist()
    top_spec = panel.groupby("spectra_type")["value"].sum().sort_values(ascending=False).head(8).index.tolist()
    panel = panel[panel["parameter_family"].isin(top_param) & panel["spectra_type"].isin(top_spec)]
    safe_heatmap(ax, panel, row_col="spectra_type", col_col="parameter_family", value_col="value", cmap="Oranges")
    ax.set_title("Spectra x parameter family", loc="left")


def _fig4_hist(ax: plt.Axes, frame: pd.DataFrame, *, xlabel: str, bins: int, title: str) -> None:
    label = {"FTIR peaks": "C", "XRD peaks": "D", "NMR shifts": "E", "TG/DSC events": "F"}[title]
    add_panel_label(ax, label)
    if frame.empty:
        annotate_empty(ax, "No filtered peak data")
        return
    values = pd.to_numeric(frame["value"], errors="coerce").dropna()
    ax.hist(values, bins=bins, color="#7BA77F", edgecolor="white")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    ax.set_title(title, loc="left")


def _parameter_group(family: str) -> str:
    text = str(family).lower()
    if "ph" in text or "concentration" in text or "solid content" in text or "acid/base" in text:
        return "sol chemistry"
    if "temperature" in text or "time" in text or "heating" in text:
        return "thermal processing"
    if "xrd" in text or "nmr" in text or "ftir" in text or "spectra" in text:
        return "spectroscopy/characterization"
    if "size" in text or "surface" in text or "mass loss" in text or "mechanical" in text:
        return "structure/property"
    return "process"


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
