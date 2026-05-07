"""Candidate-constrained LLM linker skeleton for Stage 5.5."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from .models import LinkCandidate


@dataclass
class EvidenceSpectraParameterLinker:
    dry_run: bool = True
    model_name: str | None = None

    def run(
        self,
        candidates: list[dict[str, Any]],
        *,
        paper_context: dict[str, Any] | None = None,
        max_candidates_per_call: int = 20,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if self.dry_run:
            return [], [], []
        api_key = os.getenv("LINKING_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("Stage 5.5 live linking requires LINKING_API_KEY, OPENAI_API_KEY, or DASHSCOPE_API_KEY.")
        raise NotImplementedError("Stage 5.5 live linking is intentionally deferred; use --dry-run for now.")

    def build_prompt(self, candidates: list[dict[str, Any]], paper_context: dict[str, Any] | None = None) -> str:
        paper_title = (paper_context or {}).get("title") or ""
        lines = [
            "You are reviewing linking candidates.",
            "You can only choose from the provided candidate_id values.",
            "Do not invent source_id, target_id, figure_id, parameter_id, or sample_id.",
            "If uncertain, return decision=unmatched.",
            "An empty list [] is allowed.",
            "Output JSON only.",
            f"Paper title: {paper_title}",
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
