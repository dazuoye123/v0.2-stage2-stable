from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_build_figure_context_assembles_caption_evidence_and_related_parameters() -> None:
    extractor = Stage4VisionSpectraExtractor(paper_id="paper-1", output_dir=Path("."))
    context = extractor.build_figure_context(
        figure_id="鍥?.18",
        figure_meta={
            "caption": "旋蒸后铝溶胶的IR谱图",
            "context_before": "前文指出旋蒸后铝溶胶固含量提高。",
            "context_after": "后文说明IR峰形变化与羟基有关。",
        },
        vision_meta={"alt_text": "IR spectrum after rotary evaporation"},
        evidence_group=[
            {
                "evidence_id": "鍥?.18",
                "figure_id": "鍥?.18",
                "reference_sentences": ["如图2.18所示，旋蒸后铝溶胶的IR谱图显示羟基相关吸收带变化。"],
                "key_facts": ["旋蒸后铝溶胶的IR谱图"],
                "linked_facts": ["FTIR用于说明旋蒸后溶胶结构变化"],
            }
        ],
        stage3_parameter_records=[
            {
                "canonical_key": "Al13_fraction_percent",
                "value": 50,
                "unit": "%",
                "evidence_refs": ["鍥?.18"],
            },
            {
                "canonical_key": "pH",
                "value": 3.6,
                "unit": None,
                "evidence_refs": ["鍥?.12"],
            },
        ],
    )

    assert context["alt_text"] == "IR spectrum after rotary evaporation"
    assert context["reference_sentences"]
    assert context["evidence_object_context"]["fact_summary"] == ["旋蒸后铝溶胶的IR谱图"]
    assert context["related_stage3_parameters"][0]["canonical_key"] == "Al13_fraction_percent"
    assert all(item["canonical_key"] != "pH" for item in context["related_stage3_parameters"])


def test_build_figure_context_truncates_long_context_and_records_warning() -> None:
    extractor = Stage4VisionSpectraExtractor(paper_id="paper-1", output_dir=Path("."))
    context = extractor.build_figure_context(
        figure_id="鍥?.19",
        figure_meta={
            "caption": "XRD图谱",
            "context_before": "a" * 1200,
            "context_after": "b" * 1200,
        },
        vision_meta={},
        evidence_group=[],
        stage3_parameter_records=[],
    )

    assert len(context["context_before"]) <= 800
    assert len(context["context_after"]) <= 800
    assert "context_before_truncated" in context["warnings"]
    assert "context_after_truncated" in context["warnings"]
