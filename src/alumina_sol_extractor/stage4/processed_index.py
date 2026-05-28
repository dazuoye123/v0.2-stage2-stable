"""Figure-level processed index helpers for Stage 4 resume/dedup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl


TRANSIENT_ERROR_HINTS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection aborted",
    "rate limit",
    "server error",
    "api_error",
    "transient",
    "service unavailable",
)
MISSING_IMAGE_ERROR_HINTS = (
    "missing_image_path",
    "missing image path",
    "filenotfounderror",
    "permissionerror",
    "permission denied",
    "image path",
)


def is_live_successful_stage4_summary(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    live_count = int(summary.get("live_count") or 0)
    failed_record_count = int(summary.get("failed_record_count") or 0)
    if "successful_extractions_count" in summary:
        successful_extractions_count = int(summary.get("successful_extractions_count") or 0)
    else:
        successful_extractions_count = live_count
    return live_count > 0 and failed_record_count == 0 and successful_extractions_count > 0


def is_dry_run_only_stage4_summary(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    dry_run_count = int(summary.get("dry_run_count") or 0)
    live_count = int(summary.get("live_count") or 0)
    return dry_run_count > 0 and live_count == 0


def load_stage4a_processed_figure_index(stage4_dir: Path) -> dict[str, Any]:
    stage4_dir = Path(stage4_dir)
    summary = read_json(stage4_dir / "stage4a_summary.json", default={}) or {}
    extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
    raw_vlm_outputs = read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl")
    failed_records = read_jsonl(stage4_dir / "spectra_failed_records.jsonl")

    successful_figure_ids: set[str] = set()
    successful_image_paths: set[str] = set()
    raw_vlm_figure_ids: set[str] = set()
    failed_figure_ids: set[str] = set()
    schema_failed_figure_ids: set[str] = set()
    transient_failed_figure_ids: set[str] = set()
    missing_image_path_figure_ids: set[str] = set()
    blocked_failed_figure_ids: set[str] = set()
    dry_run_only_figure_ids: set[str] = set()

    dry_run_only = is_dry_run_only_stage4_summary(summary)
    for record in extractions:
        figure_id = str(record.get("figure_id") or "").strip()
        image_path = str(record.get("source_image_path") or "").strip()
        extraction_mode = str(record.get("extraction_mode") or "").strip().lower()
        if not figure_id:
            continue
        if dry_run_only or extraction_mode == "dry_run":
            dry_run_only_figure_ids.add(figure_id)
            continue
        successful_figure_ids.add(figure_id)
        if image_path:
            successful_image_paths.add(image_path)

    for record in raw_vlm_outputs:
        figure_id = str(record.get("figure_id") or "").strip()
        if not figure_id or figure_id in successful_figure_ids:
            continue
        if bool(record.get("dry_run")):
            continue
        if record.get("raw_response") or record.get("response_payload") or record.get("raw_universal_payload"):
            raw_vlm_figure_ids.add(figure_id)

    for record in failed_records:
        figure_id = str(record.get("figure_id") or "").strip()
        if not figure_id or figure_id in successful_figure_ids:
            continue
        failed_figure_ids.add(figure_id)
        if _is_schema_validation_failure(record):
            schema_failed_figure_ids.add(figure_id)
            continue
        if _is_missing_image_failure(record):
            missing_image_path_figure_ids.add(figure_id)
            continue
        if _is_transient_failure(record):
            transient_failed_figure_ids.add(figure_id)
            continue
        blocked_failed_figure_ids.add(figure_id)

    return {
        "successful_figure_ids": successful_figure_ids,
        "successful_image_paths": successful_image_paths,
        "raw_vlm_figure_ids": raw_vlm_figure_ids,
        "failed_figure_ids": failed_figure_ids,
        "schema_failed_figure_ids": schema_failed_figure_ids,
        "transient_failed_figure_ids": transient_failed_figure_ids,
        "missing_image_path_figure_ids": missing_image_path_figure_ids,
        "blocked_failed_figure_ids": blocked_failed_figure_ids,
        "dry_run_only_figure_ids": dry_run_only_figure_ids,
        "live_success_summary": is_live_successful_stage4_summary(summary),
        "dry_run_only_summary": dry_run_only,
        "successful_extractions_count": len(successful_figure_ids),
        "raw_vlm_replayable_count": len(raw_vlm_figure_ids),
        "failed_records_count": len(failed_figure_ids),
    }


def classify_stage4a_figure_processing_action(
    candidate: dict[str, Any],
    processed_index: dict[str, Any],
) -> tuple[str, str | None]:
    figure_id = str(candidate.get("figure_id") or "").strip()
    image_path = str(candidate.get("source_image_path") or "").strip()
    if figure_id in processed_index["successful_figure_ids"] or (image_path and image_path in processed_index["successful_image_paths"]):
        return "skip_success", "already_successful_extraction"
    if candidate.get("skip_reason") in {"missing_image_path", "directory_path_error"} or figure_id in processed_index["missing_image_path_figure_ids"]:
        return "missing_image", "missing_image_path"
    if figure_id in processed_index["schema_failed_figure_ids"]:
        return "replay_candidate", "schema_validation_failed"
    if figure_id in processed_index["raw_vlm_figure_ids"]:
        return "replay_candidate", "raw_vlm_output_available"
    if figure_id in processed_index["transient_failed_figure_ids"]:
        return "rerun_transient", "transient_failure"
    if figure_id in processed_index["blocked_failed_figure_ids"]:
        return "blocked_failed", "non_replayable_failed_record"
    return "new_live", None


def merge_stage4_records_by_figure_id(
    existing_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    *,
    replaced_figure_ids: set[str],
) -> list[dict[str, Any]]:
    if not replaced_figure_ids:
        return [*existing_records, *new_records]
    merged = [
        record
        for record in existing_records
        if str(record.get("figure_id") or "").strip() not in replaced_figure_ids
    ]
    merged.extend(new_records)
    return merged


def _is_schema_validation_failure(record: dict[str, Any]) -> bool:
    error_type = str(record.get("error_type") or "").strip().lower()
    if error_type == "schema_validation_failed":
        return True
    error_message = str(record.get("error_message") or record.get("error") or "").lower()
    return "schema_validation_failed" in error_message


def _is_transient_failure(record: dict[str, Any]) -> bool:
    if bool(record.get("is_transient")):
        return True
    haystacks = [
        str(record.get("error_type") or "").lower(),
        str(record.get("error_message") or "").lower(),
        str(record.get("error") or "").lower(),
    ]
    return any(hint in haystack for haystack in haystacks for hint in TRANSIENT_ERROR_HINTS)


def _is_missing_image_failure(record: dict[str, Any]) -> bool:
    haystacks = [
        str(record.get("error_type") or "").lower(),
        str(record.get("error_message") or "").lower(),
        str(record.get("error") or "").lower(),
    ]
    return any(hint in haystack for haystack in haystacks for hint in MISSING_IMAGE_ERROR_HINTS)


__all__ = [
    "classify_stage4a_figure_processing_action",
    "is_dry_run_only_stage4_summary",
    "is_live_successful_stage4_summary",
    "load_stage4a_processed_figure_index",
    "merge_stage4_records_by_figure_id",
]
