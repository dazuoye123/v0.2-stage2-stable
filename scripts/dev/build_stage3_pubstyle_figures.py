"""
Stage 3 Publication-Style Figures — Scientific-quality redraw.

Reuses ALL data-processing logic from build_stage3_analysis_v2.py.
Only the plotting layer is redefined with unified publication-quality styling.

Output: data/analysis_outputs_stage3_pubstyle/
Formats: PNG (300 dpi) + SVG + PDF
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import warnings
from pathlib import Path
from typing import Any

# --- Project root ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# --- Set backend before importing pyplot ---
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# --- Import data-processing functions from the build script ---
_BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "dev" / "build_stage3_analysis_v2.py"


def _load_build_module():
    """Import build_stage3_analysis_v2.py via importlib."""
    spec = importlib.util.spec_from_file_location("build_stage3_analysis_v2", _BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_build = _load_build_module()

# Data-processing functions (reused unchanged)
build_cleaned_action_distribution = _build.build_cleaned_action_distribution
build_time_condition_distribution = _build.build_time_condition_distribution
build_heating_rate_distribution = _build.build_heating_rate_distribution
build_temperature_distributions = _build.build_temperature_distributions
build_real_transitions = _build.build_real_transitions
build_cleaned_network = _build.build_cleaned_network
build_sample_parameter_matrix_ppt_v2 = _build.build_sample_parameter_matrix_ppt_v2

# Utility functions (reused)
scan_process_steps_from_source = _build.scan_process_steps_from_source
load_manifest_rows = _build.load_manifest_rows
write_dataframe = _build.write_dataframe
normalize_text = _build.normalize_text
shorten_label = _build.shorten_label
classify_parameter_type = _build.classify_parameter_type
map_action_to_stage = _build.map_action_to_stage
_is_process_time_type = _build._is_process_time_type
read_json = _build.read_json
ensure_directory = _build.ensure_directory
resolve_path = _build.resolve_path

# Constants (reused)
PARAMETER_TYPE_COLORS: dict[str, str] = _build.PARAMETER_TYPE_COLORS
CATEGORY_COLORS: dict[str, str] = _build.CATEGORY_COLORS
SHORT_KEY_LABELS: dict[str, str] = _build.SHORT_KEY_LABELS
ROUTE_STAGE_LABELS: dict[str, str] = _build.ROUTE_STAGE_LABELS
ACTION_ZH_LABELS: dict[str, str] = _build.ACTION_ZH_LABELS


# ============================================================================
# Publication-Style Design System
# ============================================================================

class PubStyle:
    """Single source of truth for all visual parameters."""

    # ---- Color Palette ----
    blue_main: str = "#2F5D8A"
    blue_light: str = "#7FA6C9"
    blue_pale: str = "#C5D9EE"
    green: str = "#7AA974"
    green_dark: str = "#4A7A42"
    orange: str = "#D28B47"
    orange_light: str = "#E8C08A"
    purple: str = "#7E68B3"
    gray: str = "#9AA3AD"
    gray_light: str = "#C5CAD1"
    grid: str = "#D9DEE5"
    text: str = "#24364B"
    text_secondary: str = "#5A6B7F"
    white: str = "#FFFFFF"

    # ---- Semantic color mapping ----
    process_color: str = "#2F5D8A"       # blue — synthesis/process
    structure_color: str = "#7AA974"     # green — structure
    property_color: str = "#D28B47"      # orange — property
    char_color: str = "#7E68B3"          # purple — characterization
    other_color: str = "#9AA3AD"         # gray — other
    measurement_color: str = "#D28B47"   # orange — measurement time (distinct from process)

    # ---- Typography ----
    font_candidates: tuple = (
        "Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans",
        "Noto Sans CJK SC", "Source Han Sans SC", "sans-serif",
    )
    title_size: int = 13
    subtitle_size: int = 11
    axis_label_size: int = 10
    tick_size: int = 9
    annotation_size: int = 8
    source_size: int = 7
    kpi_value_size: int = 22
    kpi_label_size: int = 9
    title_weight: str = "bold"

    # ---- Layout ----
    dpi: int = 300
    line_width: float = 0.8
    spine_width: float = 0.6
    grid_alpha: float = 0.25
    grid_style: str = "--"
    bar_edge_width: float = 0.0

    # ---- Output ----
    formats: tuple = (".png", ".svg", ".pdf")


# Singleton style config
CFG = PubStyle()


def configure_matplotlib_pubstyle(cfg: PubStyle = CFG) -> None:
    """Set global matplotlib rcParams for publication quality."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    font_chain = [c for c in cfg.font_candidates if c in installed]
    if not font_chain:
        font_chain = ["sans-serif"]

    plt.rcParams.update({
        "font.sans-serif": font_chain,
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        # White background
        "figure.facecolor": cfg.white,
        "axes.facecolor": cfg.white,
        "savefig.facecolor": cfg.white,
        # Edge and grid
        "axes.edgecolor": cfg.gray_light,
        "axes.linewidth": cfg.spine_width,
        "grid.color": cfg.grid,
        "grid.alpha": cfg.grid_alpha,
        "grid.linestyle": cfg.grid_style,
        # Text defaults
        "text.color": cfg.text,
        "axes.labelcolor": cfg.text,
        "xtick.color": cfg.text,
        "ytick.color": cfg.text,
        # Sizing
        "font.size": cfg.tick_size,
        "axes.titlesize": cfg.subtitle_size,
        "axes.labelsize": cfg.axis_label_size,
        "xtick.labelsize": cfg.tick_size,
        "ytick.labelsize": cfg.tick_size,
        "legend.fontsize": cfg.annotation_size,
        # Output
        "figure.dpi": cfg.dpi,
        "savefig.dpi": cfg.dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.08,
        # Tick styling
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
    })


