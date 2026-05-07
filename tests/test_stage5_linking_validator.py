from __future__ import annotations

from alumina_sol_extractor.linking.validators import validate_llm_link_decisions


def test_unknown_candidate_id_is_rejected():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        candidates=[
            {
                "candidate_id": "cand-1",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "peak-1",
                "target_type": "parameter",
                "target_id": "param-1",
                "candidate_reason": "test",
                "deterministic_score": 0.5,
                "needs_llm": True,
                "candidate_status": "needs_llm",
            }
        ],
        decisions=[{"candidate_id": "missing", "decision": "accept", "link_type": "supports", "confidence": "high"}],
    )
    assert not accepted
    assert rejected[0]["reason"] == "unknown_candidate_id"
    assert not unmatched
    assert stats["invalid_source_id_count"] == 0


def test_target_id_mismatch_is_rejected():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        candidates=[
            {
                "candidate_id": "cand-1",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "peak-1",
                "target_type": "parameter",
                "target_id": "param-1",
                "candidate_reason": "test",
                "deterministic_score": 0.5,
                "needs_llm": True,
                "candidate_status": "needs_llm",
            }
        ],
        decisions=[
            {
                "candidate_id": "cand-1",
                "decision": "accept",
                "link_type": "supports",
                "confidence": "high",
                "target_id": "param-999",
            }
        ],
    )
    assert not accepted
    assert rejected[0]["reason"] == "target_id_mismatch"
    assert stats["invalid_target_id_count"] == 1
    assert not unmatched


def test_source_id_mismatch_is_rejected():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        candidates=[
            {
                "candidate_id": "cand-1",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "peak-1",
                "target_type": "parameter",
                "target_id": "param-1",
                "candidate_reason": "test",
                "deterministic_score": 0.5,
                "needs_llm": True,
                "candidate_status": "needs_llm",
            }
        ],
        decisions=[
            {
                "candidate_id": "cand-1",
                "decision": "accept",
                "link_type": "supports",
                "confidence": "high",
                "source_id": "peak-999",
            }
        ],
    )
    assert not accepted
    assert rejected[0]["reason"] == "source_id_mismatch"
    assert stats["invalid_source_id_count"] == 1
    assert not unmatched


def test_invalid_confidence_is_downgraded_to_low():
    accepted, rejected, unmatched, stats = validate_llm_link_decisions(
        candidates=[
            {
                "candidate_id": "cand-1",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "peak-1",
                "target_type": "parameter",
                "target_id": "param-1",
                "candidate_reason": "test",
                "deterministic_score": 0.5,
                "needs_llm": True,
                "candidate_status": "needs_llm",
            }
        ],
        decisions=[
            {
                "candidate_id": "cand-1",
                "decision": "accept",
                "link_type": "supports",
                "confidence": "very_confident",
                "reasoning": "",
            }
        ],
    )
    assert not rejected
    assert not unmatched
    assert accepted[0]["confidence"] == "low"
    assert "invalid_confidence_downgraded_to_low" in accepted[0]["validation_warnings"]
    assert "empty_reasoning" in accepted[0]["validation_warnings"]
