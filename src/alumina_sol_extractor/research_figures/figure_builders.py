from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FAMILY_COLORS = {
    "synthesis": "#5D87B1",
    "process": "#D0936E",
    "structure": "#74A57F",
    "property": "#9B7CBC",
    "spectra": "#4B9FB1",
    "other": "#A8A8A8",
}


def configure_publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def generate_all_figures(figures_dir: Path, figure_tables: dict[str, pd.DataFrame]) -> list[str]:
    configure_publication_style()
    figures_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    written.extend(plot_stage3_parameter_coverage(figures_dir, figure_tables["stage3_parameter_coverage"]))
    written.extend(plot_stage3_sample_parameter_heatmap(figures_dir, figure_tables["stage3_sample_parameter_heatmap"]))
    written.extend(plot_stage3_numeric_parameter_distribution(figures_dir, figure_tables["stage3_numeric_parameter_distribution"]))
    written.extend(plot_stage4_extraction_overview(figures_dir, figure_tables["stage4_extraction_overview"], figure_tables["stage4_statistics"]))
    written.extend(plot_stage4_figure_type_distribution(figures_dir, figure_tables["stage4_figure_type_distribution"]))
    written.extend(plot_stage4_spectra_type_distribution(figures_dir, figure_tables["stage4_spectra_type_distribution"]))
    written.extend(plot_stage4_peak_summary(figures_dir, figure_tables["stage4_peak_summary"]))
    written.extend(plot_stage3_stage4_link_overview(figures_dir, figure_tables["stage3_stage4_link_overview"]))
    written.extend(plot_stage3_stage4_research_overview(figures_dir, figure_tables))
    return written


def plot_stage3_parameter_coverage(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage3_parameter_coverage"
    if frame.empty:
        return _empty_figure(stem, "Stage3 parameter coverage", "No Stage3 parameter coverage data available.")
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ordered = frame.sort_values("coverage_rate", ascending=True)
    colors = [FAMILY_COLORS.get(value, FAMILY_COLORS["other"]) for value in ordered["parameter_family"]]
    ax.barh(ordered["short_label"], ordered["coverage_rate"], color=colors)
    ax.set_xlabel("Paper coverage rate")
    ax.set_title("Stage3 parameter coverage")
    ax.set_xlim(0, min(1.0, max(0.1, ordered["coverage_rate"].max() * 1.1)))
    return _save(stem, fig)


def plot_stage3_sample_parameter_heatmap(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage3_sample_parameter_heatmap"
    if frame.empty or len(frame.columns) <= 1:
        return _empty_figure(stem, "Stage3 sample-parameter heatmap", "No Stage3 sample-parameter matrix available.")
    sample_labels = frame.iloc[:, 0].astype(str).tolist()
    value_frame = frame.drop(columns=[frame.columns[0]])
    matrix = value_frame.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(7, matrix.shape[1] * 0.32), max(4, matrix.shape[0] * 0.18)))
    image = ax.imshow(matrix, aspect="auto", cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
    ax.set_xticks(np.arange(value_frame.shape[1]))
    ax.set_xticklabels(value_frame.columns.tolist(), rotation=45, ha="right", fontsize=7)
    ax.set_yticks(np.arange(len(sample_labels)))
    ax.set_yticklabels(sample_labels, fontsize=6)
    ax.set_title("Stage3 sample-parameter heatmap")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    return _save(stem, fig)


def plot_stage3_numeric_parameter_distribution(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage3_numeric_parameter_distribution"
    if frame.empty:
        return _empty_figure(stem, "Stage3 numeric parameter distribution", "No numeric Stage3 parameter values available.")
    keys = frame.groupby("short_label")["value"].count().sort_values(ascending=False).index.tolist()[:10]
    subset = frame[frame["short_label"].isin(keys)].copy()
    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    grouped = [subset.loc[subset["short_label"] == key, "value"].tolist() for key in keys]
    ax.boxplot(grouped, tick_labels=keys, vert=True, patch_artist=True, boxprops={"facecolor": "#8FB7D8", "edgecolor": "#4B6A88"}, medianprops={"color": "#C7675C"})
    ax.set_xticklabels(keys, rotation=35, ha="right")
    ax.set_ylabel("Value")
    ax.set_title("Stage3 numeric parameter distribution")
    return _save(stem, fig)


def plot_stage4_extraction_overview(figures_dir: Path, overview: pd.DataFrame, per_paper: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage4_extraction_overview"
    if overview.empty:
        return _empty_figure(stem, "Stage4 extraction overview", "No Stage4 extraction statistics available.")
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.8))
    axes[0].bar(overview["metric"], overview["count"], color=["#8FB7D8", "#70A06E", "#C7675C", "#5D87B1", "#9B7CBC", "#D1B97C"])
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].set_title("Overview counts", loc="left", fontweight="bold")
    if per_paper.empty:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "No per-paper coverage data", ha="center", va="center")
    else:
        axes[1].hist(per_paper["coverage_rate"], bins=12, color="#5D87B1", edgecolor="white")
        axes[1].set_title("Per-paper Stage4 coverage", loc="left", fontweight="bold")
        axes[1].set_xlabel("Success / candidate")
    return _save(stem, fig)


