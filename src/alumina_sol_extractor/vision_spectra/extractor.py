"""Stage 4 vision spectra dry-run extractor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import parse_json_payload, read_json, read_jsonl, write_json, write_jsonl
from .prompt_templates import get_prompt_for_figure_type
from .routing import get_schema_for_figure_type, normalize_figure_type, should_process_figure
from .validators import build_stage4_summary, validate_stage4_extraction
from .vlm_client import VLMRequest, VisionLanguageModelClient


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
    dry_run: bool = True
    client: VisionLanguageModelClient | None = None

    def run(self) -> dict[str, Any]:
        stage4_dir = Path(self.output_dir) / "stage4_vision_spectra"
        stage4_dir.mkdir(parents=True, exist_ok=True)

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
        extractions, raw_outputs, failed_records = self._run_extractions(candidates)
        summary = build_stage4_summary(
            candidates=candidates,
            extractions=extractions,
            failed_records=failed_records,
        )

        write_jsonl(candidates, stage4_dir / "stage4_candidates.jsonl")
        write_jsonl(prompts, stage4_dir / "stage4_prompts.jsonl")
        write_jsonl(extractions, stage4_dir / "spectra_extractions.jsonl")
        write_jsonl(raw_outputs, stage4_dir / "raw_vlm_outputs.jsonl")
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
        figures_by_id = self._index_by_figure_id(figures)
        vision_by_id = self._index_by_figure_id(vision_inputs)
        evidence_by_id = self._group_evidence_by_figure_id(evidence_objects)
        stage3_parameter_records = self._collect_stage3_parameter_records(stage3_schema or {})
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

        if self.max_figures > 0:
            sendable = [item for item in candidates if item.get("send_to_vlm")]
            prioritized = self._prioritize_sendable_candidates(sendable)
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
        reference_sentences = self._collect_reference_sentences(evidence_group, vision_meta, figure_meta)[:MAX_REFERENCE_SENTENCES]
        if len(self._collect_reference_sentences(evidence_group, vision_meta, figure_meta)) > MAX_REFERENCE_SENTENCES:
            warnings.append("reference_sentences_truncated")

        context_before, before_warning = self._truncate_text(
            (vision_meta.get("context_before") or figure_meta.get("context_before") or "").strip() or None,
            MAX_CONTEXT_CHARS,
            "context_before_truncated",
        )
        context_after, after_warning = self._truncate_text(
            (vision_meta.get("context_after") or figure_meta.get("context_after") or "").strip() or None,
            MAX_CONTEXT_CHARS,
            "context_after_truncated",
        )
        if before_warning:
            warnings.append(before_warning)
        if after_warning:
            warnings.append(after_warning)

        evidence_context, evidence_warning = self._build_evidence_object_context(evidence_group)
        if evidence_warning:
            warnings.append(evidence_warning)
        related_parameters = self._find_related_stage3_parameters(
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

        estimated_context_chars = self._estimate_context_chars(
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

    def _run_extractions(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        client = self.client or VisionLanguageModelClient(dry_run=self.dry_run)
        extractions: list[dict[str, Any]] = []
        raw_outputs: list[dict[str, Any]] = []
        failed_records: list[dict[str, Any]] = []
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
                parsed.setdefault("input_context_summary", self._build_input_context_summary(candidate))
                parsed.setdefault("used_context_sources", list(candidate.get("context_source", {}).values()))
                schema_cls = get_schema_for_figure_type(candidate.get("figure_type"))
                validated = schema_cls(**parsed).model_dump()
                validated["schema_name"] = schema_cls.__name__
                validated["validation_errors"] = validate_stage4_extraction(validated)
                extractions.append(validated)
            except Exception as exc:  # noqa: BLE001
                failed_records.append(
                    {
                        "figure_id": candidate.get("figure_id"),
                        "figure_type": candidate.get("figure_type"),
                        "error": str(exc),
                    }
                )
        return extractions, raw_outputs, failed_records

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
            f"Figure metadata JSON:\n{json.dumps(self._figure_metadata_for_prompt(candidate), ensure_ascii=False, indent=2)}\n"
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
            input_context_summary=self._build_input_context_summary(candidate),
            used_context_sources=list(candidate.get("context_source", {}).values()),
            image_readability=None,
            text_context_quality="available" if candidate.get("estimated_context_chars") else "minimal",
            conflict_warnings=[],
        ).model_dump()
        extraction["schema_name"] = schema_cls.__name__
        return extraction

    @staticmethod
    def _index_by_figure_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for record in records:
            figure_id = record.get("figure_id")
            if figure_id and figure_id not in index:
                index[figure_id] = record
        return index

    @staticmethod
    def _group_evidence_by_figure_id(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            figure_id = record.get("figure_id")
            if not figure_id:
                continue
            grouped.setdefault(figure_id, []).append(record)
        return grouped

    @staticmethod
    def _collect_reference_sentences(*records: Any) -> list[str]:
        collected: list[str] = []
        for record in records:
            if isinstance(record, list):
                for nested in record:
                    for item in (nested.get("reference_sentences", []) or []):
                        if item and item not in collected:
                            collected.append(item)
                continue
            if not isinstance(record, dict):
                continue
            for item in record.get("reference_sentences", []) or []:
                if item and item not in collected:
                    collected.append(item)
        return collected

    @staticmethod
    def _prioritize_sendable_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prioritized: list[dict[str, Any]] = []
        seen_types: set[str] = set()
        for candidate in candidates:
            figure_type = str(candidate.get("figure_type") or "unknown")
            if figure_type in seen_types:
                continue
            prioritized.append(candidate)
            seen_types.add(figure_type)
        prioritized_ids = {item["figure_id"] for item in prioritized}
        prioritized.extend(item for item in candidates if item["figure_id"] not in prioritized_ids)
        return prioritized

    @staticmethod
    def _truncate_text(text: str | None, limit: int, warning_name: str) -> tuple[str | None, str | None]:
        if not text:
            return None, None
        if len(text) <= limit:
            return text, None
        return text[:limit].rstrip(), warning_name

    @staticmethod
    def _truncate_text_list(items: list[str], limit: int, warning_name: str) -> tuple[list[str], str | None]:
        kept: list[str] = []
        total = 0
        for item in items:
            if not item:
                continue
            proposed = total + len(item)
            if proposed > limit and kept:
                return kept, warning_name
            if proposed > limit:
                kept.append(item[:limit].rstrip())
                return kept, warning_name
            kept.append(item)
            total = proposed
        return kept, None

    def _build_evidence_object_context(self, evidence_group: list[dict[str, Any]]) -> tuple[dict[str, Any], str | None]:
        fact_summaries: list[str] = []
        detailed_observations: list[str] = []
        linked_facts: list[str] = []
        evidence_refs: list[str] = []
        evidence_ids: list[str] = []
        for record in evidence_group:
            evidence_id = record.get("evidence_id")
            if evidence_id and evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
            refs = record.get("evidence_refs", []) or []
            for ref in refs:
                if ref and ref not in evidence_refs:
                    evidence_refs.append(ref)
            key_facts = record.get("fact_summary") or record.get("key_facts") or []
            if isinstance(key_facts, str):
                key_facts = [key_facts]
            for fact in key_facts:
                if fact and fact not in fact_summaries:
                    fact_summaries.append(fact)
            detailed = record.get("detailed_observation") or record.get("note")
            if detailed and detailed not in detailed_observations:
                detailed_observations.append(detailed)
            linked = record.get("linked_facts", []) or []
            if isinstance(linked, str):
                linked = [linked]
            for fact in linked:
                if fact and fact not in linked_facts:
                    linked_facts.append(fact)

        warning = None
        fact_summaries, fact_warning = self._truncate_text_list(fact_summaries, MAX_EVIDENCE_CONTEXT_CHARS, "stage3_evidence_context_truncated")
        if fact_warning:
            warning = fact_warning
        remaining = max(MAX_EVIDENCE_CONTEXT_CHARS - sum(len(item) for item in fact_summaries), 0)
        detailed_observations, detail_warning = self._truncate_text_list(
            detailed_observations,
            remaining if remaining > 0 else MAX_EVIDENCE_CONTEXT_CHARS,
            "stage3_evidence_context_truncated",
        )
        if detail_warning:
            warning = detail_warning
        remaining = max(
            MAX_EVIDENCE_CONTEXT_CHARS - sum(len(item) for item in fact_summaries) - sum(len(item) for item in detailed_observations),
            0,
        )
        linked_facts, linked_warning = self._truncate_text_list(
            linked_facts,
            remaining if remaining > 0 else MAX_EVIDENCE_CONTEXT_CHARS,
            "stage3_evidence_context_truncated",
        )
        if linked_warning:
            warning = linked_warning
        return {
            "fact_summary": fact_summaries,
            "detailed_observation": detailed_observations,
            "linked_facts": linked_facts,
            "evidence_refs": evidence_refs,
            "evidence_ids": evidence_ids,
        }, warning

    @staticmethod
    def _collect_stage3_parameter_records(payload: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                if "canonical_key" in node and ("value" in node or "raw_text" in node):
                    records.append(node)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        return records

    def _find_related_stage3_parameters(
        self,
        *,
        figure_id: str,
        evidence_group: list[dict[str, Any]],
        parameter_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence_ids = [item.get("evidence_id") for item in evidence_group if item.get("evidence_id")]
        related: list[dict[str, Any]] = []
        for record in parameter_records:
            refs = record.get("evidence_refs", []) or []
            if not isinstance(refs, list):
                continue
            if not self._parameter_refs_match_figure(refs, figure_id, evidence_ids):
                continue
            related.append(
                {
                    "canonical_key": record.get("canonical_key"),
                    "value": record.get("value"),
                    "unit": record.get("unit"),
                    "raw_name": record.get("raw_name"),
                    "raw_text": record.get("raw_text"),
                    "evidence_refs": refs,
                    "normalization_note": record.get("normalization_note"),
                }
            )
        return related

    @staticmethod
    def _parameter_refs_match_figure(refs: list[Any], figure_id: str, evidence_ids: list[str]) -> bool:
        for ref in refs:
            text = str(ref or "")
            if not text:
                continue
            if text == figure_id or figure_id in text:
                return True
            if any(evidence_id and (text == evidence_id or evidence_id in text or text in evidence_id) for evidence_id in evidence_ids):
                return True
        return False

    @staticmethod
    def _estimate_context_chars(
        *,
        alt_text: str | None,
        reference_sentences: list[str],
        context_before: str | None,
        context_after: str | None,
        evidence_context: dict[str, Any],
        related_parameters: list[dict[str, Any]],
    ) -> int:
        total = len(alt_text or "") + len(context_before or "") + len(context_after or "")
        total += sum(len(item) for item in reference_sentences)
        total += sum(len(item) for item in evidence_context.get("fact_summary", []))
        total += sum(len(item) for item in evidence_context.get("detailed_observation", []))
        total += sum(len(item) for item in evidence_context.get("linked_facts", []))
        total += sum(len(json.dumps(item, ensure_ascii=False)) for item in related_parameters)
        return total

    @staticmethod
    def _figure_metadata_for_prompt(candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "paper_id": candidate.get("paper_id"),
            "figure_id": candidate.get("figure_id"),
            "figure_type": candidate.get("figure_type"),
            "technique": candidate.get("technique"),
            "source_image_path": candidate.get("source_image_path"),
            "stage3_figure_type": candidate.get("stage3_figure_type"),
            "stage2_figure_class": candidate.get("stage2_figure_class"),
        }

    @staticmethod
    def _build_input_context_summary(candidate: dict[str, Any]) -> str:
        parts: list[str] = []
        if candidate.get("caption"):
            parts.append(f"caption={candidate['caption']}")
        reference_sentences = candidate.get("reference_sentences", []) or []
        if reference_sentences:
            parts.append(f"reference_sentences={len(reference_sentences)}")
        if candidate.get("evidence_object_context", {}).get("fact_summary"):
            parts.append("stage3_evidence=fact_summary")
        if candidate.get("related_stage3_parameters"):
            parts.append(f"related_parameters={len(candidate['related_stage3_parameters'])}")
        return "; ".join(parts)
