"""
Stage 3 Publication Figures — Academic paper-quality figures.
Generates 4 main-text figures with unified publication rcParams.
Each figure outputs: PDF, SVG, 600 dpi PNG, plotting_data.csv, figure_caption.md.

Output: data/analysis_outputs_stage3_publication/
"""

from __future__ import annotations

import argparse
import json
import re
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
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from scipy import stats as scipy_stats

# ============================================================================
# Publication design system
# ============================================================================

class PUB:
    """Publication rcParams and design tokens. Academic journal style."""

    # ---- Color palette (colorblind-friendly, muted) ----
    blue: str = "#4472C4"
    orange: str = "#ED7D31"
    green: str = "#70AD47"
    red: str = "#C55A5A"
    teal: str = "#5D9A9E"
    purple: str = "#9B7CBC"
    gray: str = "#808080"
    dark_gray: str = "#505050"
    light_gray: str = "#B0B0B0"
    text: str = "#333333"
    white: str = "#FFFFFF"

    # Semantic colors
    color_synthesis: str = blue
    color_process: str = blue
    color_structure: str = teal
    color_property: str = orange
    color_char: str = green
    color_other: str = gray

    # Font stack
    font_candidates: tuple = ("Arial", "DejaVu Sans", "Noto Sans CJK SC",
                               "Microsoft YaHei", "SimHei", "sans-serif")

    # Font sizes (publication scale)
    base: int = 8
    small: int = 7
    tiny: int = 6
    label: int = 9
    panel: int = 9  # panel label like "a", "b"

    # Layout
    dpi: int = 600
    axis_lw: float = 0.6
    tick_len: float = 2.5
    tick_lw: float = 0.6
    grid_lw: float = 0.3

    # Figure sizes (Nature single-column ~89mm, 1.5-col ~140mm, double ~183mm)
    # Using ~7.2in (183mm) for full-width, ~5.5in for 1.5-col
    fig_full: tuple = (7.2, 9.0)  # full-width double column
    fig_wide: tuple = (7.2, 6.0)  # wide landscape
    fig_half: tuple = (5.5, 5.0)  # 1.5 column

    formats: tuple = (".pdf", ".svg", ".png")


def _configure_pub_rc() -> None:
    """Apply publication rcParams globally."""
    installed = {f.name for f in fm.fontManager.ttflist}
    # DejaVu Sans first (best special char support), then Arial, then CJK fallbacks
    chain = [c for c in PUB.font_candidates if c in installed] or ["sans-serif"]

    plt.rcParams.update({
        # Font
        "font.sans-serif": chain,
        "font.family": "sans-serif",
        "font.size": PUB.base,
        "axes.unicode_minus": False,
        # Figure
        "figure.facecolor": PUB.white,
        "figure.dpi": PUB.dpi,
        "savefig.dpi": PUB.dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        # Axes
        "axes.facecolor": PUB.white,
        "axes.edgecolor": PUB.text,
        "axes.linewidth": PUB.axis_lw,
        "axes.labelsize": PUB.label,
        "axes.titlesize": PUB.base,
        # Ticks
        "xtick.color": PUB.text,
        "ytick.color": PUB.text,
        "xtick.labelsize": PUB.small,
        "ytick.labelsize": PUB.small,
        "xtick.major.width": PUB.tick_lw,
        "ytick.major.width": PUB.tick_lw,
        "xtick.major.size": PUB.tick_len,
        "ytick.major.size": PUB.tick_len,
        # Grid
        "grid.color": PUB.light_gray,
        "grid.linewidth": PUB.grid_lw,
        "grid.alpha": 0.4,
        "grid.linestyle": "-",
        # Legend
        "legend.fontsize": PUB.small,
        "legend.frameon": False,
        "legend.labelcolor": PUB.text,
        # Text
        "text.color": PUB.text,
        "axes.labelcolor": PUB.text,
        # Lines
        "lines.linewidth": 0.8,
        "lines.markersize": 3.0,
    })


