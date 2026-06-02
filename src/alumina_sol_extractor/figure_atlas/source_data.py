from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import write_frame, write_json
from .schemas import FigureArtifact


def artifact_paths(*, figures_root: Path, tables_root: Path, json_root: Path, tier: str, figure_id: str) -> dict[str, Path]:
    (figures_root / tier).mkdir(parents=True, exist_ok=True)
    tables_root.mkdir(parents=True, exist_ok=True)
    json_root.mkdir(parents=True, exist_ok=True)
    return {
        "figure_stem": figures_root / tier / figure_id,
        "source_csv": tables_root / f"{figure_id}_source.csv",
        "source_json": json_root / f"{figure_id}.json",
    }


def write_figure_bundle(
    *,
    figure_id: str,
    title: str,
    tier: str,
    recommendation: str,
    feasibility: str,
    source_df: pd.DataFrame,
    input_tables: list[str],
    source_csv_path: Path,
    source_json_path: Path,
    svg_path: str | None,
    png_path: str | None,
    warnings: list[str] | None = None,
    empty_data_note: str | None = None,
) -> FigureArtifact:
    write_frame(source_csv_path, source_df)
    payload = {
        "figure_id": figure_id,
        "title": title,
        "tier": tier,
        "input_tables": input_tables,
        "source_csv": str(source_csv_path),
        "svg": svg_path,
        "png": png_path,
        "row_count": int(len(source_df)),
        "columns": source_df.columns.tolist(),
        "warnings": warnings or [],
        "feasibility": feasibility,
        "empty_data_note": empty_data_note,
        "stage3_rerun": False,
        "stage4_rerun": False,
        "stage5_rerun": False,
        "llm_or_vlm_called": False,
    }
    write_json(source_json_path, payload)
    return FigureArtifact(
        figure_id=figure_id,
        title=title,
        tier=tier,
        recommendation=recommendation,
        feasibility=feasibility,
        svg=svg_path,
        png=png_path,
        source_csv=str(source_csv_path),
        source_json=str(source_json_path),
        input_tables=input_tables,
        warnings=warnings or [],
        empty_data_note=empty_data_note,
    )
