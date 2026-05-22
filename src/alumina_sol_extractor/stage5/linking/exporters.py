"""File exporters for Stage 5.5 linking outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.utils.jsonl import write_jsonl


def write_json(path: Path | str, payload: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown(path: Path | str, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def export_linking_outputs(
    output_dir: Path | str,
    *,
    candidates: list[dict[str, Any]],
    accepted_links: list[dict[str, Any]],
    unmatched_candidates: list[dict[str, Any]],
    rejected_links: list[dict[str, Any]],
    raw_llm_outputs: list[dict[str, Any]],
    summary: dict[str, Any],
    report: str,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "link_candidates": str(write_jsonl(candidates, output_dir / "link_candidates.jsonl")),
        "links": str(write_jsonl(accepted_links, output_dir / "links.jsonl")),
        "unmatched_candidates": str(write_jsonl(unmatched_candidates, output_dir / "unmatched_candidates.jsonl")),
        "rejected_links": str(write_jsonl(rejected_links, output_dir / "rejected_links.jsonl")),
        "raw_llm_linking_outputs": str(write_jsonl(raw_llm_outputs, output_dir / "raw_llm_linking_outputs.jsonl")),
        "linking_summary": str(write_json(output_dir / "linking_summary.json", summary)),
        "linking_report": str(write_markdown(output_dir / "linking_report.md", report)),
    }