def plot_stage4_figure_type_distribution(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage4_figure_type_distribution"
    if frame.empty:
        return _empty_figure(stem, "Stage4 figure type distribution", "No Stage4 figure-class data available.")
    ordered = frame.sort_values("count", ascending=True)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.barh(ordered["figure_class"], ordered["count"], color="#8FB7D8")
    ax.set_xlabel("Count")
    ax.set_title("Stage4 figure_class distribution")
    return _save(stem, fig)


def plot_stage4_spectra_type_distribution(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage4_spectra_type_distribution"
    if frame.empty:
        return _empty_figure(stem, "Stage4 spectra type distribution", "No Stage4 spectra-type data available.")
    frame = _compress_distribution(frame, label_column="spectra_type", value_column="count", top_n=15)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.bar(frame["spectra_type"], frame["count"], color="#74A57F")
    ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("Count")
    ax.set_title("Stage4 spectra type distribution")
    return _save(stem, fig)


def plot_stage4_peak_summary(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage4_peak_summary"
    if frame.empty:
        return _empty_figure(stem, "Stage4 peak summary", "No Stage4 peak-row data available.")
    top = frame.sort_values("peak_row_count", ascending=False).head(12)
    labels = [f"{row.spectra_type}\n{row.source_field}" for row in top.itertuples(index=False)]
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.barh(labels[::-1], top["peak_row_count"].tolist()[::-1], color="#4B9FB1")
    ax.set_xlabel("Peak-row count")
    ax.set_title("Stage4 peak summary")
    return _save(stem, fig)


def plot_stage3_stage4_link_overview(figures_dir: Path, frame: pd.DataFrame) -> list[str]:
    stem = figures_dir / "stage3_stage4_link_overview"
    if frame.empty:
        return _empty_figure(stem, "Stage3-Stage4 link overview", "No Stage3/Stage4 linkage data available.")
    scatter = frame[frame["row_type"] == "paper_scatter"].copy() if "row_type" in frame.columns else pd.DataFrame()
    link_rows = frame[frame["row_type"] == "spectra_parameter_link"].copy() if "row_type" in frame.columns else pd.DataFrame()
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.8))
    if scatter.empty:
        axes[0].axis("off")
        axes[0].text(0.5, 0.5, "No per-paper Stage3/Stage4 scatter data", ha="center", va="center")
    else:
        axes[0].scatter(scatter["sample_count"], scatter["stage4_success_count"], s=24, alpha=0.75, color="#5D87B1")
        axes[0].set_xlabel("Stage3 sample count")
        axes[0].set_ylabel("Stage4 successful figures")
        axes[0].set_title("Samples vs Stage4 success", loc="left", fontweight="bold")
    if link_rows.empty:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "No spectra-parameter link rows", ha="center", va="center")
    else:
        pivot = link_rows.pivot_table(index="parameter_family", columns="spectra_type", values="count", aggfunc="sum", fill_value=0)
        image = axes[1].imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="Blues")
        axes[1].set_xticks(np.arange(pivot.shape[1]))
        axes[1].set_xticklabels(pivot.columns.tolist(), rotation=30, ha="right", fontsize=7)
        axes[1].set_yticks(np.arange(pivot.shape[0]))
        axes[1].set_yticklabels(pivot.index.tolist(), fontsize=7)
        axes[1].set_title("Spectra-to-parameter links", loc="left", fontweight="bold")
        fig.colorbar(image, ax=axes[1], fraction=0.04, pad=0.02)
    return _save(stem, fig)


