"""Stage 4 vision spectra dry-run extractor."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import parse_json_payload, read_json, read_jsonl, write_json, write_jsonl
from .normalization import (
    normalize_universal_extraction_payload_for_schema,
    normalize_universal_shell_payload,
    normalize_vlm_payload_for_schema,
)
from .prompt_templates import get_prompt_for_figure_type, get_universal_compact_prompt
from .processed_index import (
    classify_stage4a_figure_processing_action,
    load_stage4a_processed_figure_index,
    merge_stage4_records_by_figure_id,
)
from .routing import (
    caption_or_context_is_scientific,
    describe_universal_candidate,
    get_schema_for_figure_type,
    normalize_figure_type,
    should_process_figure,
)
from .schemas import UnknownFigureExtraction, UniversalFigureExtraction
from .stage2_selected_loader import load_stage2_selected_figures
from .stage4_context import (
    build_evidence_object_context,
    build_input_context_summary,
    collect_reference_sentences,
    collect_stage3_parameter_records,
    estimate_context_chars,
    figure_metadata_for_prompt,
    find_related_stage3_parameters,
    group_evidence_by_figure_id,
    index_by_figure_id,
    prioritize_sendable_candidates,
    truncate_text,
)
from .stage4_failures import (
    build_error_raw_output,
    build_failed_record,
    index_previous_successes,
    reuse_previous_success,
)
from .validators import build_stage4_summary, validate_stage4_extraction
from .vlm_client import VLMRequest, VLMRequestError, VisionLanguageModelClient


DEFAULT_ALLOWED_FIGURE_TYPES = {
    "nmr_spectrum",
    "ftir_spectrum",
    "ir_spectrum",
    "raman_spectrum",
    "xrd_pattern",
    "ferron_curve",
    "tg_curve",
    "dsc_curve",
    "tg_dsc_curve",
    "sem_image",
    "tem_image",
    "microscopy",
}

MAX_REFERENCE_SENTENCES = 5
MAX_CONTEXT_CHARS = 800
MAX_EVIDENCE_CONTEXT_CHARS = 1000
MAX_RELATED_PARAMETERS = 20
LOW_TYPE_CONFIDENCE_THRESHOLD = 0.5


def _has_valid_image_file(value: Any) -> bool:
    if not value:
        return False
    try:
        path = Path(str(value))
    except Exception:  # noqa: BLE001
        return False
    return path.exists() and path.is_file()


def _image_path_state(value: Any) -> str:
    if not value:
        return "missing"
    try:
        path = Path(str(value))
    except Exception:  # noqa: BLE001
        return "missing"
    if not path.exists():
        if not path.is_absolute():
            return "relative_unchecked"
        return "missing"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "valid"
    return "missing"


def validate_universal_extraction_payload(
    universal_payload: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    normalized_shell_payload, shell_warnings = normalize_universal_shell_payload(universal_payload)
    shell = UniversalFigureExtraction(**normalized_shell_payload).model_dump()
    initial_type = normalize_figure_type(
        candidate.get("initial_figure_type")
        or candidate.get("stage2_predicted_figure_type")
        or candidate.get("stage2_figure_class")
    )
    actual_type = normalize_figure_type(shell.get("actual_figure_type"))
    type_confidence = shell.get("type_confidence")
    low_confidence = isinstance(type_confidence, (int, float)) and float(type_confidence) < LOW_TYPE_CONFIDENCE_THRESHOLD
    warnings = [*list(shell.get("warnings", []) or []), *shell_warnings]
    conflict_warnings = list(shell.get("conflict_warnings", []) or [])
    extraction_payload = dict(shell.get("extraction") or {})

    stage2_hint_type = normalize_figure_type(
        candidate.get("stage2_predicted_figure_type") or candidate.get("stage2_figure_class")
    )

    if actual_type in {"unknown", "non_extractable"} or low_confidence:
        if low_confidence and "low_type_confidence" not in warnings:
            warnings.append("low_type_confidence")
        if actual_type not in {"unknown", "non_extractable"}:
            actual_type = "unknown"
        shell["needs_manual_review"] = True
        schema_cls = UnknownFigureExtraction
        extraction_payload.setdefault("likely_figure_type", shell.get("actual_figure_type") or initial_type or None)
        extraction_payload.setdefault("why_uncertain", shell.get("type_reason"))
    else:
        schema_cls = get_schema_for_figure_type(actual_type)

    merged_payload = {
        **extraction_payload,
        "paper_id": candidate.get("paper_id"),
        "figure_id": candidate.get("figure_id"),
        "figure_type": actual_type,
        "technique": extraction_payload.get("technique") or candidate.get("technique"),
        "source_image_path": candidate.get("source_image_path"),
        "caption": candidate.get("caption"),
        "extraction_mode": "live",
        "input_context_summary": build_input_context_summary(candidate),
        "used_context_sources": list(candidate.get("context_source", {}).values()),
        "image_readability": shell.get("image_readability"),
        "text_context_quality": shell.get("text_context_quality"),
        "warnings": warnings,
        "conflict_warnings": conflict_warnings,
        "stage2_figure_class": candidate.get("stage2_figure_class"),
        "stage2_predicted_figure_type": candidate.get("stage2_predicted_figure_type"),
        "stage3_figure_type": candidate.get("stage3_figure_type"),
        "initial_figure_type": candidate.get("initial_figure_type"),
        "actual_figure_type": actual_type,
        "type_confidence": shell.get("type_confidence"),
        "type_reason": shell.get("type_reason"),
        "stage2_type_used_as_hint": shell.get("stage2_type_used_as_hint", True),
        "type_mismatch": bool(shell.get("type_mismatch")) or (initial_type not in {"", "unknown"} and actual_type != "unknown" and actual_type != initial_type),
        "corrected_from_stage2_type": shell.get("corrected_from_stage2_type") or (
            stage2_hint_type if stage2_hint_type not in {"", "unknown", "non_extractable"} and stage2_hint_type != actual_type else None
        ),
        "needs_manual_review": bool(shell.get("needs_manual_review")) or actual_type in {"unknown", "non_extractable"},
        "routing_mode": "universal_compact",
        "image_basename": Path(str(candidate.get("source_image_path") or "")).name or None,
    }
    normalized_payload, normalization_warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        merged_payload,
        figure_type=actual_type,
        schema_name=schema_cls.__name__,
        use_universal_adapter=True,
    )
    normalized_payload["warnings"] = [*(normalized_payload.get("warnings", []) or []), *normalization_warnings]
    try:
        validated = schema_cls(**normalized_payload).model_dump()
    except Exception as exc:  # noqa: BLE001
        failure_warnings = [*warnings, *normalization_warnings, "schema_validation_failed"]
        return {
            "ok": False,
            "schema_name": schema_cls.__name__,
            "actual_figure_type": actual_type,
            "error_message": str(exc),
            "raw_universal_payload": shell,
            "warnings": failure_warnings,
        }
    validated["schema_name"] = schema_cls.__name__
    validated["warnings"] = [*(validated.get("warnings", []) or []), *normalization_warnings]
    validated["validation_errors"] = validate_stage4_extraction(validated)
    return {
        "ok": True,
        "record": validated,
        "schema_name": schema_cls.__name__,
        "actual_figure_type": actual_type,
        "raw_universal_payload": shell,
    }


@dataclass
class Stage4VisionSpectraExtractor:
    paper_id: str
    output_dir: Path
    max_figures: int = 0
    allowed_figure_types: set[str] | None = None
    figure_ids: list[str] | None = None
    dry_run: bool = True
    client: VisionLanguageModelClient | None = None
    routing_mode: str = "schema_specific"
    stage3_subdir: str = "stage3_dspy_smoke"
    stage4_subdir: str = "stage4_vision_spectra"
    candidate_source: str = "stage2-selected"

    def _should_require_real_image_file(self) -> bool:
        if self.dry_run:
            return False
        return self.client is None or isinstance(self.client, VisionLanguageModelClient)

    def run(self) -> dict[str, Any]:
        plan = self.build_candidate_plan()
        stage4_dir = plan["stage4_dir"]
        previous_extractions = plan["previous_extractions"]
        previous_raw_outputs = plan["previous_raw_outputs"]
        previous_failed_records = plan["previous_failed_records"]
        config_warnings = list(plan["config_warnings"])
        candidates = plan["candidates"]
        prompts = [
            self._build_prompt_record(candidate)
            for candidate in candidates
            if candidate.get("send_to_vlm") and candidate.get("will_call_vlm")
        ]
        extractions, raw_outputs, failed_records, client_warnings = self._run_extractions(
            candidates,
            previous_extractions=previous_extractions,
            previous_raw_outputs=previous_raw_outputs,
        )
        config_warnings.extend(client_warnings)
        replaced_figure_ids = {
            str(candidate.get("figure_id") or "").strip()
            for candidate in candidates
            if candidate.get("figure_processing_action") in {"new_live", "rerun_transient", "missing_image", "replay_candidate"}
            and candidate.get("figure_id")
        }
        final_extractions = merge_stage4_records_by_figure_id(
            previous_extractions,
            extractions,
            replaced_figure_ids=replaced_figure_ids,
        )
        final_raw_outputs = merge_stage4_records_by_figure_id(
            previous_raw_outputs,
            raw_outputs,
            replaced_figure_ids=replaced_figure_ids,
        )
        final_failed_records = merge_stage4_records_by_figure_id(
            previous_failed_records,
            failed_records,
            replaced_figure_ids=replaced_figure_ids,
        )
        summary = build_stage4_summary(
            candidates=candidates,
            extractions=final_extractions,
            failed_records=final_failed_records,
            config_warnings=config_warnings,
        )

        write_jsonl(candidates, stage4_dir / "stage4_candidates.jsonl")
        write_jsonl(prompts, stage4_dir / "stage4_prompts.jsonl")
        write_jsonl(final_extractions, stage4_dir / "spectra_extractions.jsonl")
        write_jsonl(final_raw_outputs, stage4_dir / "raw_vlm_outputs.jsonl")
        write_jsonl(final_failed_records, stage4_dir / "failed_records.jsonl")
        write_jsonl(final_failed_records, stage4_dir / "spectra_failed_records.jsonl")
        write_json(stage4_dir / "stage4_summary.json", summary)
        write_json(stage4_dir / "stage4a_summary.json", summary)
        return summary

    def build_candidate_plan(self, *, create_stage4_dir: bool = True) -> dict[str, Any]:
        stage4_dir = Path(self.output_dir) / self.stage4_subdir
        if create_stage4_dir:
            stage4_dir.mkdir(parents=True, exist_ok=True)
        previous_extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
        previous_raw_outputs = read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl")
        previous_failed_records = read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
        config_warnings: list[str] = []

        stage3_dir = Path(self.output_dir) / self.stage3_subdir
        evidence_objects = read_jsonl(stage3_dir / "evidence_objects.jsonl")
        stage3_schema_path = stage3_dir / "paper_extraction.schema_v2.json"
        stage3_schema = read_json(stage3_schema_path, default={}) or {}
        if not evidence_objects:
            config_warnings.append(f"missing_or_empty_evidence_objects:{self.stage3_subdir}")
        if not stage3_schema_path.exists():
            config_warnings.append(f"missing_stage3_schema:{self.stage3_subdir}")

        if self.candidate_source != "stage2-selected":
            raise ValueError(f"Unsupported Stage4A candidate_source: {self.candidate_source}")
        stage2_selected_figures = load_stage2_selected_figures(Path(self.output_dir))
        if not stage2_selected_figures:
            figures = read_jsonl(Path(self.output_dir) / "figures.jsonl")
            vision_inputs = read_jsonl(Path(self.output_dir) / "vision_inputs.jsonl")
            if figures or vision_inputs:
                config_warnings.append("legacy_candidate_loader_compatibility_fallback")
                stage2_selected_figures = self._legacy_stage2_selected_from_records(figures, vision_inputs)
        if not stage2_selected_figures:
            config_warnings.append("no_stage2_selected_figures")

        candidates = self._select_candidates(
            stage2_selected_figures=stage2_selected_figures,
            evidence_objects=evidence_objects,
            stage3_schema=stage3_schema,
        )
        processed_index = load_stage4a_processed_figure_index(stage4_dir)
        candidates = self._apply_figure_level_dedup(candidates, processed_index)
        return {
            "stage4_dir": stage4_dir,
            "previous_extractions": previous_extractions,
            "previous_raw_outputs": previous_raw_outputs,
            "previous_failed_records": previous_failed_records,
            "config_warnings": config_warnings,
            "candidates": candidates,
            "processed_index": processed_index,
            "stage2_selected_figures": stage2_selected_figures,
        }

    @staticmethod
    def _legacy_stage2_selected_from_records(
        figures: list[dict[str, Any]],
        vision_inputs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        figures_by_id = index_by_figure_id(figures)
        vision_by_id = index_by_figure_id(vision_inputs)
        ordered_ids: list[str] = []
        for record in figures:
            figure_id = str(record.get("figure_id") or "").strip()
            if figure_id and figure_id not in ordered_ids:
                ordered_ids.append(figure_id)
        for record in vision_inputs:
            figure_id = str(record.get("figure_id") or "").strip()
            if figure_id and figure_id not in ordered_ids:
                ordered_ids.append(figure_id)

        selected: list[dict[str, Any]] = []
        for figure_id in ordered_ids:
            figure_meta = figures_by_id.get(figure_id, {})
            vision_meta = vision_by_id.get(figure_id, {})
            source_image_path = (
                vision_meta.get("vision_image_path")
                or figure_meta.get("vision_image_path")
                or vision_meta.get("image_path")
                or figure_meta.get("image_path")
            )
            selected.append(
                {
                    "figure_id": figure_id,
                    "image_path": figure_meta.get("image_path") or vision_meta.get("image_path"),
                    "vision_image_path": vision_meta.get("vision_image_path") or figure_meta.get("vision_image_path") or source_image_path,
                    "source_image_path": source_image_path,
                    "caption": figure_meta.get("caption") or figure_meta.get("raw_caption") or vision_meta.get("caption"),
                    "stage2_figure_class": vision_meta.get("figure_class") or figure_meta.get("figure_class"),
                    "stage2_predicted_figure_type": vision_meta.get("predicted_figure_type") or figure_meta.get("predicted_figure_type"),
                    "figure_label": figure_meta.get("figure_label"),
                    "page_number": figure_meta.get("page_number"),
                    "subfigure_id": figure_meta.get("subfigure_id") or figure_meta.get("subfigure_index"),
                    "reference_sentences": figure_meta.get("reference_sentences") or [],
                    "context_before": figure_meta.get("context_before"),
                    "context_after": figure_meta.get("context_after"),
                    "nearby_text": figure_meta.get("nearby_text"),
                    "related_text": figure_meta.get("related_text"),
                    "ocr_text": figure_meta.get("ocr_text"),
                    "context_text": figure_meta.get("description_text") or figure_meta.get("context_text"),
                    "description_text": figure_meta.get("description_text"),
                    "loader_warnings": ["legacy_candidate_loader_compatibility_fallback"],
                    "selection_source": "legacy_figures_or_vision_inputs",
                    "send_to_vision_model": True,
                    "keep": True,
                    "technique": figure_meta.get("technique") or vision_meta.get("technique"),
                }
            )
        return selected

    def _apply_figure_level_dedup(
        self,
        candidates: list[dict[str, Any]],
        processed_index: dict[str, Any],
    ) -> list[dict[str, Any]]:
        normalized_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            action, reason = classify_stage4a_figure_processing_action(candidate, processed_index)
            updated = dict(candidate)
            updated["figure_processing_action"] = action
            updated["figure_processing_reason"] = reason
            updated["will_call_vlm"] = bool(updated.get("send_to_vlm")) and action in {"new_live", "rerun_transient"}
            updated["replay_candidate"] = action == "replay_candidate"
            updated["rerun_reason"] = reason if action == "rerun_transient" else None
            if action == "skip_success":
                updated["skip_reason"] = reason or updated.get("skip_reason")
            elif action == "missing_image":
                updated["send_to_vlm"] = False
                updated["will_call_vlm"] = False
                updated["skip_reason"] = "missing_image_path"
            elif action in {"replay_candidate", "blocked_failed"}:
                updated["will_call_vlm"] = False
            normalized_candidates.append(updated)
        return normalized_candidates

    def _select_candidates(
        self,
        *,
        stage2_selected_figures: list[dict[str, Any]] | None = None,
        figures: list[dict[str, Any]] | None = None,
        vision_inputs: list[dict[str, Any]] | None = None,
        evidence_objects: list[dict[str, Any]],
        stage3_schema: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        allowed_types = self.allowed_figure_types or DEFAULT_ALLOWED_FIGURE_TYPES
        stage2_selected_figures = list(stage2_selected_figures or [])
        if not stage2_selected_figures:
            stage2_selected_figures = self._legacy_stage2_selected_from_records(figures or [], vision_inputs or [])
        evidence_by_id = group_evidence_by_figure_id(evidence_objects)
        stage3_parameter_records = collect_stage3_parameter_records(stage3_schema or {})
        candidates: list[dict[str, Any]] = []
        for selected in stage2_selected_figures:
            figure_id = str(selected.get("figure_id") or "").strip()
            if not figure_id:
                continue
            figure_meta = dict(selected)
            vision_meta = dict(selected)
            evidence_group = evidence_by_id.get(figure_id, [])
            evidence_type = next((item.get("figure_type") for item in evidence_group if item.get("figure_type")), None)
            stage2_class = (
                vision_meta.get("stage2_figure_class")
                or vision_meta.get("figure_class")
                or figure_meta.get("stage2_figure_class")
                or figure_meta.get("figure_class")
            )
            stage2_predicted_figure_type = (
                vision_meta.get("stage2_predicted_figure_type")
                or figure_meta.get("stage2_predicted_figure_type")
            )
            caption = (
                next((item.get("caption") for item in evidence_group if item.get("caption")), None)
                or vision_meta.get("caption")
                or figure_meta.get("caption")
                or figure_meta.get("raw_caption")
            )
            final_type = normalize_figure_type(evidence_type or stage2_predicted_figure_type or stage2_class, caption)
            source_image_path = (
                vision_meta.get("vision_image_path")
                or vision_meta.get("image_path")
                or figure_meta.get("vision_image_path")
                or figure_meta.get("image_path")
            )
            context = self.build_figure_context(
                figure_id=figure_id,
                figure_meta=figure_meta,
                vision_meta=vision_meta,
                evidence_group=evidence_group,
                stage3_parameter_records=stage3_parameter_records,
            )
            path_status = _image_path_state(source_image_path)
            if self.routing_mode == "universal_compact":
                _, routing_reason, risk_level = describe_universal_candidate(
                    initial_figure_type=final_type,
                    stage2_figure_class=stage2_class,
                    stage3_figure_type=evidence_type,
                    caption=caption,
                    context_text=" ".join(
                        item
                        for item in [
                            *context.get("reference_sentences", []),
                            context.get("context_before"),
                            context.get("context_after"),
                            figure_meta.get("context_text"),
                            figure_meta.get("nearby_text"),
                            figure_meta.get("related_text"),
                            figure_meta.get("ocr_text"),
                        ]
                        if item
                    ),
                    allow_types=allowed_types,
                )
                send_to_vlm = True
                prompt_template = get_universal_compact_prompt()
                schema_name = UniversalFigureExtraction.__name__
                skip_reason = None
            else:
                send_to_vlm = should_process_figure(final_type, allowed_types)
                prompt_template = get_prompt_for_figure_type(final_type)
                schema_name = get_schema_for_figure_type(final_type).__name__
                routing_reason = "default_schema_specific"
                risk_level = "low" if send_to_vlm else "high"
                skip_reason = None if send_to_vlm else "figure_type_not_in_allowlist_or_unknown"
            candidate = {
                "paper_id": self.paper_id,
                "figure_id": figure_id,
                "figure_type": final_type,
                "initial_figure_type": final_type,
                "stage2_predicted_figure_type": stage2_predicted_figure_type,
                "source_image_path": source_image_path,
                "vision_image_path": vision_meta.get("vision_image_path") or figure_meta.get("vision_image_path"),
                "image_path": vision_meta.get("image_path") or figure_meta.get("image_path"),
                "image_basename": Path(str(source_image_path or "")).name or None,
                "caption": caption,
                "alt_text": context.get("alt_text"),
                "reference_sentences": context.get("reference_sentences", []),
                "context_before": context.get("context_before"),
                "context_after": context.get("context_after"),
                "nearby_text": figure_meta.get("nearby_text"),
                "related_text": figure_meta.get("related_text"),
                "ocr_text": figure_meta.get("ocr_text"),
                "context_text": figure_meta.get("context_text"),
                "figure_label": figure_meta.get("figure_label"),
                "page_number": figure_meta.get("page_number"),
                "subfigure_id": figure_meta.get("subfigure_id"),
                "evidence_object_context": context.get("evidence_object_context", {}),
                "related_stage3_parameters": context.get("related_stage3_parameters", []),
                "context_source": context.get("context_source", {}),
                "context_warnings": [*context.get("warnings", []), *list(figure_meta.get("loader_warnings", []))],
                "estimated_context_chars": context.get("estimated_context_chars", 0),
                "evidence_id": next((item.get("evidence_id") for item in evidence_group if item.get("evidence_id")), None),
                "evidence_ids": [item.get("evidence_id") for item in evidence_group if item.get("evidence_id")],
                "prompt_template_name": prompt_template.name,
                "schema_name": schema_name,
                "send_to_vlm": send_to_vlm,
                "skip_reason": skip_reason,
                "stage3_figure_type": evidence_type,
                "stage2_figure_class": stage2_class,
                "technique": vision_meta.get("technique") or figure_meta.get("technique"),
                "routing_mode": self.routing_mode,
                "candidate_risk_level": risk_level,
                "routing_reason": routing_reason,
                "selection_source": figure_meta.get("selection_source"),
                "path_status": path_status,
                "max_figures_per_paper_applied": self.max_figures if self.max_figures and self.max_figures > 0 else 0,
            }
            if path_status in {"missing", "directory"}:
                candidate["send_to_vlm"] = False
                candidate["skip_reason"] = "directory_path_error" if path_status == "directory" else "missing_image_path"
                candidate["candidate_risk_level"] = "high"
            candidates.append(candidate)

        requested_ids = [item for item in (self.figure_ids or []) if item]
        if requested_ids:
            requested_set = set(requested_ids)
            present_ids = {item.get("figure_id") for item in candidates}
            missing_ids = [item for item in requested_ids if item not in present_ids]
            if missing_ids:
                raise ValueError(f"Requested figure_id(s) not found: {', '.join(missing_ids)}")
            candidates = [item for item in candidates if item.get("figure_id") in requested_set]

        if self.max_figures is not None and self.max_figures > 0:
            sendable = [item for item in candidates if item.get("send_to_vlm")]
            prioritized = prioritize_sendable_candidates(sendable)
            blocked_ids = {item["figure_id"] for item in prioritized[self.max_figures :]}
            for item in candidates:
                if item["figure_id"] in blocked_ids:
                    item["send_to_vlm"] = False
                    item["skip_reason"] = "max_figures_limit_debug"
                    item["max_figures_per_paper_applied"] = self.max_figures
        return candidates

    def build_figure_context(
        self,
        *,
        figure_id: str,
        figure_meta: dict[str, Any],
        vision_meta: dict[str, Any],
        evidence_group: list[dict[str, Any]],
        stage3_parameter_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        alt_text = (vision_meta.get("alt_text") or figure_meta.get("alt_text") or "").strip() or None
        all_reference_sentences = collect_reference_sentences(evidence_group, vision_meta, figure_meta)
        reference_sentences = all_reference_sentences[:MAX_REFERENCE_SENTENCES]
        if len(all_reference_sentences) > MAX_REFERENCE_SENTENCES:
            warnings.append("reference_sentences_truncated")

        context_before, before_warning = truncate_text(
            (vision_meta.get("context_before") or figure_meta.get("context_before") or "").strip() or None,
            MAX_CONTEXT_CHARS,
            "context_before_truncated",
        )
        context_after, after_warning = truncate_text(
            (vision_meta.get("context_after") or figure_meta.get("context_after") or "").strip() or None,
            MAX_CONTEXT_CHARS,
            "context_after_truncated",
        )
        if before_warning:
            warnings.append(before_warning)
        if after_warning:
            warnings.append(after_warning)

        evidence_context, evidence_warning = build_evidence_object_context(
            evidence_group,
            max_chars=MAX_EVIDENCE_CONTEXT_CHARS,
        )
        if evidence_warning:
            warnings.append(evidence_warning)
        related_parameters = find_related_stage3_parameters(
            figure_id=figure_id,
            evidence_group=evidence_group,
            parameter_records=stage3_parameter_records,
        )
        if len(related_parameters) > MAX_RELATED_PARAMETERS:
            related_parameters = related_parameters[:MAX_RELATED_PARAMETERS]
            warnings.append("related_stage3_parameters_truncated")

        context_source: dict[str, str] = {}
        if figure_meta.get("caption") or figure_meta.get("raw_caption") or vision_meta.get("caption"):
            context_source["caption"] = "caption"
        if alt_text:
            context_source["alt_text"] = "caption"
        if reference_sentences:
            context_source["reference_sentences"] = "reference_sentences"
        if context_before:
            context_source["context_before"] = "context_before"
        if context_after:
            context_source["context_after"] = "context_after"
        if evidence_context and any(evidence_context.values()):
            context_source["evidence_object_context"] = "stage3_evidence"
        if related_parameters:
            context_source["related_stage3_parameters"] = "stage3_parameter"

        estimated_context_chars = estimate_context_chars(
            alt_text=alt_text,
            reference_sentences=reference_sentences,
            context_before=context_before,
            context_after=context_after,
            evidence_context=evidence_context,
            related_parameters=related_parameters,
        )
        return {
            "alt_text": alt_text,
            "reference_sentences": reference_sentences,
            "context_before": context_before,
            "context_after": context_after,
            "evidence_object_context": evidence_context,
            "related_stage3_parameters": related_parameters,
            "context_source": context_source,
            "warnings": warnings,
            "estimated_context_chars": estimated_context_chars,
        }

    def _run_extractions(
        self,
        candidates: list[dict[str, Any]],
        *,
        previous_extractions: list[dict[str, Any]] | None = None,
        previous_raw_outputs: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        client = self.client or VisionLanguageModelClient(dry_run=self.dry_run)
        extractions: list[dict[str, Any]] = []
        raw_outputs: list[dict[str, Any]] = []
        failed_records: list[dict[str, Any]] = []
        config_warnings = list(getattr(client, "config_warnings", []) or [])
        previous_success_by_figure_id = index_previous_successes(previous_extractions or [])
        previous_raw_by_figure_id = self._index_latest_raw_outputs(previous_raw_outputs or [])
        for candidate in candidates:
            action = str(candidate.get("figure_processing_action") or "")
            if action == "missing_image":
                failed_records.append(
                    {
                        "figure_id": candidate.get("figure_id"),
                        "figure_type": candidate.get("figure_type"),
                        "error": "missing_image_path",
                        "error_type": "missing_image_path",
                        "error_message": "missing_image_path",
                        "is_transient": False,
                        "retry_attempts": 0,
                        "max_retries": 0,
                        "timeout_seconds": None,
                        "attempt_errors": [],
                        "fallback_used": False,
                        "fallback_source": None,
                        "final_status": "failed",
                    }
                )
                continue
            if action == "replay_candidate":
                replay_output = previous_raw_by_figure_id.get(str(candidate.get("figure_id") or ""))
                replay_result = self._replay_candidate_from_raw_output(candidate, replay_output)
                if replay_result["ok"]:
                    extractions.append(replay_result["record"])
                    raw_outputs.append(replay_result["raw_output"])
                else:
                    failed_records.append(replay_result["failed_record"])
                    if replay_result.get("raw_output") is not None:
                        raw_outputs.append(replay_result["raw_output"])
                continue
            if not candidate.get("send_to_vlm") or not candidate.get("will_call_vlm"):
                continue
            prompt_record = self._build_prompt_record(candidate)
            if self.dry_run:
                extraction = self._build_dry_run_extraction(candidate)
                extraction["validation_errors"] = validate_stage4_extraction(extraction)
                extractions.append(extraction)
                raw_outputs.append(
                    {
                        "figure_id": candidate["figure_id"],
                        "figure_type": candidate["figure_type"],
                        "raw_response": None,
                        "dry_run": True,
                        "live_request_needed": bool(candidate.get("will_call_vlm")),
                        "figure_processing_action": candidate.get("figure_processing_action"),
                        "prompt_preview": prompt_record.get("prompt"),
                    }
                )
                continue
            figure_id = str(candidate.get("figure_id") or "").strip()
            figure_started_at = time.monotonic()
            timeout_s = getattr(client, "timeout_s", None)

            try:
                print(
                    f"[Stage4A] VLM start figure_id={figure_id} "
                    f"type={candidate.get('figure_type')} timeout={timeout_s}s",
                    flush=True,
                )

                response = client.extract(
                    VLMRequest(
                        image_path=str(candidate.get("source_image_path") or ""),
                        prompt=prompt_record["prompt"],
                    )
                )

                elapsed = round(time.monotonic() - figure_started_at, 2)
                print(
                    f"[Stage4A] VLM done figure_id={figure_id} elapsed={elapsed}s",
                    flush=True,
                )
                raw_outputs.append(
                    {
                        "figure_id": candidate["figure_id"],
                        "figure_type": candidate["figure_type"],
                        "raw_response": response.get("response_text"),
                        "response_payload": response.get("response_payload"),
                        "dry_run": False,
                    }
                )
                parsed = parse_json_payload(str(response.get("response_text") or ""))
                parsed.setdefault("paper_id", self.paper_id)
                parsed.setdefault("figure_id", candidate.get("figure_id"))
                parsed.setdefault("figure_type", candidate.get("figure_type"))
                parsed.setdefault("source_image_path", candidate.get("source_image_path"))
                parsed.setdefault("caption", candidate.get("caption"))
                parsed.setdefault("extraction_mode", "live")
                parsed.setdefault("extraction_model", response.get("model"))
                parsed.setdefault("input_context_summary", build_input_context_summary(candidate))
                parsed.setdefault("used_context_sources", list(candidate.get("context_source", {}).values()))
                if self.routing_mode == "universal_compact":
                    validation_result = validate_universal_extraction_payload(parsed, candidate)
                    if validation_result.get("ok"):
                        extractions.append(validation_result["record"])
                    else:
                        error = ValueError(str(validation_result.get("error_message") or "schema_validation_failed"))
                        failed_records.append(build_failed_record(candidate, error, fallback_used=False))
                        raw_outputs.append(
                            {
                                "figure_id": candidate["figure_id"],
                                "figure_type": candidate["figure_type"],
                                "raw_response": response.get("response_text"),
                                "response_payload": response.get("response_payload"),
                                "raw_universal_payload": validation_result.get("raw_universal_payload"),
                                "warnings": validation_result.get("warnings", []),
                                "error_type": "schema_validation_failed",
                                "dry_run": False,
                                "elapsed_seconds": elapsed,
                                "timeout_seconds": timeout_s,
                            }
                        )
                else:
                    schema_cls = get_schema_for_figure_type(candidate.get("figure_type"))
                    parsed, normalization_warnings = self._normalize_live_payload(
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
            except VLMRequestError as exc:
                elapsed = round(time.monotonic() - figure_started_at, 2)
                fallback_record = None
                if exc.is_transient:
                    fallback_record = reuse_previous_success(
                        candidate=candidate,
                        previous_success=previous_success_by_figure_id.get(str(candidate.get("figure_id") or "")),
                        error_type=exc.error_type,
                    )
                failed_record = build_failed_record(candidate, exc, fallback_used=fallback_record is not None)
                failed_record["elapsed_seconds"] = elapsed
                failed_record["status"] = "timeout" if "timeout" in str(exc.error_type).lower() else "failed"
                failed_record["final_status"] = failed_record["status"]
                failed_records.append(failed_record)
                error_raw_output = build_error_raw_output(
                    candidate,
                    error_message=str(exc),
                    error_type=exc.error_type,
                    retry_attempts=exc.retry_attempts,
                    timeout_seconds=exc.timeout_seconds,
                )
                error_raw_output["elapsed_seconds"] = elapsed
                error_raw_output["status"] = failed_record["status"]
                raw_outputs.append(error_raw_output)

                print(
                    f"[Stage4A] VLM {failed_record['status']} "
                    f"figure_id={figure_id} elapsed={elapsed}s "
                    f"error_type={exc.error_type}; continue next figure",
                    flush=True,
                )
                if fallback_record is not None:
                    extractions.append(fallback_record)
            except Exception as exc:  # noqa: BLE001
                raw_outputs.append(build_error_raw_output(candidate, error_message=str(exc), error_type="processing_error"))
                failed_records.append(build_failed_record(candidate, exc, fallback_used=False))
        return extractions, raw_outputs, failed_records, config_warnings

    @staticmethod
    def _index_latest_raw_outputs(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for record in records:
            figure_id = str(record.get("figure_id") or "").strip()
            if not figure_id:
                continue
            indexed[figure_id] = record
        return indexed

    def _replay_candidate_from_raw_output(
        self,
        candidate: dict[str, Any],
        raw_output: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not raw_output:
            error = ValueError("missing_raw_vlm_output_for_replay")
            return {
                "ok": False,
                "failed_record": build_failed_record(candidate, error, fallback_used=False),
                "raw_output": None,
            }
        try:
            if raw_output.get("raw_universal_payload"):
                parsed = dict(raw_output.get("raw_universal_payload") or {})
            else:
                parsed = parse_json_payload(str(raw_output.get("raw_response") or ""))
            parsed.setdefault("paper_id", self.paper_id)
            parsed.setdefault("figure_id", candidate.get("figure_id"))
            parsed.setdefault("figure_type", candidate.get("figure_type"))
            parsed.setdefault("source_image_path", candidate.get("source_image_path"))
            parsed.setdefault("caption", candidate.get("caption"))
            parsed.setdefault("extraction_mode", "replay_materialized")
            parsed.setdefault("extraction_model", (raw_output.get("response_payload") or {}).get("model"))
            parsed.setdefault("input_context_summary", build_input_context_summary(candidate))
            parsed.setdefault("used_context_sources", list(candidate.get("context_source", {}).values()))
            if self.routing_mode == "universal_compact":
                validation_result = validate_universal_extraction_payload(parsed, candidate)
                if not validation_result.get("ok"):
                    error = ValueError(str(validation_result.get("error_message") or "schema_validation_failed"))
                    failed_record = build_failed_record(candidate, error, fallback_used=False)
                    failed_record["error_type"] = "schema_validation_failed"
                    return {
                        "ok": False,
                        "failed_record": failed_record,
                        "raw_output": {
                            **raw_output,
                            "error_type": "schema_validation_failed",
                            "warnings": validation_result.get("warnings", []),
                        },
                    }
                record = dict(validation_result["record"])
            else:
                schema_cls = get_schema_for_figure_type(candidate.get("figure_type"))
                parsed, normalization_warnings = self._normalize_live_payload(
                    parsed,
                    figure_type=str(candidate.get("figure_type") or ""),
                    schema_name=schema_cls.__name__,
                )
                record = schema_cls(**parsed).model_dump()
                record["schema_name"] = schema_cls.__name__
                if normalization_warnings:
                    record["warnings"] = [*record.get("warnings", []), *normalization_warnings]
                record["validation_errors"] = validate_stage4_extraction(record)
            record["extraction_mode"] = "replay_materialized"
            return {
                "ok": True,
                "record": record,
                "raw_output": {
                    **raw_output,
                    "replayed_without_vlm": True,
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "failed_record": build_failed_record(candidate, exc, fallback_used=False),
                "raw_output": {
                    **raw_output,
                    "error_type": raw_output.get("error_type") or "replay_processing_error",
                    "replayed_without_vlm": True,
                },
            }

    @staticmethod
    def _normalize_live_payload(
        parsed: dict[str, Any],
        *,
        figure_type: str = "",
        schema_name: str = "",
        use_universal_adapter: bool = False,
    ) -> tuple[dict[str, Any], list[str]]:
        normalized = dict(parsed)
        warnings: list[str] = []
        peaks = normalized.get("peaks")
        if isinstance(peaks, list):
            normalized["peaks"] = [
                Stage4VisionSpectraExtractor._normalize_peak_record(item, figure_type=figure_type, warnings=warnings)
                for item in peaks
                if isinstance(item, dict)
            ]
        confidence = normalized.get("confidence")
        if isinstance(confidence, str):
            coerced_confidence = Stage4VisionSpectraExtractor._coerce_confidence_value(confidence)
            if coerced_confidence is None:
                normalized["confidence"] = None
                warnings.append("confidence_cleared_from_invalid_string")
            else:
                normalized["confidence"] = coerced_confidence
        normalizer = normalize_universal_extraction_payload_for_schema if use_universal_adapter else normalize_vlm_payload_for_schema
        schema_normalized, schema_warnings = normalizer(normalized, figure_type, schema_name) if use_universal_adapter else normalizer(normalized, schema_name)
        normalized = schema_normalized
        warnings.extend(schema_warnings)
        return normalized, warnings

    @staticmethod
    def _normalize_peak_record(item: dict[str, Any], *, figure_type: str, warnings: list[str]) -> dict[str, Any]:
        peak = dict(item)
        if peak.get("warnings") is None:
            peak["warnings"] = []
        elif not isinstance(peak.get("warnings"), list):
            peak["warnings"] = [str(peak.get("warnings"))]
        if "position" not in peak:
            for source_key in ("wavenumber", "position_ppm", "two_theta", "2theta"):
                if source_key in peak:
                    peak["position"] = peak.get(source_key)
                    warnings.append(f"peak_position_mapped_from_{source_key}")
                    break
        if "chemical_shift_ppm" not in peak and "position_ppm" in peak:
            peak["chemical_shift_ppm"] = peak.get("position_ppm")
        if "assignment" not in peak:
            for source_key in ("phase_assignment", "species_assignment"):
                if source_key in peak:
                    peak["assignment"] = peak.get(source_key)
                    warnings.append(f"peak_assignment_mapped_from_{source_key}")
                    break
        if "relative_intensity" not in peak and "intensity" in peak:
            peak["relative_intensity"] = peak.get("intensity")
            warnings.append("peak_relative_intensity_mapped_from_intensity")
        relative_intensity = peak.get("relative_intensity")
        if isinstance(relative_intensity, str):
            coerced_relative_intensity = Stage4VisionSpectraExtractor._coerce_relative_intensity_value(relative_intensity)
            if coerced_relative_intensity is None:
                peak["relative_intensity"] = None
                warnings.append("peak_relative_intensity_cleared_from_invalid_string")
            else:
                peak["relative_intensity"] = coerced_relative_intensity
                warnings.append("peak_relative_intensity_coerced_from_label")
        if "unit" not in peak or not peak.get("unit"):
            default_unit = {
                "ftir_spectrum": "cm^-1",
                "ir_spectrum": "cm^-1",
                "raman_spectrum": "cm^-1",
                "nmr_spectrum": "ppm",
                "xrd_pattern": "2theta_deg",
            }.get(figure_type)
            if default_unit:
                peak["unit"] = default_unit
        peak.setdefault("intensity_level", "unknown")
        confidence = peak.get("confidence")
        if isinstance(confidence, str):
            coerced_confidence = Stage4VisionSpectraExtractor._coerce_confidence_value(confidence)
            if coerced_confidence is None:
                peak["confidence"] = None
                warnings.append("peak_confidence_cleared_from_invalid_string")
            else:
                peak["confidence"] = coerced_confidence
                warnings.append("peak_confidence_coerced_from_label")
        return peak

    @staticmethod
    def _coerce_confidence_value(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            numeric = float(value)
            return numeric if 0.0 <= numeric <= 1.0 else None
        if not isinstance(value, str):
            return None
        stripped = value.strip().lower()
        label_map = {
            "high": 0.9,
            "medium": 0.6,
            "low": 0.3,
            "very high": 0.95,
            "very low": 0.15,
        }
        if stripped in label_map:
            return label_map[stripped]
        try:
            numeric = float(stripped)
        except ValueError:
            return None
        return numeric if 0.0 <= numeric <= 1.0 else None

    @staticmethod
    def _coerce_relative_intensity_value(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None
        stripped = value.strip().lower()
        label_map = {
            "very weak": 0.15,
            "weak": 0.3,
            "medium": 0.6,
            "moderate": 0.6,
            "strong": 0.85,
            "stronger": 0.9,
            "very strong": 0.95,
        }
        if stripped in label_map:
            return label_map[stripped]
        try:
            return float(stripped)
        except ValueError:
            return None

    def _build_prompt_record(self, candidate: dict[str, Any]) -> dict[str, Any]:
        template = get_universal_compact_prompt() if self.routing_mode == "universal_compact" else get_prompt_for_figure_type(candidate.get("figure_type"))
        attached_context = {
            "caption": candidate.get("caption"),
            "alt_text": candidate.get("alt_text"),
            "reference_sentences": candidate.get("reference_sentences", []),
            "context_before": candidate.get("context_before"),
            "context_after": candidate.get("context_after"),
            "nearby_text": candidate.get("nearby_text"),
            "related_text": candidate.get("related_text"),
            "ocr_text": candidate.get("ocr_text"),
            "context_text": candidate.get("context_text"),
            "evidence_object_context": candidate.get("evidence_object_context", {}),
            "related_stage3_parameters": candidate.get("related_stage3_parameters", []),
            "context_source": candidate.get("context_source", {}),
            "stage2_figure_class": candidate.get("stage2_figure_class"),
            "stage2_predicted_figure_type": candidate.get("stage2_predicted_figure_type"),
            "stage3_figure_type": candidate.get("stage3_figure_type"),
            "initial_figure_type": candidate.get("initial_figure_type"),
        }
        prompt_text = template.text
        composed_prompt = (
            f"{prompt_text}\n"
            f"Figure metadata JSON:\n{json.dumps(figure_metadata_for_prompt(candidate), ensure_ascii=False, indent=2)}\n"
            f"Attached text context JSON:\n{json.dumps(attached_context, ensure_ascii=False, indent=2)}"
        )
        return {
            "paper_id": self.paper_id,
            "figure_id": candidate.get("figure_id"),
            "figure_type": candidate.get("figure_type"),
            "image_path": candidate.get("source_image_path"),
            "schema_name": candidate.get("schema_name"),
            "prompt_template_name": template.name,
            "prompt_text": prompt_text,
            "attached_context": attached_context,
            "estimated_context_chars": candidate.get("estimated_context_chars", 0),
            "warnings": candidate.get("context_warnings", []),
            "dry_run_no_vlm_called": self.dry_run,
            "prompt": composed_prompt,
            "routing_mode": candidate.get("routing_mode"),
            "routing_reason": candidate.get("routing_reason"),
        }

    def _build_dry_run_extraction(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if self.routing_mode == "universal_compact":
            extraction = {
                "paper_id": self.paper_id,
                "figure_id": candidate.get("figure_id"),
                "figure_type": candidate.get("initial_figure_type"),
                "initial_figure_type": candidate.get("initial_figure_type"),
                "actual_figure_type": None,
                "stage2_figure_class": candidate.get("stage2_figure_class"),
                "stage3_figure_type": candidate.get("stage3_figure_type"),
                "routing_mode": "universal_compact",
                "type_confidence": None,
                "type_reason": "dry_run_no_vlm_called",
                "type_mismatch": False,
                "needs_manual_review": True,
                "source_image_path": candidate.get("source_image_path"),
                "caption": candidate.get("caption"),
                "extraction_model": None,
                "extraction_mode": "dry_run",
                "confidence": None,
                "warnings": ["dry_run_no_vlm_called", *candidate.get("context_warnings", [])],
                "raw_notes": "Universal compact prompt generated only; no VLM request was sent.",
                "input_context_summary": build_input_context_summary(candidate),
                "used_context_sources": list(candidate.get("context_source", {}).values()),
                "image_readability": None,
                "text_context_quality": "available" if candidate.get("estimated_context_chars") else "minimal",
                "conflict_warnings": [],
                "schema_name": UniversalFigureExtraction.__name__,
            }
            return extraction
        schema_cls = get_schema_for_figure_type(candidate.get("figure_type"))
        extraction = schema_cls(
            paper_id=self.paper_id,
            figure_id=candidate.get("figure_id"),
            figure_type=candidate.get("figure_type"),
            technique=candidate.get("technique"),
            source_image_path=candidate.get("source_image_path"),
            caption=candidate.get("caption"),
            extraction_model=None,
            extraction_mode="dry_run",
            confidence=None,
            warnings=["dry_run_no_vlm_called", *candidate.get("context_warnings", [])],
            raw_notes="Prompt generated only; no VLM request was sent.",
            input_context_summary=build_input_context_summary(candidate),
            used_context_sources=list(candidate.get("context_source", {}).values()),
            image_readability=None,
            text_context_quality="available" if candidate.get("estimated_context_chars") else "minimal",
            conflict_warnings=[],
        ).model_dump()
        extraction["schema_name"] = schema_cls.__name__
        return extraction
