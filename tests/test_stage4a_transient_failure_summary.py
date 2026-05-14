from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.quality_review import load_stage4_outputs, review_stage4_extractions


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""), encoding="utf-8")


def test_quality_review_treats_reused_previous_success_as_warning_not_fail(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2-3",
                "figure_type": "xrd_pattern",
                "schema_name": "XRDExtraction",
                "extraction_mode": "reused_previous_success",
                "technique": "XRD",
                "confidence": 0.8,
                "warnings": ["reused_previous_success_due_to_read_timeout"],
                "conflict_warnings": [],
                "peaks": [],
            }
        ],
    )
    _write_jsonl(
        stage4_dir / "failed_records.jsonl",
        [
            {
                "figure_id": "图2-3",
                "error": "Read timed out",
                "error_type": "read_timeout",
                "is_transient": True,
                "retry_attempts": 3,
                "max_retries": 3,
                "timeout_seconds": 300,
                "fallback_used": True,
                "final_status": "reused_previous_success",
            }
        ],
    )
    (stage4_dir / "stage4_summary.json").write_text(
        json.dumps(
            {
                "validation_error_count": 0,
                "failed_record_count": 0,
                "hard_failed_record_count": 0,
                "fallback_reused_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))

    assert review_payload["summary"]["failed_record_count"] == 0
    assert review_payload["summary"]["fallback_reused_count"] == 1
    assert review_payload["summary"]["overall_status"] == "warning"
    assert any(item["warning"] == "reused_previous_success" for item in review_payload["global_warnings"])
