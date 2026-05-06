from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_stage4_dry_run_writes_outputs_without_api_key(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "鍥?.18",
                "caption": "旋蒸后铝溶胶的IR谱图",
                "image_path": "fig18.jpg",
                "context_before": "前文描述该铝溶胶在旋蒸后具有更高Al13占比。",
                "context_after": "后文说明该图对应IR谱图中的羟基相关变化。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "鍥?.18",
                "figure_class": "ftir_spectrum",
                "vision_image_path": "vision18.jpg",
                "alt_text": "IR spectrum after rotary evaporation",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "evidence_objects.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": "鍥?.18",
                "figure_id": "鍥?.18",
                "figure_type": "ftir_spectrum",
                "caption": "旋蒸后铝溶胶的IR谱图",
                "reference_sentences": ["如图2.18所示，旋蒸后铝溶胶的IR谱图显示羟基相关吸收带变化。"],
                "key_facts": ["旋蒸后铝溶胶的IR谱图"],
                "linked_facts": ["FTIR用于说明旋蒸后溶胶结构变化"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "paper_extraction.schema_v2.json").write_text(
        json.dumps(
            {
                "global_constants": {
                    "additional_parameter_records": [
                        {
                            "canonical_key": "Al13_fraction_percent",
                            "value": 50,
                            "unit": "%",
                            "evidence_refs": ["鍥?.18"],
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        max_figures=10,
        allowed_figure_types={"ftir_spectrum"},
        dry_run=True,
    ).run()

    assert summary["total_candidates"] == 1
    assert summary["dry_run_count"] == 1
    extraction_lines = (output_dir / "stage4_vision_spectra" / "spectra_extractions.jsonl").read_text(encoding="utf-8")
    assert "dry_run_no_vlm_called" in extraction_lines
    prompt_lines = (output_dir / "stage4_vision_spectra" / "stage4_prompts.jsonl").read_text(encoding="utf-8")
    assert "reference_sentences" in prompt_lines
    assert "related_stage3_parameters" in prompt_lines
