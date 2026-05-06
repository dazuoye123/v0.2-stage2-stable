from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_prompt_record_includes_caption_reference_and_attached_context() -> None:
    extractor = Stage4VisionSpectraExtractor(paper_id="paper-1", output_dir=Path("."), dry_run=True)
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "鍥?.18",
        "figure_type": "ftir_spectrum",
        "source_image_path": "fig18.jpg",
        "caption": "旋蒸后铝溶胶的IR谱图",
        "alt_text": "IR spectrum after rotary evaporation",
        "reference_sentences": ["如图2.18所示，旋蒸后铝溶胶的IR谱图显示羟基相关吸收带变化。"],
        "context_before": "前文指出旋蒸后铝溶胶固含量提高。",
        "context_after": None,
        "evidence_object_context": {"fact_summary": ["旋蒸后铝溶胶的IR谱图"], "detailed_observation": [], "linked_facts": [], "evidence_refs": [], "evidence_ids": ["鍥?.18"]},
        "related_stage3_parameters": [{"canonical_key": "Al13_fraction_percent", "value": 50, "unit": "%"}],
        "context_source": {"caption": "caption", "reference_sentences": "reference_sentences", "evidence_object_context": "stage3_evidence"},
        "context_warnings": [],
        "estimated_context_chars": 120,
        "schema_name": "VibrationalSpectrumExtraction",
        "prompt_template_name": "ftir_spectrum_prompt",
        "stage3_figure_type": "ftir_spectrum",
        "stage2_figure_class": "ftir_spectrum",
        "technique": "FTIR",
    }

    prompt_record = extractor._build_prompt_record(candidate)

    assert prompt_record["image_path"] == "fig18.jpg"
    assert "旋蒸后铝溶胶的IR谱图" in prompt_record["prompt"]
    assert "reference_sentences" in prompt_record["prompt"]
    assert prompt_record["attached_context"]["related_stage3_parameters"][0]["canonical_key"] == "Al13_fraction_percent"
    assert prompt_record["dry_run_no_vlm_called"] is True