def save_figure_pubstyle(fig: plt.Figure, base_path: Path, cfg: PubStyle = CFG) -> None:
    """Save figure in all output formats at publication quality."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    for fmt in cfg.formats:
        save_kwargs: dict[str, Any] = dict(dpi=cfg.dpi, bbox_inches="tight",
                                            facecolor=cfg.white, edgecolor="none")
        if fmt == ".pdf":
            save_kwargs["metadata"] = {"Creator": "Stage3 PubStyle Generator"}
        fig.savefig(base_path.with_suffix(fmt), **save_kwargs)
    plt.close(fig)


def _add_source_note(fig: plt.Figure, text: str, cfg: PubStyle = CFG) -> None:
    """Add a subtle source note at the bottom-left."""
    fig.text(0.01, 0.005, text, fontsize=cfg.source_size, color=cfg.gray, style="italic")


def _add_title_block(fig: plt.Figure, title: str, subtitle: str = "",
                     cfg: PubStyle = CFG, y: float = 0.975) -> None:
    """Add a clean title block at the top."""
    fig.text(0.02, y, title, fontsize=cfg.title_size, fontweight=cfg.title_weight,
             color=cfg.text, va="top")
    if subtitle:
        fig.text(0.02, y - 0.025, subtitle, fontsize=cfg.subtitle_size - 1,
                 color=cfg.text_secondary, va="top")


# ============================================================================
# Figure 1: Stage 3 Overview Dashboard
# ============================================================================

def plot_overview_dashboard_pubstyle(
    summary: dict[str, Any],
    parameter_distribution: pd.DataFrame,
    action_cleaned: pd.DataFrame,
    paper_stage3_summary: pd.DataFrame,
    base_path: Path,
    cfg: PubStyle = CFG,
) -> None:
    """Publication-quality overview dashboard with KPI cards and 3 subplots."""
    fig = plt.figure(figsize=(16, 9))
    gs = GridSpec(12, 28, figure=fig, hspace=0.4, wspace=0.5)

    n_actions = int(action_cleaned["count"].sum()) if not action_cleaned.empty else 0

    kpi_data = [
        (str(summary.get("total_papers", "—")), "Papers"),
        (str(summary.get("total_data_points", "—")), "Data points"),
        (str(summary.get("total_process_steps", "—")), "Process steps"),
        (str(summary.get("total_evidence_objects", "—")), "Evidence objects"),
        (str(summary.get("unique_canonical_key_count", "—")), "Unique keys"),
        (str(n_actions), "Cleaned steps"),
    ]

    kpi_colors = [cfg.blue_main, cfg.blue_light, cfg.green, cfg.orange, cfg.purple, cfg.blue_main]

    # --- KPI Cards (rows 0-3) ---
    for idx, ((value, label), color) in enumerate(zip(kpi_data, kpi_colors)):
        row = 0 if idx < 3 else 2
        col = (idx % 3) * 9 + (0 if idx < 3 else 2)
        ax_kpi = fig.add_subplot(gs[row:row + 2, col:col + 8])
        ax_kpi.set_xlim(0, 1)
        ax_kpi.set_ylim(0, 1)
        ax_kpi.axis("off")

        # Card background
        rect = plt.Rectangle((0, 0), 1, 1, transform=ax_kpi.transAxes,
                             facecolor=cfg.white, edgecolor=cfg.grid,
                             linewidth=0.8, zorder=0)
        ax_kpi.add_patch(rect)

        # Accent line at top
        accent = plt.Rectangle((0.15, 0.85), 0.7, 0.03, transform=ax_kpi.transAxes,
                               facecolor=color, linewidth=0, zorder=2)
        ax_kpi.add_patch(accent)

        ax_kpi.text(0.5, 0.62, value, transform=ax_kpi.transAxes, ha="center", va="center",
                    fontsize=cfg.kpi_value_size, fontweight="bold", color=color)
        ax_kpi.text(0.5, 0.28, label, transform=ax_kpi.transAxes, ha="center", va="center",
                    fontsize=cfg.kpi_label_size, color=cfg.text_secondary)

    # --- Subplot 1: Top canonical keys (rows 4-12, cols 0-10) ---
    ax1 = fig.add_subplot(gs[4:12, 0:10])
    if not parameter_distribution.empty:
        top_keys = parameter_distribution.head(12)[::-1]
        bars = ax1.barh(range(len(top_keys)), top_keys["count"].values,
                        color=cfg.blue_main, height=0.65)
        ax1.set_yticks(range(len(top_keys)))
        labels = [shorten_label(k) for k in top_keys["canonical_key"].values]
        ax1.set_yticklabels(labels, fontsize=cfg.tick_size - 1)
        ax1.set_xlabel("Count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
        ax1.set_title("Top Canonical Keys", fontsize=cfg.subtitle_size,
                      fontweight=cfg.title_weight, color=cfg.text)
        ax1.grid(axis="x", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
        ax1.tick_params(axis="x", labelsize=cfg.tick_size - 1)
        # Add count labels
        for i, v in enumerate(top_keys["count"].values):
            ax1.text(v + max(top_keys["count"].values) * 0.01, i, str(v),
                     va="center", fontsize=cfg.annotation_size - 1, color=cfg.text)
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax1.transAxes)
        ax1.axis("off")

    # --- Subplot 2: Top cleaned actions (rows 4-12, cols 10-20) ---
    ax2 = fig.add_subplot(gs[4:12, 10:20])
    if not action_cleaned.empty:
        top_actions = action_cleaned.head(12)[::-1]
        bars = ax2.barh(range(len(top_actions)), top_actions["count"].values,
                        color=cfg.green, height=0.65)
        ax2.set_yticks(range(len(top_actions)))
        labels = [f"{a} ({ACTION_ZH_LABELS.get(a, a)})" for a in top_actions["action"].values]
        ax2.set_yticklabels(labels, fontsize=cfg.tick_size - 1)
        ax2.set_xlabel("Count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
        ax2.set_title("Top Cleaned Actions", fontsize=cfg.subtitle_size,
                      fontweight=cfg.title_weight, color=cfg.text)
        ax2.grid(axis="x", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
        ax2.tick_params(axis="x", labelsize=cfg.tick_size - 1)
        for i, v in enumerate(top_actions["count"].values):
            ax2.text(v + max(top_actions["count"].values) * 0.01, i, str(v),
                     va="center", fontsize=cfg.annotation_size - 1, color=cfg.text)
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax2.transAxes)
        ax2.axis("off")

    # --- Subplot 3: Category contribution (rows 4-12, cols 20-28) ---
    ax3 = fig.add_subplot(gs[4:12, 20:28])
    if not paper_stage3_summary.empty and "category" in paper_stage3_summary.columns:
        cat_counts = paper_stage3_summary["category"].value_counts()
        cats = cat_counts.index.tolist()[:6]
        counts = cat_counts.values[:6]
        colors_cat = [cfg.blue_main, cfg.blue_light, cfg.green, cfg.orange, cfg.purple, cfg.gray][:len(cats)]
        bars = ax3.barh(range(len(cats)), counts, color=colors_cat, height=0.6)
        ax3.set_yticks(range(len(cats)))
        ax3.set_yticklabels(cats, fontsize=cfg.tick_size - 1)
        ax3.set_xlabel("Paper count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
        ax3.set_title("Category Papers", fontsize=cfg.subtitle_size,
                      fontweight=cfg.title_weight, color=cfg.text)
        ax3.grid(axis="x", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
        ax3.tick_params(axis="x", labelsize=cfg.tick_size - 1)
        for i, v in enumerate(counts):
            ax3.text(v + max(counts) * 0.01, i, str(v),
                     va="center", fontsize=cfg.annotation_size - 1, color=cfg.text)
    else:
        ax3.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax3.transAxes)
        ax3.axis("off")

    _add_title_block(fig, "Stage 3 Literature Extraction — Overview",
                     f"N = {summary.get('total_papers', '—')} papers  |  "
                     f"{summary.get('total_data_points', '—')} data points  |  "
                     f"{n_actions} cleaned process steps")
    _add_source_note(fig, "Source: Stage 3 batch extraction → process_steps.jsonl / schema_v2.json → aggregated statistics")

    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 2: Process Step Action Distribution
# ============================================================================

def plot_action_distribution_pubstyle(
    action_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Horizontal bar chart of cleaned action distribution."""
    if action_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    total = int(action_df["count"].sum())
    # Top 15 actions, merge rest as "other"
    top_df = action_df.head(15).copy()
    other_count = int(action_df.iloc[15:]["count"].sum()) if len(action_df) > 15 else 0
    other_pct = other_count / total * 100 if total else 0

    is_merged = action_df[action_df["action"] == "other"]
    merged_count = int(is_merged["count"].sum()) if not is_merged.empty and len(action_df) > 15 else None

    plot_df = top_df[::-1].copy()  # reverse for horizontal (bottom-to-top)
    actions = plot_df["action"].tolist()
    counts = plot_df["count"].tolist()
    zh_labels = [ACTION_ZH_LABELS.get(a, "") for a in actions]
    labels = [f"{a}  ({zh})" if zh else a for a, zh in zip(actions, zh_labels)]

    fig_height = max(6.5, len(plot_df) * 0.42)
    fig, ax = plt.subplots(figsize=(11, fig_height))

    colors = [cfg.gray if a == "other" else cfg.blue_main for a in actions]
    bars = ax.barh(range(len(plot_df)), counts, color=colors, height=0.7, linewidth=0)

    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels(labels, fontsize=cfg.tick_size)
    ax.set_xlabel("Number of process steps", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
    ax.tick_params(axis="x", labelsize=cfg.tick_size)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    max_count = max(counts)
    for i, (count, action) in enumerate(zip(counts, actions)):
        pct = count / total * 100
        label = f"{count} ({pct:.1f}%)"
        x_pos = count + max_count * 0.015
        ax.text(x_pos, i, label, va="center", fontsize=cfg.annotation_size, color=cfg.text)

    # If "other" contains merged data, add a visual separator
    if merged_count is not None and merged_count > 0:
        ax.axhline(y=0.5, color=cfg.grid, linewidth=1, linestyle="-")

    _add_title_block(fig, "Process Step Action Distribution",
                     f"N = {total} steps  |  {len(action_df['action'].unique())} unique actions")
    _add_source_note(fig, "Source: process_steps.jsonl → cleaned action canonicalization")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 3: Time Condition Distribution by Type
# ============================================================================

def plot_time_condition_by_type_pubstyle(
    time_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Publication-quality 2x4 grid of time condition histograms."""
    type_labels = {
        "aging_time": "Aging time",
        "drying_time": "Drying time",
        "calcination_holding_time": "Calcination\nholding time",
        "sintering_holding_time": "Sintering\nholding time",
        "hydrolysis_time": "Hydrolysis time",
        "stirring_time": "Stirring time",
        "holding_time": "Holding time",
        "measurement_time": "Measurement time",
        "generic_holding_time": "未判定持续时间",
    }
    all_types = list(type_labels.keys())
    present_types = [t for t in all_types if (time_df["time_type"] == t).any()] if not time_df.empty else []

    if not present_types:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    n_types = len(present_types)
    n_cols = min(4, n_types)
    n_rows = int(np.ceil(n_types / n_cols))

    # Sort: process times first, then measurement_time, then generic
    def _sort_key(t: str) -> tuple[int, str]:
        if t == "generic_holding_time":
            return (2, t)
        if t == "measurement_time":
            return (1, t)
        return (0, t)
    present_types.sort(key=_sort_key)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.5 * n_cols, 3.2 * n_rows))
    axes_flat = axes.flatten() if n_rows * n_cols > 1 else [axes]

    for idx, tt in enumerate(present_types):
        ax = axes_flat[idx]
        subset = time_df[time_df["time_type"] == tt]["value_h"].dropna()

        if len(subset) == 0:
            ax.text(0.5, 0.5, "N=0", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(type_labels.get(tt, tt), fontsize=cfg.subtitle_size - 1,
                         fontweight=cfg.title_weight, color=cfg.text)
            ax.axis("off")
            continue

        is_measurement = (tt == "measurement_time")
        is_generic = (tt == "generic_holding_time")
        color = cfg.measurement_color if is_measurement else (cfg.purple if is_generic else cfg.blue_main)

        use_log = (subset.max() / max(subset.min(), 0.01)) > 100
        if use_log:
            bins = np.logspace(np.log10(max(subset.min(), 0.01)), np.log10(max(subset.max(), 0.1)), 20)
            ax.set_xscale("log")
        else:
            bins = min(20, max(8, int(np.sqrt(len(subset)))))

        ax.hist(subset, bins=bins, color=color, edgecolor=cfg.white, linewidth=0.3, alpha=0.85)
        median_val = subset.median()
        mean_val = subset.mean()
        ax.axvline(median_val, color=cfg.orange, linestyle="--", linewidth=1.0, alpha=0.8)

        # Stats box
        stats_text = f"N={len(subset)}\nMed={median_val:.1f}h\nMean={mean_val:.1f}h"
        ax.text(0.97, 0.97, stats_text, transform=ax.transAxes, ha="right", va="top",
                fontsize=cfg.annotation_size - 1, color=cfg.text_secondary,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=cfg.white, edgecolor=cfg.grid, linewidth=0.5, alpha=0.9))

        ax.set_title(type_labels.get(tt, tt), fontsize=cfg.subtitle_size - 1,
                     fontweight=cfg.title_weight, color=cfg.text)
        ax.set_xlabel("Time / h", fontsize=cfg.tick_size - 1, color=cfg.text_secondary)
        ax.set_ylabel("Count", fontsize=cfg.tick_size - 1, color=cfg.text_secondary)
        ax.tick_params(labelsize=cfg.tick_size - 1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)

    # Hide unused subplots
    for idx in range(n_types, n_rows * n_cols):
        axes_flat[idx].axis("off")

    _add_title_block(fig, "Time Condition Distribution by Type",
                     "Process times (blue)  ·  Measurement time (orange)  ·  未判定持续时间 (purple, fallback)")
    note = ("Note: generic_holding_time is a fallback type without specific process-stage identification. "
            "Measurement times are characterization durations, not synthesis parameters.")
    fig.text(0.01, 0.01, note, fontsize=cfg.source_size, color=cfg.gray, style="italic")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 4: Calcination / Sintering Temperature Overlay
# ============================================================================

def plot_calcination_sintering_overlay_pubstyle(
    calc_df: pd.DataFrame, sinter_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Step histogram overlay with inset boxplot for calcination vs sintering."""
    fig = plt.figure(figsize=(10, 5.5))
    gs = GridSpec(1, 1, figure=fig)

    ax = fig.add_subplot(gs[0, 0])
    calc_vals = calc_df["temperature_C"].dropna().values if not calc_df.empty else np.array([])
    sinter_vals = sinter_df["temperature_C"].dropna().values if not sinter_df.empty else np.array([])

    if len(calc_vals) == 0 and len(sinter_vals) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    combined = np.concatenate([calc_vals, sinter_vals]) if len(calc_vals) > 0 and len(sinter_vals) > 0 else (calc_vals if len(calc_vals) > 0 else sinter_vals)
    bins = np.linspace(max(50, combined.min() - 50), combined.max() + 50, 18)

    if len(calc_vals) > 0:
        ax.hist(calc_vals, bins=bins, histtype="step", linewidth=2.0, color=cfg.blue_main, label=f"Calcination (n={len(calc_vals)})")
        ax.axvline(np.median(calc_vals), color=cfg.blue_main, linestyle="--", linewidth=1.2, alpha=0.7)

    if len(sinter_vals) > 0:
        ax.hist(sinter_vals, bins=bins, histtype="step", linewidth=2.0, color=cfg.green, label=f"Sintering (n={len(sinter_vals)})")
        ax.axvline(np.median(sinter_vals), color=cfg.green, linestyle="--", linewidth=1.2, alpha=0.7)

    ax.set_xlabel("Temperature (°C)", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.set_ylabel("Count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.legend(fontsize=cfg.annotation_size, loc="upper right", frameon=True,
              facecolor=cfg.white, edgecolor=cfg.grid, framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
    ax.tick_params(labelsize=cfg.tick_size)

    # Inset boxplot
    if len(calc_vals) > 0 and len(sinter_vals) > 0:
        inset = ax.inset_axes([0.55, 0.6, 0.38, 0.3])
        bp = inset.boxplot([calc_vals, sinter_vals], labels=["Calcin.", "Sinter."],
                           patch_artist=True, widths=0.5, medianprops=dict(color=cfg.text, linewidth=1.2))
        bp["boxes"][0].set_facecolor(cfg.blue_pale)
        bp["boxes"][1].set_facecolor("#C5E0C5")
        inset.tick_params(labelsize=cfg.annotation_size - 1)
        inset.set_ylabel("°C", fontsize=cfg.annotation_size - 1)
        inset.spines["top"].set_visible(False)
        inset.spines["right"].set_visible(False)

    _add_title_block(fig, "Calcination vs. Sintering Temperature",
                     f"Filtered range: 100–2500 °C  |  N_calc={len(calc_vals)}, N_sinter={len(sinter_vals)}")
    _add_source_note(fig, "Source: process_condition_distribution.csv → temperature_cleaned")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figures 5 & 6: Calcination / Sintering Temperature (individual)
# ============================================================================

def _plot_single_temp_hist(
    values: np.ndarray, label: str, color: str, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Reusable single-temperature histogram."""
    fig, ax = plt.subplots(figsize=(9, 5))
    if len(values) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    ax.hist(values, bins=16, color=color, edgecolor=cfg.white, linewidth=0.5, alpha=0.85)
    median_val = np.median(values)
    mean_val = np.mean(values)
    ax.axvline(median_val, color=cfg.orange, linestyle="--", linewidth=1.5, alpha=0.8, label=f"Median = {median_val:.0f} °C")
    ax.axvline(mean_val, color=cfg.gray, linestyle=":", linewidth=1.2, alpha=0.6, label=f"Mean = {mean_val:.0f} °C")

    stats_str = f"N = {len(values)}\nMedian = {median_val:.0f} °C\nMean = {mean_val:.0f} °C\nSD = {np.std(values):.0f} °C"
    ax.text(0.97, 0.97, stats_str, transform=ax.transAxes, ha="right", va="top",
            fontsize=cfg.annotation_size, color=cfg.text_secondary,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=cfg.white, edgecolor=cfg.grid, linewidth=0.5, alpha=0.95))

    ax.set_xlabel("Temperature (°C)", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.set_ylabel("Count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
    ax.tick_params(labelsize=cfg.tick_size)
    ax.legend(fontsize=cfg.annotation_size, loc="upper left", frameon=True, facecolor=cfg.white, edgecolor=cfg.grid)

    title = f"{label} Temperature Distribution"
    _add_title_block(fig, title, f"Filtered range: 100–2500 °C  |  N = {len(values)}")
    _add_source_note(fig, "Source: process_condition_distribution.csv → temperature_cleaned")
    save_figure_pubstyle(fig, base_path, cfg)


def plot_calcination_temperature_pubstyle(
    calc_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    _plot_single_temp_hist(
        calc_df["temperature_C"].dropna().values if not calc_df.empty else np.array([]),
        "Calcination", cfg.blue_main, base_path, cfg,
    )


def plot_sintering_temperature_pubstyle(
    sinter_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    _plot_single_temp_hist(
        sinter_df["temperature_C"].dropna().values if not sinter_df.empty else np.array([]),
        "Sintering", cfg.green, base_path, cfg,
    )


# ============================================================================
# Figure 7: Heating Rate Distribution
# ============================================================================

def plot_heating_rate_pubstyle(
    hr_df: pd.DataFrame, outliers_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Histogram + clean stats panel for heating rate."""
    fig = plt.figure(figsize=(11, 5))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[3, 1], wspace=0.25)

    ax = fig.add_subplot(gs[0, 0])
    vals = hr_df["heating_rate_C_per_min"].dropna().values if not hr_df.empty else np.array([])

    if len(vals) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    ax.hist(vals, bins=min(22, max(10, int(np.sqrt(len(vals))))), color=cfg.blue_main,
            edgecolor=cfg.white, linewidth=0.5, alpha=0.85)
    median_val = np.median(vals)
    ax.axvline(median_val, color=cfg.orange, linestyle="--", linewidth=1.5, alpha=0.8)

    ax.set_xlabel("Heating rate (°C/min)", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.set_ylabel("Count", fontsize=cfg.axis_label_size, color=cfg.text_secondary)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=cfg.grid_style, alpha=cfg.grid_alpha, color=cfg.grid)
    ax.tick_params(labelsize=cfg.tick_size)

    # Stats panel
    ax_stats = fig.add_subplot(gs[0, 1])
    ax_stats.axis("off")
    n_outliers = len(outliers_df) if not outliers_df.empty else 0
    stats_lines = [
        f"N = {len(vals)}",
        f"Median = {median_val:.1f} °C/min",
        f"Mean = {np.mean(vals):.1f} °C/min",
        f"SD = {np.std(vals):.1f} °C/min",
        f"Min = {np.min(vals):.1f}",
        f"Max = {np.max(vals):.1f}",
    ]
    if n_outliers > 0:
        stats_lines.append(f"Outliers: {n_outliers} excluded")
    for i, line in enumerate(stats_lines):
        ax_stats.text(0.05, 0.9 - i * 0.11, line, transform=ax_stats.transAxes,
                      fontsize=cfg.annotation_size + 1, color=cfg.text, fontfamily="monospace")

    _add_title_block(fig, "Heating Rate Distribution",
                     f"Filtered range: 0.1–200 °C/min  |  Excluded {n_outliers} outlier(s)")
    footnote = f"Outliers: " + (", ".join(outliers_df["reason"].unique()[:3]) if n_outliers > 0 else "none")
    fig.text(0.01, 0.01, footnote, fontsize=cfg.source_size, color=cfg.gray, style="italic")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 8: Sample-Parameter Matrix Sparsity Heatmap
# ============================================================================

def plot_sample_parameter_matrix_pubstyle(
    matrix_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Publication-quality heatmap with short labels and category sidebar."""
    if matrix_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    param_cols = [c for c in matrix_df.columns if c not in ("category", "paper_id")]
    data_matrix = matrix_df[param_cols].fillna(0).astype(int).values
    categories = matrix_df["category"].values
    paper_ids = matrix_df["paper_id"].values

    # Short labels for columns
    short_labels = [shorten_label(c) for c in param_cols]
    short_papers = [str(p)[:15] for p in paper_ids]

    # Category color mapping
    cat_unique = sorted(set(categories))
    cat_colors_map = {
        "fiber_process": cfg.blue_main,
        "mechanism": cfg.blue_light,
        "applications": cfg.green,
        "rheology": cfg.purple,
    }
    cat_colors_list = [cat_colors_map.get(c, cfg.gray) for c in cat_unique]

    fig = plt.figure(figsize=(14, 8))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[0.03, 1], wspace=0.02)

    # Category sidebar
    ax_cat = fig.add_subplot(gs[0, 0])
    cat_to_idx = {c: i for i, c in enumerate(cat_unique)}
    cat_indices = [cat_to_idx[c] for c in categories]
    cat_array = np.array(cat_indices).reshape(-1, 1)
    cmap_cat = plt.matplotlib.colors.ListedColormap(cat_colors_list)
    ax_cat.imshow(cat_array, aspect="auto", cmap=cmap_cat)
    ax_cat.set_xticks([])
    ax_cat.set_yticks([])

    # Main heatmap
    ax = fig.add_subplot(gs[0, 1])
    cmap_blues = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "pub_blues", [cfg.white, cfg.blue_pale, cfg.blue_main], N=256,
    )
    im = ax.imshow(data_matrix, aspect="auto", cmap=cmap_blues, vmin=0, vmax=1, interpolation="nearest")

    ax.set_xticks(range(len(short_labels)))
    ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=6.5, color=cfg.text)
    ax.set_yticks(range(len(short_papers)))
    ax.set_yticklabels(short_papers, fontsize=6, color=cfg.text)
    ax.tick_params(axis="x", which="both", length=2)
    ax.tick_params(axis="y", which="both", length=2)

    # Category legend on sidebar
    for i, cat in enumerate(cat_unique):
        c_idx = [j for j, c in enumerate(categories) if c == cat]
        if c_idx:
            y_mid = np.mean(c_idx)
            ax_cat.text(0.5, y_mid / len(categories), cat, rotation=90,
                        ha="center", va="center", fontsize=5, color=cfg.white, fontweight="bold")

    density = (data_matrix.sum() / data_matrix.size) * 100
    _add_title_block(fig, "Sample–Parameter Coverage Matrix",
                     f"{data_matrix.shape[0]} papers × {data_matrix.shape[1]} parameters  |  Density = {density:.1f}%")
    _add_source_note(fig, "Source: sample_parameter_long.csv → sample_parameter_matrix_summary.json")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 9: Process Route Transition Diagram (2 versions)
# ============================================================================

def _get_stage_coords(stages: list[str]) -> dict[str, tuple[float, float]]:
    """Compute node positions for process route stages."""
    n = len(stages)
    coords: dict[str, tuple[float, float]] = {}
    for i, stage in enumerate(stages):
        y = 0.5
        x = 0.1 + 0.8 * i / max(n - 1, 1)
        coords[stage] = (x, y)
    return coords


def plot_transition_diagram_simplified_pubstyle(
    transitions_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Simplified version: only dominant forward transitions."""
    _draw_transition_diagram(transitions_df, base_path, cfg, simplified=True)


def plot_transition_diagram_analysis_pubstyle(
    transitions_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG,
) -> None:
    """Full analysis version: all transitions with backward edges."""
    _draw_transition_diagram(transitions_df, base_path, cfg, simplified=False)


def _draw_transition_diagram(
    transitions_df: pd.DataFrame, base_path: Path, cfg: PubStyle = CFG, simplified: bool = False,
) -> None:
    """Internal: draw a process route transition diagram."""
    if transitions_df.empty:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    stage_order = ["sol_prep", "aging_concentration", "spinning", "drying",
                   "calcination_sintering", "characterization", "other"]
    stage_labels = ROUTE_STAGE_LABELS
    coords = _get_stage_coords(stage_order)

    # Aggregate transitions by stage
    stage_transitions: dict[tuple[str, str], int] = {}
    total_count = 0
    for _, row in transitions_df.iterrows():
        src = map_action_to_stage(str(row["source_action"]))
        tgt = map_action_to_stage(str(row["target_action"]))
        if src != tgt:
            key = (src, tgt)
            stage_transitions[key] = stage_transitions.get(key, 0) + int(row["count"])
            total_count += int(row["count"])

    if not stage_transitions:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.text(0.5, 0.5, "No transitions", ha="center", va="center")
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    # Sort by count
    sorted_trans = sorted(stage_transitions.items(), key=lambda x: x[1], reverse=True)

    # For simplified mode: keep top 80% of forward transitions
    if simplified:
        forward_trans = {k: v for k, v in sorted_trans if stage_order.index(k[0]) < stage_order.index(k[1])}
        threshold = sum(forward_trans.values()) * 0.1
        keep = {k: v for k, v in forward_trans.items() if v >= threshold}
        # Also keep backward edges
        backward_trans = {k: v for k, v in sorted_trans if stage_order.index(k[0]) > stage_order.index(k[1])}
        keep.update(backward_trans)
        sorted_trans = sorted(keep.items(), key=lambda x: x[1], reverse=True)

    fig_width = 14 if simplified else 15
    fig, ax = plt.subplots(figsize=(fig_width, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0.05, 0.95)
    ax.axis("off")

    max_count = max(v for _, v in sorted_trans) if sorted_trans else 1

    # Draw nodes
    node_width = 0.09
    node_height = 0.22
    for stage in stage_order:
        x, y = coords[stage]
        rect = plt.Rectangle((x - node_width / 2, y - node_height / 2), node_width, node_height,
                             facecolor=cfg.blue_pale, edgecolor=cfg.blue_main, linewidth=1.5,
                             zorder=3, transform=ax.transAxes)
        ax.add_patch(rect)
        label = stage_labels.get(stage, stage)
        ax.text(x, y, label, ha="center", va="center", fontsize=cfg.annotation_size,
                color=cfg.text, fontweight="bold", transform=ax.transAxes, zorder=4)

    # Draw edges
    for (src, tgt), count in sorted_trans:
        if src not in coords or tgt not in coords:
            continue
        x1, y1 = coords[src]
        x2, y2 = coords[tgt]
        is_forward = stage_order.index(src) < stage_order.index(tgt)
        lw = 1.0 + 4.0 * (count / max_count)

        if is_forward:
            color = cfg.blue_main
            alpha = 0.7
        else:
            color = cfg.orange
            alpha = 0.4
            if simplified:
                continue

        if abs(x2 - x1) > 0.3:
            # Long edge: use curved connection
            mid_y = y1 + 0.12 * ((-1) ** (hash((src, tgt)) % 3))
            connection = f"arc3,rad={0.15 * (-1) ** (hash((src, tgt)) % 2 + 1)}"
            arrow = FancyArrowPatch((x1 + node_width / 2, y1), (x2 - node_width / 2, y2),
                                    connectionstyle=connection, arrowstyle="->",
                                    color=color, linewidth=lw, alpha=alpha,
                                    mutation_scale=12, zorder=2)
        else:
            arrow = FancyArrowPatch((x1 + node_width / 2, y1 + 0.02), (x2 - node_width / 2, y2 + 0.02),
                                    arrowstyle="->", color=color, linewidth=lw, alpha=alpha,
                                    mutation_scale=12, zorder=2)
        ax.add_patch(arrow, )

        # Label
        mid_x = (x1 + x2) / 2
        mid_y = y1 + 0.08 * (-1) ** (hash((src, tgt)) % 3)
        ax.text(mid_x, mid_y, str(count), ha="center", va="center",
                fontsize=cfg.annotation_size - 2, color=color, alpha=alpha + 0.2,
                fontweight="bold", transform=ax.transAxes, zorder=5)

    ver = "Simplified" if simplified else "Full Analysis"
    _add_title_block(fig, f"Process Route Transition Diagram — {ver}",
                     f"Total transitions: {total_count}  |  Edges shown: {len(sorted_trans)}")
    _add_source_note(fig, "Source: process_steps.jsonl (step_order) → transition_edges.csv")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 10: Parameter Co-occurrence Network
# ============================================================================

def plot_cleaned_network_pubstyle(
    edges_df: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    network_summary: dict[str, Any],
    base_path: Path,
    cfg: PubStyle = CFG,
) -> None:
    """Publication-quality network graph with external labels."""
    if edges_df.empty:
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    G = nx.Graph()
    counts: dict[str, int] = {}
    if not parameter_distribution.empty:
        for _, row in parameter_distribution.iterrows():
            counts[str(row["canonical_key"])] = int(row["count"])

    for _, row in edges_df.iterrows():
        src = str(row["source_canonical_key"])
        tgt = str(row["target_canonical_key"])
        weight = float(row["cooccurrence_count"])
        G.add_edge(src, tgt, weight=weight)

    max_count = max(counts.values()) if counts else 100

    # Kamada-Kawai layout for better small-world visualization
    try:
        pos = nx.kamada_kawai_layout(G, weight="weight", scale=2.5)
    except Exception:
        pos = nx.spring_layout(G, k=2.5, iterations=100, seed=42)

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-3.5, 3.5)
    ax.axis("off")

    # Draw edges
    edge_widths = [1.0 + 3.0 * G[u][v]["weight"] / max(d["weight"] for _, _, d in G.edges(data=True))
                   for u, v in G.edges()]
    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths, edge_color=cfg.blue_pale,
                           alpha=0.7, style="solid")

    # Draw nodes
    for node in G.nodes():
        node_size = 400 + 15 * counts.get(node, 10)
        node_type = classify_parameter_type(node)
        type_colors = {
            "synthesis": cfg.blue_main, "process": cfg.blue_light,
            "structure": cfg.green, "property": cfg.orange,
            "characterization": cfg.purple, "other": cfg.gray,
        }
        node_color = type_colors.get(node_type, cfg.gray)
        nx.draw_networkx_nodes(G, pos, nodelist=[node], ax=ax, node_size=node_size,
                               node_color=node_color, edgecolors=cfg.white, linewidths=2.0)

    # Draw labels with offset to avoid overlapping nodes
    for node, (x, y) in pos.items():
        angle = np.arctan2(y, x)
        offset_x = 0.15 * np.cos(angle)
        offset_y = 0.15 * np.sin(angle)
        ha = "left" if x >= 0 else "right"
        short = shorten_label(node)
        ax.text(x + offset_x, y + offset_y, short, fontsize=cfg.annotation_size,
                ha=ha, va="center", color=cfg.text, fontweight="bold")

    threshold = network_summary.get("threshold_used", "—")
    _add_title_block(fig, "Parameter Co-occurrence Network",
                     f"{len(G.nodes())} nodes, {len(G.edges())} edges  |  Co-occurrence threshold ≥ {threshold}")
    _add_source_note(fig, "Source: parameter_cooccurrence_edges.csv → network_summary.json")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Figure 11 & 12: Canonical Key × Category Heatmaps
# ============================================================================

def plot_count_heatmap_pubstyle(
    canonical_key_by_category: pd.DataFrame, base_path: Path, top_n: int = 20,
    cfg: PubStyle = CFG,
) -> None:
    """Count heatmap with selective annotations."""
    _draw_heatmap(canonical_key_by_category, base_path, cfg, value_col="count",
                  cmap_name="pub_blues", top_n=top_n, annotate=True, is_normalized=False)


def plot_normalized_heatmap_pubstyle(
    canonical_key_by_category: pd.DataFrame, base_path: Path, top_n: int = 20,
    cfg: PubStyle = CFG,
) -> None:
    """Normalized frequency heatmap emphasizing color hierarchy."""
    _draw_heatmap(canonical_key_by_category, base_path, cfg, value_col="normalized_frequency",
                  cmap_name="pub_oranges", top_n=top_n, annotate=False, is_normalized=True)


def _draw_heatmap(
    df: pd.DataFrame, base_path: Path, cfg: PubStyle,
    value_col: str, cmap_name: str, top_n: int, annotate: bool, is_normalized: bool,
) -> None:
    """Internal: draw a canonical-key × category heatmap."""
    if df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        save_figure_pubstyle(fig, base_path, cfg)
        return

    totals = df.groupby("canonical_key")["count"].sum().sort_values(ascending=False)
    top_keys = totals.head(top_n).index.tolist()
    subset = df[df["canonical_key"].isin(top_keys)].copy()

    pivot = subset.pivot(index="canonical_key", columns="category", values=value_col).fillna(0)
    categories = sorted(pivot.columns.tolist())
    pivot = pivot[categories]

    if cmap_name == "pub_blues":
        cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
            "pub_blues_ht", [cfg.white, cfg.blue_pale, cfg.blue_main], N=256)
    else:
        cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
            "pub_oranges_ht", [cfg.white, cfg.orange_light, cfg.orange], N=256)

    short_keys = [shorten_label(k) for k in pivot.index]
    fig, ax = plt.subplots(figsize=(max(8, len(categories) * 2.2), max(5, len(short_keys) * 0.4)))
    im = ax.imshow(pivot.values, aspect="auto", cmap=cmap)

    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=cfg.tick_size - 1, color=cfg.text)
    ax.set_yticks(range(len(short_keys)))
    ax.set_yticklabels(short_keys, fontsize=cfg.tick_size - 1, color=cfg.text)
    ax.tick_params(axis="both", which="both", length=2)

    # Annotate count heatmap (only cells with visible values)
    if annotate:
        max_val = pivot.values.max()
        for i in range(len(short_keys)):
            for j in range(len(categories)):
                val = pivot.values[i, j]
                if val > 0:
                    text_color = cfg.white if val > max_val * 0.5 else cfg.text
                    ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                            fontsize=cfg.annotation_size - 2, color=text_color)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar_label = "Count" if not is_normalized else "Normalized frequency (within category)"
    cbar.set_label(cbar_label, fontsize=cfg.annotation_size, color=cfg.text_secondary)
    cbar.ax.tick_params(labelsize=cfg.annotation_size - 1)

    title = "Canonical Key × Category (Count)" if not is_normalized else "Canonical Key × Category (Normalized)"
    sub = f"Top {top_n} keys by total count" if not is_normalized else "Normalized within each category — emphasizes distribution patterns"
    _add_title_block(fig, title, sub)
    _add_source_note(fig, "Source: canonical_key_by_category.csv → canonical_key_category_summary.csv")
    save_figure_pubstyle(fig, base_path, cfg)


