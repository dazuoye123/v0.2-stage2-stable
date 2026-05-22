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
    sample_parameter_matrix: list[dict[str, Any]],
    showcase_rows: list[dict[str, Any]],
    include_showcase: bool,
) -> dict[str, Any]:
    primary_statuses = {"strong_evidence", "process_step_evidence", "linked_evidence", "linked_spectra"}
    evidence_link_statuses = {"strong_evidence", "process_step_evidence", "linked_evidence"}
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
            if row.get("linked_sample_ids")
            or row.get("linked_spectra_ids")
            or row.get("evidence_status") in primary_statuses
        ),
        "parameters_with_sample_link": sum(1 for row in final_parameters_linked if row.get("linked_sample_ids")),
        "parameters_with_evidence_link": sum(
            1 for row in final_parameters_linked if row.get("evidence_status") in evidence_link_statuses
        ),
        "parameters_with_spectra_link": sum(1 for row in final_parameters_linked if row.get("linked_spectra_ids")),
        "parameters_missing_all_links": sum(
            1
            for row in final_parameters_linked
            if not row.get("linked_sample_ids")
            and not row.get("linked_spectra_ids")
            and row.get("evidence_status") not in primary_statuses
        ),
        "total_evidence_parameter_links": len(evidence_parameter_links),
        "total_spectra_parameter_links": len(spectra_parameter_links),
        "process_step_parameter_links": process_step_parameter_links,
        "evidence_object_parameter_links": evidence_object_parameter_links,
        "spectra_parameter_links": spectra_parameter_links_count,
        "visual_parameter_links": visual_parameter_links,
        "total_samples": len(sample_parameter_matrix),
        "sample_matrix_rows": len(sample_parameter_matrix),
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
            "sample_parameter_matrix_long.csv",
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
            "- `sample_parameter_matrix_long.csv`: provenance-aware long table for sample-level values; prefer this for plotting and diagnostics.",
            "",
            "## Additional Files",
            "- `sample_matrix_missing_diagnosis.csv`: per-sample / per-canonical-key explanation of why a matrix cell is blank or left blank.",
            "- `final_parameters_linked.parquet`: parquet version of the linked parameter table.",
            showcase_note,
            "- `link_aware_export_summary.json`: export statistics and guidance on which tables to treat as primary.",
            "- `link_aware_export_diagnosis.md`: a markdown snapshot rebuilt from the latest summary, latest table row counts, and sample-matrix completeness diagnostics.",
            "",
            "## Notes",
            "- Original `parameters.jsonl`, `process_steps.jsonl`, `evidence.jsonl`, `spectra.jsonl`, and `samples.jsonl` are not modified.",
            "- Missing links remain explicit; the exporter does not invent unsupported evidence or spectra relationships.",
            "- Prefer the primary tables above for final analysis, database loading, and group-meeting reporting.",
            "- `parameter_count` and `linked_parameter_count` in `sample_parameter_matrix.csv` are legacy fields kept for compatibility.",
            "- For new analysis and plotting, prefer `matrix_parameter_field_count`, `sample_parameter_value_count`, `unique_linked_parameter_count`, `linked_parameter_edge_count`, `linked_evidence_edge_count`, `linked_spectra_edge_count`, and `linked_process_step_edge_count`.",
            "- `sample_parameter_matrix_long.csv` records `value_origin` so you can distinguish `direct_sample_link` from conservative `broadcast_global` fills.",
            "- `sample_matrix_missing_diagnosis.csv` explains blanks such as `no_parameter_extracted`, `extracted_but_unresolved_sample`, `global_applies_to_all_samples`, and `not_sample_level`.",
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


