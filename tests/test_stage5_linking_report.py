from __future__ import annotations

from alumina_sol_extractor.linking.report import render_linking_report


def test_linking_report_renders_and_recommends_live():
    report = render_linking_report(
        file_presence={"paper": True, "parameters": True, "evidence": True, "spectra": True},
        candidates=[{"candidate_id": "cand-1"}],
        accepted_links=[
            {
                "link_id": "link-1",
                "source_id": "spectra-图2.2",
                "target_id": "图2.2",
                "source_type": "spectra_record",
                "target_type": "evidence_object",
                "link_type": "same_figure",
                "confidence": "high",
                "created_by": "deterministic",
                "reasoning": "same figure",
            }
        ],
        unmatched_candidates=[{"candidate_id": "cand-2", "source_type": "spectra_peak", "source_id": "peak-1", "target_type": "parameter", "target_id": "param-1", "unmatched_reason": "needs_llm_review"}],
        rejected_links=[],
        summary={
            "total_candidates": 2,
            "deterministic_links": 1,
            "llm_reviewed_candidates": 0,
            "accepted_links": 1,
            "unmatched_candidates": 1,
            "rejected_links": 0,
            "invalid_source_id_count": 0,
            "invalid_target_id_count": 0,
        },
    )
    assert "# Stage 5.5 Linking Report" in report
    assert "suggest_live_linking" in report