# ============================================================================
# Main Entry Point
# ============================================================================

def build_pubstyle_figures(
    manifest_path: Path,
    analysis_dir: Path,
    outputs_dir: Path,
    output_dir: Path,
    stage3_subdir: str = "stage3_twopass",
    top_n: int = 30,
    paper_limit: int = 50,
) -> dict[str, Any]:
    """Orchestrate data loading and figure generation."""
    configure_matplotlib_pubstyle()
    output_dir = ensure_directory(output_dir)
    figures_dir = ensure_directory(output_dir / "figures")

    print("Loading input data...")
    manifest_rows = load_manifest_rows(manifest_path)

    process_action_orig = pd.read_csv(analysis_dir / "process_step_action_distribution.csv")
    process_conditions_orig = pd.read_csv(analysis_dir / "process_condition_distribution.csv")
    canonical_key_by_category = pd.read_csv(analysis_dir / "canonical_key_by_category.csv")
    sample_parameter_long = pd.read_csv(analysis_dir / "sample_parameter_long.csv")
    parameter_cooccurrence_edges = pd.read_csv(analysis_dir / "parameter_cooccurrence_edges.csv")
    parameter_distribution = pd.read_csv(analysis_dir / "parameter_distribution.csv")
    paper_stage3_summary = pd.read_csv(analysis_dir / "paper_stage3_summary.csv")
    stage3_summary = json.loads((analysis_dir / "stage3_analysis_summary.json").read_text(encoding="utf-8"))

    print("Scanning process_steps.jsonl for action canonicalization...")
    steps_df = scan_process_steps_from_source(manifest_rows, stage3_subdir)

    figure_records: list[dict[str, Any]] = []

    # ---- 1. Action distribution ----
    print("[1/12] Action distribution...")
    action_cleaned = build_cleaned_action_distribution(steps_df)
    write_dataframe(action_cleaned, output_dir / "process_step_action_distribution_cleaned.csv")
    plot_action_distribution_pubstyle(action_cleaned, figures_dir / "process_step_action_distribution_cleaned")
    figure_records.append({"name": "process_step_action_distribution_cleaned", "N": int(action_cleaned["count"].sum())})

    old_other = int(process_action_orig.loc[process_action_orig["action"] == "other", "count"].sum()) if "other" in process_action_orig["action"].values else 0
    new_other = int(action_cleaned.loc[action_cleaned["action"] == "other", "count"].sum()) if not action_cleaned.empty else 0

    # ---- 2. Time condition distributions ----
    print("[2/12] Time condition distributions...")
    time_cond_df, time_outliers = build_time_condition_distribution(steps_df, process_conditions_orig)
    write_dataframe(time_cond_df, output_dir / "time_condition_distribution_by_type.csv")
    if time_outliers:
        pd.DataFrame(time_outliers).to_csv(output_dir / "time_condition_outliers.csv", index=False, encoding="utf-8-sig")
    plot_time_condition_by_type_pubstyle(time_cond_df, figures_dir / "time_condition_distribution_by_type")
    figure_records.append({"name": "time_condition_distribution_by_type", "N": len(time_cond_df)})

    # ---- 3. Heating rate ----
    print("[3/12] Heating rate distribution...")
    hr_df, hr_outliers = build_heating_rate_distribution(process_conditions_orig)
    write_dataframe(hr_df, output_dir / "heating_rate_cleaned.csv")
    if not hr_outliers.empty:
        write_dataframe(hr_outliers, output_dir / "heating_rate_outliers.csv")
    plot_heating_rate_pubstyle(hr_df, hr_outliers, figures_dir / "heating_rate_distribution")
    figure_records.append({"name": "heating_rate_distribution", "N": len(hr_df)})

    # ---- 4-6. Temperature distributions ----
    print("[4-6/12] Temperature distributions...")
    calc_df, sinter_df, temp_outliers = build_temperature_distributions(process_conditions_orig)
    write_dataframe(calc_df, output_dir / "calcination_temperature_cleaned.csv")
    write_dataframe(sinter_df, output_dir / "sintering_temperature_cleaned.csv")
    if not temp_outliers.empty:
        write_dataframe(temp_outliers, output_dir / "temperature_outliers.csv")
    plot_calcination_temperature_pubstyle(calc_df, figures_dir / "calcination_temperature_distribution")
    plot_sintering_temperature_pubstyle(sinter_df, figures_dir / "sintering_temperature_distribution")
    plot_calcination_sintering_overlay_pubstyle(calc_df, sinter_df, figures_dir / "calcination_sintering_temperature_overlay")
    figure_records.extend([
        {"name": "calcination_temperature_distribution", "N": len(calc_df)},
        {"name": "sintering_temperature_distribution", "N": len(sinter_df)},
        {"name": "calcination_sintering_temperature_overlay", "N": len(calc_df) + len(sinter_df)},
    ])

    # ---- 7-8. Transition diagram (2 versions) ----
    print("[7-8/12] Process route transition diagrams...")
    transitions_df = build_real_transitions(steps_df)
    write_dataframe(transitions_df, output_dir / "transition_edges.csv")
    plot_transition_diagram_simplified_pubstyle(transitions_df, figures_dir / "process_route_transition_diagram_simplified")
    plot_transition_diagram_analysis_pubstyle(transitions_df, figures_dir / "process_route_transition_diagram_analysis")
    figure_records.extend([
        {"name": "process_route_transition_diagram_simplified", "N": int(transitions_df["count"].sum()) if not transitions_df.empty else 0},
        {"name": "process_route_transition_diagram_analysis", "N": int(transitions_df["count"].sum()) if not transitions_df.empty else 0},
    ])

    # ---- 9. Parameter co-occurrence network ----
    print("[9/12] Parameter co-occurrence network...")
    network_edges, network_summary = build_cleaned_network(parameter_cooccurrence_edges, parameter_distribution, sample_parameter_long)
    write_dataframe(network_edges, output_dir / "parameter_cooccurrence_edges_top.csv")
    (output_dir / "network_summary.json").write_text(json.dumps(network_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_cleaned_network_pubstyle(network_edges, parameter_distribution, network_summary,
                                  figures_dir / "parameter_cooccurrence_network_cleaned")
    figure_records.append({"name": "parameter_cooccurrence_network_cleaned", "N": network_summary.get("n_nodes", 0)})

    # ---- 10. Sample-parameter matrix ----
    print("[10/12] Sample-parameter matrix heatmap...")
    matrix_df, matrix_summary = build_sample_parameter_matrix_ppt_v2(sample_parameter_long, parameter_distribution, paper_limit)
    (output_dir / "sample_parameter_matrix_summary.json").write_text(json.dumps(matrix_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_sample_parameter_matrix_pubstyle(matrix_df, figures_dir / "sample_parameter_matrix_sparsity_heatmap_ppt")
    figure_records.append({"name": "sample_parameter_matrix_sparsity_heatmap_ppt", "N": f"{matrix_summary.get('matrix_shape', ['?','?'])[0]}×{matrix_summary.get('matrix_shape', ['?','?'])[1]}"})

    # ---- 11-12. Canonical key × category heatmaps ----
    print("[11-12/12] Canonical key × category heatmaps...")
    plot_count_heatmap_pubstyle(canonical_key_by_category, figures_dir / "canonical_key_category_heatmap_top20_count", min(20, top_n))
    plot_normalized_heatmap_pubstyle(canonical_key_by_category, figures_dir / "canonical_key_category_heatmap_top20_normalized", min(20, top_n))
    totals = canonical_key_by_category.groupby("canonical_key")["count"].sum().sort_values(ascending=False)
    top_keys = totals.head(min(20, top_n)).index.tolist()
    subset = canonical_key_by_category[canonical_key_by_category["canonical_key"].isin(top_keys)].copy()
    write_dataframe(subset, output_dir / "canonical_key_category_summary.csv")
    figure_records.append({"name": "canonical_key_category_heatmap_top20_count", "N": 5683})
    figure_records.append({"name": "canonical_key_category_heatmap_top20_normalized", "N": 5683})

    # ---- 13. Overview dashboard ----
    print("[Dashboard] Overview dashboard...")
    plot_overview_dashboard_pubstyle(stage3_summary, parameter_distribution, action_cleaned, paper_stage3_summary,
                                     figures_dir / "stage3_overview_dashboard")
    figure_records.append({"name": "stage3_overview_dashboard", "N": stage3_summary.get("total_papers", "—")})

    # ---- Summary ----
    summary_output = {
        "title": "Stage 3 Publication-Style Figures — Summary",
        "output_directory": str(output_dir),
        "figures_directory": str(figures_dir),
        "figures_generated": figure_records,
        "total_figures": len(figure_records),
        "style_config": {
            "colors": {"blue_main": CFG.blue_main, "green": CFG.green, "orange": CFG.orange,
                       "purple": CFG.purple, "gray": CFG.gray},
            "dpi": CFG.dpi,
            "formats": list(CFG.formats),
            "font_candidates": list(CFG.font_candidates),
        },
        "action_cleaned_total": int(action_cleaned["count"].sum()) if not action_cleaned.empty else 0,
        "old_other_count": old_other,
        "new_other_count": new_other,
    }
    (output_dir / "pubstyle_summary.json").write_text(json.dumps(summary_output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone! Output written to: {output_dir}")
    print(f"  Figures: {figures_dir}")
    print(f"  Total figures: {len(figure_records)}")
    return summary_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate publication-quality Stage 3 figures")
    parser.add_argument("--manifest", default="data/batch_manifest/source_manifest.csv")
    parser.add_argument("--analysis-dir", default="data/analysis_outputs_stage3")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--output-dir", default="data/analysis_outputs_stage3_pubstyle")
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--top-n", default=30, type=int)
    parser.add_argument("--paper-limit", default=50, type=int, help="Max papers for matrix heatmap rows")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = resolve_path(args.manifest)
    analysis_dir = resolve_path(args.analysis_dir)
    outputs_dir = resolve_path(args.outputs_dir)
    output_dir = resolve_path(args.output_dir)

    build_pubstyle_figures(
        manifest_path=manifest_path,
        analysis_dir=analysis_dir,
        outputs_dir=outputs_dir,
        output_dir=output_dir,
        stage3_subdir=args.stage3_subdir,
        top_n=args.top_n,
        paper_limit=args.paper_limit,
    )


if __name__ == "__main__":
    main()
