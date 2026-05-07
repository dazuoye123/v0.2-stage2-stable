from __future__ import annotations

from alumina_sol_extractor.linking.validators import (
    merge_live_unmatched_candidates,
    sanitize_link_decision_payloads,
    validate_llm_link_decisions,
)


def _candidate():
    return [
        {
            "candidate_id": "cand-1",
            "paper_id": "paper-1",
            "source_type": "evidence_object",
            "source_id": "图2.2",
            "target_type": "parameter",
            "target_id": "param-1",
            "candidate_reason": "test",
            "deterministic_score": 0.55,
            "needs_llm": True,
            "candidate_status": "needs_llm",
        }
    ]


def test_valid_llm_candidate_id_generates_link_record():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        _candidate(),
        [{"candidate_id": "cand-1", "decision": "accept", "link_type": "supports", "confidence": "medium", "reasoning": "same value"}],
    )
    assert len(accepted) == 1
    assert accepted[0]["target_id"] == "param-1"
    assert not rejected
    assert not unmatched
    assert stats["invalid_source_id_count"] == 0
    assert stats["invalid_target_id_count"] == 0


def test_invalid_link_type_is_rejected():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        _candidate(),
        [{"candidate_id": "cand-1", "decision": "accept", "link_type": "random_type", "confidence": "high", "reasoning": "oops"}],
    )
    assert not accepted
    assert rejected[0]["reason"] == "invalid_link_type"
    assert not unmatched
    assert stats["invalid_source_id_count"] == 0


def test_sanitize_keeps_only_allowed_fields():
    sanitized = sanitize_link_decision_payloads(
        [
            {
                "candidate_id": "cand-1",
                "decision": "accept",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "ok",
                "hallucinated": "ignore me",
            }
        ]
    )
    assert sanitized == [
        {
            "candidate_id": "cand-1",
            "decision": "accept",
            "link_type": "supports",
            "confidence": "high",
            "reasoning": "ok",
            "source_id": None,
            "target_id": None,
        }
    ]


def test_merge_live_unmatched_candidates_removes_resolved_needs_llm_items():
    base_unmatched = [
        {"candidate_id": "cand-1", "unmatched_reason": "needs_llm_review"},
        {"candidate_id": "cand-2", "unmatched_reason": "needs_llm_review"},
        {"candidate_id": "cand-3", "unmatched_reason": "other_reason"},
    ]
    llm_candidates = [{"candidate_id": "cand-1"}, {"candidate_id": "cand-2"}]
    llm_unmatched = [{"candidate_id": "cand-2", "reason": "llm_unmatched"}]
    merged = merge_live_unmatched_candidates(base_unmatched, llm_candidates, llm_unmatched)
    assert merged == [
        {"candidate_id": "cand-3", "unmatched_reason": "other_reason"},
        {"candidate_id": "cand-2", "reason": "llm_unmatched"},
    ]
