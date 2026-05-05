from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _backfill_core_parameter_evidence
from alumina_sol_extractor.models.schema_v2 import (
    DataPoint,
    EvidenceObject,
    ExperimentSeries,
    GlobalConstants,
    PaperExtractionRecord,
    ParameterRecord,
)


def test_backfill_inherits_explicit_datapoint_evidence_for_matching_global_core_parameter() -> None:
    record = PaperExtractionRecord(
        global_constants=GlobalConstants(
            additional_parameter_records=[
                ParameterRecord(
                    canonical_key="viscosity_Pa_s",
                    raw_name="viscosity",
                    value=400,
                    unit="Pa*s",
                    normalization_note="moved_from_global_constants_top_level",
                )
            ]
        ),
        experiment_series=[
            ExperimentSeries(
                series_id="ES-01",
                data_points=[
                    DataPoint(
                        sample_id="ES-01-400",
                        evidence_refs=["图2-10", "表007", "# section"],
                        independent_variable_values=[
                            ParameterRecord(
                                canonical_key="viscosity_Pa_s",
                                raw_name="viscosity",
                                value=400,
                                unit="Pa*s",
                            )
                        ],
                    )
                ],
            )
        ],
        evidence_objects=[
            EvidenceObject(evidence_id="图2-10", figure_id="图2-10"),
            EvidenceObject(evidence_id="table_007", table_id="table_007"),
        ],
    )
    ontology = {"viscosity_Pa_s": {"is_core_statistical_field": True}}

    updated = _backfill_core_parameter_evidence(record=record, ontology=ontology)

    data_point_record = updated.experiment_series[0].data_points[0].independent_variable_values[0]
    assert len(data_point_record.evidence_refs) == 1
    assert data_point_record.evidence_refs[0].figure_id == "图2-10"

    global_record = updated.global_constants.additional_parameter_records[0]
    assert len(global_record.evidence_refs) == 1
    assert global_record.evidence_refs[0].figure_id == "图2-10"
    assert "matched_data_point_parameter:ES-01-400" in str(global_record.normalization_note)
    assert "missing_evidence_reason:" not in str(global_record.normalization_note)


def test_backfill_leaves_core_parameter_empty_when_only_nonmatching_or_nonexplicit_refs_exist() -> None:
    record = PaperExtractionRecord(
        global_constants=GlobalConstants(
            additional_parameter_records=[
                ParameterRecord(
                    canonical_key="spinning_channel_temperature_C",
                    raw_name="spinning channel temperature",
                    value=25,
                    unit="C",
                )
            ]
        ),
        experiment_series=[
            ExperimentSeries(
                series_id="ES-01",
                data_points=[
                    DataPoint(
                        sample_id="ES-01-400",
                        evidence_refs=["# 1. process summary"],
                        independent_variable_values=[
                            ParameterRecord(
                                canonical_key="viscosity_Pa_s",
                                raw_name="viscosity",
                                value=400,
                                unit="Pa*s",
                            )
                        ],
                    )
                ],
            )
        ],
        evidence_objects=[EvidenceObject(evidence_id="图2-18", figure_id="图2-18")],
    )
    ontology = {
        "spinning_channel_temperature_C": {"is_core_statistical_field": True},
        "viscosity_Pa_s": {"is_core_statistical_field": True},
    }

    updated = _backfill_core_parameter_evidence(record=record, ontology=ontology)

    global_record = updated.global_constants.additional_parameter_records[0]
    assert global_record.evidence_refs == []
    assert "missing_evidence_reason:no_explicit_evidence_inherited_or_matched" in str(global_record.normalization_note)

    data_point_record = updated.experiment_series[0].data_points[0].independent_variable_values[0]
    assert data_point_record.evidence_refs == []
    assert "missing_evidence_reason:no_explicit_evidence_inherited_or_matched" in str(data_point_record.normalization_note)


