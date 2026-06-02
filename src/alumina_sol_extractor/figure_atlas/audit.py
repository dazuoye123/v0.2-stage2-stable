from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .discovery import discover_inputs
from .io import write_frame, write_json, write_markdown
from .schemas import planned_figure_specs


def run_audit(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    audit_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
) -> dict[str, Any]:
    inventory = discover_inputs(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_final_export_dir,
        stage3_analysis_dir=stage3_analysis_dir,
        stage3_publication_dir=stage3_publication_dir,
    )
    availability = pd.DataFrame(inventory["availability_rows"])
    schema_report = inventory["schema_reports"]
    feasibility = pd.DataFrame(_build_feasibility_rows(inventory))

    write_json(audit_dir / "result_inventory.json", _inventory_json(inventory, availability, schema_report))
    write_markdown(audit_dir / "result_inventory.md", _inventory_markdown(inventory, availability))
    write_frame(audit_dir / "data_availability_matrix.csv", availability)
    write_frame(audit_dir / "figure_feasibility_matrix.csv", feasibility)
    write_json(audit_dir / "input_table_schema_report.json", schema_report)
    write_markdown(audit_dir / "input_table_schema_report.md", _schema_markdown(schema_report))

    return {
        "inventory": inventory,
        "availability": availability,
        "feasibility": feasibility,
        "schema_report": schema_report,
        "core_inputs_ready": all(inventory["core_input_availability"].values()),
    }


def _build_feasibility_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    available_sources = {
        "normalized_parameters": inventory["core_input_availability"].get("all_papers_final_parameters_linked.csv", False),
        "normalized_process_steps": inventory["core_input_availability"].get("all_papers_process_steps_table.csv", False),
        "normalized_stage4_spectra": inventory["stage4_paper_count"] > 0,
        "normalized_stage4_peaks": inventory["stage4_paper_count"] > 0,
        "normalized_stage5_links": inventory["core_input_availability"].get("all_papers_spectra_parameter_links.csv", False),
        "normalized_sample_matrix": inventory["core_input_availability"].get("all_papers_final_parameters_linked.csv", False),
    }
    rows: list[dict[str, Any]] = []
    for spec in planned_figure_specs():
        missing = [item for item in spec.required_tables if not available_sources.get(item, False)]
        optional_available = [item for item in spec.optional_tables if available_sources.get(item, False)]
        if not missing:
            feasibility = "ready"
            reason = "all required inputs available"
        elif len(missing) < len(spec.required_tables):
            feasibility = "partial"
            reason = f"missing required inputs: {', '.join(missing)}"
        else:
            feasibility = "not_available"
            reason = f"missing all required inputs: {', '.join(missing)}"
        if spec.tier == "qa":
            recommended_tier = "qa"
        elif spec.tier == "cross_stage":
            recommended_tier = "cross_stage"
        else:
            recommended_tier = spec.tier
        rows.append(
            {
                "figure_id": spec.figure_id,
                "figure_title": spec.title,
                "required_inputs": "; ".join(spec.required_tables),
                "optional_inputs": "; ".join(spec.optional_tables),
                "available": not missing,
                "feasibility": feasibility,
                "reason": reason,
                "recommended_tier": recommended_tier,
            }
        )
    return rows


def _inventory_json(inventory: dict[str, Any], availability: pd.DataFrame, schema_report: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage3_directories_found": inventory["stage3_dirs_found"],
        "stage3_publication_directories_found": inventory["stage3_publication_dirs_found"],
        "stage4_paper_count": inventory["stage4_paper_count"],
        "stage5_paper_count": inventory["stage5_paper_count"],
        "batch_export_files_found": inventory["batch_export_files_found"],
        "core_input_availability": inventory["core_input_availability"],
        "missing_files": availability.loc[~availability["exists"], "file_path"].tolist(),
        "row_counts": {
            row["file_path"]: int(row["row_count"])
            for row in availability.to_dict(orient="records")
            if row["exists"]
        },
        "schema_columns": {item["name"]: item["columns"] for item in schema_report},
        "warnings": inventory["warnings"],
    }


def _inventory_markdown(inventory: dict[str, Any], availability: pd.DataFrame) -> str:
    lines = [
        "# Result Inventory",
        "",
        "## Current result locations",
        f"- Stage3 dirs: {', '.join(inventory['stage3_dirs_found']) or 'none'}",
        f"- Stage3 publication dirs: {', '.join(inventory['stage3_publication_dirs_found']) or 'none'}",
        f"- Stage4 paper count: {inventory['stage4_paper_count']}",
        f"- Stage5 paper count: {inventory['stage5_paper_count']}",
        "",
        "## Batch export availability",
    ]
    for filename, exists in inventory["core_input_availability"].items():
        lines.append(f"- {filename}: {'ok' if exists else 'missing'}")
    usable = availability["usable_for_figures"].sum() if not availability.empty else 0
    lines.extend(
        [
            "",
            "## Figure readiness",
            f"- Data sources usable for figures: {int(usable)}",
            f"- Missing files: {int((~availability['exists']).sum()) if not availability.empty else 0}",
            f"- Overall sufficient for plotting: {'yes' if all(inventory['core_input_availability'].values()) else 'no'}",
            "",
            "## Warnings",
        ]
    )
    if inventory["warnings"]:
        lines.extend(f"- {warning}" for warning in inventory["warnings"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _schema_markdown(schema_report: list[dict[str, Any]]) -> str:
    lines = ["# Input Table Schema Report", ""]
    for item in schema_report:
        lines.append(f"## {item['name']}")
        lines.append(f"- rows: {item['row_count']}")
        lines.append(f"- columns: {item['column_count']}")
        lines.append(f"- fields: {', '.join(item['columns'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
