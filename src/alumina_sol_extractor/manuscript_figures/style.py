from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


DOUBLE_COLUMN_WIDTH_IN = 7.09

CATEGORY_COLORS = {
    "mechanism": "#2F6F8F",
    "fiber_process": "#4E9A51",
    "applications": "#B56576",
    "rheology": "#8C6D9C",
    "uncategorized": "#9AA1A8",
}

OBJECT_TYPE_COLORS = {
    "paper_count": "#325D88",
    "sample_count": "#4E9A51",
    "parameter_count": "#C7793A",
    "process_step_count": "#8C6D9C",
    "spectra_count": "#2F6F8F",
    "link_count": "#B56576",
}

PARAMETER_GROUP_COLORS = {
    "sol chemistry": "#4E9A51",
    "thermal processing": "#C7793A",
    "structure/property": "#2F6F8F",
    "spectroscopy/characterization": "#8C6D9C",
    "process": "#B56576",
    "other": "#9AA1A8",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.frameon": False,
            "legend.fontsize": 6.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.12,
        1.06,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        fontweight="bold",
    )
