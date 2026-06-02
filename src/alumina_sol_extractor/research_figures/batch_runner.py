from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .figure_builders import generate_all_figures
from .figure_data import build_research_figure_data, build_stage3_stage4_figure_index
from .io import ensure_dir, write_csv, write_json, write_markdown
from .stage3_inputs import filter_stage3_analysis, load_stage3_analysis
from .stage4_inputs import load_stage4_batch_data


def run_research_figures(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_output_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
    manifest_path: Path | None = None,
    generate_figures: bool = True,
) -> dict[str, Any]:
    stage3_payload = load_stage3_analysis(project_root=project_root, analysis_dir=stage3_analysis_dir, publication_dir=stage3_publication_dir)
    selection = _load_manifest_selection(manifest_path)
    stage3_payload = filter_stage3_analysis(stage3_payload, selected_pairs=selection["selected_pairs"], selected_paper_ids=selection["selected_paper_ids"])
    stage4_payload = load_stage4_batch_data(outputs_dir, selected_pairs=selection["selected_pairs"], selected_paper_ids=selection["selected_paper_ids"])
    figure_tables = build_research_figure_data(stage3_payload, stage4_payload)

    timestamp_dir = ensure_dir(batch_output_dir / datetime.now().strftime("%Y%m%d_%H%M%S") / "research_figures")
    figures_dir = ensure_dir(timestamp_dir / "figures")
    tables_dir = ensure_dir(timestamp_dir / "tables")
    figure_data_dir = ensure_dir(timestamp_dir / "figure_data")

    written_tables = _write_tables(tables_dir, figure_tables)
    figure_index = build_stage3_stage4_figure_index(figure_tables)
    stage3_stage4_joint_data = _resolve_stage3_stage4_joint_data(figure_tables)
    stage3_stage4_joint_path = timestamp_dir / "stage3_stage4_figure_data.csv"
    if isinstance(stage3_stage4_joint_data, pd.DataFrame):
        stage3_stage4_joint_data.to_csv(stage3_stage4_joint_path, index=False, encoding="utf-8-sig")
    else:
        write_csv(stage3_stage4_joint_path, stage3_stage4_joint_data)
    for item in figure_index:
        table = _resolve_figure_snapshot_table(item["figure_name"], figure_tables)
        write_json(
            figure_data_dir / f"{item['figure_name']}.json",
            _serialize_figure_table(item["figure_name"], item["description"], item["primary_csv"], table),
        )
    write_json(
        figure_data_dir / "input_sources.json",
        {
            "stage3_analysis_dir": stage3_payload["analysis_dir"],
            "stage3_publication_dir": stage3_payload["publication_dir"],
            "outputs_dir": str(outputs_dir),
            "manifest_path": str(manifest_path) if manifest_path else None,
            "selected_pairs": sorted(f"{category}/{paper_id}" for category, paper_id in selection["selected_pairs"]),
            "selected_paper_ids": sorted(selection["selected_paper_ids"]),
            "warnings": sorted(set(stage3_payload["warnings"] + stage4_payload["warnings"])),
        },
    )

    written_figures: list[str] = []
    if generate_figures:
        written_figures = generate_all_figures(figures_dir, figure_tables)

    report_path = write_markdown(
        timestamp_dir / "batch_research_figures.md",
        _render_batch_report(
            stage3_payload=stage3_payload,
            stage4_payload=stage4_payload,
            written_tables=written_tables,
            written_figures=written_figures,
            figure_index=figure_index,
            manifest_path=manifest_path,
        ),
    )
    return {
        "output_dir": str(timestamp_dir),
        "figures_dir": str(figures_dir),
        "tables_dir": str(tables_dir),
        "figure_data_dir": str(figure_data_dir),
        "report_path": str(report_path),
        "written_figures": written_figures,
        "written_tables": written_tables,
    }


