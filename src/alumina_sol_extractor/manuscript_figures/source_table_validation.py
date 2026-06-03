from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from alumina_sol_extractor.figure_atlas.loaders import load_all_inputs
from alumina_sol_extractor.figure_atlas.manuscript_diagnosis import (
    build_data_quality_report,
    build_data_quality_summary,
    build_manuscript_figure_plan,
    build_manuscript_figure_plan_md,
    build_table_inventory,
)
from alumina_sol_extractor.figure_atlas.table_builder import build_normalized_tables
from alumina_sol_extractor.manuscript_figures.data_logic import prepare_v2_payload


def run_source_table_validation(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    output_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    tables_root = root / "tables"
    source_root = root / "source_tables"
    qc_root = root / "qc"
    tables_root.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    qc_root.mkdir(parents=True, exist_ok=True)

    inputs = load_all_inputs(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_final_export_dir,
        stage3_analysis_dir=stage3_analysis_dir,
        stage3_publication_dir=stage3_publication_dir,
    )
    normalized_tables = build_normalized_tables(inputs)
    for name, frame in normalized_tables.items():
        _write_frame(tables_root / f"{name}.csv", frame)

    atlas_named_tables = {f"{name}.csv": frame for name, frame in normalized_tables.items()}
    inventory = build_table_inventory(atlas_named_tables)
    quality_summary = build_data_quality_summary(atlas_named_tables, inventory)
    figure_plan = build_manuscript_figure_plan(atlas_named_tables)
    v2_payload = prepare_v2_payload(root, support_tables_dir=tables_root)
    source_tables = {
        "Fig1_dataset_coverage_source.csv": v2_payload["figures"]["Fig1"],
        "Fig2_synthesis_parameter_landscape_source.csv": v2_payload["figures"]["Fig2"],
        "Fig4_characterization_evidence_atlas_source.csv": v2_payload["figures"]["Fig4"],
    }

    _write_frame(root / "normalized_table_summary.csv", _normalized_summary(normalized_tables))
    _write_frame(root / "table_inventory.csv", inventory)
    (root / "data_quality_summary.json").write_text(json.dumps(quality_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "data_quality_report.md").write_text(build_data_quality_report(quality_summary, inventory), encoding="utf-8")
    (root / "manuscript_figure_plan.json").write_text(json.dumps([row.__dict__ for row in figure_plan], ensure_ascii=False, indent=2), encoding="utf-8")
    _write_frame(root / "manuscript_figure_plan.csv", pd.DataFrame([row.__dict__ for row in figure_plan]))
    (root / "manuscript_figure_plan.md").write_text(build_manuscript_figure_plan_md(figure_plan), encoding="utf-8")

    source_inventory_rows: list[dict[str, Any]] = []
    manuscript_summary_rows: list[dict[str, Any]] = []
    for name, frame in source_tables.items():
        _write_frame(source_root / name, frame)
        included = int(frame["included_in_main_plot"].fillna(False).astype(bool).sum()) if "included_in_main_plot" in frame.columns else 0
        source_inventory_rows.append(
            {
                "file_name": name,
                "row_count": int(len(frame.index)),
                "column_count": int(len(frame.columns)),
                "included_rows": included,
                "excluded_rows": int(len(frame.index) - included),
            }
        )
        manuscript_summary_rows.append(
            {
                "figure_id": name.split("_")[0],
                "source_table": name,
                "row_count": int(len(frame.index)),
                "included_rows": included,
                "official_category_rows": int(frame["category"].isin({"mechanism", "fiber_process", "applications", "rheology"}).sum()) if "category" in frame.columns else 0,
            }
        )
    _write_frame(root / "source_table_inventory.csv", pd.DataFrame(source_inventory_rows))
    _write_frame(root / "manuscript_source_table_summary.csv", pd.DataFrame(manuscript_summary_rows))

    fig1_validation = _validate_fig1(source_tables["Fig1_dataset_coverage_source.csv"])
    fig2_validation = _validate_fig2(source_tables["Fig2_synthesis_parameter_landscape_source.csv"])
    fig4_validation = _validate_fig4(source_tables["Fig4_characterization_evidence_atlas_source.csv"])
    _write_frame(root / "fig1_source_validation.csv", fig1_validation)
    _write_frame(root / "fig2_source_validation.csv", fig2_validation)
    _write_frame(root / "fig4_source_validation.csv", fig4_validation)
    report = _build_report(fig1_validation, fig2_validation, fig4_validation)
    (root / "source_table_validation_report.md").write_text(report, encoding="utf-8")
    (root / "diagnosis_report.md").write_text(report, encoding="utf-8")

    return {
        "output_dir": str(root),
        "support_tables_dir": str(tables_root),
        "source_tables_dir": str(source_root),
        "report": str(root / "source_table_validation_report.md"),
    }


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _normalized_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, frame in tables.items():
        rows.append({"table_name": f"{name}.csv", "row_count": int(len(frame.index)), "column_count": int(len(frame.columns))})
    return pd.DataFrame(rows)


def _validate_fig1(frame: pd.DataFrame) -> pd.DataFrame:
    included = frame[frame["included_in_main_plot"].fillna(False).astype(bool)].copy()
    checks = [
        {"check": "no_uncategorized_in_main_panels", "passed": bool(~included["category"].fillna("").isin({"", "uncategorized", "unknown", "other"}).any()), "detail": f"included_rows={len(included.index)}"},
        {"check": "link_completeness_uses_fraction", "passed": bool(((included["panel_id"] == "C") & (included["metric"] == "completeness_fraction")).any()), "detail": "panel C should use completeness_fraction"},
    ]
    return pd.DataFrame(checks)


def _validate_fig2(frame: pd.DataFrame) -> pd.DataFrame:
    included = frame[frame["included_in_main_plot"].fillna(False).astype(bool)].copy()
    forbidden = {"unit", "context", "key", "source_text", "evidence_ref", "variables", "series_name", "xrd peak", "ftir peak", "nmr shift", "tg/dsc event"}
    labels = included["entity_label"].fillna("").astype(str).str.lower()
    panels = set(included["panel_id"].astype(str))
    checks = [
        {"check": "no_metadata_like_or_characterization_labels", "passed": bool(~labels.isin(forbidden).any()), "detail": f"forbidden_hits={int(labels.isin(forbidden).sum())}"},
        {"check": "temperature_and_time_split", "passed": bool("D" in panels and "E" in panels), "detail": "expect panel D temperature and panel E time"},
        {"check": "ph_distribution_retained", "passed": bool(((included["panel_id"] == "C") & included["entity_label"].fillna("").astype(str).str.contains("pH", case=False)).any()), "detail": "panel C should include pH rows"},
    ]
    return pd.DataFrame(checks)


def _validate_fig4(frame: pd.DataFrame) -> pd.DataFrame:
    included = frame[frame["included_in_main_plot"].fillna(False).astype(bool)].copy()
    checks = [
        {"check": "no_raw_peak_histogram_as_main_panel", "passed": bool(~((included["panel_id"] == "D_raw")).any()), "detail": "raw peak audit rows must stay excluded"},
        {"check": "approximate_bin_panel_present", "passed": bool(((included["panel_id"] == "D") & (included["metric"] == "binned_peak_count")).any()), "detail": "panel D should use binned_peak_count"},
        {"check": "heatmap_panels_present", "passed": bool(set(["A", "B", "C"]).issubset(set(included["panel_id"].astype(str)))), "detail": "expect panels A-C"},
    ]
    return pd.DataFrame(checks)


def _build_report(fig1: pd.DataFrame, fig2: pd.DataFrame, fig4: pd.DataFrame) -> str:
    def render(frame: pd.DataFrame, title: str) -> list[str]:
        lines = [f"## {title}"]
        for row in frame.to_dict(orient="records"):
            lines.append(f"- {row['check']}: {row['passed']} ({row['detail']})")
        return lines

    lines = ["# Source Table Validation", ""]
    lines.extend(render(fig1, "Fig1"))
    lines.append("")
    lines.extend(render(fig2, "Fig2"))
    lines.append("")
    lines.extend(render(fig4, "Fig4"))
    lines.append("")
    lines.append("Only existing Stage3/Stage4/Stage5 derived outputs were read. No upstream rerun or LLM/VLM call was used.")
    return "\n".join(lines) + "\n"
