"""Validation helpers for Stage 5 dataset fusion."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_quality_summary(
    *,
    stage3_summary: dict[str, Any],
    stage4_summary: dict[str, Any],
    stage4_review: dict[str, Any],
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    process_steps: list[dict[str, Any]],
    fusion_warnings: list[str],
    rejected_parameters: list[dict[str, Any]],
) -> dict[str, Any]:
    parameters_with_strong_evidence = sum(1 for item in parameters if item.get("linked_evidence_ids"))
    parameters_with_weak_spectra_link = sum(
        1 for item in parameters if "weak_link_from_spectra" in set(item.get("quality_flags") or [])
    )
    parameters_without_evidence = sum(
        1
        for item in parameters
        if not item.get("linked_evidence_ids") and "weak_link_from_spectra" not in set(item.get("quality_flags") or [])
    )
    paper_level_parameters_without_direct_evidence = sum(
        1 for item in parameters if not item.get("linked_evidence_ids") and not item.get("sample_id")
    )
    spectra_with_warning = sum(
        1
        for item in spectra
        if item.get("warning_codes") or item.get("conflict_warnings") or str(item.get("quality_review_assessment") or "").endswith("warning")
    )
    return {
        "stage3_schema_valid": stage3_summary.get("schema_valid"),
        "stage3_canonical_key_errors_count": stage3_summary.get("canonical_key_errors_count", 0),
        "stage3_core_parameter_without_evidence_count": stage3_summary.get("core_parameter_without_evidence_count", 0),
        "stage4_total_records": stage4_summary.get("total_candidates", stage4_review.get("summary", {}).get("total_records", 0)),
        "stage4_failed_record_count": stage4_summary.get("failed_record_count", 0),
        "stage4_validation_error_count": stage4_summary.get("validation_error_count", 0),
        "stage4_overall_status": stage4_review.get("summary", {}).get("overall_status"),
        "total_parameters": len(parameters),
        "total_evidence": len(evidence),
        "total_spectra": len(spectra),
        "total_samples": len(samples),
        "total_process_steps": len(process_steps),
        "process_steps_with_reagent_amount_count": sum(1 for item in process_steps if item.get("reagent_amount") not in (None, "")),
        "process_steps_with_evidence_count": sum(1 for item in process_steps if str(item.get("evidence_text") or "").strip()),
        "process_steps_needs_manual_review_count": sum(1 for item in process_steps if bool(item.get("needs_manual_review"))),
        "parameters_with_strong_evidence_count": parameters_with_strong_evidence,
        "parameters_with_weak_spectra_link_count": parameters_with_weak_spectra_link,
        "parameters_without_evidence_count": parameters_without_evidence,
        "paper_level_parameters_without_direct_evidence_count": paper_level_parameters_without_direct_evidence,
        "invalid_canonical_key_count": len(rejected_parameters),
        "spectra_with_warning_count": spectra_with_warning,
        "fusion_warning_count": len(fusion_warnings),
        "fusion_warning_types": dict(Counter(fusion_warnings)),
    }
