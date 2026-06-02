from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .plot_style import configure_plot_style


def save_figure(fig: plt.Figure, stem: Path) -> tuple[str, str]:
    configure_plot_style()
    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")
    fig.tight_layout()
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return str(svg_path), str(png_path)


def empty_figure(stem: Path, title: str, message: str) -> tuple[str, str]:
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.axis("off")
    ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=11, fontweight="bold")
    ax.text(0.5, 0.42, message, ha="center", va="center", fontsize=9, color="#555555", wrap=True)
    return save_figure(fig, stem)


def bar_figure(stem: Path, frame: pd.DataFrame, *, label_col: str, value_col: str, title: str, horizontal: bool = False, top_n: int | None = None, compress_other: bool = False, color: str = "#5D87B1") -> tuple[str, str]:
    if frame.empty or label_col not in frame.columns or value_col not in frame.columns:
        return empty_figure(stem, title, "No data available.")
    working = frame[[label_col, value_col]].copy()
    working[label_col] = working[label_col].fillna("Unknown").astype(str)
    working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
    working = working.replace([np.inf, -np.inf], np.nan).dropna(subset=[value_col])
    if working.empty:
        return empty_figure(stem, title, "No numeric data available.")
    working = working.sort_values(value_col, ascending=False)
    if top_n is not None:
        working = _compress(working, label_col=label_col, value_col=value_col, top_n=top_n, compress_other=compress_other)
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    if horizontal:
        ordered = working.sort_values(value_col, ascending=True)
        ax.barh(ordered[label_col], ordered[value_col], color=color)
    else:
        ax.bar(working[label_col], working[value_col], color=color)
        ax.tick_params(axis="x", rotation=25)
    ax.set_title(title)
    ax.set_ylabel(value_col.replace("_", " ").title())
    return save_figure(fig, stem)


