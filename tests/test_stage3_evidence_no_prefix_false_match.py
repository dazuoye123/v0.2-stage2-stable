from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _split_evidence_objects_payload


def test_figure_prefix_is_not_false_matched() -> None:
    payload = [
        {
            "evidence_id": "fig3-10",
            "caption": "fig3-10 rheology",
            "reference_sentences": ["see fig3-10 and fig3-11 for the rheology trend"],
        }
    ]
    figure_metadata_map = {
        "fig3-1": {"figure_id": "fig3-1", "caption": "fig3-1 overview"},
        "fig3-10": {"figure_id": "fig3-10", "caption": "fig3-10 rheology"},
        "fig3-11": {"figure_id": "fig3-11", "caption": "fig3-11 rheology"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[],
    )
    assert {row["figure_id"] for row in split_rows} == {"fig3-10", "fig3-11"}
    assert all(row["figure_id"] != "fig3-1" for row in split_rows)


def test_only_explicit_figure_ids_are_split() -> None:
    payload = [
        {
            "evidence_id": "fig3-9, fig3-10, fig3-11",
            "caption": "fig3-9, fig3-10, fig3-11",
            "reference_sentences": [],
        }
    ]
    figure_metadata_map = {
        "fig3-1": {"figure_id": "fig3-1"},
        "fig3-9": {"figure_id": "fig3-9"},
        "fig3-10": {"figure_id": "fig3-10"},
        "fig3-11": {"figure_id": "fig3-11"},
        "fig3-12": {"figure_id": "fig3-12"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[],
    )
    assert {row["figure_id"] for row in split_rows} == {"fig3-9", "fig3-10", "fig3-11"}
    assert len(split_rows) == 3


def test_other_prefix_variants_are_not_false_matched() -> None:
    payload = [
        {
            "evidence_id": "fig2-10",
            "caption": "fig2-10 morphology",
            "reference_sentences": ["fig2-10 and fig2-14 and fig2-15 support the claim"],
        }
    ]
    figure_metadata_map = {
        "fig2-1": {"figure_id": "fig2-1"},
        "fig2-10": {"figure_id": "fig2-10"},
        "fig2-14": {"figure_id": "fig2-14"},
        "fig2-15": {"figure_id": "fig2-15"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[],
    )
    assert {row["figure_id"] for row in split_rows} == {"fig2-10", "fig2-14", "fig2-15"}
    assert all(row["figure_id"] != "fig2-1" for row in split_rows)
