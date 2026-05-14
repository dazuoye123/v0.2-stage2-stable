"""Reparse persisted Stage 4 raw VLM outputs without new model calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .extractor import Stage4VisionSpectraExtractor
from .io import parse_json_payload, read_jsonl, write_json, write_jsonl
from .quality_review import load_stage4_outputs, review_stage4_extractions, write_stage4_quality_review
from .routing import get_schema_for_figure_type
from .stage4_context import build_input_context_summary
from .validators import build_stage4_summary, validate_stage4_extraction


def reparse_stage4_vlm_outputs(stage4_dir: Path) -> dict[str, Any]:
    candidates = read_jsonl(stage4_dir / "stage4_candidates.jsonl")
    raw_outputs = read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl")

    latest_raw_by_figure_id: dict[str, dict[str, Any]] = {}
    for record in raw_outputs:
        figure_id = str(record.get("figure_id") or "")
        if not figure_id:
            continue
        if record.get("raw_response"):
            latest_raw_by_figure_id[figure_id] = record
        elif figure_id not in latest_raw_by_figure_id:
            latest_raw_by_figure_id[figure_id] = record

    extractions: list[dict[str, Any]] = []
    failed_records: list[dict[str, Any]] = []

    for candidate in candidates:
        if not candidate.get("send_to_vlm"):
            continue
        figure_id = str(candidate.get("figure_id") or "")
        raw_record = latest_raw_by_figure_id.get(figure_id)
        if not raw_record or not raw_record.get("raw_response"):
            failed_records.append(
                {
                    "figure_id": figure_id,
                    "figure_type": candidate.get("figure_type"),
                    "error": "missing_raw_response_for_reparse",
                }
            )
            continue
        try:
            parsed = parse_json_payload(str(raw_record.get("raw_response") or ""))
            parsed["paper_id"] = candidate.get("paper_id")
            parsed["figure_id"] = candidate.get("figure_id")
            parsed["figure_type"] = candidate.get("figure_type")
            parsed["source_image_path"] = candidate.get("source_image_path")
            parsed["caption"] = candidate.get("caption")
            parsed["extraction_mode"] = "live"
            response_payload = raw_record.get("response_payload") or {}
            parsed["extraction_model"] = response_payload.get("model")
            parsed.setdefault("input_context_summary", build_input_context_summary(candidate))
            parsed.setdefault("used_context_sources", list(candidate.get("context_source", {}).values()))

            schema_cls = get_schema_for_figure_type(candidate.get("figure_type"))
            parsed, normalization_warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
                parsed,
                figure_type=str(candidate.get("figure_type") or ""),
                schema_name=schema_cls.__name__,
            )
            validated = schema_cls(**parsed).model_dump()
            validated["schema_name"] = schema_cls.__name__
            if normalization_warnings:
                validated["warnings"] = [*validated.get("warnings", []), *normalization_warnings]
            validated["validation_errors"] = validate_stage4_extraction(validated)
            extractions.append(validated)
        except Exception as exc:  # noqa: BLE001
            failed_records.append(
                {
                    "figure_id": figure_id,
                    "figure_type": candidate.get("figure_type"),
                    "error": str(exc),
                }
            )

    summary = build_stage4_summary(candidates=candidates, extractions=extractions, failed_records=failed_records)
    write_jsonl(extractions, stage4_dir / "spectra_extractions.jsonl")
    write_jsonl(failed_records, stage4_dir / "failed_records.jsonl")
    write_json(stage4_dir / "stage4_summary.json", summary)

    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))
    write_stage4_quality_review(
        review_payload,
        output_md=stage4_dir / "stage4_quality_review.md",
        output_json=stage4_dir / "stage4_quality_review.json",
    )
    return summary
