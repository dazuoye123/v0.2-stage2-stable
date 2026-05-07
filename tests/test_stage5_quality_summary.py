from __future__ import annotations

from alumina_sol_extractor.dataset_fusion.validators import build_quality_summary


def test_quality_summary_counts_spectra_warnings_and_missing_evidence() -> None:
    summary = build_quality_summary(
        stage3_summary={"schema_valid": True, "canonical_key_errors_count": 1, "core_parameter_without_evidence_count": 2},
        stage4_summary={"total_candidates": 2, "failed_record_count": 0, "validation_error_count": 0},
        stage4_review={"summary": {"overall_status": "warning"}},
        parameters=[
            {"linked_evidence_ids": [], "quality_flags": []},
            {"linked_evidence_ids": ["ev-1"], "quality_flags": []},
        ],
        evidence=[{"evidence_id": "ev-1"}],
        spectra=[{"warning_codes": ["low_confidence_peak"], "conflict_warnings": [], "quality_review_assessment": "usable_with_warning"}],
        samples=[{"sample_id": "sample-1"}],
        fusion_warnings=["parameter_without_evidence", "spectra_with_warning"],
    )
    assert summary["parameters_without_evidence_count"] == 1
    assert summary["spectra_with_warning_count"] == 1
    assert summary["fusion_warning_count"] == 2