def test_backfill_uses_structured_datapoint_process_and_result_values() -> None:
    record = PaperExtractionRecord(
        global_constants=GlobalConstants(
            additional_parameter_records=[
                ParameterRecord(canonical_key="spinning_channel_temperature_C", raw_name="temperature", value=25, unit="C"),
                ParameterRecord(canonical_key="feed_pressure_MPa", raw_name="pressure", value=8.8, unit="MPa"),
                ParameterRecord(canonical_key="relative_humidity_percent", raw_name="humidity", value=30.8, unit="%"),
                ParameterRecord(canonical_key="average_fiber_diameter_um", raw_name="diameter", value=12, unit="um"),
                ParameterRecord(canonical_key="tensile_strength_MPa", raw_name="strength", value=2100, unit="MPa"),
            ]
        ),
        experiment_series=[
            ExperimentSeries(
                series_id="ES-01",
                data_points=[
                    DataPoint(
                        sample_id="ES-01-400",
                        evidence_refs=["fig2-18"],
                        process_parameters={
                            "forming": {
                                "spinning_channel_temperature_C": 25,
                                "feed_pressure_MPa": 8.8,
                                "relative_humidity_percent": 30.8,
                            }
                        },
                        results={
                            "microstructure_and_pores": {"ceramic_fiber_diameter_um": 12},
                            "mechanical_properties": {"ceramic_fiber_tensile_strength_GPa": 2.1},
                        },
                    )
                ],
            )
        ],
        evidence_objects=[EvidenceObject(evidence_id="fig2-18", figure_id="fig2-18")],
    )
    ontology = {
        "spinning_channel_temperature_C": {"is_core_statistical_field": True},
        "feed_pressure_MPa": {"is_core_statistical_field": True},
        "relative_humidity_percent": {"is_core_statistical_field": True},
        "average_fiber_diameter_um": {"is_core_statistical_field": True},
        "tensile_strength_MPa": {"is_core_statistical_field": True},
    }

    updated = _backfill_core_parameter_evidence(record=record, ontology=ontology)

    for parameter_record in updated.global_constants.additional_parameter_records:
        assert parameter_record.evidence_refs
        assert parameter_record.evidence_refs[0].figure_id == "fig2-18"
        assert "matched_data_point_parameter:ES-01-400" in str(parameter_record.normalization_note)


def test_backfill_uses_linked_facts_and_table_rows_without_fuzzy_numeric_fill() -> None:
    record = PaperExtractionRecord(
        global_constants=GlobalConstants(
            additional_parameter_records=[
                ParameterRecord(canonical_key="holding_time_h", raw_name="holding time", value=50, unit="h"),
                ParameterRecord(canonical_key="strength_retention_percent", raw_name="strength retention", value=80, unit="%"),
            ]
        ),
        evidence_objects=[
            EvidenceObject(
                evidence_id="fig3-21",
                figure_id="fig3-21",
                caption="Fiber SEM after holding at 1200°C for 50h",
            ),
            EvidenceObject(
                evidence_id="table_016",
                object_type="table",
                extended_data={},
                table_id="table_016",
                caption="High-temperature strength retention",
                linked_facts=["1200℃/50h, 81.6% retained strength."],
            ),
        ],
    )
    tables_summary = [
        {
            "table_id": "table_016",
            "rows": [
                {"0": "sample", "1": "strength retention (%)"},
                {"0": "1200℃/50h", "1": "81.6%"},
            ],
        }
    ]
    ontology = {
        "holding_time_h": {"is_core_statistical_field": True},
        "strength_retention_percent": {"is_core_statistical_field": True},
    }

    updated = _backfill_core_parameter_evidence(
        record=record,
        ontology=ontology,
        tables_summary=tables_summary,
    )

    holding_time_record = updated.global_constants.additional_parameter_records[0]
    assert holding_time_record.evidence_refs
    assert holding_time_record.evidence_refs[0].source_id == "fig3-21"
    assert "matched_evidence_object:fig3-21" in str(holding_time_record.normalization_note)

    retention_record = updated.global_constants.additional_parameter_records[1]
    assert retention_record.evidence_refs == []
    assert "missing_evidence_reason:no_explicit_evidence_inherited_or_matched" in str(retention_record.normalization_note)


def test_backfill_uses_table_output_when_value_and_field_match_exactly() -> None:
    record = PaperExtractionRecord(
        global_constants=GlobalConstants(
            additional_parameter_records=[
                ParameterRecord(canonical_key="holding_time_h", raw_name="holding time", value=50, unit="h")
            ]
        ),
        evidence_objects=[
            EvidenceObject(
                evidence_id="table_001",
                object_type="table",
                table_id="table_001",
                caption="Holding time schedule",
            )
        ],
    )
    tables_summary = [
        {
            "table_id": "table_001",
            "rows": [
                {"0": "holding time (h)", "1": "note"},
                {"0": "50h", "1": "stable"},
            ],
        }
    ]
    ontology = {"holding_time_h": {"is_core_statistical_field": True}}

    updated = _backfill_core_parameter_evidence(
        record=record,
        ontology=ontology,
        tables_summary=tables_summary,
    )

    parameter_record = updated.global_constants.additional_parameter_records[0]
    assert parameter_record.evidence_refs
    assert parameter_record.evidence_refs[0].source_id == "table_001"
    assert parameter_record.evidence_refs[0].table_id is None
    assert "matched_table_output:table_001" in str(parameter_record.normalization_note)
