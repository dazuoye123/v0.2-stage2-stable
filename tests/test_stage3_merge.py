from __future__ import annotations

from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord
from alumina_sol_extractor.stage3.merge import (
    ensure_required_top_level_sections,
    ensure_schema_version,
    merge_stage_outputs_to_paper_record,
)


def test_merge_stage_outputs_builds_valid_record() -> None:
    record = merge_stage_outputs_to_paper_record(
        paper_basic_info={"paper_id": "paper-1", "title": "demo"},
        global_constants={"scope_note": "shared"},
        experiment_series=[{"series_id": "series-1", "series_name": "A"}],
        data_points=[{"sample_id": "sample-1", "extended_data": {"series_id": "series-1"}}],
        evidence_objects=[{"evidence_id": "ev-1", "figure_id": "图1"}],
    )
    assert isinstance(record, PaperExtractionRecord)
    assert record.schema_version == "2.0"
    assert len(record.experiment_series) == 1
    assert len(record.experiment_series[0].data_points) == 1


def test_ensure_required_sections_fills_defaults() -> None:
    payload = ensure_required_top_level_sections(ensure_schema_version({}))
    assert payload["schema_version"] == "2.0"
    assert payload["experiment_series"] == []
    assert payload["evidence_objects"] == []


def test_merge_sanitizes_null_list_fields_from_model_output() -> None:
    record = merge_stage_outputs_to_paper_record(
        paper_basic_info={
            "paper_id": "paper-2",
            "title": "demo",
            "authors": None,
            "keywords": None,
        },
    )
    assert record.paper_basic_info is not None
    assert record.paper_basic_info.authors == []
    assert record.paper_basic_info.keywords == []


def test_merge_coerces_numeric_identifier_fields_to_strings() -> None:
    record = merge_stage_outputs_to_paper_record(
        experiment_series=[{"series_id": 1, "series_name": "A"}],
        data_points=[{"sample_id": 7, "extended_data": {"series_id": "1"}}],
    )
    assert record.experiment_series[0].series_id == "1"
    assert record.experiment_series[0].data_points[0].sample_id == "7"


def test_merge_synthesizes_series_when_data_points_exist_without_series() -> None:
    record = merge_stage_outputs_to_paper_record(
        data_points=[
            {"sample_id": "dp-1", "extended_data": {"parent_series_id": "1", "series_name": "Series A"}},
            {"sample_id": "dp-2", "extended_data": {"parent_series_id": "2"}},
        ],
    )
    assert len(record.experiment_series) == 2
    assert record.experiment_series[0].series_id == "1"
    assert record.experiment_series[0].series_name == "Series A"
    assert len(record.experiment_series[0].data_points) == 1
    assert record.experiment_series[1].series_id == "2"
    assert len(record.experiment_series[1].data_points) == 1


def test_merge_ignores_scalar_items_in_series_and_process_lists() -> None:
    record = merge_stage_outputs_to_paper_record(
        experiment_series=[
            {"series_id": "series-1", "series_name": "Valid Series"},
            "bad-scalar-series-entry",
        ],
        data_points=[
            {"sample_id": "dp-1", "extended_data": {"series_id": "series-1"}},
            "bad-scalar-datapoint-entry",
        ],
        process_steps=[
            {"step_id": "step-1", "action": "calcine"},
            "bad-scalar-step-entry",
        ],
    )

    assert len(record.experiment_series) == 1
    assert record.experiment_series[0].series_id == "series-1"
    assert len(record.experiment_series[0].data_points) == 1
    assert len(record.process_steps) == 1
    assert record.process_steps[0].action == "calcine"
