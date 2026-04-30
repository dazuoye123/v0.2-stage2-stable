"""Reporting helpers for Stage 3 dry-run validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_stage3_validation_report(
    *,
    output_path: Path,
    schema_valid: bool,
    canonical_key_errors: list[dict[str, Any]],
    unit_warnings: list[dict[str, Any]],
    duplicate_ids: list[dict[str, Any]],
    evidence_ref_warnings: list[dict[str, Any]],
    extended_data_core_keys: list[dict[str, Any]],
    rejected_parameter_records: list[dict[str, Any]],
    quality_flags: list[str],
) -> dict[str, Any]:
    """Write a markdown validation report and return its summary payload."""

    summary = {
        "schema_valid": schema_valid,
        "canonical_key_errors_count": len(canonical_key_errors),
        "unit_warning_count": len(unit_warnings),
        "duplicate_id_count": len(duplicate_ids),
        "evidence_ref_warning_count": len(evidence_ref_warnings),
        "extended_data_core_key_count": len(extended_data_core_keys),
        "rejected_parameter_records_count": len(rejected_parameter_records),
        "quality_flags": quality_flags,
        "report_path": str(output_path),
    }

    sections = [
        "# Stage 3 Validation Report",
        "",
        f"- schema_valid: `{schema_valid}`",
        f"- canonical_key_errors_count: `{len(canonical_key_errors)}`",
        f"- unit_warning_count: `{len(unit_warnings)}`",
        f"- duplicate_id_count: `{len(duplicate_ids)}`",
        f"- evidence_ref_warning_count: `{len(evidence_ref_warnings)}`",
        f"- extended_data_core_key_count: `{len(extended_data_core_keys)}`",
        f"- rejected_parameter_records_count: `{len(rejected_parameter_records)}`",
        f"- quality_flags: `{quality_flags}`",
        "",
        _format_issue_section("Canonical Key Errors", canonical_key_errors),
        _format_issue_section("Unit Warnings", unit_warnings),
        _format_issue_section("Duplicate IDs", duplicate_ids),
        _format_issue_section("Evidence Ref Warnings", evidence_ref_warnings),
        _format_issue_section("Core Keys Hidden in extended_data", extended_data_core_keys),
        _format_issue_section("Rejected Parameter Records", rejected_parameter_records),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections).strip() + "\n", encoding="utf-8")
    return summary


def _format_issue_section(title: str, issues: list[dict[str, Any]]) -> str:
    lines = [f"## {title}", ""]
    if not issues:
        lines.append("- none")
        lines.append("")
        return "\n".join(lines)
    for issue in issues[:50]:
        lines.append(f"- `{issue}`")
    if len(issues) > 50:
        lines.append(f"- ... and {len(issues) - 50} more")
    lines.append("")
    return "\n".join(lines)