def _save(fig: plt.Figure, stem: Path) -> None:
    """Save figure in all formats."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.tight_layout(pad=0.5, h_pad=0.8, w_pad=0.8)
    for fmt in PUB.formats:
        fpath = str(stem.with_suffix(fmt))
        if fmt == ".png":
            fig.savefig(fpath, dpi=PUB.dpi, bbox_inches="tight",
                        facecolor=PUB.white, edgecolor="none")
        else:
            fig.savefig(fpath, bbox_inches="tight",
                        facecolor=PUB.white, edgecolor="none")
    plt.close(fig)


def _save_plotting_data(df: pd.DataFrame, stem: Path) -> None:
    """Save plotting data CSV."""
    df.to_csv(str(stem) + "_plotting_data.csv", index=False, encoding="utf-8-sig")


def _save_caption(stem: Path, figure_number: str, title: str,
                  panels: list[dict], source_note: str,
                  stats: str = "") -> None:
    """Write figure_caption.md."""
    lines = [
        f"# {figure_number}: {title}",
        "",
    ]
    if stats:
        lines.append(f"**Key statistics:** {stats}")
        lines.append("")
    for p in panels:
        label = p["label"]
        desc = p["desc"]
        lines.append(f"**({label})** {desc}")
    lines.append("")
    lines.append(f"*Source note:* {source_note}")
    lines.append("")

    cap_path = str(stem) + "_figure_caption.md"
    Path(cap_path).write_text("\n".join(lines), encoding="utf-8")


def _label_panel(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.05) -> None:
    """Add bold panel label like 'a' or 'b'."""
    ax.text(x, y, label, transform=ax.transAxes, fontsize=PUB.panel,
            fontweight="bold", color=PUB.text, va="bottom", ha="left")


_CJK_RE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')


def _abbreviate_paper_id(paper_id: str) -> str:
    """Strip CJK characters from paper_id, keep numeric prefix + ASCII author name."""
    # Remove CJK chars
    cleaned = _CJK_RE.sub('', paper_id)
    # Clean up: remove consecutive underscores, special chars
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = re.sub(r'[^\x20-\x7E_]', '', cleaned)  # keep ASCII printable + underscore
    cleaned = cleaned.strip('_').strip()
    if not cleaned or len(cleaned) < 3:
        # Fallback: keep just the numeric prefix from original
        num_match = re.match(r'^(\d+)', paper_id)
        if num_match:
            cleaned = f"Paper_{num_match.group(1)}"
        else:
            cleaned = paper_id[:15]
    # Truncate to 22 chars
    return cleaned[:22]


# ============================================================================
# Short label mapping (used across all figures)
# ============================================================================

def _build_short_labels() -> dict[str, dict[str, str]]:
    """Build short label mapping for all canonical keys and actions."""
    mapping = {}

    # ---- Canonical keys ----
    key_labels = {
        "nmr_27Al_peak_position_ppm": ("27Al NMR shift", "ppm", "characterization"),
        "pH": ("pH", "", "synthesis"),
        "particle_size_nm": ("Particle size", "nm", "structure"),
        "ftir_peak_position_cm_1": ("FTIR peak", "cm^{-1}", "characterization"),
        "Al_concentration_mol_L": ("Al conc.", "mol/L", "synthesis"),
        "calcination_temperature_C": ("Calcination T", "C", "process"),
        "sintering_temperature_C": ("Sintering T", "C", "process"),
        "mass_loss_wt_percent": ("Mass loss", "wt%", "property"),
        "aging_time_h": ("Aging time", "h", "process"),
        "specific_surface_area_m2_g": ("BET SSA", "m^{2}/g", "structure"),
        "heating_rate_C_min": ("Heating rate", "C/min", "process"),
        "aging_temperature_C": ("Aging T", "C", "process"),
        "holding_time_h": ("Holding time", "h", "process"),
        "dsc_peak_temperature_C": ("DSC peak T", "C", "characterization"),
        "solid_content_wt_percent": ("Solid content", "wt%", "synthesis"),
        "average_fiber_diameter_um": ("Fiber diam.", "um", "structure"),
        "viscosity_Pa_s": ("Viscosity", "Pa.s", "property"),
        "tensile_strength_MPa": ("Tensile strength", "MPa", "property"),
        "hydrolysis_temperature_C": ("Hydrolysis T", "C", "process"),
        "drying_temperature_C": ("Drying T", "C", "process"),
        "drying_time_h": ("Drying time", "h", "process"),
        "xrd_peak_position_2theta_deg": ("XRD 2theta", "deg", "characterization"),
        "raman_peak_position_cm_1": ("Raman shift", "cm^{-1}", "characterization"),
        "pore_volume_cm3_g": ("Pore volume", "cm^{3}/g", "structure"),
        "average_pore_size_nm": ("Pore size", "nm", "structure"),
        "crystallite_size_nm": ("Crystallite size", "nm", "structure"),
        "zeta_potential_mV": ("Zeta potential", "mV", "property"),
        "water_to_aluminum_molar_ratio": ("H2O/Al ratio", "", "synthesis"),
        "acid_to_aluminum_molar_ratio": ("Acid/Al ratio", "", "synthesis"),
        "stirring_time_h": ("Stirring time", "h", "process"),
        "hydrolysis_time_h": ("Hydrolysis time", "h", "process"),
        "calcination_holding_time_h": ("Calc. hold time", "h", "process"),
        "sintering_holding_time_h": ("Sint. hold time", "h", "process"),
        "elastic_modulus_GPa": ("Elastic modulus", "GPa", "property"),
        "elongation_at_break_percent": ("Elong. at break", "%", "property"),
        "thermal_conductivity_W_mK": ("Thermal cond.", "W/mK", "property"),
        "porosity_percent": ("Porosity", "%", "structure"),
        "shrinkage_percent": ("Shrinkage", "%", "structure"),
        "density_g_cm3": ("Density", "g/cm^{3}", "structure"),
        "spinnability": ("Spinnability", "", "property"),
        "average_fiber_diameter_nm": ("Fiber diam.", "nm", "structure"),
    }

    for key, (short, unit, ptype) in key_labels.items():
        mapping[key] = {
            "canonical_key": key,
            "short_label": short,
            "unit": unit,
            "parameter_type": ptype,
        }

    # ---- Actions ----
    action_labels = {
        "add": ("Add/Mix", "Sol prep"),
        "spin": ("Spin", "Spinning"),
        "stir": ("Stir", "Sol prep"),
        "heat": ("Heat", "Thermal"),
        "dry": ("Dry", "Drying"),
        "other": ("Other", "Other"),
        "hydrolyze": ("Hydrolyze", "Sol prep"),
        "dissolve": ("Dissolve", "Sol prep"),
        "age": ("Age", "Aging"),
        "calcine": ("Calcine", "Thermal"),
        "characterize": ("Characterize", "Characterization"),
        "sinter": ("Sinter", "Thermal"),
        "concentrate": ("Concentrate", "Aging"),
        "filter": ("Filter", "Sol prep"),
        "cool": ("Cool", "Aging"),
        "wash": ("Wash", "Sol prep"),
        "gelation": ("Gelation", "Aging"),
        "collect": ("Collect", "Other"),
        "peptize": ("Peptize", "Sol prep"),
    }
    for action, (short, stage) in action_labels.items():
        mapping[action] = {
            "canonical_key": action,
            "short_label": short,
            "unit": "",
            "parameter_type": stage,
        }

    return mapping


def _write_label_mapping(output_dir: Path) -> None:
    """Write full label_mapping.csv."""
    mapping = _build_short_labels()
    rows = []
    for key, info in sorted(mapping.items()):
        rows.append({
            "canonical_key": key,
            "short_label": info["short_label"],
            "unit": info["unit"],
            "parameter_type": info["parameter_type"],
        })
    df = pd.DataFrame(rows)
    df.to_csv(output_dir / "label_mapping.csv", index=False, encoding="utf-8-sig")
    return df


# ============================================================================
# Data loaders
# ============================================================================

DATA_V2 = PROJECT_ROOT / "data" / "analysis_outputs_stage3_v2"
DATA_STAGE3 = PROJECT_ROOT / "data" / "analysis_outputs_stage3"


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_V2 / name
    if path.exists():
        return pd.read_csv(path)
    alt = DATA_STAGE3 / name
    if alt.exists():
        return pd.read_csv(alt)
    raise FileNotFoundError(f"Cannot find {name}")


def _read_json(name: str) -> dict:
    path = DATA_V2 / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    alt = DATA_STAGE3 / name
    if alt.exists():
        return json.loads(alt.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Cannot find {name}")


# ============================================================================
# Stage → action mapping for transition aggregation
# ============================================================================

_ACTION_TO_STAGE: dict[str, str] = {
    "add": "Sol prep", "mix": "Sol prep", "dissolve": "Sol prep",
    "hydrolyze": "Sol prep", "peptize": "Sol prep", "stir": "Sol prep",
    "filter": "Sol prep", "wash": "Sol prep",
    "age": "Aging", "concentrate": "Aging", "evaporate": "Aging",
    "rotary_evaporate": "Aging", "cool": "Aging", "gelation": "Aging",
    "spin": "Spinning", "electrospin": "Spinning",
    "dry": "Drying",
    "calcine": "Thermal", "sinter": "Thermal", "heat": "Thermal",
    "characterize": "Char.", "measure": "Char.",
}

_STAGE_ORDER_STANDARD = ["Sol prep", "Aging", "Spinning", "Drying", "Thermal", "Char."]


# ============================================================================
# Figure 1: Extraction Summary (2x2 multi-panel)
# ============================================================================

def figure_1_extraction_summary(output_dir: Path) -> None:
    """2x2 multi-panel: (a) scale bars, (b) action reduction, (c) categories,
    (d) coverage density."""
    print("[1/4] Extraction summary...")

    summary = _read_json("analysis_outputs_stage3_summary.json")
    action_df = _read_csv("process_step_action_distribution_cleaned.csv")
    spl = pd.read_csv(DATA_STAGE3 / "sample_parameter_long.csv")

    fig = plt.figure(figsize=PUB.fig_full, facecolor=PUB.white)
    gs = GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.40,
                  left=0.10, right=0.96, top=0.94, bottom=0.08)

    # ---- (a) Extraction scale bar chart ----
    ax_a = fig.add_subplot(gs[0, 0])
    scale_items = [
        ("Papers", 343, PUB.blue),
        ("Data points", 5683, PUB.teal),
        ("Process steps", 2819, PUB.green),
        ("Evidence\npassages", 3289, PUB.orange),
    ]
    labels = [s[0] for s in scale_items]
    values = [s[1] for s in scale_items]
    colors = [s[2] for s in scale_items]

    bars = ax_a.barh(range(len(labels)), values, height=0.55, color=colors,
                     edgecolor="none")
    ax_a.set_yticks(range(len(labels)))
    ax_a.set_yticklabels(labels, fontsize=PUB.small)
    ax_a.set_xlabel("Count", fontsize=PUB.small)
    ax_a.invert_yaxis()
    # Value labels
    for i, (v, c) in enumerate(zip(values, colors)):
        ax_a.text(v + max(values) * 0.02, i, f"{v:,}", va="center",
                  fontsize=PUB.small, color=PUB.text, fontweight="bold")
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.tick_params(axis="x", labelsize=PUB.small)
    ax_a.set_xlim(0, max(values) * 1.20)
    _label_panel(ax_a, "a")
    ax_a.set_title("Extraction scale", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left")

    # Save plotting data
    pd.DataFrame({"item": labels, "count": values}).to_csv(
        str(output_dir / "fig1a_extraction_scale_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    # ---- (b) Action reduction: 73 -> 24 ----
    ax_b = fig.add_subplot(gs[0, 1])
    reduction_data = {
        "Original\nactions": 73,
        "Normalized\nactions": 24,
        "'Other'\nbefore": 671,
        "'Other'\nafter": 215,
    }
    bar_labels = list(reduction_data.keys())
    bar_values = list(reduction_data.values())
    bar_colors = [PUB.red, PUB.green, PUB.red, PUB.green]

    b_bars = ax_b.bar(range(len(bar_labels)), bar_values, width=0.5,
                      color=bar_colors, edgecolor="none")
    ax_b.set_xticks(range(len(bar_labels)))
    ax_b.set_xticklabels(bar_labels, fontsize=PUB.tiny)
    ax_b.set_ylabel("Count", fontsize=PUB.small)
    for i, v in enumerate(bar_values):
        ax_b.text(i, v + max(bar_values) * 0.03, str(v), ha="center",
                  fontsize=PUB.small, color=PUB.text, fontweight="bold")
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.tick_params(axis="y", labelsize=PUB.small)
    ax_b.set_ylim(0, max(bar_values) * 1.18)
    _label_panel(ax_b, "b")
    ax_b.set_title("Action normalization", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left")

    # Add reduction annotation
    ax_b.annotate("68% reduction\nin 'other'",
                  xy=(2, 671), xytext=(3.1, 550),
                  fontsize=PUB.tiny, color=PUB.red,
                  arrowprops=dict(arrowstyle="->", color=PUB.red, lw=0.6),
                  ha="left", va="center")

    pd.DataFrame({"metric": bar_labels, "count": bar_values}).to_csv(
        str(output_dir / "fig1b_action_reduction_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    # ---- (c) Category contribution stacked bar ----
    ax_c = fig.add_subplot(gs[1, 0])
    categories = summary["top_categories"]
    cat_names = []
    cat_counts = []
    for cat in categories:
        name = cat["category"].replace("fiber_process", "Fiber").replace(
            "mechanism", "Mechanism").replace("applications", "Appl.").replace(
            "rheology", "Rheology")
        cat_names.append(name)
        cat_counts.append(cat["data_point_count"])

    cat_colors = [PUB.blue, PUB.teal, PUB.orange, PUB.purple]
    bars_c = ax_c.bar(range(len(cat_names)), cat_counts, width=0.5,
                      color=cat_colors, edgecolor="none")
    ax_c.set_xticks(range(len(cat_names)))
    ax_c.set_xticklabels(cat_names, fontsize=PUB.small)
    ax_c.set_ylabel("Data points", fontsize=PUB.small)
    for i, v in enumerate(cat_counts):
        ax_c.text(i, v + max(cat_counts) * 0.02, f"{v:,}", ha="center",
                  fontsize=PUB.small, color=PUB.text, fontweight="bold")
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.tick_params(axis="y", labelsize=PUB.small)
    ax_c.set_ylim(0, max(cat_counts) * 1.15)
    _label_panel(ax_c, "c")
    ax_c.set_title("Category contribution", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left")

    pd.DataFrame({"category": cat_names, "data_points": cat_counts}).to_csv(
        str(output_dir / "fig1c_category_contribution_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    # ---- (d) Coverage density summary ----
    ax_d = fig.add_subplot(gs[1, 1])
    papers_per_key = spl.groupby("canonical_key")["paper_id"].nunique().sort_values(ascending=False)
    keys_per_paper = spl.groupby("paper_id")["canonical_key"].nunique().sort_values(ascending=False)

    # Histogram of keys per paper
    ax_d.hist(keys_per_paper, bins=25, color=PUB.blue, alpha=0.6, edgecolor="white",
              linewidth=0.3)
    mean_coverage = keys_per_paper.mean()
    median_coverage = keys_per_paper.median()
    ax_d.axvline(x=mean_coverage, color=PUB.orange, linestyle="--", linewidth=0.8,
                 label=f"Mean = {mean_coverage:.1f}")
    ax_d.axvline(x=median_coverage, color=PUB.red, linestyle=":", linewidth=0.8,
                 label=f"Median = {median_coverage:.0f}")
    ax_d.set_xlabel("Canonical keys per paper", fontsize=PUB.small)
    ax_d.set_ylabel("Papers", fontsize=PUB.small)
    ax_d.legend(fontsize=PUB.tiny, loc="upper right")
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    ax_d.tick_params(labelsize=PUB.small)
    _label_panel(ax_d, "d")
    ax_d.set_title("Coverage density", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left")

    pd.DataFrame({"paper_id": keys_per_paper.index,
                  "canonical_keys_count": keys_per_paper.values}).to_csv(
        str(output_dir / "fig1d_coverage_density_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    stem = output_dir / "figures" / "stage3_extraction_summary"
    _save(fig, stem)

    _save_caption(
        stem, "Figure 1", "Stage 3 extraction summary",
        panels=[
            {"label": "a", "desc": "Overall extraction scale across 343 papers."},
            {"label": "b", "desc": "Action normalization: original 73 unique actions reduced to 24 canonical actions; 'other' category decreased from 671 to 215 steps (68% reduction)."},
            {"label": "c", "desc": "Data point contribution by research category."},
            {"label": "d", "desc": "Distribution of canonical keys per paper. Mean = {:.1f}, median = {:.0f}, n = {} papers.".format(mean_coverage, median_coverage, len(keys_per_paper))},
        ],
        source_note="Data: process_step_action_distribution_cleaned.csv, analysis_outputs_stage3_summary.json, sample_parameter_long.csv",
        stats=f"343 papers, 5,683 data points, 2,819 process steps, 73->24 actions, matrix density 33%"
    )
    print("  -> stage3_extraction_summary saved")


# ============================================================================
# Figure 2: Process Action and Transition
# ============================================================================

def figure_2_process_action_and_transition(output_dir: Path) -> None:
    """Three panels: (a) action bar chart, (b) transition matrix, (c) alluvial."""
    print("[2/4] Process action and transition...")

    action_df = _read_csv("process_step_action_distribution_cleaned.csv")
    transitions = _read_csv("transition_edges.csv")
    mapping = _build_short_labels()

    # Filter to top actions (exclude very low counts and data_processing/spectral stubs)
    top_actions = action_df[action_df["count"] >= 5].nlargest(14, "count").copy()
    top_actions = top_actions.iloc[::-1]  # reverse for horizontal display

    fig = plt.figure(figsize=PUB.fig_full, facecolor=PUB.white)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[1.0, 1.2],
                  hspace=0.50, left=0.12, right=0.96, top=0.94, bottom=0.06)

    # ---- (a) Action horizontal bar chart ----
    ax_a = fig.add_subplot(gs[0, 0])
    actions_list = top_actions["action"].tolist()
    counts_list = top_actions["count"].tolist()
    total_steps = int(action_df["count"].sum())

    # Colors by action stage
    action_stage_colors = {
        "Sol prep": PUB.blue, "Aging": PUB.teal, "Spinning": PUB.purple,
        "Drying": PUB.orange, "Thermal": PUB.red, "Char.": PUB.green,
    }
    action_stages = {
        "add": "Sol prep", "spin": "Spinning", "stir": "Sol prep",
        "heat": "Thermal", "dry": "Drying", "other": "Other",
        "hydrolyze": "Sol prep", "dissolve": "Sol prep", "age": "Aging",
        "calcine": "Thermal", "characterize": "Char.", "sinter": "Thermal",
        "concentrate": "Aging", "filter": "Sol prep", "cool": "Aging",
    }
    bar_colors = [action_stage_colors.get(action_stages.get(a, ""), PUB.gray)
                  for a in actions_list]

    ax_a.barh(range(len(actions_list)), counts_list, height=0.6,
              color=bar_colors, edgecolor="none")

    # Short labels
    short_action_labels = [mapping.get(a, {}).get("short_label", a) for a in actions_list]
    ax_a.set_yticks(range(len(actions_list)))
    ax_a.set_yticklabels(short_action_labels, fontsize=PUB.small)
    ax_a.set_xlabel("Number of process steps", fontsize=PUB.small)

    # Value labels
    max_c = max(counts_list)
    for i, (c, a) in enumerate(zip(counts_list, actions_list)):
        pct = c / total_steps * 100
        ax_a.text(c + max_c * 0.015, i, f"{c} ({pct:.1f}%)",
                  va="center", fontsize=PUB.tiny, color=PUB.text)
    ax_a.set_xlim(0, max_c * 1.30)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.tick_params(axis="x", labelsize=PUB.small)
    _label_panel(ax_a, "a")
    ax_a.set_title("Canonicalized process actions (top 14 of 24)",
                   fontsize=PUB.base, color=PUB.text, fontweight="bold", loc="left")

    # Legend for action stages
    legend_items = [
        mpatches.Patch(color=c, label=s)
        for s, c in action_stage_colors.items() if s != "Other"
    ]
    ax_a.legend(handles=legend_items, fontsize=PUB.tiny, loc="lower right",
                ncol=3, frameon=False, handlelength=1.0, handleheight=0.8,
                columnspacing=0.8)

    pd.DataFrame({
        "action": actions_list,
        "short_label": short_action_labels,
        "count": counts_list,
        "percentage": [c / total_steps * 100 for c in counts_list],
        "stage": [action_stages.get(a, "Other") for a in actions_list],
    }).to_csv(str(output_dir / "fig2a_action_distribution_plotting_data.csv"),
              index=False, encoding="utf-8-sig")

    # ---- (b) Stage transition matrix heatmap + (c) alluvial ----
    gs_lower = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1, 0],
                                        width_ratios=[1, 1.2], wspace=0.35)

    # (b) Transition matrix
    ax_b = fig.add_subplot(gs_lower[0, 0])
    stage_order = _STAGE_ORDER_STANDARD
    n_stages = len(stage_order)
    matrix = np.zeros((n_stages, n_stages))

    for _, row in transitions.iterrows():
        src = _ACTION_TO_STAGE.get(str(row["source_action"]), "")
        tgt = _ACTION_TO_STAGE.get(str(row["target_action"]), "")
        if src in stage_order and tgt in stage_order:
            si = stage_order.index(src)
            ti = stage_order.index(tgt)
            matrix[si, ti] += int(row["count"])

    # Log scale for better visibility
    matrix_log = np.log1p(matrix)

    im = ax_b.imshow(matrix_log, aspect="auto", cmap="YlOrRd",
                     interpolation="nearest")
    ax_b.set_xticks(range(n_stages))
    ax_b.set_xticklabels(stage_order, rotation=30, ha="right", fontsize=PUB.tiny)
    ax_b.set_yticks(range(n_stages))
    ax_b.set_yticklabels(stage_order, fontsize=PUB.tiny)
    ax_b.set_title("Stage transition matrix", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left")

    # Annotate cells with count
    for i in range(n_stages):
        for j in range(n_stages):
            if matrix[i, j] > 0:
                text_color = "white" if matrix_log[i, j] > matrix_log.max() * 0.6 else PUB.text
                ax_b.text(j, i, f"{matrix[i, j]:.0f}", ha="center", va="center",
                          fontsize=PUB.tiny - 1, color=text_color)

    _label_panel(ax_b, "b")
    cbar = fig.colorbar(im, ax=ax_b, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=PUB.tiny)
    cbar.set_label("log(count+1)", fontsize=PUB.tiny, color=PUB.text)

    # Save matrix data
    matrix_rows = []
    for i in range(n_stages):
        for j in range(n_stages):
            matrix_rows.append({
                "source_stage": stage_order[i],
                "target_stage": stage_order[j],
                "transition_count": int(matrix[i, j]),
            })
    pd.DataFrame(matrix_rows).to_csv(
        str(output_dir / "fig2b_transition_matrix_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    # ---- (c) Simplified alluvial ----
    ax_c = fig.add_subplot(gs_lower[0, 1])
    ax_c.set_xlim(0, 1)
    ax_c.set_ylim(0, 1)
    ax_c.axis("off")

    # Build stage-level flows, filter to significant ones
    stage_flows: dict[tuple[str, str], int] = defaultdict(int)
    for _, row in transitions.iterrows():
        src = _ACTION_TO_STAGE.get(str(row["source_action"]), "")
        tgt = _ACTION_TO_STAGE.get(str(row["target_action"]), "")
        if src in stage_order and tgt in stage_order and src != tgt:
            stage_flows[(src, tgt)] += int(row["count"])

    # Keep top flows
    if stage_flows:
        threshold = sorted(stage_flows.values(), reverse=True)[
            min(len(stage_flows) - 1, 12)]
        filtered = {k: v for k, v in stage_flows.items() if v >= threshold}
    else:
        filtered = {}

    if filtered:
        max_flow = max(filtered.values())
        n_stages_plot = len(stage_order)
        stage_x = {s: 0.08 + 0.84 * i / (n_stages_plot - 1) for i, s in enumerate(stage_order)}
        node_w = 0.06

        # Draw nodes
        for stage in stage_order:
            x = stage_x[stage]
            rect = mpatches.FancyBboxPatch(
                (x - node_w / 2, 0.40 - 0.10), node_w, 0.25,
                boxstyle="round,pad=0.01,rounding_size=0.02",
                facecolor=PUB.white, edgecolor=PUB.dark_gray, linewidth=0.6, zorder=5)
            ax_c.add_patch(rect)
            ax_c.text(x, 0.525, stage, ha="center", va="center",
                      fontsize=PUB.tiny - 0.5, color=PUB.text, fontweight="bold", zorder=6,
                      transform=ax_c.transAxes)

        # Draw flows
        flow_colors = [PUB.blue, PUB.teal, PUB.orange, PUB.green, PUB.purple]
        for idx, ((src, tgt), count) in enumerate(
            sorted(filtered.items(), key=lambda x: -x[1])):
            x1 = stage_x[src] + node_w / 2
            x2 = stage_x[tgt] - node_w / 2
            is_fwd = stage_order.index(src) < stage_order.index(tgt)
            color = flow_colors[idx % len(flow_colors)] if is_fwd else PUB.red
            alpha = 0.4 + 0.35 * (count / max_flow)
            lw = 1.0 + 5.0 * (count / max_flow)

            y_off = 0.02 * (idx % 5 - 2)
            mid_y = 0.525 + y_off
            ctrl_y = mid_y + 0.10 * ((-1) ** idx)

            bezier_path = mpath.Path(
                [(x1, 0.525), ((x1 + x2) / 2, ctrl_y), (x2, 0.525)],
                [mpath.Path.MOVETO, mpath.Path.CURVE3, mpath.Path.CURVE3])
            patch = mpatches.PathPatch(bezier_path, facecolor="none", edgecolor=color,
                                        linewidth=lw, alpha=alpha, zorder=1,
                                        joinstyle="round")
            ax_c.add_patch(patch)

            # Label
            if lw > 1.5:
                ax_c.text((x1 + x2) / 2, ctrl_y + 0.02, str(count),
                          ha="center", va="bottom", fontsize=PUB.tiny - 1,
                          color=color, alpha=alpha + 0.1, fontweight="bold",
                          transform=ax_c.transAxes, zorder=4)

    _label_panel(ax_c, "c")
    ax_c.set_title("Major stage transitions", fontsize=PUB.base, color=PUB.text,
                   fontweight="bold", loc="left", x=0.05, y=0.97)

    # Save alluvial data
    alluvial_rows = [{"source": s, "target": t, "count": c}
                     for (s, t), c in sorted(filtered.items(), key=lambda x: -x[1])]
    pd.DataFrame(alluvial_rows).to_csv(
        str(output_dir / "fig2c_stage_transitions_plotting_data.csv"),
        index=False, encoding="utf-8-sig")

    stem = output_dir / "figures" / "stage3_process_action_and_transition"
    _save(fig, stem)

    _save_caption(
        stem, "Figure 2", "Process action distribution and stage transitions",
        panels=[
            {"label": "a", "desc": f"Top 14 canonicalized process actions from {total_steps} extracted steps across 343 papers. Labels show count and percentage of total. Colors indicate process stage."},
            {"label": "b", "desc": "Stage-level transition matrix aggregated from action-level transition edges. Cells show transition counts. Color intensity on log scale."},
            {"label": "c", "desc": "Simplified alluvial diagram of major stage-to-stage transitions (thresholded). Arrow width proportional to transition count. Forward transitions in blue/teal; backward in red."},
        ],
        source_note="Data: process_step_action_distribution_cleaned.csv, transition_edges.csv (221 edges)",
        stats=f"2,819 total steps, 24 unique actions, 6 process stages, {len(filtered)} major transitions"
    )
    print("  -> stage3_process_action_and_transition saved")


# ============================================================================
# Figure 3: Sample-Parameter Coverage
# ============================================================================

def figure_3_sample_parameter_coverage(output_dir: Path) -> None:
    """Binary matrix heatmap: top 25 papers x top 25 parameters with category strip."""
    print("[3/4] Sample-parameter coverage...")

    spl = pd.read_csv(DATA_STAGE3 / "sample_parameter_long.csv")
    mapping = _build_short_labels()

    # Get top papers and parameters by coverage
    paper_fills = spl.groupby("paper_id")["canonical_key"].nunique().sort_values(ascending=False)
    param_fills = spl.groupby("canonical_key")["paper_id"].nunique().sort_values(ascending=False)

    top_n = 25
    top_papers = paper_fills.head(top_n).index.tolist()
    top_params = param_fills.head(top_n).index.tolist()

    # Sort params by type then frequency
    param_types = {}
    for p in top_params:
        info = mapping.get(p, {})
        ptype = info.get("parameter_type", "other")
        param_types[p] = ptype
    type_order = {"synthesis": 0, "process": 1, "structure": 2, "property": 3,
                  "characterization": 4, "other": 5}
    param_order = sorted(top_params, key=lambda p: (
        type_order.get(param_types.get(p, "other"), 99),
        -param_fills.get(p, 0)))

    # Sort papers by category then density
    paper_cats = spl.groupby("paper_id")["category"].first()
    cat_priority = {"fiber_process": 0, "mechanism": 1, "applications": 2, "rheology": 3}
    paper_sort = sorted(top_papers, key=lambda p: (
        cat_priority.get(str(paper_cats.get(p, "")), 99),
        -paper_fills.get(p, 0)))

    # Build binary matrix
    data = spl[spl["paper_id"].isin(paper_sort) & spl["canonical_key"].isin(param_order)]
    matrix = pd.crosstab(data["paper_id"], data["canonical_key"])
    matrix = matrix.reindex(index=paper_sort, columns=param_order).fillna(0).astype(int)
    binary = (matrix > 0).astype(int)
    density = binary.values.sum() / binary.values.size * 100

    # Short labels
    short_params = [mapping.get(p, {}).get("short_label", p[:20]) for p in param_order]
    short_papers = [_abbreviate_paper_id(str(p)) for p in paper_sort]

    # Parameter type colors for column labels
    type_colors = {
        "synthesis": PUB.blue, "process": PUB.teal, "structure": PUB.green,
        "property": PUB.orange, "characterization": PUB.purple, "other": PUB.gray,
    }
    param_label_colors = [type_colors.get(param_types.get(p, "other"), PUB.gray)
                          for p in param_order]

    # Category colors
    cat_colors_map = {
        "fiber_process": PUB.blue, "mechanism": PUB.teal,
        "applications": PUB.orange, "rheology": PUB.purple,
    }
    cat_short = {"fiber_process": "Fiber", "mechanism": "Mech.",
                 "applications": "Appl.", "rheology": "Rheo."}

    fig = plt.figure(figsize=(7.2, 7.5), facecolor=PUB.white)
    gs = GridSpec(1, 1, figure=fig, left=0.02, right=0.88, top=0.96, bottom=0.14)

    # Main heatmap area
    ax_main = fig.add_subplot(gs[0, 0])
    gs_inner = GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[0, 0],
                                        width_ratios=[0.03, 1.0, 0.04], wspace=0.03)

    # Category sidebar
    ax_cat = fig.add_subplot(gs_inner[0, 0])
    cat_rows = []
    for p in paper_sort:
        cat = str(paper_cats.get(p, "unknown"))
        cat_rows.append(cat_priority.get(cat, 0))
    cat_cmap = plt.matplotlib.colors.ListedColormap(
        [PUB.blue, PUB.teal, PUB.orange, PUB.purple])
    ax_cat.imshow(np.array(cat_rows).reshape(-1, 1), aspect="auto", cmap=cat_cmap)
    ax_cat.set_xticks([])
    ax_cat.set_yticks([])

    # Main heatmap
    ax_hm = fig.add_subplot(gs_inner[0, 1])
    hm_cmap = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "pub_binary", [(1, 1, 1), PUB.blue], N=256)
    ax_hm.imshow(binary.values, aspect="auto", cmap=hm_cmap, vmin=0, vmax=1,
                 interpolation="nearest")

    # Column labels colored by parameter type
    ax_hm.set_xticks(range(len(short_params)))
    ax_hm.set_xticklabels(short_params, rotation=45, ha="right", fontsize=PUB.tiny - 0.5)
    for i, color in enumerate(param_label_colors):
        ax_hm.get_xticklabels()[i].set_color(color)

    # Row labels
    ax_hm.set_yticks(range(len(short_papers)))
    ax_hm.set_yticklabels(short_papers, fontsize=PUB.tiny - 1.5)
    ax_hm.tick_params(axis="both", length=1.5)

    # Coverage bar on right
    ax_cov = fig.add_subplot(gs_inner[0, 2])
    densities = binary.sum(axis=1).values / len(param_order)
    ax_cov.barh(range(len(densities)), densities, height=0.7,
                color=PUB.teal, alpha=0.7, edgecolor="none")
    ax_cov.set_ylim(-0.5, len(densities) - 0.5)
    ax_cov.invert_yaxis()
    ax_cov.set_xlim(0, 1.0)
    ax_cov.spines["top"].set_visible(False)
    ax_cov.spines["right"].set_visible(False)
    ax_cov.set_yticks([])
    ax_cov.tick_params(axis="x", labelsize=PUB.tiny)
    ax_cov.set_xlabel("Cov.", fontsize=PUB.tiny, color=PUB.text)
    ax_cov.axvline(x=density / 100, color=PUB.orange, linestyle="--", linewidth=0.6)
    ax_cov.text(1.05, len(densities) - 0.5, f"avg\n{density:.1f}%",
                fontsize=PUB.tiny, color=PUB.orange, ha="left", va="top")

    # Legend for parameter types
    handles = [mpatches.Patch(color=c, label=t.capitalize())
               for t, c in type_colors.items() if t != "other"]
    leg = fig.legend(handles=handles, fontsize=PUB.tiny, loc="lower center",
                     ncol=5, frameon=False, handlelength=1.0, handleheight=0.8,
                     columnspacing=1.0, bbox_to_anchor=(0.5, 0.02))

    # Category legend
    cat_handles = [
        mpatches.Patch(color=cat_colors_map[c], label=cat_short.get(c, c))
        for c in ["fiber_process", "mechanism", "applications", "rheology"]
    ]
    leg2 = fig.legend(handles=cat_handles, fontsize=PUB.tiny, loc="lower center",
                      ncol=4, frameon=False, handlelength=1.0, handleheight=0.8,
                      columnspacing=1.0, bbox_to_anchor=(0.5, 0.06))
    # Remove first legend (parameter types) — use only one
    leg.remove()
    # Actually keep both but reposition
    fig.legend(handles=handles, fontsize=PUB.tiny, loc="lower center",
               ncol=5, frameon=False, handlelength=1.0, handleheight=0.8,
               columnspacing=1.0, bbox_to_anchor=(0.5, 0.02))
    leg2.remove()

    # Add category legend as text
    cat_legend_parts = []
    for c in ["fiber_process", "mechanism", "applications", "rheology"]:
        cat_legend_parts.append(f"{cat_short[c]}")
    fig.text(0.5, 0.065, "Categories: " + "  |  ".join(cat_legend_parts),
             ha="center", fontsize=PUB.tiny, color=PUB.text)

    # Save data
    pd.DataFrame(binary.values, index=short_papers, columns=short_params).to_csv(
        str(output_dir / "fig3_coverage_matrix_plotting_data.csv"),
        encoding="utf-8-sig")
    pd.DataFrame({
        "paper_id": paper_sort,
        "short_label": short_papers,
        "category": [str(paper_cats.get(p, "")) for p in paper_sort],
        "coverage": [binary.loc[p].sum() / len(param_order) for p in paper_sort],
    }).to_csv(str(output_dir / "fig3_paper_metadata_plotting_data.csv"),
              index=False, encoding="utf-8-sig")

    stem = output_dir / "figures" / "stage3_sample_parameter_coverage"
    _save(fig, stem)

    _save_caption(
        stem, "Figure 3", "Sample-parameter coverage matrix",
        panels=[
            {"label": "heatmap", "desc": f"Binary presence/absence matrix for top {top_n} papers (rows) and top {top_n} parameters (columns). Papers sorted by category then coverage density; parameters sorted by type then frequency. Left sidebar: paper category. Right bar: per-paper coverage (fraction of {top_n} parameters present)."},
        ],
        source_note="Data: sample_parameter_long.csv (4,190 observations, 295 papers, 102 unique keys). Full label mapping in label_mapping.csv.",
        stats=f"Matrix {top_n}x{top_n}, density {density:.1f}%"
    )
    print("  -> stage3_sample_parameter_coverage saved")


# ============================================================================
# Figure 4: Thermal Processing Window
# ============================================================================

def figure_4_thermal_processing_window(output_dir: Path) -> None:
    """Violin/box/strip comparison of calcination vs sintering temperature."""
    print("[4/4] Thermal processing window...")

    calc = _read_csv("calcination_temperature_cleaned.csv")
    sinter = _read_csv("sintering_temperature_cleaned.csv")

    calc_vals = calc["temperature_C"].dropna().values.astype(float)
    sinter_vals = sinter["temperature_C"].dropna().values.astype(float)

    fig = plt.figure(figsize=(5.5, 5.0), facecolor=PUB.white)
    gs = GridSpec(3, 1, figure=fig, height_ratios=[2.5, 1, 0.3],
                  hspace=0.30, left=0.14, right=0.96, top=0.94, bottom=0.10)

    # ---- (a) Violin + box + strip ----
    ax = fig.add_subplot(gs[0, 0])

    datasets = [
        (calc_vals, "Calcination", PUB.blue),
        (sinter_vals, "Sintering", PUB.green),
    ]

    for pos, (vals, label, color) in enumerate(datasets):
        # Violin
        vp = ax.violinplot(vals, positions=[pos], vert=False, showmeans=False,
                           showmedians=False, showextrema=False)
        for body in vp["bodies"]:
            body.set_facecolor(color)
            body.set_alpha(0.30)
            body.set_edgecolor(color)
            body.set_linewidth(0.3)

        # Box plot (horizontal, compact)
        q1, med, q3 = np.percentile(vals, [25, 50, 75])
        iqr = q3 - q1
        box_h = 0.12
        box = mpatches.FancyBboxPatch(
            (q1, pos - box_h), q3 - q1, 2 * box_h,
            boxstyle="round,pad=0.005,rounding_size=0.01",
            facecolor=color, alpha=0.40, edgecolor=color, linewidth=0.6, zorder=5)
        ax.add_patch(box)
        ax.plot([med, med], [pos - box_h - 0.04, pos + box_h + 0.04],
                color=PUB.white, linewidth=1.5, zorder=6, solid_capstyle="butt")

        # Whiskers
        whisk_low = max(vals.min(), q1 - 1.5 * iqr)
        whisk_high = min(vals.max(), q3 + 1.5 * iqr)
        ax.plot([whisk_low, q1], [pos, pos], color=color, linewidth=0.6, zorder=4)
        ax.plot([q3, whisk_high], [pos, pos], color=color, linewidth=0.6, zorder=4)
        ax.plot([whisk_low, whisk_low], [pos - 0.05, pos + 0.05],
                color=color, linewidth=0.6, zorder=4)
        ax.plot([whisk_high, whisk_high], [pos - 0.05, pos + 0.05],
                color=color, linewidth=0.6, zorder=4)

        # Strip points (jittered)
        jitter = np.random.default_rng(42).uniform(-0.08, 0.08, len(vals))
        ax.scatter(vals, np.full_like(vals, pos - 0.18) + jitter,
                   s=3, c=color, alpha=0.20, edgecolors="none", zorder=2)

        # Stats annotation
        stats_str = f"n={len(vals)}\nmedian={med:.0f} C\nIQR=[{q1:.0f}, {q3:.0f}]"
        ax.text(0.98, pos + 0.15, stats_str, ha="right", va="center",
                fontsize=PUB.tiny - 0.5, color=PUB.text,
                transform=ax.get_yaxis_transform())

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Calcination", "Sintering"], fontsize=PUB.small)
    ax.set_xlabel("Temperature (C)", fontsize=PUB.small)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="x", labelsize=PUB.small)
    ax.tick_params(axis="y", length=0)
    _label_panel(ax, "a", x=-0.12)

    # ---- (b) Compact histogram ----
    ax_hist = fig.add_subplot(gs[1, 0])
    bins = np.linspace(0, 1700, 22)
    ax_hist.hist(calc_vals, bins=bins, alpha=0.5, color=PUB.blue,
                 edgecolor="white", linewidth=0.2, label="Calcination")
    ax_hist.hist(sinter_vals, bins=bins, alpha=0.5, color=PUB.green,
                 edgecolor="white", linewidth=0.2, label="Sintering")
    ax_hist.set_xlabel("Temperature (C)", fontsize=PUB.small)
    ax_hist.set_ylabel("Count", fontsize=PUB.small)
    ax_hist.spines["top"].set_visible(False)
    ax_hist.spines["right"].set_visible(False)
    ax_hist.tick_params(labelsize=PUB.small)
    ax_hist.legend(fontsize=PUB.tiny, loc="upper right", frameon=False,
                   handlelength=1.0)
    _label_panel(ax_hist, "b", x=-0.12)

    # ---- Source note ----
    ax_note = fig.add_subplot(gs[2, 0])
    ax_note.axis("off")
    ax_note.text(0, 0.5, "Data: calcination_temperature_cleaned.csv (n=114), "
                 "sintering_temperature_cleaned.csv (n=73)",
                 fontsize=PUB.tiny - 0.5, color=PUB.gray, style="italic",
                 va="center", transform=ax_note.transAxes)

    # Save data
    pd.DataFrame({
        "calcination_temperature_C": np.sort(calc_vals),
        "temp_type": "calcination",
    }).to_csv(str(output_dir / "fig4_calcination_plotting_data.csv"),
              index=False, encoding="utf-8-sig")
    pd.DataFrame({
        "sintering_temperature_C": np.sort(sinter_vals),
        "temp_type": "sintering",
    }).to_csv(str(output_dir / "fig4_sintering_plotting_data.csv"),
              index=False, encoding="utf-8-sig")

    stem = output_dir / "figures" / "stage3_thermal_processing_window"
    _save(fig, stem)

    _save_caption(
        stem, "Figure 4", "Thermal processing window: calcination vs sintering temperature",
        panels=[
            {"label": "a", "desc": f"Violin plot with overlaid box-and-whisker and jittered strip points. Calcination: n={len(calc_vals)}, median={np.median(calc_vals):.0f} C, IQR=[{np.percentile(calc_vals, 25):.0f}, {np.percentile(calc_vals, 75):.0f}]. Sintering: n={len(sinter_vals)}, median={np.median(sinter_vals):.0f} C, IQR=[{np.percentile(sinter_vals, 25):.0f}, {np.percentile(sinter_vals, 75):.0f}]."},
            {"label": "b", "desc": "Histogram overlay showing the temperature distribution for both processes (22 bins)."},
        ],
        source_note="Data: calcination_temperature_cleaned.csv, sintering_temperature_cleaned.csv. Temperatures filtered to [100, 2500] C range.",
        stats=f"Calcination: n={len(calc_vals)}, median={np.median(calc_vals):.0f} C; Sintering: n={len(sinter_vals)}, median={np.median(sinter_vals):.0f} C"
    )
    print("  -> stage3_thermal_processing_window saved")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Stage 3 Publication Figures")
    parser.add_argument("--output-dir", default="data/analysis_outputs_stage3_publication",
                        help="Output directory (relative to project root)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    figs_dir = output_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    _configure_pub_rc()
    print(f"Generating publication figures -> {output_dir}")

    # Build and write label mapping
    _write_label_mapping(output_dir)
    print("  -> label_mapping.csv written")

    figure_1_extraction_summary(output_dir)
    figure_2_process_action_and_transition(output_dir)
    figure_3_sample_parameter_coverage(output_dir)
    figure_4_thermal_processing_window(output_dir)

    print(f"\nDone! 4 publication figures generated in {figs_dir}")


if __name__ == "__main__":
    main()
