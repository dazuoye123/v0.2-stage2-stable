from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor
from alumina_sol_extractor.vision_spectra.vlm_client import VLMRequest, VLMRequestError


class AlwaysTimeoutClient:
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
            attempt_errors=[
                {"attempt_index": 1, "error_type": "read_timeout", "error_message": "Read timed out"},
                {"attempt_index": 2, "error_type": "read_timeout", "error_message": "Read timed out"},
                {"attempt_index": 3, "error_type": "read_timeout", "error_message": "Read timed out"},
            ],
        )


def test_timeout_reuses_previous_success(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir = output_dir / "stage4_vision_spectra"
    stage4_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "figures.jsonl").write_text(json.dumps({"figure_id": "图2-3", "caption": "XRD图", "image_path": "fig23.jpg"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "vision_inputs.jsonl").write_text(json.dumps({"figure_id": "图2-3", "figure_class": "xrd_pattern", "vision_image_path": "fig23.jpg"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")
    (stage4_dir / "spectra_extractions.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "图2-3",
                "figure_type": "xrd_pattern",
                "schema_name": "XRDExtraction",
                "extraction_mode": "live",
                "peaks": [],
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
        figure_ids=["图2-3"],
        max_figures=1,
        allowed_figure_types={"xrd_pattern"},
        dry_run=False,
        client=AlwaysTimeoutClient(),
    ).run()

    spectra_records = [
        json.loads(line)
        for line in (stage4_dir / "spectra_extractions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failed_records = [
        json.loads(line)
        for line in (stage4_dir / "failed_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["failed_record_count"] == 0
    assert summary["hard_failed_record_count"] == 0
    assert summary["fallback_reused_count"] == 1
    assert summary["reused_figure_ids"] == ["图2-3"]
    assert spectra_records[0]["reused_previous_success"] is True
    assert spectra_records[0]["extraction_mode"] == "reused_previous_success"
    assert failed_records[0]["fallback_used"] is True
    assert failed_records[0]["final_status"] == "reused_previous_success"


def test_timeout_without_previous_success_stays_failed(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "figures.jsonl").write_text(json.dumps({"figure_id": "图2-3", "caption": "XRD图", "image_path": "fig23.jpg"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "vision_inputs.jsonl").write_text(json.dumps({"figure_id": "图2-3", "figure_class": "xrd_pattern", "vision_image_path": "fig23.jpg"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        figure_ids=["图2-3"],
        max_figures=1,
        allowed_figure_types={"xrd_pattern"},
        dry_run=False,
        client=AlwaysTimeoutClient(),
    ).run()

    failed_records = [
        json.loads(line)
        for line in (output_dir / "stage4_vision_spectra" / "failed_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["failed_record_count"] == 1
    assert summary["hard_failed_record_count"] == 1
    assert summary["fallback_reused_count"] == 0
    assert failed_records[0]["fallback_used"] is False