def plot_stage3_stage4_research_overview(figures_dir: Path, figure_tables: dict[str, pd.DataFrame]) -> list[str]:
    stem = figures_dir / "stage3_stage4_research_overview"
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.6))
    axes = axes.ravel()
    cov = figure_tables["stage3_parameter_coverage"]
    if cov.empty:
        axes[0].axis("off")
        axes[0].text(0.5, 0.5, "No Stage3 coverage data", ha="center", va="center")
    else:
        top = cov.head(8)
        axes[0].barh(top["short_label"][::-1], top["coverage_rate"][::-1], color="#5D87B1")
        axes[0].set_title("A. Stage3 coverage", loc="left", fontweight="bold")
    spec = figure_tables["stage4_spectra_type_distribution"]
    if spec.empty:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "No Stage4 spectra data", ha="center", va="center")
    else:
        spec_top = _compress_distribution(spec, label_column="spectra_type", value_column="count", top_n=8)
        axes[1].bar(spec_top["spectra_type"], spec_top["count"], color="#74A57F")
        axes[1].tick_params(axis="x", rotation=25)
        axes[1].set_title("B. Stage4 spectra coverage", loc="left", fontweight="bold")
    peak = figure_tables["stage4_peak_summary"]
    if peak.empty:
        axes[2].axis("off")
        axes[2].text(0.5, 0.5, "No peak summary data", ha="center", va="center")
    else:
        peak_top = peak.head(8)
        axes[2].barh([f"{row.spectra_type}:{row.source_field}" for row in peak_top.itertuples(index=False)][::-1], peak_top["peak_row_count"].tolist()[::-1], color="#4B9FB1")
        axes[2].set_title("C. Peak summary", loc="left", fontweight="bold")
    heatmap = figure_tables["stage3_sample_parameter_heatmap"]
    if heatmap.empty or len(heatmap.columns) <= 1:
        axes[3].axis("off")
        axes[3].text(0.5, 0.5, "No heatmap data", ha="center", va="center")
    else:
        matrix = heatmap.drop(columns=[heatmap.columns[0]]).to_numpy(dtype=float)
        axes[3].imshow(matrix, aspect="auto", cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
        axes[3].set_xticks([])
        axes[3].set_yticks([])
        axes[3].set_title("D. Sample-parameter matrix", loc="left", fontweight="bold")
    fig.suptitle("Stage3 + Stage4 research overview", fontsize=11, fontweight="bold")
    return _save(stem, fig)


def _save(stem: Path, fig: plt.Figure) -> list[str]:
    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")
    fig.tight_layout()
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return [str(svg_path), str(png_path)]


def _empty_figure(stem: Path, title: str, message: str) -> list[str]:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.axis("off")
    ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=11, fontweight="bold")
    ax.text(0.5, 0.42, message, ha="center", va="center", fontsize=9, color="#555555", wrap=True)
    return _save(stem, fig)


def _compress_distribution(frame: pd.DataFrame, *, label_column: str, value_column: str, top_n: int) -> pd.DataFrame:
    ordered = frame.sort_values(value_column, ascending=False).reset_index(drop=True)
    if len(ordered) <= top_n:
        return ordered
    head = ordered.head(top_n).copy()
    other_count = ordered.iloc[top_n:][value_column].sum()
    if other_count > 0:
        head.loc[len(head)] = {label_column: "Other", value_column: other_count}
    return head
