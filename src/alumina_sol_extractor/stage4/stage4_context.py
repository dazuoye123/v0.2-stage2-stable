"""Context assembly helpers for Stage 4 vision spectra extraction."""

from __future__ import annotations

import json
from typing import Any


def index_by_figure_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        figure_id = record.get("figure_id")
        if figure_id and figure_id not in index:
            index[figure_id] = record
    return index


def group_evidence_by_figure_id(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        figure_id = record.get("figure_id")
        if not figure_id:
            continue
        grouped.setdefault(figure_id, []).append(record)
    return grouped


def collect_reference_sentences(*records: Any) -> list[str]:
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


def prioritize_sendable_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def truncate_text(text: str | None, limit: int, warning_name: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    if len(text) <= limit:
        return text, None
    return text[:limit].rstrip(), warning_name


def truncate_text_list(items: list[str], limit: int, warning_name: str) -> tuple[list[str], str | None]:
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


def build_evidence_object_context(
    evidence_group: list[dict[str, Any]],
    *,
    max_chars: int,
) -> tuple[dict[str, Any], str | None]:
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
    fact_summaries, fact_warning = truncate_text_list(fact_summaries, max_chars, "stage3_evidence_context_truncated")
    if fact_warning:
        warning = fact_warning
    remaining = max(max_chars - sum(len(item) for item in fact_summaries), 0)
    detailed_observations, detail_warning = truncate_text_list(
        detailed_observations,
        remaining if remaining > 0 else max_chars,
        "stage3_evidence_context_truncated",
    )
    if detail_warning:
        warning = detail_warning
    remaining = max(
        max_chars - sum(len(item) for item in fact_summaries) - sum(len(item) for item in detailed_observations),
        0,
    )
    linked_facts, linked_warning = truncate_text_list(
        linked_facts,
        remaining if remaining > 0 else max_chars,
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


def collect_stage3_parameter_records(payload: Any) -> list[dict[str, Any]]:
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


def find_related_stage3_parameters(
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
        if not parameter_refs_match_figure(refs, figure_id, evidence_ids):
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


def parameter_refs_match_figure(refs: list[Any], figure_id: str, evidence_ids: list[str]) -> bool:
    for ref in refs:
        text = str(ref or "")
        if not text:
            continue
        if text == figure_id or figure_id in text:
            return True
        if any(evidence_id and (text == evidence_id or evidence_id in text or text in evidence_id) for evidence_id in evidence_ids):
            return True
    return False


def estimate_context_chars(
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


def figure_metadata_for_prompt(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": candidate.get("paper_id"),
        "figure_id": candidate.get("figure_id"),
        "figure_type": candidate.get("figure_type"),
        "initial_figure_type": candidate.get("initial_figure_type"),
        "technique": candidate.get("technique"),
        "source_image_path": candidate.get("source_image_path"),
        "stage3_figure_type": candidate.get("stage3_figure_type"),
        "stage2_figure_class": candidate.get("stage2_figure_class"),
        "routing_mode": candidate.get("routing_mode"),
        "routing_reason": candidate.get("routing_reason"),
        "candidate_risk_level": candidate.get("candidate_risk_level"),
    }


def build_input_context_summary(candidate: dict[str, Any]) -> str:
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
