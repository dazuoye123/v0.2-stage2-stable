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


def test_existing_live_success_is_skipped_before_timeout_fallback(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir = output_dir / "stage4_vision_spectra"
    stage4_dir.mkdir(parents=True, exist_ok=True)

    image_path = output_dir / "fig23.jpg"
    image_path.write_bytes(b"img")
    (output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-2-3", "caption": "XRD figure", "image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-2-3", "figure_class": "xrd_pattern", "vision_image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")
    (stage4_dir / "spectra_extractions.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-2-3",
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
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 1, "dry_run_count": 0, "successful_extractions_count": 1, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        figure_ids=["fig-2-3"],
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
    assert summary["fallback_reused_count"] == 0
    assert summary["figure_level_skip_success_count"] == 1
    assert summary["duplicate_vlm_prevented_count"] == 1
    assert len(spectra_records) == 1
    assert failed_records == []


def test_timeout_without_previous_success_stays_failed(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)

    image_path = output_dir / "fig23.jpg"
    image_path.write_bytes(b"img")
    (output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-2-3", "caption": "XRD figure", "image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-2-3", "figure_class": "xrd_pattern", "vision_image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")

    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        figure_ids=["fig-2-3"],
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
    assert summary["figure_level_new_live_count"] == 1
    assert failed_records[0]["fallback_used"] is False
