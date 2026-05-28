"""Validation helpers for Stage 4 outputs."""

from __future__ import annotations

from collections import Counter
from numbers import Number
from typing import Any


_KNOWN_FIGURE_TYPES = {
    "nmr_spectrum",
    "ftir_spectrum",
    "ir_spectrum",
    "raman_spectrum",
    "xrd_pattern",
    "ferron_curve",
    "tg_curve",
    "dsc_curve",
    "tg_dsc_curve",
    "sem_image",
    "tem_image",
    "microscopy",
    "unknown",
    "non_extractable",
}


def validate_stage4_extraction(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not record.get("figure_id"):
        errors.append("missing_figure_id")
    figure_type = record.get("figure_type")
    if figure_type and figure_type not in _KNOWN_FIGURE_TYPES:
        errors.append("unknown_figure_type")
    schema_name = record.get("schema_name")
    if schema_name and not isinstance(schema_name, str):
        errors.append("invalid_schema_name")
    peaks = record.get("peaks")
    if peaks is not None and not isinstance(peaks, list):
        errors.append("peaks_not_list")
    confidence = record.get("confidence")
    if confidence is not None and (not isinstance(confidence, Number) or confidence < 0 or confidence > 1):
        errors.append("invalid_confidence")
    return errors


def build_stage4_summary(
    *,
    candidates: list[dict[str, Any]],
    extractions: list[dict[str, Any]],
    failed_records: list[dict[str, Any]],
    config_warnings: list[str] | None = None,
) -> dict[str, Any]:
    by_type = Counter(str(item.get("figure_type") or "unknown") for item in candidates)
    by_stage2_class = Counter(str(item.get("stage2_figure_class") or "unknown") for item in candidates)
    by_initial_type = Counter(str(item.get("initial_figure_type") or item.get("figure_type") or "unknown") for item in candidates)
    by_routing_reason = Counter(str(item.get("routing_reason") or "unknown") for item in candidates)
    by_risk = Counter(str(item.get("candidate_risk_level") or "unknown") for item in candidates)
    by_processing_action = Counter(str(item.get("figure_processing_action") or "unknown") for item in candidates)
    total_stage2_selected_figures = len(candidates)
    valid_stage2_selected_figures = sum(
        1
        for item in candidates
        if str(item.get("path_status") or "valid") in {"valid", "relative_unchecked"}
    )
    missing_image_path_count = sum(
        1
        for item in candidates
        if str(item.get("path_status") or "") == "missing"
    )
    directory_path_error_count = sum(
        1
        for item in candidates
        if str(item.get("path_status") or "") == "directory"
    )
    processed_count = sum(1 for item in candidates if item.get("send_to_vlm"))
    skipped_count = sum(1 for item in candidates if not item.get("send_to_vlm"))
    figure_level_skip_success_count = sum(1 for item in candidates if item.get("figure_processing_action") == "skip_success")
    figure_level_replay_candidate_count = sum(1 for item in candidates if item.get("figure_processing_action") == "replay_candidate")
    figure_level_rerun_transient_count = sum(1 for item in candidates if item.get("figure_processing_action") == "rerun_transient")
    figure_level_new_live_count = sum(
        1 for item in candidates if item.get("figure_processing_action") == "new_live" and item.get("send_to_vlm")
    )
    figure_level_missing_image_count = sum(1 for item in candidates if item.get("figure_processing_action") == "missing_image")
    duplicate_vlm_prevented_count = figure_level_skip_success_count + figure_level_replay_candidate_count
    schema_replay_candidate_count = sum(
        1 for item in candidates if item.get("figure_processing_reason") == "schema_validation_failed"
    )
    raw_vlm_replay_candidate_count = sum(
        1 for item in candidates if item.get("figure_processing_reason") == "raw_vlm_output_available"
    )
    rescued_unknown_by_caption_count = sum(
        1 for item in candidates if item.get("routing_reason") == "stage2_unknown_caption_scientific" and item.get("send_to_vlm")
    )
    skipped_unknown_schema_specific_count = sum(
        1 for item in candidates if item.get("routing_mode") == "schema_specific" and item.get("skip_reason") == "figure_type_not_in_allowlist_or_unknown"
    )
    dry_run_count = sum(1 for item in extractions if item.get("extraction_mode") == "dry_run")
    live_count = sum(1 for item in extractions if item.get("extraction_mode") == "live")
    retry_attempt_count = sum(max(int(item.get("retry_attempts") or 0) - 1, 0) for item in failed_records)
    transient_failures = [item for item in failed_records if item.get("is_transient")]
    fallback_reused = [item for item in failed_records if item.get("fallback_used")]
    hard_failed = [item for item in failed_records if item.get("final_status") != "reused_previous_success"]
    validation_error_count = sum(len(item.get("validation_errors", [])) for item in extractions)
    non_extractable_count = sum(
        1
        for item in extractions
        if str(item.get("actual_figure_type") or item.get("figure_type") or "") == "non_extractable"
    )
    return {
        "total_stage2_selected_figures": total_stage2_selected_figures,
        "valid_stage2_selected_figures": valid_stage2_selected_figures,
        "missing_image_path_count": missing_image_path_count,
        "directory_path_error_count": directory_path_error_count,
        "already_successful_figure_count": figure_level_skip_success_count,
        "raw_vlm_replay_candidate_count": raw_vlm_replay_candidate_count,
        "schema_replay_candidate_count": schema_replay_candidate_count,
        "transient_rerun_candidate_count": figure_level_rerun_transient_count,
        "new_live_candidate_count": figure_level_new_live_count,
        "non_extractable_count": non_extractable_count,
        "live_success_count": live_count,
        "max_figures_per_paper_applied": int(candidates[0].get("max_figures_per_paper_applied") or 0) if candidates else 0,
        "total_candidates": len(candidates),
        "processed_count": processed_count,
        "skipped_count": skipped_count,
        "dry_run_count": dry_run_count,
        "live_count": live_count,
        "successful_extractions_count": len(extractions),
        "by_figure_type": dict(by_type),
        "by_stage2_figure_class": dict(by_stage2_class),
        "by_initial_figure_type": dict(by_initial_type),
        "routing_reason_distribution": dict(by_routing_reason),
        "candidate_risk_level_distribution": dict(by_risk),
        "figure_processing_action_distribution": dict(by_processing_action),
        "send_to_vision_model_count": processed_count,
        "figure_level_skip_success_count": figure_level_skip_success_count,
        "figure_level_replay_candidate_count": figure_level_replay_candidate_count,
        "figure_level_rerun_transient_count": figure_level_rerun_transient_count,
        "figure_level_new_live_count": figure_level_new_live_count,
        "figure_level_missing_image_count": figure_level_missing_image_count,
        "duplicate_vlm_prevented_count": duplicate_vlm_prevented_count,
        "rescued_unknown_by_caption_count": rescued_unknown_by_caption_count,
        "skipped_unknown_schema_specific_count": skipped_unknown_schema_specific_count,
        "validation_error_count": validation_error_count,
        "retry_attempt_count": retry_attempt_count,
        "transient_failure_count": len(transient_failures),
        "fallback_reused_count": len(fallback_reused),
        "hard_failed_record_count": len(hard_failed),
        "failed_record_count": len(hard_failed),
        "reused_figure_ids": [str(item.get("figure_id")) for item in fallback_reused if item.get("figure_id")],
        "hard_failed_figure_ids": [str(item.get("figure_id")) for item in hard_failed if item.get("figure_id")],
        "live_figure_ids": [str(item.get("figure_id")) for item in extractions if item.get("extraction_mode") == "live" and item.get("figure_id")],
        "failed_figure_ids": [str(item.get("figure_id")) for item in hard_failed if item.get("figure_id")],
        "output_warnings": list(config_warnings or []),
    }
