from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.io import write_json, write_jsonl
from alumina_sol_extractor.vision_spectra.reparse import reparse_stage4_vlm_outputs


def test_reparse_stage4_outputs_recovers_half_compliant_xrd_tem_and_thermal(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    stage4_dir.mkdir(parents=True)

    candidates = [
        {
            "figure_id": "Fig.3",
            "figure_type": "xrd_pattern",
            "send_to_vlm": True,
            "paper_id": "paper",
            "source_image_path": "xrd.png",
            "caption": "xrd",
            "context_source": {},
        },
        {
            "figure_id": "Fig.1",
            "figure_type": "tem_image",
            "send_to_vlm": True,
            "paper_id": "paper",
            "source_image_path": "tem.png",
            "caption": "tem",
            "context_source": {},
        },
        {
            "figure_id": "Fig.4",
            "figure_type": "tg_curve",
            "send_to_vlm": True,
            "paper_id": "paper",
            "source_image_path": "tg.png",
            "caption": "tg",
            "context_source": {},
        },
    ]
    raw_outputs = [
        {
            "figure_id": "Fig.3",
            "figure_type": "xrd_pattern",
            "raw_response": json.dumps(
                {
                    "figure_id": "Fig.3",
                    "figure_type": "xrd_pattern",
                    "confidence": "high",
                    "detected_phases": [{"phase": "mullite", "source": "image_and_text", "confidence": "high"}],
                    "crystallinity_trend": {"description": "broad halo indicates low crystallinity", "source": "text"},
                    "peaks": [{"2theta": 17.5, "confidence": "high", "source": "image"}],
                },
                ensure_ascii=False,
            ),
            "response_payload": {"model": "test-model"},
            "dry_run": False,
        },
        {
            "figure_id": "Fig.1",
            "figure_type": "tem_image",
            "raw_response": json.dumps(
                {
                    "figure_id": "Fig.1",
                    "figure_type": "tem_image",
                    "confidence": "low",
                    "peaks": None,
                    "scale_bar": {"length": 200, "unit": "nm", "source": "image"},
                },
                ensure_ascii=False,
            ),
            "response_payload": {"model": "test-model"},
            "dry_run": False,
        },
        {
            "figure_id": "Fig.4",
            "figure_type": "tg_curve",
            "raw_response": json.dumps(
                {
                    "figure_id": "Fig.4",
                    "figure_type": "tg_curve",
                    "confidence": "medium",
                    "transition_temperatures": [
                        {"temperature": 150, "description": "water loss", "source": "text"},
                        {"temperature": 450, "description": "organic burnout", "source": "text"},
                    ],
                },
                ensure_ascii=False,
            ),
            "response_payload": {"model": "test-model"},
            "dry_run": False,
        },
    ]

    write_jsonl(candidates, stage4_dir / "stage4_candidates.jsonl")
    write_jsonl(raw_outputs, stage4_dir / "raw_vlm_outputs.jsonl")
    write_jsonl([], stage4_dir / "spectra_extractions.jsonl")
    write_jsonl(
        [
            {"figure_id": "Fig.3", "error": "old"},
            {"figure_id": "Fig.1", "error": "old"},
            {"figure_id": "Fig.4", "error": "old"},
        ],
        stage4_dir / "failed_records.jsonl",
    )
    write_json(stage4_dir / "stage4_summary.json", {})
    write_jsonl([], stage4_dir / "stage4_prompts.jsonl")

    summary = reparse_stage4_vlm_outputs(stage4_dir)

    assert summary["failed_record_count"] == 0
    spectra = [
        json.loads(line)
        for line in (stage4_dir / "spectra_extractions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(spectra) == 3
    xrd = next(item for item in spectra if item["figure_id"] == "Fig.3")
    tem = next(item for item in spectra if item["figure_id"] == "Fig.1")
    tg = next(item for item in spectra if item["figure_id"] == "Fig.4")
    assert xrd["schema_name"] == "XRDExtraction"
    assert xrd["detected_phases"] == ["mullite"]
    assert xrd["crystallinity_trend"] == "broad halo indicates low crystallinity"
    assert tem["schema_name"] == "MicroscopyExtraction"
    assert tem["scale_bar"] == "200 nm"
    assert tg["schema_name"] == "ThermalAnalysisExtraction"
    assert tg["transition_temperatures"] == [150.0, 450.0]


def test_reparse_keeps_invalid_payload_in_failed_records(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    stage4_dir.mkdir(parents=True)

    write_jsonl(
        [
            {
                "figure_id": "Fig.bad",
                "figure_type": "xrd_pattern",
                "send_to_vlm": True,
                "paper_id": "paper",
                "source_image_path": "xrd.png",
                "caption": "bad",
                "context_source": {},
            }
        ],
        stage4_dir / "stage4_candidates.jsonl",
    )
    write_jsonl(
        [
            {
                "figure_id": "Fig.bad",
                "figure_type": "xrd_pattern",
                "raw_response": "not-json",
                "response_payload": {"model": "test-model"},
                "dry_run": False,
            }
        ],
        stage4_dir / "raw_vlm_outputs.jsonl",
    )
    write_jsonl([], stage4_dir / "spectra_extractions.jsonl")
    write_jsonl([], stage4_dir / "failed_records.jsonl")
    write_json(stage4_dir / "stage4_summary.json", {})
    write_jsonl([], stage4_dir / "stage4_prompts.jsonl")

    summary = reparse_stage4_vlm_outputs(stage4_dir)

    assert summary["failed_record_count"] == 1
    failed = [
        json.loads(line)
        for line in (stage4_dir / "failed_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert failed[0]["figure_id"] == "Fig.bad"