def build_link_aware_diagnosis(output_dir: Path | str) -> str:
    output_dir = Path(output_dir)
    summary_path = output_dir / "link_aware_export_summary.json"
    summary: dict[str, Any] = {}
    warnings: list[str] = []

    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warnings.append("could_not_parse_summary:link_aware_export_summary.json")
    else:
        warnings.append("missing_file:link_aware_export_summary.json")

    table_summaries = [
        _collect_table_count(output_dir, "final_parameters_linked.csv", warnings, summary),
        _collect_table_count(output_dir, "process_steps_table.csv", warnings, summary),
        _collect_table_count(output_dir, "evidence_parameter_links.csv", warnings, summary),
        _collect_table_count(output_dir, "spectra_parameter_links.csv", warnings, summary),
        _collect_table_count(output_dir, "sample_parameter_matrix.csv", warnings, summary),
        _collect_table_count(output_dir, "sample_parameter_matrix_long.csv", warnings, summary),
        _collect_table_count(output_dir, "sample_matrix_missing_diagnosis.csv", warnings, summary),
    ]
    summary_lines = [
        f"- `total_parameters`: {_render_summary_value(summary, 'total_parameters')}",
        f"- `parameters_with_any_link`: {_render_summary_value(summary, 'parameters_with_any_link')}",
        f"- `parameters_missing_all_links`: {_render_summary_value(summary, 'parameters_missing_all_links')}",
        f"- `process_step_parameter_links`: {_render_summary_value(summary, 'process_step_parameter_links')}",
        f"- `sample_matrix_rows`: {_render_summary_value(summary, 'sample_matrix_rows')}",
    ]
    table_lines = []
    for item in table_summaries:
        label = f"`{item['file_name']}` rows"
        if item["row_count"] is None:
            table_lines.append(f"- {label}: warning")
            continue
        suffix = f" ({item['source_label']})" if item["source_label"] else ""
        table_lines.append(f"- {label}: {item['row_count']}{suffix}")

    warning_lines = warnings or ["none"]
    completeness_lines = _build_sample_matrix_completeness_lines(output_dir, warnings, summary)
    return "\n".join(
        [
            "# Link-aware Export Diagnosis",
            "",
            "Generated from the latest `link_aware_export_summary.json` and current table files in this directory.",
            "",
            "## Summary Snapshot",
            *summary_lines,
            "",
            "## Table Row Counts",
            *table_lines,
            "",
            "## Sample Matrix Count Notes",
            "- `parameter_count` and `linked_parameter_count` are legacy fields kept for backward compatibility.",
            "- Prefer `matrix_parameter_field_count`, `sample_parameter_value_count`, `unique_linked_parameter_count`, and the `linked_*_edge_count` fields for new analysis.",
            "- Prefer `sample_parameter_matrix_long.csv` when you need provenance (`direct_sample_link` vs `broadcast_global`) for plotting or QA.",
            "",
            "## Sample Matrix Completeness",
            *completeness_lines,
            "",
            "## Warnings",
            *[f"- `{item}`" for item in warning_lines],
        ]
    )


def _collect_table_count(
    output_dir: Path,
    file_name: str,
    warnings: list[str],
    summary: dict[str, Any],
) -> dict[str, Any]:
    canonical_path = output_dir / file_name
    fallback_name = f"{canonical_path.stem}.generated{canonical_path.suffix}"
    fallback_path = output_dir / fallback_name
    locked_files = set(summary.get("locked_files") or [])

    if file_name in locked_files:
        if fallback_path.exists():
            return {
                "file_name": file_name,
                "row_count": _csv_row_count(fallback_path),
                "source_label": f"latest fallback `{fallback_name}`",
            }
        warnings.append(f"locked_file_missing_fallback:{file_name}")
        return {"file_name": file_name, "row_count": None, "source_label": None}

    if canonical_path.exists():
        return {"file_name": file_name, "row_count": _csv_row_count(canonical_path), "source_label": None}

    if fallback_path.exists():
        warnings.append(f"missing_canonical_using_fallback:{file_name}")
        return {
            "file_name": file_name,
            "row_count": _csv_row_count(fallback_path),
            "source_label": f"fallback `{fallback_name}`",
        }

    warnings.append(f"missing_file:{file_name}")
    return {"file_name": file_name, "row_count": None, "source_label": None}


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _render_summary_value(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    return "warning" if value is None else str(value)


def _build_sample_matrix_completeness_lines(
    output_dir: Path,
    warnings: list[str],
    summary: dict[str, Any],
) -> list[str]:
    diagnosis_info = _collect_table_count(output_dir, "sample_matrix_missing_diagnosis.csv", warnings, summary)
    long_info = _collect_table_count(output_dir, "sample_parameter_matrix_long.csv", warnings, summary)
    diagnosis_path = _resolved_table_path(output_dir, diagnosis_info["file_name"], summary)
    long_path = _resolved_table_path(output_dir, long_info["file_name"], summary)
    lines: list[str] = []

    if diagnosis_path is None or not diagnosis_path.exists():
        return ["- warning: sample matrix missing diagnosis is unavailable."]

    reason_counts: dict[str, int] = {}
    with diagnosis_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            reason = (row.get("missing_reason") or "").strip() or "unknown"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    if not reason_counts:
        lines.append("- no blank matrix cells were recorded in `sample_matrix_missing_diagnosis.csv`.")
    else:
        for reason in sorted(reason_counts):
            lines.append(f"- `{reason}`: {reason_counts[reason]}")

    if long_path is not None and long_path.exists():
        origin_counts: dict[str, int] = {}
        with long_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                origin = (row.get("value_origin") or "").strip() or "unknown"
                origin_counts[origin] = origin_counts.get(origin, 0) + 1
        for origin in sorted(origin_counts):
            lines.append(f"- `value_origin={origin}` rows: {origin_counts[origin]}")
    else:
        lines.append("- warning: `sample_parameter_matrix_long.csv` is unavailable, so provenance counts could not be summarized.")
    return lines


def _resolved_table_path(output_dir: Path, file_name: str, summary: dict[str, Any]) -> Path | None:
    canonical_path = output_dir / file_name
    if canonical_path.exists() and file_name not in set(summary.get("locked_files") or []):
        return canonical_path
    fallback_path = output_dir / f"{canonical_path.stem}.generated{canonical_path.suffix}"
    if fallback_path.exists():
        return fallback_path
    if canonical_path.exists():
        return canonical_path
    return None
