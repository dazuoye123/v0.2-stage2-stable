"""Defensive JSON parsing helpers for model outputs."""

from __future__ import annotations

import json
import re


def extract_json_from_markdown(text: str) -> str:
    """Extract JSON content from fenced markdown if present."""
    if not text:
        return ""
    fenced = re.search(r"```json\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    generic = re.search(r"```\s*(.*?)```", text, flags=re.DOTALL)
    if generic:
        return generic.group(1).strip()
    start_candidates = [pos for pos in (text.find("{"), text.find("[")) if pos != -1]
    if start_candidates:
        start = min(start_candidates)
        end = max(text.rfind("}"), text.rfind("]"))
        if end >= start:
            return text[start : end + 1].strip()
    return text.strip()


def try_repair_json(text: str) -> str:
    """Apply a few conservative repairs to near-JSON text."""
    candidate = extract_json_from_markdown(text)
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    candidate = candidate.replace("\u201c", '"').replace("\u201d", '"')
    candidate = candidate.replace("\u2018", "'").replace("\u2019", "'")
    return candidate.strip()


def safe_json_loads(text: str) -> tuple[object | None, str | None]:
    """Parse JSON safely, attempting one conservative repair pass."""
    candidate = extract_json_from_markdown(text)
    try:
        return json.loads(candidate), None
    except json.JSONDecodeError:
        repaired = try_repair_json(candidate)
        try:
            return json.loads(repaired), None
        except json.JSONDecodeError as exc:
            return None, str(exc)
