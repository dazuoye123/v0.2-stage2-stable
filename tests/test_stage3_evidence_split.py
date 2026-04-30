from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _split_evidence_objects_payload


def test_multi_figure_evidence_is_split_into_one_row_per_figure() -> None:
    payload = [
        {
            "evidence_id": "图2-9, 图2-10",
            "caption": "图2-9 XRD; 图2-10 FTIR",
            "reference_sentences": ["图2-9和图2-10显示了结构变化。"],
        }
    ]
    figure_metadata_map = {
        "图2-9": {"figure_id": "图2-9", "figure_class": "xrd_pattern", "caption": "图2-9 XRD"},
        "图2-10": {"figure_id": "图2-10", "figure_class": "ftir_spectrum", "caption": "图2-10 FTIR"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[],
    )
    assert len(split_rows) == 2
    assert {row["figure_id"] for row in split_rows} == {"图2-9", "图2-10"}
    assert {row["figure_type"] for row in split_rows} == {"XRD", "FTIR"}


def test_mixed_figure_and_table_evidence_is_split() -> None:
    payload = [
        {
            "evidence_id": "图3-16, table_012",
            "caption": "图3-16 SEM; 表12 数据",
        }
    ]
    figure_metadata_map = {
        "图3-16": {"figure_id": "图3-16", "figure_class": "microscopy_image", "caption": "图3-16 TEM"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[{"table_id": "table_012", "rows": []}],
    )
    assert len(split_rows) == 2
    assert any(row.get("figure_id") == "图3-16" for row in split_rows)
    assert any(row.get("table_id") == "table_012" for row in split_rows)
