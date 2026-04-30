from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.models.schema_v2 import DataPoint, DataProvenance, ExperimentSeries, GlobalConstants, PaperBasicInfo, PaperExtractionRecord, ParameterRecord
from alumina_sol_extractor.ontology import get_ontology_entry_map
from alumina_sol_extractor.stage3.validators import (
    build_quality_flags,
    validate_evidence_refs,
    validate_id_uniqueness,
    validate_no_core_keys_in_extended_data,
    validate_units_against_ontology,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _build_record() -> PaperExtractionRecord:
    return PaperExtractionRecord(
        paper_basic_info=PaperBasicInfo(paper_id="paper-1"),
        global_constants=GlobalConstants(
            extended_data={"viscosity_Pa_s": 1.2},
            additional_parameter_records=[
                ParameterRecord(canonical_key="aging_time_h", value=30, unit="min"),
            ],
        ),
        experiment_series=[
            ExperimentSeries(
                series_id="series-1",
                data_points=[
                    DataPoint(
                        sample_id="sample-1",
                        additional_parameter_records=[
                            ParameterRecord(canonical_key="aging_time_h", value=60, unit="min")
                        ],
                        evidence_refs=[],
                    ),
                    DataPoint(sample_id="sample-1"),
                ],
            )
        ],
        data_provenance=DataProvenance(),
    )


def test_duplicate_id_detection() -> None:
    record = _build_record()
    issues = validate_id_uniqueness(record)
    assert any(issue["id_type"] == "sample_id" for issue in issues)


def test_core_key_in_extended_data_detection() -> None:
    record = _build_record()
    ontology = get_ontology_entry_map(PROJECT_ROOT)
    issues = validate_no_core_keys_in_extended_data(record, ontology)
    assert any(issue["canonical_key"] == "viscosity_Pa_s" for issue in issues)


def test_unit_warning_detection_and_quality_flags() -> None:
    record = _build_record()
    ontology = get_ontology_entry_map(PROJECT_ROOT)
    unit_warnings = validate_units_against_ontology(record, ontology)
    quality_flags = build_quality_flags(record, [{"type": "unit_warning"}])
    assert unit_warnings
    assert "unit_normalization_review_needed" in quality_flags


def test_evidence_ref_warnings_are_empty_for_missing_refs() -> None:
    record = _build_record()
    issues = validate_evidence_refs(record)
    assert issues == []
