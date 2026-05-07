"""Candidate-constrained LLM linker for Stage 5.5."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from .models import LinkCandidate


@dataclass
class EvidenceSpectraParameterLinker:
    dry_run: bool = True
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_s: int = 120

    def run(
        self,
        candidates: list[dict[str, Any]],
        *,
        paper_context: dict[str, Any] | None = None,
        max_candidates_per_call: int = 20,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if self.dry_run:
            return [], [], []
        api_key = self.api_key or os.getenv("LINKING_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("Stage 5.5 live linking requires LINKING_API_KEY, OPENAI_API_KEY, or DASHSCOPE_API_KEY.")
        base_url = self.base_url or os.getenv("OPENAI_BASE_URL") or (
            "https://dashscope.aliyuncs.com/compatible-mode/v1" if os.getenv("DASHSCOPE_API_KEY") else None
        )
        if not base_url:
            raise RuntimeError("Stage 5.5 live linking requires OPENAI_BASE_URL or a DashScope-compatible default.")
        model_name = self.model_name or os.getenv("LINKING_MODEL_NAME") or os.getenv("MODEL_NAME") or "qwen-max"
        all_decisions: list[dict[str, Any]] = []
        raw_outputs: list[dict[str, Any]] = []
        parse_failures: list[dict[str, Any]] = []
        for start in range(0, len(candidates), max(1, max_candidates_per_call)):
            batch = candidates[start : start + max(1, max_candidates_per_call)]
            prompt = self.build_prompt(batch, paper_context)
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
            }
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout_s,
            )
            raw_payload: dict[str, Any]
            try:
                raw_payload = response.json()
            except Exception:
                raw_payload = {"raw_text": response.text}
            response_text = _coerce_response_text(raw_payload.get("choices", [{}])[0].get("message", {}).get("content")) if response.ok else response.text
            raw_outputs.append(
                {
                    "candidate_ids": [item["candidate_id"] for item in batch],
                    "model": model_name,
                    "prompt": prompt,
                    "response_status": response.status_code,
                    "response_text": response_text,
                    "response_payload": raw_payload,
                }
            )
            if response.status_code >= 400:
                parse_failures.extend(
                    {
                        "candidate_id": item["candidate_id"],
                        "reason": "llm_http_error",
                        "status_code": response.status_code,
                        "response_text": response_text,
                    }
                    for item in batch
                )
                continue
            try:
                parsed = extract_json_payload(response_text or "")
            except ValueError as exc:
                parse_failures.extend(
                    {
                        "candidate_id": item["candidate_id"],
                        "reason": "llm_parse_failed",
                        "error": str(exc),
                        "response_text": response_text,
                    }
                    for item in batch
                )
                continue
            if isinstance(parsed, dict):
                parsed = parsed.get("links") or parsed.get("decisions") or []
            if not isinstance(parsed, list):
                parse_failures.extend(
                    {
                        "candidate_id": item["candidate_id"],
                        "reason": "llm_non_list_payload",
                        "response_text": response_text,
                    }
                    for item in batch
                )
                continue
            normalized = [item for item in parsed if isinstance(item, dict)]
            all_decisions.extend(normalized)
        return all_decisions, raw_outputs, parse_failures

    def build_prompt(self, candidates: list[dict[str, Any]], paper_context: dict[str, Any] | None = None) -> str:
        paper_title = (paper_context or {}).get("title") or ""
        paper_keywords = (paper_context or {}).get("keywords") or []
        allowed_ids = [item["candidate_id"] for item in candidates]
        lines = [
            "You are reviewing linking candidates.",
            "You can only choose from the provided candidate_id values.",
            "Do not invent source_id, target_id, figure_id, parameter_id, or sample_id.",
            "If uncertain, return decision=unmatched.",
            "An empty list [] is allowed.",
            "Output JSON only.",
            "Allowed decision values: accept, reject, unmatched.",
            "Allowed link_type values: supports, weak_supports, describes, derived_from, same_figure, conflicts.",
            "Allowed confidence values: high, medium, low.",
            "Any other decision, link_type, or confidence value will be automatically rejected.",
            "Do not use synonyms such as matched, linked, evidence_to_parameter, figure_to_parameter, yes, or maybe.",
            f"Paper title: {paper_title}",
            f"Paper keywords: {json.dumps(paper_keywords, ensure_ascii=False)}",
            f"Allowed candidate_ids: {json.dumps(allowed_ids, ensure_ascii=False)}",
            'Return a JSON list. Each item must contain only: candidate_id, decision, link_type, confidence, reasoning.',
            'Valid example: [{"candidate_id":"cand-1","decision":"accept","link_type":"supports","confidence":"high","reasoning":"same figure and matching value"}]',
            "Candidates:",
        ]
        for item in candidates:
            candidate = LinkCandidate.model_validate(item)
            lines.append(
                json.dumps(
                    {
                        "candidate_id": candidate.candidate_id,
                        "source_type": candidate.source_type,
                        "source_id": candidate.source_id,
                        "source_text": candidate.source_text,
                        "source_value": candidate.source_value,
                        "source_unit": candidate.source_unit,
                        "source_figure_id": candidate.source_figure_id,
                        "target_type": candidate.target_type,
                        "target_id": candidate.target_id,
                        "target_text": candidate.target_text,
                        "target_value": candidate.target_value,
                        "target_unit": candidate.target_unit,
                        "target_figure_id": candidate.target_figure_id,
                        "candidate_reason": candidate.candidate_reason,
                        "deterministic_score": candidate.deterministic_score,
                    },
                    ensure_ascii=False,
                )
            )
        return "\n".join(lines)


def extract_json_payload(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty linking model output.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for block in fenced:
        block = block.strip()
        if not block:
            continue
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    start = min((index for index in [text.find("["), text.find("{")] if index != -1), default=-1)
    if start >= 0:
        sliced = text[start:]
        try:
            return json.loads(sliced)
        except json.JSONDecodeError:
            pass
    raise ValueError("Could not extract JSON payload from linking model output.")


def _coerce_response_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(part for part in text_parts if part) or None
    return str(content)