def hist_figure(stem: Path, frame: pd.DataFrame, *, value_col: str, title: str, bins: int = 20, color: str = "#74A57F") -> tuple[str, str]:
    if frame.empty or value_col not in frame.columns:
        return empty_figure(stem, title, "No numeric data available.")
    values = pd.to_numeric(frame[value_col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return empty_figure(stem, title, "No numeric data available.")
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.hist(values, bins=bins, color=color, edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(value_col.replace("_", " ").title())
    return save_figure(fig, stem)


def scatter_figure(stem: Path, frame: pd.DataFrame, *, x_col: str, y_col: str, title: str, color: str = "#5D87B1") -> tuple[str, str]:
    if frame.empty or x_col not in frame.columns or y_col not in frame.columns:
        return empty_figure(stem, title, "No scatter data available.")
    subset = frame[[x_col, y_col]].dropna()
    if subset.empty:
        return empty_figure(stem, title, "No scatter data available.")
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.scatter(subset[x_col], subset[y_col], s=24, alpha=0.75, color=color)
    ax.set_title(title)
    ax.set_xlabel(x_col.replace("_", " ").title())
    ax.set_ylabel(y_col.replace("_", " ").title())
    return save_figure(fig, stem)


def heatmap_figure(stem: Path, frame: pd.DataFrame, *, index_col: str, column_col: str, value_col: str, title: str, top_n_rows: int | None = None, top_n_cols: int | None = None, cmap: str = "Blues") -> tuple[str, str]:
    if frame.empty or any(column not in frame.columns for column in (index_col, column_col, value_col)):
        return empty_figure(stem, title, "No matrix data available.")
    working = frame.copy()
    if top_n_rows is not None:
        keep_rows = working.groupby(index_col)[value_col].sum().sort_values(ascending=False).head(top_n_rows).index
        working = working[working[index_col].isin(keep_rows)].copy()
    if top_n_cols is not None:
        keep_cols = working.groupby(column_col)[value_col].sum().sort_values(ascending=False).head(top_n_cols).index
        working = working[working[column_col].isin(keep_cols)].copy()
    pivot = working.pivot_table(index=index_col, columns=column_col, values=value_col, aggfunc="sum", fill_value=0)
    if pivot.empty:
        return empty_figure(stem, title, "No matrix data available.")
    fig, ax = plt.subplots(figsize=(max(6.8, pivot.shape[1] * 0.38), max(4.6, pivot.shape[0] * 0.25)))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap)
    ax.set_xticks(np.arange(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns.tolist(), rotation=35, ha="right", fontsize=7)
    ax.set_yticks(np.arange(pivot.shape[0]))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=7)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    return save_figure(fig, stem)


def box_figure(stem: Path, frame: pd.DataFrame, *, group_col: str, value_col: str, title: str, top_n: int = 10) -> tuple[str, str]:
    if frame.empty or any(column not in frame.columns for column in (group_col, value_col)):
        return empty_figure(stem, title, "No box-plot data available.")
    working = frame[[group_col, value_col]].dropna().copy()
    if working.empty:
        return empty_figure(stem, title, "No box-plot data available.")
    keep = working.groupby(group_col)[value_col].count().sort_values(ascending=False).head(top_n).index.tolist()
    grouped = [working.loc[working[group_col] == key, value_col].tolist() for key in keep]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.boxplot(grouped, tick_labels=keep, patch_artist=True, boxprops={"facecolor": "#8FB7D8", "edgecolor": "#4B6A88"}, medianprops={"color": "#C7675C"})
    ax.tick_params(axis="x", rotation=25)
    ax.set_title(title)
    ax.set_ylabel(value_col.replace("_", " ").title())
    return save_figure(fig, stem)


def multi_panel_overview(stem: Path, panels: list[tuple[pd.DataFrame, dict[str, Any]]], *, title: str) -> tuple[str, str]:
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.6))
    axes = axes.ravel()
    for axis, panel in zip(axes, panels):
        frame, meta = panel
        kind = meta["kind"]
        if frame.empty:
            axis.axis("off")
            axis.text(0.5, 0.5, meta["title"], ha="center", va="center", fontsize=10, fontweight="bold")
            continue
        if kind == "bar":
            working = _compress(frame[[meta["label_col"], meta["value_col"]]].copy(), label_col=meta["label_col"], value_col=meta["value_col"], top_n=meta.get("top_n", 8), compress_other=True)
            axis.bar(working[meta["label_col"]], working[meta["value_col"]], color=meta.get("color", "#74A57F"))
            axis.tick_params(axis="x", rotation=25)
        elif kind == "barh":
            working = frame[[meta["label_col"], meta["value_col"]]].copy().sort_values(meta["value_col"], ascending=True).tail(meta.get("top_n", 8))
            axis.barh(working[meta["label_col"]], working[meta["value_col"]], color=meta.get("color", "#5D87B1"))
        elif kind == "heatmap":
            pivot = frame.pivot_table(index=meta["index_col"], columns=meta["column_col"], values=meta["value_col"], aggfunc="sum", fill_value=0)
            axis.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=meta.get("cmap", "Blues"))
            axis.set_xticks([])
            axis.set_yticks([])
        axis.set_title(meta["title"], loc="left", fontweight="bold")
    fig.suptitle(title, fontsize=11, fontweight="bold")
    return save_figure(fig, stem)


def _compress(frame: pd.DataFrame, *, label_col: str, value_col: str, top_n: int, compress_other: bool) -> pd.DataFrame:
    ordered = frame.sort_values(value_col, ascending=False).reset_index(drop=True)
    if len(ordered) <= top_n or not compress_other:
        return ordered.head(top_n)
    head = ordered.head(top_n).copy()
    other_count = pd.to_numeric(ordered.iloc[top_n:][value_col], errors="coerce").fillna(0).sum()
    if other_count > 0:
        head.loc[len(head)] = {label_col: "Other", value_col: other_count}
    return head
