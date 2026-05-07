from pathlib import Path

from alumina_sol_extractor.dspy_modules.runner import _postprocess_paper_basic_info
from alumina_sol_extractor.stage3.merge import merge_stage_outputs_to_paper_record


def test_postprocess_paper_basic_info_normalizes_none_list_fields() -> None:
    result = _postprocess_paper_basic_info(
        payload={
            "title": "多晶型氧化铝连续纤维的研制及性能",
            "authors": None,
            "keywords": None,
        },
        paper_text="多晶型氧化铝连续纤维的研制及性能",
        source_file=Path("polycrystalline_alumina_fiber.md"),
    )

    assert result["authors"] == []
    assert result["keywords"] == []
    assert "authors:normalized_none_to_empty_list" in result["normalization_warnings"]
    assert "keywords:normalized_none_to_empty_list" in result["normalization_warnings"]


def test_merge_normalizes_none_iterables_to_empty_collections() -> None:
    record = merge_stage_outputs_to_paper_record(
        paper_basic_info={"title": "Example", "authors": None, "keywords": None},
        global_constants={"additional_parameter_records": None, "extended_data": None},
        experiment_series=[
            {
                "series_id": "1",
                "data_points": None,
                "independent_variables": None,
                "relevant_source_sections": None,
                "relevant_figure_ids": None,
                "relevant_table_ids": None,
                "extended_data": None,
            }
        ],
        data_points=None,
        evidence_objects=None,
    )

    assert record.paper_basic_info is not None
    assert record.paper_basic_info.authors == []
    assert record.paper_basic_info.keywords == []
    assert record.global_constants is not None
    assert record.global_constants.additional_parameter_records == []
    assert record.global_constants.extended_data == {}
    assert len(record.experiment_series) == 1
    assert record.experiment_series[0].data_points == []
    assert record.experiment_series[0].independent_variables == []
    assert record.experiment_series[0].relevant_source_sections == []
    assert record.experiment_series[0].relevant_figure_ids == []
    assert record.experiment_series[0].relevant_table_ids == []
    assert record.experiment_series[0].extended_data == {}
    assert record.evidence_objects == []
