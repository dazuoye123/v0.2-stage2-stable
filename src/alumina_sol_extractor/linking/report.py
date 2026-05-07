"""Markdown reporting for Stage 5.5 linking dry-run/live outputs."""

from __future__ import annotations

import json
from typing import Any


def render_linking_report(
    *,
    file_presence: dict[str, bool],
    candidates: list[dict[str, Any]],
    accepted_links: list[dict[str, Any]],
    unmatched_candidates: list[dict[str, Any]],
    rejected_links: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    high_conf = [item for item in accepted_links if item.get("confidence") == "high"][:5]
    low_conf = [item for item in accepted_links if item.get("confidence") == "low"][:5]
    recommend_live = bool(unmatched_candidates) and summary.get("rejected_links", 0) == 0 and summary.get("invalid_source_id_count", 0) == 0 and summary.get("invalid_target_id_count", 0) == 0
    lines = [
        "# Stage 5.5 Linking Report",
        "",
        "## Input Files",
        f"- {json.dumps(file_presence, ensure_ascii=False)}",
        "",
        "## Linking Counts",
        f"- total_candidates: {summary.get('total_candidates', 0)}",
        f"- deterministic_links: {summary.get('deterministic_links', 0)}",
        f"- llm_reviewed_candidates: {summary.get('llm_reviewed_candidates', 0)}",
        f"- accepted_links: {summary.get('accepted_links', 0)}",
        f"- unmatched_candidates: {summary.get('unmatched_candidates', 0)}",
        f"- rejected_links: {summary.get('rejected_links', 0)}",
        "",
        "## Deterministic Links",
    ]
    deterministic = [item for item in accepted_links if item.get("created_by") == "deterministic"]
    if deterministic:
        for item in deterministic[:10]:
            lines.append(
                f"- {item['link_id']}: {item['source_type']} {item['source_id']} -> {item['target_type']} {item['target_id']} ({item['link_type']}, {item['confidence']})"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Unmatched Candidates"])
    if unmatched_candidates:
        for item in unmatched_candidates[:10]:
            lines.append(
                f"- {item['candidate_id']}: {item['source_type']} {item['source_id']} -> {item['target_type']} {item['target_id']} reason={item.get('unmatched_reason') or item.get('reason')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Rejected Links"])
    if rejected_links:
        for item in rejected_links[:10]:
            lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
    else:
        lines.append("- none")
    lines.extend(["", "## High-confidence Examples"])
    if high_conf:
        for item in high_conf:
            lines.append(f"- {item['source_id']} -> {item['target_id']}: {item.get('reasoning')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Low-confidence Examples"])
    if low_conf:
        for item in low_conf:
            lines.append(f"- {item['source_id']} -> {item['target_id']}: {item.get('reasoning')}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Recommendation",
            f"- {'suggest_live_linking' if recommend_live else 'hold_for_manual_review'}",
            "",
        ]
    )
    return "\n".join(lines)
