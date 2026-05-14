"""I/O helpers for link-aware export generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable


def build_link_aware_summary(
    *,
    final_parameters_linked: list[dict[str, Any]],
    evidence_parameter_links: list[dict[str, Any]],
    spectra_parameter_links: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    showcase_rows: list[dict[str, Any]],
    include_showcase: bool,
) -> dict[str, Any]:
    primary_statuses = {"strong_evidence", "process_step_evidence", "linked_evidence", "linked_spectra"}
    showcase_complete = include_showcase and bool(showcase_rows) and any(
        row.get("evidence_status") in primary_statuses for row in final_parameters_linked
    )
    process_step_parameter_links = sum(1 for row in evidence_parameter_links if row.get("source_type") == "process_step")
    evidence_object_parameter_links = sum(
        1
        for row in evidence_parameter_links
        if row.get("source_type") == "evidence_object" or row.get("created_by") == "direct_evidence_refs"
    )
    spectra_parameter_links_count = sum(
        1
        for row in spectra_parameter_links
        if row.get("created_by") not in {"deterministic_visual_value_match", "indirect"}
    )
    visual_parameter_links = sum(
        1
        for row in spectra_parameter_links
        if row.get("created_by") == "deterministic_visual_value_match"
    )
    return {
        "total_parameters": len(final_parameters_linked),
        "parameters_with_any_link": sum(
            1
            for row in final_parameters_linked
            if row.get("linked_sample_ids") or row.get("linked_evidence_ids") or row.get("linked_spectra_ids")
        ),
        "parameters_with_sample_link": sum(1 for row in final_parameters_linked if row.get("linked_sample_ids")),
        "parameters_with_evidence_link": sum(
            1 for row in final_parameters_linked if row.get("evidence_status") in {"strong_evidence", "process_step_evidence", "linked_evidence"}
        ),
        "parameters_with_spectra_link": sum(1 for row in final_parameters_linked if row.get("linked_spectra_ids")),
        "parameters_missing_all_links": sum(
            1
            for row in final_parameters_linked
            if not row.get("linked_sample_ids") and not row.get("linked_evidence_ids") and not row.get("linked_spectra_ids")
        ),
        "total_evidence_parameter_links": len(evidence_parameter_links),
        "total_spectra_parameter_links": len(spectra_parameter_links),
        "process_step_parameter_links": process_step_parameter_links,
        "evidence_object_parameter_links": evidence_object_parameter_links,
        "spectra_parameter_links": spectra_parameter_links_count,
        "visual_parameter_links": visual_parameter_links,
        "total_samples": len(samples),
        "sample_matrix_rows": len(samples),
        "showcase_rows": len(showcase_rows),
        "showcase_is_complete": showcase_complete,
        "showcase_warning": None
        if showcase_complete
        else "Preview/showcase table is incomplete or disabled; use the linked parameter, process step, evidence, spectra, and sample matrix tables as the primary outputs.",
        "recommended_primary_tables": [
            "final_parameters_linked.csv",
            "process_steps_table.csv",
            "evidence_parameter_links.csv",
            "spectra_parameter_links.csv",
            "sample_parameter_matrix.csv",
        ],
        "warning_count": sum(
            1
            for row in final_parameters_linked
            if row.get("evidence_status") == "missing" or "multi" in str(row.get("quality_flags") or "")
        ),
    }


def build_link_aware_readme(*, include_showcase: bool, output_warnings: list[str] | None = None) -> str:
    showcase_note = (
        "- `final_showcase_table.csv`: quick preview only; it is not the authoritative table for downstream statistics or database ingestion."
        if include_showcase
        else "- `final_showcase_table.csv`: preview generation was skipped; rely on the primary linked tables below."
    )
    warning_lines = (
        ["", "## Output Warnings", *[f"- `{item}`" for item in output_warnings]]
        if output_warnings
        else []
    )
    return "\n".join(
        [
            "# Link-aware Final Dataset Exports",
            "",
            "## Primary Tables",
            "- `final_parameters_linked.csv`: the main parameter-level table with resolved sample, evidence, process-step, and spectra links.",
            "- `process_steps_table.csv`: ordered experimental procedure steps with linked parameters and evidence text.",
            "- `evidence_parameter_links.csv`: direct process-step and evidence-object links to parameters.",
            "- `spectra_parameter_links.csv`: direct spectra peak links and indirect spectra-evidence-parameter links.",
            "- `sample_parameter_matrix.csv`: sample-centric comparison matrix for meetings and sample-level review.",
            "",
            "## Additional Files",
            "- `final_parameters_linked.parquet`: parquet version of the linked parameter table.",
            showcase_note,
            "- `link_aware_export_summary.json`: export statistics and guidance on which tables to treat as primary.",
            "",
            "## Notes",
            "- Original `parameters.jsonl`, `process_steps.jsonl`, `evidence.jsonl`, `spectra.jsonl`, and `samples.jsonl` are not modified.",
            "- Missing links remain explicit; the exporter does not invent unsupported evidence or spectra relationships.",
            "- Prefer the primary tables above for final analysis, database loading, and group-meeting reporting.",
            "- If a CSV is locked by Excel, WPS, VS Code preview, or Explorer preview pane, the exporter keeps the warning and writes a `*.generated.csv` fallback when possible.",
            "- If `process_steps_table.csv` could not be overwritten, check `process_steps_table.generated.csv` first, then close the locking application and rerun the Stage 5+ export command.",
            *warning_lines,
        ]
    )


def write_csv_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def write_parquet_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=fieldnames)
    for column in frame.columns:
        if str(frame[column].dtype) == "object":
            frame[column] = frame[column].apply(_parquet_value).astype("string")
    frame.to_parquet(path, index=False)


def safe_write(
    path: Path,
    writer: Callable[[Path], None],
    warnings: list[str],
    *,
    locked_files: list[str] | None = None,
    fallback_outputs: list[str] | None = None,
) -> None:
    try:
        writer(path)
    except PermissionError:
        warnings.append(f"could_not_overwrite_locked_file:{path.name}")
        if locked_files is not None:
            locked_files.append(path.name)
        fallback_path = path.with_name(f"{path.stem}.generated{path.suffix}")
        try:
            writer(fallback_path)
            warnings.append(f"wrote_fallback_output:{fallback_path.name}")
            if fallback_outputs is not None:
                fallback_outputs.append(fallback_path.name)
        except PermissionError:
            warnings.append(f"could_not_write_fallback_output:{fallback_path.name}")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _parquet_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
