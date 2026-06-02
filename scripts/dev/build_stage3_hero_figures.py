"""
Stage 3 Hero Figures — Publication-quality presentation figures.
Reads from existing CSV/JSON data only. No data processing logic changed.

Output: data/analysis_outputs_stage3_hero/
Formats: PNG (300 dpi) + SVG + PDF
Layout: 16:9 PPT ratio for all figures
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from scipy import stats as scipy_stats


# ============================================================================
# Design system
# ============================================================================

class HERO:
    """Hero figure design tokens."""

    # Palette
    navy: str = "#17324D"
    steel: str = "#4F7EA8"
    teal: str = "#4E9A8E"
    orange: str = "#D98945"
    green: str = "#7FA66A"
    bg: str = "#F7F9FC"
    grid: str = "#D8DEE8"
    text: str = "#2B3A4A"
    text_light: str = "#6B7A8A"
    white: str = "#FFFFFF"
    accent_gold: str = "#C8A44E"
    accent_red: str = "#C4685A"

    # Typography
    fonts: tuple = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
                     "Arial", "DejaVu Sans", "sans-serif")
    title: int = 18
    h1: int = 16
    h2: int = 13
    h3: int = 11
    body: int = 9
    small: int = 7.5
    kpi_num: int = 36
    kpi_label: int = 10

    # Layout
    dpi: int = 300
    ratio_16_9: tuple = (16, 9)

    # Output
    formats: tuple = (".png", ".svg", ".pdf")


def _configure() -> None:
    installed = {f.name for f in fm.fontManager.ttflist}
    chain = [c for c in HERO.fonts if c in installed] or ["sans-serif"]
    plt.rcParams.update({
        "font.sans-serif": chain,
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "figure.facecolor": HERO.white,
        "axes.facecolor": HERO.white,
        "savefig.facecolor": HERO.white,
        "axes.edgecolor": HERO.grid,
        "axes.linewidth": 0.6,
        "grid.color": HERO.grid,
        "grid.alpha": 0.4,
        "grid.linestyle": "-",
        "text.color": HERO.text,
        "axes.labelcolor": HERO.text,
        "xtick.color": HERO.text,
        "ytick.color": HERO.text,
        "font.size": HERO.body,
        "axes.titlesize": HERO.h2,
        "axes.labelsize": HERO.h3,
        "xtick.labelsize": HERO.small,
        "ytick.labelsize": HERO.small,
        "legend.fontsize": HERO.small,
        "figure.dpi": HERO.dpi,
        "savefig.dpi": HERO.dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.12,
    })


def _save(fig: plt.Figure, stem: Path) -> None:
    fig.set_constrained_layout(False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.tight_layout(pad=1.5, h_pad=1.0, w_pad=1.0)
    for fmt in HERO.formats:
        fig.savefig(str(stem.with_suffix(fmt)), dpi=HERO.dpi, bbox_inches="tight",
                    facecolor=HERO.white, edgecolor="none")
    plt.close(fig)


def _safe_unit(text: str) -> str:
    """Replace special Unicode that may render as tofu."""
    return (text.replace("℃", "C").replace("°C", "C").replace("°", "deg ")
            .replace("⁻¹", "^-1").replace("⁻¹", "^-1")
            .replace("²", "2").replace("²", "2")
            .replace("μm", "um").replace("µm", "um")
            .replace("·", ".").replace("·", "."))


def _add_margin(fig: plt.Figure, top_inches: float = 1.2) -> None:
    """Add top margin for title block."""
    fig.subplots_adjust(top=0.88)


# ============================================================================
# Utility: load data
# ============================================================================

DATA = Path("data/analysis_outputs_stage3_v2")
STAGE3 = Path("data/analysis_outputs_stage3")
HERO_DIR = Path("data/analysis_outputs_stage3_hero")
FIG_DIR = HERO_DIR / "figures"


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA / name
    if path.exists():
        return pd.read_csv(path)
    alt = STAGE3 / name
    if alt.exists():
        return pd.read_csv(alt)
    raise FileNotFoundError(f"Neither {path} nor {alt} exists")


def _read_json(name: str) -> dict:
    path = DATA / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    alt = STAGE3 / name
    if alt.exists():
        return json.loads(alt.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Neither {path} nor {alt} exists")


# ============================================================================
# Action → Stage mapping (mirrors build_stage3)
# ============================================================================

_ACTION_TO_STAGE: dict[str, str] = {
    "add": "sol_prep", "mix": "sol_prep", "dissolve": "sol_prep",
    "hydrolyze": "sol_prep", "peptize": "sol_prep",
    "age": "aging_concentration", "aging": "aging_concentration",
    "concentrate": "aging_concentration", "evaporate": "aging_concentration",
    "rotary_evaporate": "aging_concentration",
    "spin": "spinning", "electrospin": "spinning",
    "dry": "drying",
    "calcine": "calcination_sintering", "sinter": "calcination_sintering",
    "heat": "calcination_sintering",
    "characterize": "characterization", "measure": "characterization",
    "stir": "sol_prep", "filter": "sol_prep", "cool": "aging_concentration",
    "gelation": "aging_concentration", "gel": "aging_concentration",
}

_STAGE_ORDER = ["sol_prep", "aging_concentration", "spinning", "drying",
                "calcination_sintering", "characterization"]
_STAGE_LABELS = {
    "sol_prep": "Sol Preparation",
    "aging_concentration": "Aging &\nConcentration",
    "spinning": "Spinning",
    "drying": "Drying",
    "calcination_sintering": "Calcination\n& Sintering",
    "characterization": "Characterization",
}

# Parameter type mapping
_PARAM_TYPE = {
    "calcination_temperature_C": "process",
    "sintering_temperature_C": "process",
    "heating_rate_C_min": "process",
    "drying_temperature_C": "process",
    "hydrolysis_temperature_C": "process",
    "aging_temperature_C": "process",
    "holding_time_h": "process",
    "aging_time_h": "process",
    "drying_time_h": "process",
    "stirring_time_h": "process",
    "calcination_holding_time_h": "process",
    "sintering_holding_time_h": "process",
    "pH": "synthesis",
    "Al_concentration_mol_L": "synthesis",
    "solid_content_wt_percent": "synthesis",
    "water_to_aluminum_molar_ratio": "synthesis",
    "acid_to_aluminum_molar_ratio": "synthesis",
    "particle_size_nm": "structure",
    "crystallite_size_nm": "structure",
    "average_fiber_diameter_um": "structure",
    "average_pore_size_nm": "structure",
    "pore_volume_cm3_g": "structure",
    "specific_surface_area_m2_g": "structure",
    "porosity_percent": "structure",
    "density_g_cm3": "structure",
    "shrinkage_percent": "structure",
    "tensile_strength_MPa": "property",
    "elastic_modulus_GPa": "property",
    "elongation_at_break_percent": "property",
    "thermal_conductivity_W_mK": "property",
    "viscosity_Pa_s": "property",
    "mass_loss_wt_percent": "property",
    "zeta_potential_mV": "property",
    "nmr_27Al_peak_position_ppm": "characterization",
    "ftir_peak_position_cm_1": "characterization",
    "xrd_peak_position_2theta_deg": "characterization",
    "raman_peak_position_cm_1": "characterization",
    "dsc_peak_temperature_C": "characterization",
}

_TYPE_COLORS = {
    "synthesis": HERO.steel,
    "process": HERO.navy,
    "structure": HERO.teal,
    "property": HERO.orange,
    "characterization": HERO.green,
    "other": HERO.text_light,
}

_TYPE_ORDER = ["synthesis", "process", "structure", "property", "characterization", "other"]


def _type_label(key: str) -> str:
    return _PARAM_TYPE.get(key, "other")


def _shorten(key: str) -> str:
    """Short label for a canonical key."""
    mapping = {
        "nmr_27Al_peak_position_ppm": "27Al NMR shift",
        "pH": "pH",
        "particle_size_nm": "Particle size",
        "ftir_peak_position_cm_1": "FTIR peak",
        "Al_concentration_mol_L": "Al concentration",
        "calcination_temperature_C": "Calcin. temp",
        "sintering_temperature_C": "Sinter. temp",
        "mass_loss_wt_percent": "Mass loss",
        "aging_time_h": "Aging time",
        "specific_surface_area_m2_g": "BET surface area",
        "heating_rate_C_min": "Heating rate",
        "aging_temperature_C": "Aging temp",
        "holding_time_h": "Holding time",
        "dsc_peak_temperature_C": "DSC peak temp",
        "solid_content_wt_percent": "Solid content",
        "average_fiber_diameter_um": "Fiber diameter",
        "average_fiber_diameter_nm": "Fiber diameter",
        "viscosity_Pa_s": "Viscosity",
        "tensile_strength_MPa": "Tensile strength",
        "hydrolysis_temperature_C": "Hydrolysis temp",
        "drying_temperature_C": "Drying temp",
        "drying_time_h": "Drying time",
        "xrd_peak_position_2theta_deg": "XRD 2theta",
        "raman_peak_position_cm_1": "Raman shift",
        "pore_volume_cm3_g": "Pore volume",
        "average_pore_size_nm": "Pore size",
        "crystallite_size_nm": "Crystallite size",
        "spinnability": "Spinnability",
        "zeta_potential_mV": "Zeta potential",
        "water_to_aluminum_molar_ratio": "H2O/Al ratio",
        "acid_to_aluminum_molar_ratio": "Acid/Al ratio",
        "stirring_time_h": "Stirring time",
        "hydrolysis_time_h": "Hydrolysis time",
        "calcination_holding_time_h": "Calcin. hold time",
        "sintering_holding_time_h": "Sinter. hold time",
        "elastic_modulus_GPa": "Elastic modulus",
        "elongation_at_break_percent": "Elongation",
        "thermal_conductivity_W_mK": "Thermal conductivity",
        "porosity_percent": "Porosity",
        "shrinkage_percent": "Shrinkage",
        "density_g_cm3": "Density",
    }
    if key in mapping:
        return mapping[key]
    words = key.replace("_", " ").replace("percent", "%").split()
    return " ".join(words[:3])


# ============================================================================
# Figure 1: HERO OVERVIEW INFOGRAPHIC
# ============================================================================

def figure_1_hero_overview(output_dir: Path) -> None:
    """Infographic overview — like a graphical abstract, not a dashboard."""
    print("[1/5] Hero overview infographic...")
    summary = _read_json("analysis_outputs_stage3_summary.json")

    fig = plt.figure(figsize=(16, 9), facecolor=HERO.white)
    # Add a subtle background band at top
    gs = GridSpec(20, 30, figure=fig, hspace=0.6, wspace=0.6)

    # ---- Top title block ----
    ax_title = fig.add_subplot(gs[0:2, 1:29])
    ax_title.axis("off")
    ax_title.text(0, 0.7, "Stage 3 Literature Extraction at Scale",
                  fontsize=HERO.title, fontweight="bold", color=HERO.navy, va="center")
    ax_title.text(0, 0.15, "Systematic extraction of synthesis parameters from 343 alumina sol-gel papers",
                  fontsize=HERO.h3, color=HERO.text_light, va="center")

    # ---- KPI cards row (6 cards) ----
    kpis = [
        ("343", "Papers", HERO.navy),
        ("5,683", "Data points", HERO.steel),
        ("2,819", "Process steps", HERO.teal),
        ("3,289", "Evidence passages", HERO.orange),
        ("102", "Unique canonical keys", HERO.green),
        ("24", "Normalized actions", HERO.accent_gold),
    ]

    for i, (num, label, color) in enumerate(kpis):
        col = i * 5 + 1
        ax = fig.add_subplot(gs[2:5, col:col + 4])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Subtle card background
        card = mpatches.FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                        boxstyle="round,pad=0.04,rounding_size=0.04",
                                        facecolor=HERO.bg, edgecolor=HERO.grid, linewidth=0.6)
        ax.add_patch(card)

        # Accent line
        line = mpatches.Rectangle((0.2, 0.82), 0.6, 0.025, facecolor=color, linewidth=0, zorder=3)
        ax.add_patch(line)

        ax.text(0.5, 0.55, num, ha="center", va="center", fontsize=HERO.kpi_num,
                fontweight="bold", color=color)
        ax.text(0.5, 0.15, label, ha="center", va="center", fontsize=HERO.kpi_label,
                color=HERO.text_light)

    # ---- Three summary panels (rows 6-19) ----
    # Panel 1: What was extracted
    ax1 = fig.add_subplot(gs[6:19, 1:10])
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.axis("off")
    ax1.text(0.05, 0.92, "WHAT WAS EXTRACTED", fontsize=HERO.h1 - 2, fontweight="bold",
             color=HERO.navy, va="top")
    ax1.text(0.05, 0.84, "From full-text PDFs and supplementary materials",
             fontsize=HERO.small, color=HERO.text_light, va="top")

    items1 = [("5,683", "Structured data points", HERO.steel),
              ("3,289", "Evidence passages with context", HERO.orange),
              ("2,819", "Process step descriptions", HERO.teal)]
    for j, (num, desc, color) in enumerate(items1):
        y = 0.68 - j * 0.22
        # Circle
        circle = mpatches.Ellipse((0.12, y + 0.06), 0.10, 0.10, facecolor=color, alpha=0.15,
                                  edgecolor=color, linewidth=1.5, transform=ax1.transAxes)
        ax1.add_patch(circle)
        ax1.text(0.12, y + 0.06, num, ha="center", va="center", fontsize=HERO.h1 - 2,
                 fontweight="bold", color=color, transform=ax1.transAxes)
        ax1.text(0.21, y + 0.08, desc, fontsize=HERO.body, color=HERO.text, va="center",
                 transform=ax1.transAxes)

    # Panel 2: What was normalized
    ax2 = fig.add_subplot(gs[6:19, 10:20])
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.axis("off")
    ax2.text(0.05, 0.92, "WHAT WAS NORMALIZED", fontsize=HERO.h1 - 2, fontweight="bold",
             color=HERO.navy, va="top")
    ax2.text(0.05, 0.84, "Ontology-driven mapping and cleaning",
             fontsize=HERO.small, color=HERO.text_light, va="top")

    items2 = [("102", "Unique canonical parameter keys across ontology", HERO.green),
              ("73 → 24", "Raw actions reduced (68% cleaner)", HERO.accent_gold),
              ("671 → 215", "'Other' steps reclassified", HERO.accent_red)]
    for j, (num, desc, color) in enumerate(items2):
        y = 0.68 - j * 0.18
        ax2.text(0.08, y, num, fontsize=HERO.h2, fontweight="bold", color=color,
                 transform=ax2.transAxes)
        ax2.text(0.08, y - 0.07, desc, fontsize=HERO.body, color=HERO.text_light,
                 transform=ax2.transAxes)
        # Thin separator
        if j < 2:
            ax2.plot([0.05, 0.95], [y - 0.13, y - 0.13], color=HERO.grid, linewidth=0.5,
                     transform=ax2.transAxes, clip_on=False)

    # Panel 3: Why it matters
    ax3 = fig.add_subplot(gs[6:19, 20:29])
    ax3.set_xlim(0, 1)
    ax3.set_ylim(0, 1)
    ax3.axis("off")
    ax3.text(0.05, 0.92, "WHY IT MATTERS", fontsize=HERO.h1 - 2, fontweight="bold",
             color=HERO.navy, va="top")
    ax3.text(0.05, 0.84, "Analysis-ready structured dataset",
             fontsize=HERO.small, color=HERO.text_light, va="top")

    why_items = [
        "343 papers x 30 parameters = 10,290-cell matrix",
        "33% coverage density across parameter space",
        "Enables meta-analysis of synthesis-structure-property relationships",
        "12 co-occurrence network modules identified",
        "Process route atlas for alumina sol-gel synthesis",
    ]
    for j, item in enumerate(why_items):
        y = 0.70 - j * 0.09
        ax3.plot(0.08, y, "o", color=HERO.steel, markersize=4, transform=ax3.transAxes)
        ax3.text(0.13, y, item, fontsize=HERO.body - 0.5, color=HERO.text, va="center",
                 transform=ax3.transAxes)

    # Source note
    fig.text(0.02, 0.015, "Source: Stage 3 batch extraction pipeline → process_steps.jsonl / schema_v2.json",
             fontsize=HERO.small - 1, color=HERO.text_light, style="italic")

    _add_margin(fig)
    _save(fig, output_dir / "stage3_hero_overview")
    print("  -> stage3_hero_overview saved")


# ============================================================================
# Figure 2: PROCESS ROUTE ALLUVIAL / FLOW
# ============================================================================

def figure_2_process_route_alluvial(output_dir: Path) -> None:
    """Alluvial-style flow diagram using bezier curves for process transitions."""
    print("[2/5] Process route alluvial...")
    transitions = _read_csv("transition_edges.csv")

    # Aggregate from action-level to stage-level
    stage_flows: dict[tuple[str, str], int] = defaultdict(int)
    for _, row in transitions.iterrows():
        src_a = str(row["source_action"])
        tgt_a = str(row["target_action"])
        src_s = _ACTION_TO_STAGE.get(src_a, "other")
        tgt_s = _ACTION_TO_STAGE.get(tgt_a, "other")
        if src_s != tgt_s and src_s in _STAGE_ORDER and tgt_s in _STAGE_ORDER:
            stage_flows[(src_s, tgt_s)] += int(row["count"])

    # Filter: keep only flows >= threshold
    if stage_flows:
        threshold = max(10, sorted(stage_flows.values(), reverse=True)[min(len(stage_flows) - 1, 15)])
        filtered = {k: v for k, v in stage_flows.items() if v >= threshold}
    else:
        filtered = {}

    fig = plt.figure(figsize=(16, 9), facecolor=HERO.white)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 1)
    ax.set_ylim(0.05, 0.85)
    ax.axis("off")

    n_stages = len(_STAGE_ORDER)
    stage_x = {s: 0.08 + 0.84 * i / (n_stages - 1) for i, s in enumerate(_STAGE_ORDER)}
    node_width = 0.07
    max_flow = max(filtered.values()) if filtered else 1

    # Draw stage nodes (vertical capsules)
    for stage in _STAGE_ORDER:
        x = stage_x[stage]
        rect = mpatches.FancyBboxPatch((x - node_width / 2, 0.35 - 0.10), node_width, 0.20,
                                        boxstyle="round,pad=0.02,rounding_size=0.03",
                                        facecolor=HERO.bg, edgecolor=HERO.navy, linewidth=1.5, zorder=5)
        ax.add_patch(rect)
        ax.text(x, 0.45, _STAGE_LABELS[stage], ha="center", va="center",
                fontsize=HERO.body - 1, color=HERO.navy, fontweight="bold", zorder=6,
                transform=ax.transAxes)

    # Draw flows as bezier curves
    colors_flow = [HERO.steel, HERO.teal, HERO.orange, HERO.green]
    for idx, ((src, tgt), count) in enumerate(sorted(filtered.items(), key=lambda x: -x[1])):
        x1 = stage_x[src] + node_width / 2
        x2 = stage_x[tgt] - node_width / 2
        is_forward = _STAGE_ORDER.index(src) < _STAGE_ORDER.index(tgt)
        color = colors_flow[idx % len(colors_flow)] if is_forward else HERO.accent_red
        alpha = 0.5 + 0.3 * (count / max_flow)
        lw = 1.5 + 6.0 * (count / max_flow)

        y_off = 0.03 * (idx % 5 - 2)
        mid_y = 0.45 + y_off
        ctrl_y = mid_y + 0.08 * (-1)**idx

        bezier_path = mpath.Path(
            [(x1, 0.45), (x1 + (x2 - x1) * 0.5, ctrl_y), (x2, 0.45)],
            [mpath.Path.MOVETO, mpath.Path.CURVE3, mpath.Path.CURVE3])
        patch = mpatches.PathPatch(bezier_path, facecolor="none", edgecolor=color,
                                    linewidth=lw, alpha=alpha, zorder=1)
        ax.add_patch(patch)

        # Flow label
        label_x = (x1 + x2) / 2
        ax.text(label_x, ctrl_y + 0.015, str(count), ha="center", va="bottom",
                fontsize=HERO.small - 1.5, color=color, alpha=alpha + 0.1, fontweight="bold",
                transform=ax.transAxes, zorder=4)

    ax.text(0.5, 0.02, "Major transition patterns reconstructed from step_order in process_steps.jsonl",
            ha="center", va="center", fontsize=HERO.small - 1, color=HERO.text_light,
            style="italic", transform=ax.transAxes)
    fig.text(0.02, 0.005, "Source: transition_edges.csv (221 raw edges, thresholded for clarity)",
             fontsize=HERO.small - 1, color=HERO.text_light, style="italic")

    _add_margin(fig)
    _save(fig, output_dir / "stage3_process_route_alluvial")
    print("  -> stage3_process_route_alluvial saved")


# ============================================================================
# Figure 3: PROCESS ACTION LANDSCAPE (Lollipop chart)
# ============================================================================

def figure_3_process_action_landscape(output_dir: Path) -> None:
    """Lollipop chart showing top actions with group coloring."""
    print("[3/5] Process action landscape...")
    action_df = _read_csv("process_step_action_distribution_cleaned.csv")

    # Sort descending, take top 12
    df = action_df.nlargest(12, "count").copy()
    df = df.iloc[::-1]  # Reverse for bottom-to-top display
    total = int(action_df["count"].sum())

    # Map each action to a stage for coloring
    action_stage: dict[str, str] = {
        "add": "sol_prep", "mix": "sol_prep", "dissolve": "sol_prep",
        "hydrolyze": "sol_prep", "stir": "sol_prep", "filter": "sol_prep",
        "age": "aging_concentration", "concentrate": "aging_concentration",
        "gelation": "aging_concentration", "cool": "aging_concentration",
        "spin": "spinning",
        "dry": "drying",
        "calcine": "calcination_sintering", "sinter": "calcination_sintering",
        "heat": "calcination_sintering",
        "characterize": "characterization",
    }
    stage_colors = {
        "sol_prep": HERO.steel,
        "aging_concentration": HERO.teal,
        "spinning": HERO.navy,
        "drying": HERO.orange,
        "calcination_sintering": HERO.accent_red,
        "characterization": HERO.green,
    }

    actions = df["action"].tolist()
    counts = df["count"].tolist()
    colors = [stage_colors.get(action_stage.get(a, ""), HERO.text_light) for a in actions]

    fig = plt.figure(figsize=(16, 9), facecolor=HERO.white)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[3, 1], wspace=0.2)

    # Main lollipop chart
    ax = fig.add_subplot(gs[0, 0])
    y_positions = range(len(actions))
    max_count = max(counts)

    # Lollipop stems
    for y, count, color in zip(y_positions, counts, colors):
        ax.plot([0, count], [y, y], color=color, linewidth=1.8, alpha=0.6, zorder=2)
    # Lollipop heads
    ax.scatter(counts, y_positions, s=120, c=colors, edgecolors="white", linewidth=1.5, zorder=3)

    # Value labels
    for y, count in zip(y_positions, counts):
        pct = count / total * 100
        ax.text(count + max_count * 0.02, y, f"{count}  ({pct:.1f}%)",
                va="center", fontsize=HERO.body, color=HERO.text, fontweight="bold")

    # Y-axis labels
    zh = {"add": "Add/Mix", "spin": "Spin", "stir": "Stir", "heat": "Heat",
          "dry": "Dry", "dissolve": "Dissolve", "age": "Age", "hydrolyze": "Hydrolyze",
          "calcine": "Calcine", "characterize": "Characterize", "concentrate": "Concentrate",
          "filter": "Filter", "cool": "Cool", "sinter": "Sinter", "gelation": "Gelation"}
    labels_y = [f"{a}  ({zh.get(a, a)})" for a in actions]
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(labels_y, fontsize=HERO.body + 1)
    ax.set_xlim(0, max_count * 1.28)
    ax.set_ylim(-0.8, len(actions) - 0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(HERO.grid)
    ax.spines["bottom"].set_color(HERO.grid)
    ax.grid(axis="x", color=HERO.grid, linewidth=0.4, alpha=0.6)
    ax.tick_params(axis="x", labelsize=HERO.body)
    ax.set_xlabel("Number of process steps", fontsize=HERO.h3, color=HERO.text_light)

    # Right panel: stage legend
    ax_leg = fig.add_subplot(gs[0, 1])
    ax_leg.set_xlim(0, 1)
    ax_leg.set_ylim(0, 1)
    ax_leg.axis("off")

    stage_names = {
        "sol_prep": "Sol Preparation\n(add, stir, dissolve, hydrolyze, filter)",
        "aging_concentration": "Aging & Concentration\n(age, concentrate, gelation, cool)",
        "spinning": "Spinning\n(spin)",
        "drying": "Drying\n(dry)",
        "calcination_sintering": "Thermal Treatment\n(calcine, sinter, heat)",
        "characterization": "Characterization\n(characterize)",
    }
    for j, (stage, label) in enumerate(stage_names.items()):
        y = 0.90 - j * 0.15
        color = stage_colors.get(stage, HERO.text_light)
        ax_leg.plot(0.05, y, "o", color=color, markersize=12, markeredgecolor="white",
                    markeredgewidth=1.5, transform=ax_leg.transAxes)
        ax_leg.text(0.15, y, label, fontsize=HERO.body - 1, color=HERO.text, va="center",
                    transform=ax_leg.transAxes)

    # Other count note
    other_count = int(action_df[~action_df["action"].isin(actions)]["count"].sum())
    ax_leg.text(0.05, 0.05, f"+ {other_count} steps in other actions",
                fontsize=HERO.small, color=HERO.text_light, style="italic", transform=ax_leg.transAxes)

    fig.text(0.02, 0.99, "Canonicalized Process Actions", fontsize=HERO.h1, fontweight="bold",
             color=HERO.navy, va="top")
    fig.text(0.02, 0.95, f"{total} extracted steps mapped to {action_df['action'].nunique()} normalized actions",
             fontsize=HERO.h3, color=HERO.text_light, va="top")
    fig.text(0.02, 0.01, "Source: process_step_action_distribution_cleaned.csv",
             fontsize=HERO.small - 1, color=HERO.text_light, style="italic")

    _save(fig, output_dir / "stage3_process_action_landscape")
    print("  -> stage3_process_action_landscape saved")


# ============================================================================
# Figure 4: THERMAL PROCESSING WINDOW (Raincloud)
# ============================================================================

def figure_4_thermal_processing_window(output_dir: Path) -> None:
    """Raincloud plot: density + box + strip for calcination vs sintering temperature."""
    print("[4/5] Thermal processing window...")
    calc = _read_csv("calcination_temperature_cleaned.csv")
    sinter = _read_csv("sintering_temperature_cleaned.csv")

    calc_vals = calc["temperature_C"].dropna().values
    sinter_vals = sinter["temperature_C"].dropna().values

    fig = plt.figure(figsize=(16, 9), facecolor=HERO.white)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[3, 1], hspace=0.3)

    # ---- Main raincloud ----
    ax = fig.add_subplot(gs[0, 0])
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlim(0, 1700)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.set_yticks([])

    datasets = [
        (calc_vals, "Calcination", HERO.steel, 0.2),
        (sinter_vals, "Sintering", HERO.green, 0.7),
    ]

    for vals, label, color, y_center in datasets:
        if len(vals) < 3:
            continue
        # KDE density (half violin)
        kde = scipy_stats.gaussian_kde(vals)
        x_range = np.linspace(vals.min() - 50, vals.max() + 50, 300)
        density = kde(x_range)
        density = density / density.max() * 0.25
        ax.fill_between(x_range, y_center, y_center + density, alpha=0.35, color=color, linewidth=0)
        ax.plot(x_range, y_center + density, color=color, linewidth=1.2, alpha=0.7)

        # Box plot (horizontal)
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        box_h = 0.06
        rect = mpatches.FancyBboxPatch((q1, y_center - box_h), q3 - q1, 2 * box_h,
                                        boxstyle="round,pad=0.01,rounding_size=0.01",
                                        facecolor=color, alpha=0.5, edgecolor=color, linewidth=1.2, zorder=5)
        ax.add_patch(rect)
        ax.plot([med, med], [y_center - box_h - 0.02, y_center + box_h + 0.02],
                color="white", linewidth=2, zorder=6)

        # Whiskers
        iqr = q3 - q1
        whisk_low = max(vals.min(), q1 - 1.5 * iqr)
        whisk_high = min(vals.max(), q3 + 1.5 * iqr)
        ax.plot([whisk_low, q1], [y_center, y_center], color=color, linewidth=1.0, zorder=4)
        ax.plot([q3, whisk_high], [y_center, y_center], color=color, linewidth=1.0, zorder=4)

        # Strip points (jittered)
        jitter = np.random.default_rng(42).uniform(-0.04, 0.04, len(vals))
        ax.scatter(vals, np.full_like(vals, y_center - 0.10) + jitter,
                   s=8, c=color, alpha=0.25, edgecolors="none", zorder=2)

        # Stats label
        ax.text(1650, y_center + 0.00, f"{label}\nn = {len(vals)}\nmedian = {med:.0f} C\nIQR = {q1:.0f}–{q3:.0f} C",
                ha="right", va="center", fontsize=HERO.body - 0.5, color=HERO.text,
                fontweight="bold")

    ax.set_xlabel("Temperature (C)", fontsize=HERO.h3, color=HERO.text_light)
    ax.grid(axis="x", color=HERO.grid, linewidth=0.4, alpha=0.5)
    ax.tick_params(axis="x", labelsize=HERO.body)
    ax.text(0.01, 1.08, "Thermal Processing Window", transform=ax.transAxes,
            fontsize=HERO.h1, fontweight="bold", color=HERO.navy, va="bottom")

    # ---- Bottom: compact histogram ----
    ax_hist = fig.add_subplot(gs[1, 0])
    bins = np.linspace(0, 1700, 25)
    ax_hist.hist(calc_vals, bins=bins, alpha=0.5, color=HERO.steel, edgecolor="white", linewidth=0.3)
    ax_hist.hist(sinter_vals, bins=bins, alpha=0.5, color=HERO.green, edgecolor="white", linewidth=0.3)
    ax_hist.spines["top"].set_visible(False)
    ax_hist.spines["right"].set_visible(False)
    ax_hist.set_xlabel("Temperature (C)", fontsize=HERO.h3, color=HERO.text_light)
    ax_hist.set_ylabel("Count", fontsize=HERO.h3, color=HERO.text_light)
    ax_hist.grid(axis="y", color=HERO.grid, linewidth=0.4, alpha=0.5)
    ax_hist.tick_params(labelsize=HERO.body)

    fig.text(0.02, 0.01, "Source: calcination_temperature_cleaned.csv / sintering_temperature_cleaned.csv",
             fontsize=HERO.small - 1, color=HERO.text_light, style="italic")

    _save(fig, output_dir / "stage3_thermal_processing_window")
    print("  -> stage3_thermal_processing_window saved")


# ============================================================================
# Figure 5: PARAMETER COVERAGE FINGERPRINT
# ============================================================================

def figure_5_parameter_coverage_fingerprint(output_dir: Path) -> None:
    """Curated heatmap: top 25 papers x top 25 parameters with category bands."""
    print("[5/5] Parameter coverage fingerprint...")
    sample_long = pd.read_csv(STAGE3 / "sample_parameter_long.csv")
    matrix_summary = _read_json("sample_parameter_matrix_summary.json")

    # Get top papers and parameters by coverage
    paper_fills = sample_long.groupby("paper_id")["canonical_key"].nunique().sort_values(ascending=False)
    param_fills = sample_long.groupby("canonical_key")["paper_id"].nunique().sort_values(ascending=False)

    top_n_papers = min(25, len(paper_fills))
    top_n_params = min(25, len(param_fills))
    top_papers = paper_fills.head(top_n_papers).index.tolist()
    top_params = param_fills.head(top_n_params).index.tolist()

    # Sort params by type then frequency
    param_types = {p: _type_label(p) for p in top_params}
    param_order = sorted(top_params, key=lambda p: (_TYPE_ORDER.index(param_types.get(p, "other")),
                                                     -param_fills.get(p, 0)))

    # Sort papers by category then density
    paper_cats = sample_long.groupby("paper_id")["category"].first()
    cat_order = {"fiber_process": 0, "mechanism": 1, "applications": 2, "rheology": 3}
    paper_sort = sorted(top_papers, key=lambda p: (cat_order.get(str(paper_cats.get(p, "")), 99),
                                                    -paper_fills.get(p, 0)))

    # Build matrix
    data = sample_long[sample_long["paper_id"].isin(paper_sort) & sample_long["canonical_key"].isin(param_order)]
    matrix = pd.crosstab(data["paper_id"], data["canonical_key"])
    matrix = matrix.reindex(index=paper_sort, columns=param_order).fillna(0).astype(int)
    matrix = (matrix > 0).astype(int)  # Binary

    density = matrix.values.sum() / matrix.values.size * 100

    # Short labels
    short_params = [_shorten(p) for p in param_order]
    short_papers = [str(p)[:18] for p in paper_sort]

    # Colors per parameter type
    param_colors = [_TYPE_COLORS.get(_type_label(p), HERO.text_light) for p in param_order]
    paper_cat_colors_map = {
        "fiber_process": HERO.navy, "mechanism": HERO.steel,
        "applications": HERO.teal, "rheology": HERO.orange,
    }

    fig = plt.figure(figsize=(16, 9), facecolor=HERO.white)
    gs = GridSpec(1, 3, figure=fig, width_ratios=[0.04, 1, 0.06], wspace=0.03)

    # Left: paper category bar
    ax_cat = fig.add_subplot(gs[0, 0])
    cat_data = []
    for p in paper_sort:
        cat = str(paper_cats.get(p, "unknown"))
        cat_data.append(cat_order.get(cat, 0))
    ax_cat.imshow(np.array(cat_data).reshape(-1, 1), aspect="auto",
                  cmap=plt.matplotlib.colors.ListedColormap(
                      [HERO.navy, HERO.steel, HERO.teal, HERO.orange]))
    ax_cat.set_xticks([])
    ax_cat.set_yticks([])

    # Main heatmap
    ax = fig.add_subplot(gs[0, 1])
    cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "navy_white", [HERO.white, HERO.steel, HERO.navy], N=256)
    ax.imshow(matrix.values, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")

    ax.set_xticks(range(len(short_params)))
    ax.set_xticklabels(short_params, rotation=45, ha="right", fontsize=HERO.small - 1.5, color=HERO.text)
    ax.set_yticks(range(len(short_papers)))
    ax.set_yticklabels(short_papers, fontsize=HERO.small - 2, color=HERO.text)

    # Color top x-axis labels by type
    for i, (label, color) in enumerate(zip(short_params, param_colors)):
        ax.get_xticklabels()[i].set_color(color)

    ax.tick_params(axis="x", which="both", length=2)
    ax.tick_params(axis="y", which="both", length=2)

    # Right: coverage density bar
    ax_density = fig.add_subplot(gs[0, 2])
    densities = matrix.sum(axis=1).values / len(param_order)
    ax_density.barh(range(len(densities)), densities, height=0.7, color=HERO.steel, alpha=0.7)
    ax_density.set_ylim(-0.5, len(densities) - 0.5)
    ax_density.set_xlim(0, 1)
    ax_density.invert_yaxis()
    ax_density.spines["top"].set_visible(False)
    ax_density.spines["right"].set_visible(False)
    ax_density.set_yticks([])
    ax_density.set_xlabel("Coverage", fontsize=HERO.small - 1, color=HERO.text_light)
    ax_density.tick_params(axis="x", labelsize=HERO.small - 1)

    # Add avg density line
    ax_density.axvline(x=density / 100, color=HERO.orange, linestyle="--", linewidth=1.0, alpha=0.7)
    ax_density.text(density / 100 + 0.02, len(densities) - 1, f"avg\n{density:.1f}%",
                    fontsize=HERO.small - 1, color=HERO.orange, va="top")

    fig.text(0.02, 0.99, "Sample-Parameter Coverage Fingerprint", fontsize=HERO.h1,
             fontweight="bold", color=HERO.navy, va="top")
    fig.text(0.02, 0.95, f"Top {top_n_papers} papers x {top_n_params} parameters  |  "
             f"Matrix density = {density:.1f}%  |  "
             f"Rows sorted by category + coverage  |  Columns sorted by parameter type",
             fontsize=HERO.h3, color=HERO.text_light, va="top")
    fig.text(0.02, 0.01, "Source: sample_parameter_long.csv → curated top papers × parameters",
             fontsize=HERO.small - 1, color=HERO.text_light, style="italic")

    _save(fig, output_dir / "stage3_parameter_coverage_fingerprint")
    print("  -> stage3_parameter_coverage_fingerprint saved")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Stage 3 Hero Figures")
    parser.add_argument("--output-dir", default="data/analysis_outputs_stage3_hero")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    figs_dir = output_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    _configure()
    print(f"Generating hero figures -> {output_dir}")

    figure_1_hero_overview(figs_dir)
    figure_2_process_route_alluvial(figs_dir)
    figure_3_process_action_landscape(figs_dir)
    figure_4_thermal_processing_window(figs_dir)
    figure_5_parameter_coverage_fingerprint(figs_dir)

    print(f"\nDone! {5} hero figures generated in {figs_dir}")


if __name__ == "__main__":
    main()
