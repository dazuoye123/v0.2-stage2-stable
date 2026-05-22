"""Failure handling helpers for Stage 4 vision spectra extraction."""

from __future__ import annotations

import json
from typing import Any

from .validators import validate_stage4_extraction
from .vlm_client import VLMRequestError


def index_previous_successes(previous_extractions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in previous_extractions:
        figure_id = str(record.get("figure_id") or "")
        if not figure_id:
            continue
        indexed.setdefault(figure_id, record)
    return indexed


def reuse_previous_success(
    *,
    candidate: dict[str, Any],
    previous_success: dict[str, Any] | None,
    error_type: str,
) -> dict[str, Any] | None:
    if not previous_success:
        return None
    reused = json.loads(json.dumps(previous_success, ensure_ascii=False))
    reused["reused_previous_success"] = True
    reused["fallback_reason"] = error_type
    reused["previous_extraction_source"] = "stage4_vision_spectra/spectra_extractions.jsonl"
    reused["extraction_mode"] = "reused_previous_success"
    reused.setdefault("warnings", [])
    reused["warnings"] = [
        *reused.get("warnings", []),
        f"reused_previous_success_due_to_{error_type}",
    ]
    reused.setdefault("validation_errors", validate_stage4_extraction(reused))
    reused.setdefault("figure_id", candidate.get("figure_id"))
    reused.setdefault("figure_type", candidate.get("figure_type"))
    return reused


def build_failed_record(
    candidate: dict[str, Any],
    exc: Exception,
    *,
    fallback_used: bool,
) -> dict[str, Any]:
    if isinstance(exc, VLMRequestError):
        error_type = exc.error_type
        is_transient = exc.is_transient
        retry_attempts = exc.retry_attempts
        max_retries = exc.max_retries
        timeout_seconds = exc.timeout_seconds
        attempt_errors = exc.attempt_errors
    else:
        error_type = exc.__class__.__name__
        is_transient = False
        retry_attempts = 1
        max_retries = 1
        timeout_seconds = None
        attempt_errors = []
    final_status = "reused_previous_success" if fallback_used else "failed"
    return {
        "figure_id": candidate.get("figure_id"),
        "figure_type": candidate.get("figure_type"),
        "error": str(exc),
        "error_type": error_type,
        "error_message": str(exc),
        "is_transient": is_transient,
        "retry_attempts": retry_attempts,
        "max_retries": max_retries,
        "timeout_seconds": timeout_seconds,
        "attempt_errors": attempt_errors,
        "fallback_used": fallback_used,
        "fallback_source": "previous_spectra_extractions" if fallback_used else None,
        "final_status": final_status,
    }


def build_error_raw_output(
    candidate: dict[str, Any],
    *,
    error_message: str,
    error_type: str,
    retry_attempts: int | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    payload = {
        "figure_id": candidate.get("figure_id"),
        "figure_type": candidate.get("figure_type"),
        "raw_response": None,
        "dry_run": False,
        "error": error_message,
        "error_type": error_type,
    }
    if retry_attempts is not None:
        payload["retry_attempts"] = retry_attempts
    if timeout_seconds is not None:
        payload["timeout_seconds"] = timeout_seconds
    return payload