def _write_tables(tables_dir: Path, figure_tables: dict[str, pd.DataFrame]) -> dict[str, str]:
    written: dict[str, str] = {}
    for name, frame in figure_tables.items():
        filename = f"{name}.csv"
        path = tables_dir / filename
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            write_csv(path, frame)
        written[filename] = str(path)
    alias_map = {
        "stage3_sample_parameter_heatmap.csv": "stage3_sample_parameter_matrix.csv",
        "stage3_stage4_link_overview.csv": "stage3_stage4_link_table.csv",
    }
    for source_name, alias_name in alias_map.items():
        if source_name not in written:
            continue
        source_path = tables_dir / source_name
        alias_path = tables_dir / alias_name
        alias_path.write_bytes(source_path.read_bytes())
        written[alias_name] = str(alias_path)
    return written


def _render_batch_report(
    *,
    stage3_payload: dict[str, Any],
    stage4_payload: dict[str, Any],
    written_tables: dict[str, str],
    written_figures: list[str],
    figure_index: list[dict[str, Any]],
    manifest_path: Path | None,
) -> str:
    lines = [
        "# Batch Research Figures",
        "",
        "## Input data sources",
        f"- Stage3 analysis dir: {stage3_payload['analysis_dir']}",
        f"- Stage3 publication dir: {stage3_payload['publication_dir']}",
        f"- Outputs dir: {stage4_payload.get('outputs_dir', 'scanned from CLI path')}" if stage4_payload.get("outputs_dir") else "- Outputs dir: scanned from CLI path",
        f"- Manifest path: {manifest_path}" if manifest_path else "- Manifest path: none",
        f"- Stage4 papers scanned: {len(stage4_payload['per_paper_rows'])}",
        "",
        "## Figures generated",
    ]
    if written_figures:
        lines.extend(f"- {Path(path).name}" for path in written_figures)
    else:
        lines.append("- no figures generated")
    lines.extend(["", "## Figure to CSV mapping"])
    for item in figure_index:
        lines.append(f"- {item['figure_name']}: {item['primary_csv']}")
    lines.extend(["", "## Data warnings"])
    warnings = sorted(set(stage3_payload["warnings"] + stage4_payload["warnings"]))
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _serialize_figure_table(
    figure_name: str,
    description: str,
    primary_csv: str,
    table: Any,
) -> dict[str, Any]:
    if isinstance(table, pd.DataFrame):
        return {
            "figure_name": figure_name,
            "description": description,
            "primary_csv": primary_csv,
            "columns": table.columns.tolist(),
            "row_count": int(len(table)),
            "rows": table.to_dict(orient="records"),
        }
    return {
        "figure_name": figure_name,
        "description": description,
        "primary_csv": primary_csv,
        "columns": [],
        "row_count": 0,
        "rows": [],
    }


def _resolve_figure_snapshot_table(figure_name: str, figure_tables: dict[str, Any]) -> Any:
    if figure_name == "stage3_stage4_research_overview":
        return _resolve_stage3_stage4_joint_data(figure_tables)
    return figure_tables.get(figure_name)


def _resolve_stage3_stage4_joint_data(figure_tables: dict[str, Any]) -> Any:
    return figure_tables.get("stage3_stage4_link_overview", pd.DataFrame())


def _load_manifest_selection(manifest_path: Path | None) -> dict[str, set[Any]]:
    if manifest_path is None or not manifest_path.exists():
        return {"selected_pairs": set(), "selected_paper_ids": set()}
    manifest = pd.read_csv(manifest_path)
    paper_column = "paper_id_guess" if "paper_id_guess" in manifest.columns else "paper_id" if "paper_id" in manifest.columns else None
    category_column = "category" if "category" in manifest.columns else None
    selected_pairs: set[tuple[str, str]] = set()
    selected_paper_ids: set[str] = set()
    if paper_column is None:
        return {"selected_pairs": selected_pairs, "selected_paper_ids": selected_paper_ids}
    for _, row in manifest.iterrows():
        paper_id = _clean_manifest_value(row.get(paper_column))
        category = _clean_manifest_value(row.get(category_column)) if category_column else ""
        if not paper_id:
            continue
        selected_paper_ids.add(paper_id)
        if category:
            selected_pairs.add((category, paper_id))
    return {"selected_pairs": selected_pairs, "selected_paper_ids": selected_paper_ids}


def _clean_manifest_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()
