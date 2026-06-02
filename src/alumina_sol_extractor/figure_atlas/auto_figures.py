from __future__ import annotations

from pathlib import Path

import pandas as pd

from .plot_utils import bar_figure, heatmap_figure, hist_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_auto_figures(
    *,
    figures_root: Path,
    tables_root: Path,
    json_root: Path,
    tables: dict[str, pd.DataFrame],
    max_auto_figures: int = 50,
) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    figure_count = 0
    for table_name, frame in tables.items():
        if figure_count >= max_auto_figures or frame.empty:
            continue
        generated_for_table = 0
        candidates = _auto_candidates(table_name, frame)
        for suffix, source_df, mode in candidates:
            if figure_count >= max_auto_figures or generated_for_table >= 3:
                break
            figure_id = f"auto_fig_{figure_count + 1:02d}_{suffix}"
            title = figure_id.replace("_", " ")
            paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="auto", figure_id=figure_id)
            if mode == "heatmap":
                svg, png = heatmap_figure(paths["figure_stem"], source_df, index_col=source_df.columns[0], column_col=source_df.columns[1], value_col=source_df.columns[2], title=title, top_n_rows=12, top_n_cols=12)
            elif mode == "hist":
                svg, png = hist_figure(paths["figure_stem"], source_df, value_col=source_df.columns[-1], title=title)
            else:
                svg, png = bar_figure(paths["figure_stem"], source_df, label_col=source_df.columns[0], value_col=source_df.columns[1], title=title, top_n=15, compress_other=True)
            artifact = write_figure_bundle(
                figure_id=figure_id,
                title=title,
                tier="auto",
                recommendation="exploratory",
                feasibility="exploratory",
                source_df=source_df,
                input_tables=[table_name],
                source_csv_path=paths["source_csv"],
                source_json_path=paths["source_json"],
                svg_path=svg,
                png_path=png,
                warnings=["auto_generated"],
                empty_data_note=None if not source_df.empty else "No auto-figure data available.",
            )
            artifacts.append(artifact.__dict__)
            generated_for_table += 1
            figure_count += 1
    return artifacts


def _auto_candidates(table_name: str, frame: pd.DataFrame) -> list[tuple[str, pd.DataFrame, str]]:
    candidates: list[tuple[str, pd.DataFrame, str]] = []
    categorical_cols = [column for column in frame.columns if frame[column].dtype == object]
    numeric_cols = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
        group = frame.groupby(categorical_cols[0])[numeric_cols[0]].sum().reset_index()
        candidates.append((f"{table_name}_bar", group, "bar"))
    if len(numeric_cols) >= 1:
        candidates.append((f"{table_name}_hist", frame[[numeric_cols[0]]].dropna(), "hist"))
    if len(categorical_cols) >= 2 and len(numeric_cols) >= 1:
        group = frame.groupby([categorical_cols[0], categorical_cols[1]])[numeric_cols[0]].sum().reset_index()
        candidates.append((f"{table_name}_heatmap", group, "heatmap"))
    return candidates
