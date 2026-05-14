"""Stage 4 vision spectra dry-run extractor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import parse_json_payload, read_json, read_jsonl, write_json, write_jsonl
from .normalization import normalize_vlm_payload_for_schema
from .prompt_templates import get_prompt_for_figure_type
from .routing import get_schema_for_figure_type, normalize_figure_type, should_process_figure
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


@dataclass
class Stage4VisionSpectraExtractor:
    paper_id: str
    output_dir: Path
    max_figures: int = 10
    allowed_figure_types: set[str] | None = None
    figure_ids: list[str] | None = None
    dry_run: bool = True
    client: VisionLanguageModelClient | None = None

    def run(self) -> dict[str, Any]:
        stage4_dir = Path(self.output_dir) / "stage4_vision_spectra"
        stage4_dir.mkdir(parents=True, exist_ok=True)
        previous_extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")

        figures = read_jsonl(Path(self.output_dir) / "figures.jsonl")
        vision_inputs = read_jsonl(Path(self.output_dir) / "vision_inputs.jsonl")
        evidence_objects = read_jsonl(Path(self.output_dir) / "stage3_dspy_smoke" / "evidence_objects.jsonl")
        stage3_schema = read_json(Path(self.output_dir) / "stage3_dspy_smoke" / "paper_extraction.schema_v2.json", default={}) or {}

        candidates = self._select_candidates(
            figures=figures,
            vision_inputs=vision_inputs,
            evidence_objects=evidence_objects,
            stage3_schema=stage3_schema,
        )
        prompts = [self._build_prompt_record(candidate) for candidate in candidates if candidate.get("send_to_vlm")]
        extractions, raw_outputs, failed_records, config_warnings = self._run_extractions(
            candidates,
            previous_extractions=previous_extractions,
        )
        summary = build_stage4_summary(
            candidates=candidates,
            extractions=extractions,
            failed_records=failed_records,
            config_warnings=config_warnings,
        )

        write_jsonl(candidates, stage4_dir / "stage4_candidates.jsonl")
        write_jsonl(prompts, stage4_dir / "stage4_prompts.jsonl")
        write_jsonl(extractions, stage4_dir / "spectra_extractions.jsonl")
        write_jsonl(raw_outputs, stage4_dir / "raw_vlm_outputs.jsonl")
        write_jsonl(failed_records, stage4_dir / "failed_records.jsonl")
        write_json(stage4_dir / "stage4_summary.json", summary)
        return summary

    def _select_candidates(
        self,
        *,
        figures: list[dict[str, Any]],
        vision_inputs: list[dict[str, Any]],
        evidence_objects: list[dict[str, Any]],
        stage3_schema: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        allowed_types = self.allowed_figure_types or DEFAULT_ALLOWED_FIGURE_TYPES
        figures_by_id = index_by_figure_id(figures)
        vision_by_id = index_by_figure_id(vision_inputs)
        evidence_by_id = group_evidence_by_figure_id(evidence_objects)
        stage3_parameter_records = collect_stage3_parameter_records(stage3_schema or {})
        ordered_ids: list[str] = []
        for evidence in evidence_objects:
            figure_id = evidence.get("figure_id")
            if figure_id and figure_id not in ordered_ids:
                ordered_ids.append(figure_id)
        for figure_id in figures_by_id:
            if figure_id not in ordered_ids:
                ordered_ids.append(figure_id)

        candidates: list[dict[str, Any]] = []
        for figure_id in ordered_ids:
            figure_meta = figures_by_id.get(figure_id, {})
            vision_meta = vision_by_id.get(figure_id, {})
            evidence_group = evidence_by_id.get(figure_id, [])
            evidence_type = next((item.get("figure_type") for item in evidence_group if item.get("figure_type")), None)
            stage2_class = vision_meta.get("figure_class") or figure_meta.get("figure_class")
            caption = (
                next((item.get("caption") for item in evidence_group if item.get("caption")), None)
                or vision_meta.get("caption")
                or figure_meta.get("caption")
                or figure_meta.get("raw_caption")
            )
            final_type = normalize_figure_type(evidence_type or stage2_class, caption)
            send_to_vlm = should_process_figure(final_type, allowed_types)
            prompt_template = get_prompt_for_figure_type(final_type)
            schema_cls = get_schema_for_figure_type(final_type)
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
            candidate = {
                "paper_id": self.paper_id,
                "figure_id": figure_id,
                "figure_type": final_type,
                "source_image_path": source_image_path,
                "caption": caption,
                "alt_text": context.get("alt_text"),
                "reference_sentences": context.get("reference_sentences", []),
                "context_before": context.get("context_before"),
                "context_after": context.get("context_after"),
                "evidence_object_context": context.get("evidence_object_context", {}),
                "related_stage3_parameters": context.get("related_stage3_parameters", []),
                "context_source": context.get("context_source", {}),
                "context_warnings": context.get("warnings", []),
                "estimated_context_chars": context.get("estimated_context_chars", 0),
                "evidence_id": next((item.get("evidence_id") for item in evidence_group if item.get("evidence_id")), None),
                "evidence_ids": [item.get("evidence_id") for item in evidence_group if item.get("evidence_id")],
                "prompt_template_name": prompt_template.name,
                "schema_name": schema_cls.__name__,
                "send_to_vlm": send_to_vlm,
                "skip_reason": None if send_to_vlm else "figure_type_not_in_allowlist_or_unknown",
                "stage3_figure_type": evidence_type,
                "stage2_figure_class": stage2_class,
                "technique": vision_meta.get("technique") or figure_meta.get("technique"),
            }
            candidates.append(candidate)

        requested_ids = [item for item in (self.figure_ids or []) if item]
        if requested_ids:
            requested_set = set(requested_ids)
            present_ids = {item.get("figure_id") for item in candidates}
            missing_ids = [item for item in requested_ids if item not in present_ids]
            if missing_ids:
                raise ValueError(f"Requested figure_id(s) not found: {', '.join(missing_ids)}")
            candidates = [item for item in candidates if item.get("figure_id") in requested_set]

        if self.max_figures > 0:
            sendable = [item for item in candidates if item.get("send_to_vlm")]
            prioritized = prioritize_sendable_candidates(sendable)
            blocked_ids = {item["figure_id"] for item in prioritized[self.max_figures :]}
            for item in candidates:
                if item["figure_id"] in blocked_ids:
                    item["send_to_vlm"] = False
                    item["skip_reason"] = "max_figures_limit"
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
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        client = self.client or VisionLanguageModelClient(dry_run=self.dry_run)
        extractions: list[dict[str, Any]] = []
        raw_outputs: list[dict[str, Any]] = []
        failed_records: list[dict[str, Any]] = []
        config_warnings = list(getattr(client, "config_warnings", []) or [])
        previous_success_by_figure_id = index_previous_successes(previous_extractions or [])
        for candidate in candidates:
            if not candidate.get("send_to_vlm"):
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
                        "prompt_preview": prompt_record.get("prompt"),
                    }
                )
                continue
            try:
                response = client.extract(
                    VLMRequest(
                        image_path=str(candidate.get("source_image_path") or ""),
                        prompt=prompt_record["prompt"],
                    )
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
                fallback_record = None
                if exc.is_transient:
                    fallback_record = reuse_previous_success(
                        candidate=candidate,
                        previous_success=previous_success_by_figure_id.get(str(candidate.get("figure_id") or "")),
                        error_type=exc.error_type,
                    )
                failed_record = build_failed_record(candidate, exc, fallback_used=fallback_record is not None)
                failed_records.append(failed_record)
                raw_outputs.append(
                    build_error_raw_output(
                        candidate,
                        error_message=str(exc),
                        error_type=exc.error_type,
                        retry_attempts=exc.retry_attempts,
                        timeout_seconds=exc.timeout_seconds,
                    )
                )
                if fallback_record is not None:
                    extractions.append(fallback_record)
            except Exception as exc:  # noqa: BLE001
                raw_outputs.append(build_error_raw_output(candidate, error_message=str(exc), error_type="processing_error"))
                failed_records.append(build_failed_record(candidate, exc, fallback_used=False))
        return extractions, raw_outputs, failed_records, config_warnings

    @staticmethod
    def _normalize_live_payload(
        parsed: dict[str, Any],
        *,
        figure_type: str = "",
        schema_name: str = "",
    ) -> tuple[dict[str, Any], list[str]]:
        normalized = dict(parsed)
        warnings: list[str] = []
        list_fields = ("peaks", "endothermic_peaks", "exothermic_peaks")
        for field_name in list_fields:
            value = normalized.get(field_name)
            if value is None:
                continue
            if not isinstance(value, list):
                normalized[field_name] = []
                warnings.append(f"{field_name}_coerced_to_empty_list")
                continue
            if field_name == "peaks":
                normalized[field_name] = [
                    Stage4VisionSpectraExtractor._normalize_peak_record(item, figure_type=figure_type, warnings=warnings)
                    for item in value
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
        schema_normalized, schema_warnings = normalize_vlm_payload_for_schema(normalized, schema_name)
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
        template = get_prompt_for_figure_type(candidate.get("figure_type"))
        attached_context = {
            "caption": candidate.get("caption"),
            "alt_text": candidate.get("alt_text"),
            "reference_sentences": candidate.get("reference_sentences", []),
            "context_before": candidate.get("context_before"),
            "context_after": candidate.get("context_after"),
            "evidence_object_context": candidate.get("evidence_object_context", {}),
            "related_stage3_parameters": candidate.get("related_stage3_parameters", []),
            "context_source": candidate.get("context_source", {}),
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
        }

    def _build_dry_run_extraction(self, candidate: dict[str, Any]) -> dict[str, Any]:
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
