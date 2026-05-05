from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _split_evidence_objects_payload
from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord
from alumina_sol_extractor.stage3.validators import validate_evidence_figure_id_alignment


def test_same_figure_gets_unique_evidence_ids() -> None:
    payload = [
        {
            "evidence_id": "fig3-8",
            "caption": "fig3-8 SEM",
            "reference_sentences": ["fig3-8 shows the first claim"],
        },
        {
            "evidence_id": "fig3-8",
            "caption": "fig3-8 SEM",
            "reference_sentences": ["fig3-8 also supports the second claim"],
        },
    ]
    figure_metadata_map = {
        "fig3-8": {"figure_id": "fig3-8", "caption": "fig3-8 SEM"},
    }
    split_rows = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=[],
    )
    assert [row["evidence_id"] for row in split_rows] == ["fig3-8__ev01", "fig3-8__ev02"]
    assert all(row["figure_id"] == "fig3-8" for row in split_rows)


def test_evidence_figure_id_alignment_warning() -> None:
    record = PaperExtractionRecord.model_validate(
        {
            "evidence_objects": [
                {"evidence_id": "fig3-8__ev01", "figure_id": "fig3-8"},
                {"evidence_id": "fig3-9", "figure_id": "fig3-8"},
            ]
        }
    )
    issues = validate_evidence_figure_id_alignment(record)
    assert len(issues) == 1
    assert issues[0]["evidence_id"] == "fig3-9"
    assert issues[0]["figure_id"] == "fig3-8"
