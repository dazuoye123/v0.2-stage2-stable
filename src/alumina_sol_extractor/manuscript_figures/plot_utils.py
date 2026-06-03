from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .style import configure_style


def save_figure_bundle(fig: plt.Figure, stem: Path) -> dict[str, str]:
    configure_style()
    fig.tight_layout()
    svg = stem.with_suffix(".svg")
    pdf = stem.with_suffix(".pdf")
    png = stem.with_suffix(".png")
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, bbox_inches="tight", dpi=600)
    plt.close(fig)
    return {"svg": str(svg), "pdf": str(pdf), "png": str(png)}


def safe_heatmap(
    ax: plt.Axes,
    frame: pd.DataFrame,
    *,
    row_col: str,
    col_col: str,
    value_col: str,
    cmap: str = "Blues",
    normalize: bool = False,
    colorbar_label: str | None = None,
    value_range: tuple[float, float] | None = None,
) -> pd.DataFrame:
    if frame.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return pd.DataFrame()
    pivot = frame.pivot_table(index=row_col, columns=col_col, values=value_col, aggfunc="sum", fill_value=0)
    if normalize:
        pivot = pivot.divide(pivot.max(axis=0).replace(0, 1), axis=1)
    imshow_kwargs: dict[str, Any] = {"aspect": "auto", "cmap": cmap}
    if value_range is not None:
        imshow_kwargs["vmin"] = value_range[0]
        imshow_kwargs["vmax"] = value_range[1]
    image = ax.imshow(pivot.to_numpy(dtype=float), **imshow_kwargs)
    ax.set_xticks(np.arange(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns.tolist(), rotation=35, ha="right")
    ax.set_yticks(np.arange(pivot.shape[0]))
    ax.set_yticklabels(pivot.index.tolist())
    colorbar = plt.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    if colorbar_label:
        colorbar.set_label(colorbar_label)
    return pivot


def annotate_empty(ax: plt.Axes, message: str) -> None:
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center")
