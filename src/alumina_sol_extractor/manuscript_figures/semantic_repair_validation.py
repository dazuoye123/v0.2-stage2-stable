from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..figure_atlas.io import write_frame, write_json, write_markdown
from ..figure_atlas.loaders import load_all_inputs
from ..figure_atlas.table_builder import build_normalized_tables
from .data_logic import OFFICIAL_CATEGORIES, attach_resolved_category, build_paper_category_map


def run_semantic_repair_validation(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    validation_dir: Path,
) -> dict[str, str]:
    validation_dir.mkdir(parents=True, exist_ok=True)

    inputs = load_all_inputs(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_final_export_dir,
    )
    normalized_tables = build_normalized_tables(inputs)

    raw_tables = {
        "all_papers_final_parameters_linked.csv": _read_csv(batch_final_export_dir / "all_papers_final_parameters_linked.csv"),
        "all_papers_sample_parameter_matrix.csv": _read_csv(batch_final_export_dir / "all_papers_sample_parameter_matrix.csv"),
        "all_papers_evidence_parameter_links.csv": _read_csv(batch_final_export_dir / "all_papers_evidence_parameter_links.csv"),
        "all_papers_process_step_parameter_links.csv": _read_csv(batch_final_export_dir / "all_papers_process_step_parameter_links.csv"),
        "all_papers_spectra_parameter_links.csv": _read_csv(batch_final_export_dir / "all_papers_spectra_parameter_links.csv"),
        "all_papers_process_steps_table.csv": _read_csv(batch_final_export_dir / "all_papers_process_steps_table.csv"),
        "all_papers_excluded_parameters.csv": _read_csv(batch_final_export_dir / "all_papers_excluded_parameters.csv"),
        "all_papers_parameter_semantic_qa.csv": _read_csv(batch_final_export_dir / "all_papers_parameter_semantic_qa.csv"),
    }

    inventory = _build_inventory(batch_final_export_dir, raw_tables)
    category_validation = _build_category_semantics_validation(raw_tables)
    identity_validation = _build_identity_validation(raw_tables)
    parameter_semantic_summary = _build_parameter_semantic_summary(raw_tables["all_papers_parameter_semantic_qa.csv"])
    excluded_parameters = raw_tables["all_papers_excluded_parameters.csv"].copy()
    manuscript_summary = _build_manuscript_source_summary(normalized_tables)

    inventory_path = validation_dir / "repaired_export_inventory.csv"
    category_path = validation_dir / "category_semantics_validation.csv"
    identity_path = validation_dir / "identity_column_validation.csv"
    parameter_path = validation_dir / "parameter_semantic_role_summary.csv"
    excluded_path = validation_dir / "excluded_parameter_rows.csv"
    manuscript_path = validation_dir / "repaired_manuscript_source_table_summary.csv"
    report_path = validation_dir / "semantic_repair_report.md"

    write_frame(inventory_path, inventory)
    write_frame(category_path, category_validation)
    write_frame(identity_path, identity_validation)
    write_frame(parameter_path, parameter_semantic_summary)
    write_frame(excluded_path, excluded_parameters)
    write_frame(manuscript_path, manuscript_summary)

    manifest = {
        "outputs_dir": str(outputs_dir),
        "batch_final_export_dir": str(batch_final_export_dir),
        "validation_dir": str(validation_dir),
        "data_safety": {
            "stage3_rerun": False,
            "stage4_rerun": False,
            "stage5_rerun": False,
            "llm_or_vlm_called": False,
            "wrote_data_outputs": False,
        },
    }
    write_json(validation_dir / "semantic_repair_manifest.json", manifest)
    write_markdown(report_path, _build_report(inventory, category_validation, identity_validation, parameter_semantic_summary, manuscript_summary))

    return {
        "inventory": str(inventory_path),
        "category_validation": str(category_path),
        "identity_validation": str(identity_path),
        "parameter_semantic_summary": str(parameter_path),
        "excluded_parameters": str(excluded_path),
        "manuscript_summary": str(manuscript_path),
        "report": str(report_path),
    }


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _build_inventory(batch_final_export_dir: Path, raw_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in raw_tables.items():
        path = batch_final_export_dir / name
        rows.append(
            {
                "file_name": name,
                "exists": path.exists(),
                "row_count": int(len(frame.index)),
                "column_count": int(len(frame.columns)),
                "size_bytes": int(path.stat().st_size) if path.exists() else 0,
            }
        )
    return pd.DataFrame(rows)


def _build_category_semantics_validation(raw_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for table_name, frame in raw_tables.items():
        if frame.empty:
            rows.append(
                {
                    "table_name": table_name,
                    "row_count": 0,
                    "official_category_rows": 0,
                    "non_primary_category_rows": 0,
                    "missing_paper_category_rows": 0,
                    "category_mismatch_rows": 0,
                }
            )
            continue
        paper_category = frame["paper_category"].fillna("").astype(str) if "paper_category" in frame.columns else pd.Series("", index=frame.index)
        category = frame["category"].fillna("").astype(str) if "category" in frame.columns else pd.Series("", index=frame.index)
        paper_category_status = frame["paper_category_status"].fillna("").astype(str) if "paper_category_status" in frame.columns else pd.Series("", index=frame.index)
        rows.append(
            {
                "table_name": table_name,
                "row_count": int(len(frame.index)),
                "official_category_rows": int(paper_category.isin(OFFICIAL_CATEGORIES).sum()),
                "non_primary_category_rows": int((paper_category_status != "official").sum()) if "paper_category_status" in frame.columns else int((~paper_category.isin(OFFICIAL_CATEGORIES)).sum()),
                "missing_paper_category_rows": int((paper_category.str.strip() == "").sum()),
                "category_mismatch_rows": int(((category.str.strip() != "") & (paper_category.str.strip() != "") & (category != paper_category)).sum()) if "category" in frame.columns else 0,
            }
        )
    return pd.DataFrame(rows)


def _build_identity_validation(raw_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    required_columns = ["paper_id", "paper_category", "paper_category_status", "paper_dir"]
    rows: list[dict[str, Any]] = []
    for table_name, frame in raw_tables.items():
        row = {"table_name": table_name, "row_count": int(len(frame.index))}
        for column in required_columns:
            row[f"has_{column}"] = column in frame.columns
            row[f"missing_{column}_rows"] = int(frame[column].fillna("").astype(str).str.strip().eq("").sum()) if column in frame.columns else int(len(frame.index))
        for column in ("source_file", "source_stage"):
            row[f"has_{column}"] = column in frame.columns
            row[f"missing_{column}_rows"] = int(frame[column].fillna("").astype(str).str.strip().eq("").sum()) if column in frame.columns else 0
        rows.append(row)
    return pd.DataFrame(rows)


def _build_parameter_semantic_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["parameter_semantic_role", "included_in_main_parameter_landscape", "exclusion_reason", "row_count", "paper_count"])
    grouped = (
        frame.groupby(["parameter_semantic_role", "included_in_main_parameter_landscape", "exclusion_reason"], dropna=False)
        .agg(row_count=("parameter_id", "count"), paper_count=("paper_id", "nunique"))
        .reset_index()
        .sort_values(["parameter_semantic_role", "row_count"], ascending=[True, False])
    )
    return grouped


def _build_manuscript_source_summary(normalized_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    paper_category_map = build_paper_category_map(
        {
            "stage3_paper_summary": normalized_tables["stage3_paper_summary"],
            "stage4_paper_summary": normalized_tables["stage4_paper_summary"],
            "normalized_parameters": normalized_tables["normalized_parameters"],
            "normalized_stage4_spectra": normalized_tables["normalized_stage4_spectra"],
            "normalized_stage5_links": normalized_tables["normalized_stage5_links"],
        }
    )
    params = attach_resolved_category(normalized_tables["normalized_parameters"], paper_category_map)
    spectra = attach_resolved_category(normalized_tables["normalized_stage4_spectra"], paper_category_map)
    peaks = attach_resolved_category(normalized_tables["normalized_stage4_peaks"], paper_category_map)
    links = attach_resolved_category(normalized_tables["normalized_stage5_links"], paper_category_map)

    rows = [
        _summary_row("Fig1", "normalized_parameters", params),
        _summary_row("Fig1", "normalized_stage5_links", links),
        _summary_row("Fig2", "normalized_parameters", params),
        _summary_row("Fig4", "normalized_stage4_spectra", spectra),
        _summary_row("Fig4", "normalized_stage4_peaks", peaks),
        _summary_row("Fig4", "normalized_stage5_links", links[links["link_family"].astype(str) == "spectra"] if not links.empty and "link_family" in links.columns else links),
    ]
    return pd.DataFrame(rows)


def _summary_row(figure_id: str, source_component: str, frame: pd.DataFrame) -> dict[str, Any]:
    official = frame["resolved_category"].isin(OFFICIAL_CATEGORIES) if not frame.empty and "resolved_category" in frame.columns else pd.Series(dtype=bool)
    return {
        "figure_id": figure_id,
        "source_component": source_component,
        "row_count": int(len(frame.index)),
        "official_category_rows": int(official.sum()) if not frame.empty and "resolved_category" in frame.columns else 0,
        "non_primary_rows": int((~official).sum()) if not frame.empty and "resolved_category" in frame.columns else 0,
        "paper_count": int(frame["paper_id"].nunique()) if not frame.empty and "paper_id" in frame.columns else 0,
    }


def _build_report(
    inventory: pd.DataFrame,
    category_validation: pd.DataFrame,
    identity_validation: pd.DataFrame,
    parameter_semantic_summary: pd.DataFrame,
    manuscript_summary: pd.DataFrame,
) -> str:
    total_files = int(len(inventory.index))
    total_rows = int(inventory["row_count"].sum()) if not inventory.empty else 0
    mismatch_rows = int(category_validation["category_mismatch_rows"].sum()) if not category_validation.empty else 0
    missing_identity_rows = int(identity_validation[[col for col in identity_validation.columns if col.startswith("missing_")]].sum().sum()) if not identity_validation.empty else 0
    excluded_rows = int(parameter_semantic_summary[parameter_semantic_summary["included_in_main_parameter_landscape"].astype(str).str.lower().isin({"false", "0"})]["row_count"].sum()) if not parameter_semantic_summary.empty else 0
    lines = [
        "# Semantic Repair Validation",
        "",
        "## Summary",
        f"- aggregate_files_checked: {total_files}",
        f"- aggregate_rows_checked: {total_rows}",
        f"- category_mismatch_rows: {mismatch_rows}",
        f"- identity_missing_cells: {missing_identity_rows}",
        f"- excluded_parameter_rows: {excluded_rows}",
        "",
        "## Data Safety",
        "- Stage3 rerun: false",
        "- Stage4 rerun: false",
        "- Stage5 rerun: false",
        "- LLM or VLM called: false",
        "- data/outputs modified in place: false",
        "",
        "## Manuscript Source Readiness",
    ]
    if manuscript_summary.empty:
        lines.append("- no source summaries generated")
    else:
        for row in manuscript_summary.to_dict(orient="records"):
            lines.append(
                f"- {row['figure_id']} / {row['source_component']}: rows={row['row_count']}, "
                f"official={row['official_category_rows']}, non_primary={row['non_primary_rows']}, papers={row['paper_count']}"
            )
    return "\n".join(lines) + "\n"
