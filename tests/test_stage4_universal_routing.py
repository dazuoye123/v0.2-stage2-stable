from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor
from alumina_sol_extractor.vision_spectra.vlm_client import VLMRequest, VLMRequestError


class _AlwaysTimeoutClient:
    def __init__(self) -> None:
        self.config_warnings: list[str] = []

    def extract(self, request: VLMRequest) -> dict[str, object]:
        raise VLMRequestError(
            "Read timed out",
            error_type="read_timeout",
            is_transient=True,
            retry_attempts=3,
            max_retries=3,
            timeout_seconds=300,
            attempt_errors=[{"attempt_index": 1, "error_type": "read_timeout", "error_message": "Read timed out"}],
        )


def test_universal_candidate_selection_rescues_unknown_stage2_by_scientific_caption() -> None:
    extractor = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=Path("."),
        routing_mode="universal_compact",
    )
    candidates = extractor._select_candidates(
        figures=[{"figure_id": "fig-1", "caption": "FTIR spectrum of precursor", "image_path": "fig1.jpg"}],
        vision_inputs=[{"figure_id": "fig-1", "figure_class": "other", "vision_image_path": "fig1.jpg"}],
        evidence_objects=[],
    )
    assert candidates[0]["send_to_vlm"] is True
    assert candidates[0]["routing_reason"] == "stage2_unknown_caption_scientific"
    assert candidates[0]["prompt_template_name"] == "universal_compact_prompt"


def test_universal_prompt_record_includes_stage_hints_and_caption() -> None:
    extractor = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=Path("."),
        routing_mode="universal_compact",
        dry_run=True,
    )
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-1",
        "figure_type": "unknown",
        "initial_figure_type": "unknown",
        "source_image_path": "fig1.jpg",
        "caption": "FTIR spectrum",
        "alt_text": None,
        "reference_sentences": [],
        "context_before": None,
        "context_after": None,
        "evidence_object_context": {},
        "related_stage3_parameters": [],
        "context_source": {},
        "context_warnings": [],
        "estimated_context_chars": 10,
        "schema_name": "UniversalFigureExtraction",
        "stage2_figure_class": "unknown",
        "stage3_figure_type": "ftir_spectrum",
        "routing_mode": "universal_compact",
        "routing_reason": "stage2_unknown_caption_scientific",
    }
    prompt = extractor._build_prompt_record(candidate)
    assert prompt["prompt_template_name"] == "universal_compact_prompt"
    assert '"stage2_figure_class": "unknown"' in prompt["prompt"]
    assert '"stage3_figure_type": "ftir_spectrum"' in prompt["prompt"]
    assert '"caption": "FTIR spectrum"' in prompt["prompt"]


def test_universal_run_reads_stage3_twopass_without_schema_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "caption": "FTIR spectrum", "image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "figure_class": "unknown", "vision_image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    stage3_dir = output_dir / "stage3_twopass"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        routing_mode="universal_compact",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        dry_run=True,
    ).run()

    assert summary["dry_run_count"] == 1
    assert "missing_stage3_schema:stage3_twopass" in summary["output_warnings"]
    extraction_lines = (output_dir / "stage4_vision_spectra_universal" / "spectra_extractions.jsonl").read_text(encoding="utf-8")
    assert '"routing_mode": "universal_compact"' in extraction_lines


def test_universal_previous_success_fallback_still_works(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir = output_dir / "stage3_twopass"
    stage4_dir = output_dir / "stage4_vision_spectra_universal"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "caption": "FTIR spectrum", "image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "figure_class": "other", "vision_image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage4_dir / "spectra_extractions.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-1",
                "figure_type": "unknown",
                "routing_mode": "universal_compact",
                "schema_name": "UnknownFigureExtraction",
                "safe_observations": [],
                "warnings": [],
                "conflict_warnings": [],
                "confidence": 0.8,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        figure_ids=["fig-1"],
        routing_mode="universal_compact",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        dry_run=False,
        client=_AlwaysTimeoutClient(),
    ).run()

    assert summary["fallback_reused_count"] == 1
    assert summary["hard_failed_record_count"] == 0
