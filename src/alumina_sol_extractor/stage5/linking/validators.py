"""Validation helpers for Stage 5.5 linking outputs."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import LinkCandidate, LinkRecord, LinkingSummary

VALID_LINK_TYPES = {"supports", "describes", "derived_from", "same_figure", "weak_supports", "conflicts"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_DECISIONS = {"accept", "reject", "unmatched"}


def merge_live_unmatched_candidates(
    base_unmatched_candidates: list[dict[str, Any]],
    llm_candidates: list[dict[str, Any]],
    llm_unmatched_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reviewed_ids = {str(item.get("candidate_id")) for item in llm_candidates if item.get("candidate_id") is not None}
    preserved = [
        item
        for item in base_unmatched_candidates
        if str(item.get("candidate_id")) not in reviewed_ids
    ]
    return preserved + list(llm_unmatched_candidates)


def validate_llm_link_decisions(
    candidates: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    starting_index: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    candidate_index = {item["candidate_id"]: LinkCandidate.model_validate(item) for item in candidates}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    stats = {"invalid_source_id_count": 0, "invalid_target_id_count": 0}
    counter = starting_index

    for payload in decisions:
        candidate_id = payload.get("candidate_id")
        candidate = candidate_index.get(candidate_id)
        if candidate is None:
            rejected.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "unknown_candidate_id",
                    "raw_decision": payload,
                }
            )
            continue
        decision = str(payload.get("decision") or "unmatched").strip().lower()
        if decision not in VALID_DECISIONS:
            decision = "unmatched"
        warnings: list[str] = []
        source_id = payload.get("source_id")
        target_id = payload.get("target_id")
        if source_id is not None and str(source_id) != candidate.source_id:
            stats["invalid_source_id_count"] += 1
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reason": "source_id_mismatch",
                    "expected_source_id": candidate.source_id,
                    "raw_decision": payload,
                }
            )
            continue
        if target_id is not None and str(target_id) != candidate.target_id:
            stats["invalid_target_id_count"] += 1
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reason": "target_id_mismatch",
                    "expected_target_id": candidate.target_id,
                    "raw_decision": payload,
                }
            )
            continue
        link_type = payload.get("link_type") or ("weak_supports" if candidate.needs_llm else "supports")
        if link_type not in VALID_LINK_TYPES:
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reason": "invalid_link_type",
                    "raw_decision": payload,
                }
            )
            continue
        confidence = payload.get("confidence") or "low"
        if confidence not in VALID_CONFIDENCE:
            confidence = "low"
            warnings.append("invalid_confidence_downgraded_to_low")
        reasoning = payload.get("reasoning")
        if not reasoning:
            warnings.append("empty_reasoning")
        if decision == "accept":
            accepted.append(
                LinkRecord(
                    link_id=f"link-{counter:05d}",
                    paper_id=candidate.paper_id,
                    source_type=candidate.source_type,
                    source_id=candidate.source_id,
                    target_type=candidate.target_type,
                    target_id=candidate.target_id,
                    link_type=link_type,
                    confidence=confidence,
                    confidence_score={"high": 0.95, "medium": 0.7, "low": 0.4}[confidence],
                    reasoning=reasoning,
                    evidence_text=candidate.source_text,
                    validation_status="accepted",
                    validation_warnings=warnings,
                    created_by="deterministic_plus_llm" if candidate.candidate_status == "deterministic" else "llm",
                ).model_dump()
            )
            counter += 1
        elif decision == "reject":
            rejected.append({"candidate_id": candidate.candidate_id, "reason": "llm_rejected", "raw_decision": payload})
        else:
            unmatched.append({"candidate_id": candidate.candidate_id, "reason": "llm_unmatched", "raw_decision": payload})
    return accepted, rejected, unmatched, stats


def sanitize_link_decision_payloads(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for payload in decisions:
        if not isinstance(payload, dict):
            continue
        sanitized.append(
            {
                "candidate_id": payload.get("candidate_id"),
                "decision": payload.get("decision"),
                "link_type": payload.get("link_type"),
                "confidence": payload.get("confidence"),
                "reasoning": payload.get("reasoning"),
                "source_id": payload.get("source_id"),
                "target_id": payload.get("target_id"),
            }
        )
    return sanitized


def build_linking_summary(
    *,
    candidates: list[dict[str, Any]],
    accepted_links: list[dict[str, Any]],
    rejected_links: list[dict[str, Any]],
    unmatched_candidates: list[dict[str, Any]],
    raw_llm_outputs: list[dict[str, Any]],
    invalid_source_id_count: int = 0,
    invalid_target_id_count: int = 0,
) -> dict[str, Any]:
    by_link_type = Counter(item.get("link_type") for item in accepted_links if item.get("link_type"))
    by_confidence = Counter(item.get("confidence") for item in accepted_links if item.get("confidence"))
    warning_count = 0
    for link in accepted_links:
        warning_count += len(link.get("validation_warnings", []))
    summary = LinkingSummary(
        total_candidates=len(candidates),
        deterministic_links=sum(1 for item in accepted_links if item.get("created_by") == "deterministic"),
        llm_reviewed_candidates=sum(
            len(item.get("candidate_ids", []))
            if isinstance(item, dict) and isinstance(item.get("candidate_ids"), list)
            else len(item.get("candidate_batch", []))
            if isinstance(item, dict) and isinstance(item.get("candidate_batch"), list)
            else 0
            for item in raw_llm_outputs
        ),
        accepted_links=len(accepted_links),
        rejected_links=len(rejected_links),
        unmatched_candidates=len(unmatched_candidates),
        invalid_source_id_count=invalid_source_id_count,
        invalid_target_id_count=invalid_target_id_count,
        by_link_type=dict(by_link_type),
        by_confidence=dict(by_confidence),
        warning_count=warning_count,
    )
    return summary.model_dump()
