from __future__ import annotations

from alumina_sol_extractor.dataset_fusion.validators import build_quality_summary


def test_quality_summary_counts_strong_weak_and_invalid_parameters() -> None:
    summary = build_quality_summary(
        stage3_summary={"schema_valid": True, "canonical_key_errors_count": 1, "core_parameter_without_evidence_count": 2},
        stage4_summary={"total_candidates": 2, "failed_record_count": 0, "validation_error_count": 0},
        stage4_review={"summary": {"overall_status": "warning"}},
        parameters=[
            {"linked_evidence_ids": [], "quality_flags": [], "sample_id": None},
            {"linked_evidence_ids": ["ev-1"], "quality_flags": [], "sample_id": "sample-1"},
            {"linked_evidence_ids": [], "quality_flags": ["weak_link_from_spectra"], "sample_id": None},
        ],
        evidence=[{"evidence_id": "ev-1"}],
        spectra=[{"warning_codes": ["low_confidence_peak"], "conflict_warnings": [], "quality_review_assessment": "usable_with_warning"}],
        samples=[{"sample_id": "sample-1"}],
        process_steps=[
            {"reagent_amount": 0.005, "evidence_text": "0.005 mol AlCl3·6H2O", "needs_manual_review": False},
            {"reagent_amount": "一定量", "evidence_text": "加入一定量 PVP", "needs_manual_review": True},
        ],
        fusion_warnings=["parameter_without_evidence", "spectra_with_warning", "weak_link_from_spectra"],
        rejected_parameters=[{"reason": "invalid_canonical_key"}],
    )
    assert summary["parameters_with_strong_evidence_count"] == 1
    assert summary["parameters_with_weak_spectra_link_count"] == 1
    assert summary["parameters_without_evidence_count"] == 1
    assert summary["paper_level_parameters_without_direct_evidence_count"] == 2
    assert summary["invalid_canonical_key_count"] == 1
    assert summary["spectra_with_warning_count"] == 1
    assert summary["total_process_steps"] == 2
    assert summary["process_steps_with_reagent_amount_count"] == 2
    assert summary["process_steps_with_evidence_count"] == 2
    assert summary["process_steps_needs_manual_review_count"] == 1
    assert summary["fusion_warning_count"] == 3
