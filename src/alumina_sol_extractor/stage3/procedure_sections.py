"""Procedure-section selection for Stage 3 process-step extraction."""

from __future__ import annotations

import re
from typing import Any

from .sections import parse_markdown_sections


PRIMARY_PROCEDURE_KEYWORDS = (
    "\u521d\u59cb\u94dd\u6eb6\u80f6\u7684\u5236\u5907",
    "\u94dd\u6eb6\u80f6\u7684\u5236\u5907",
    "\u524d\u9a71\u4f53\u7684\u5236\u5907",
    "\u6837\u54c1\u5236\u5907",
    "\u5236\u5907\u8fc7\u7a0b",
    "\u5b9e\u9a8c\u65b9\u6cd5",
    "\u5b9e\u9a8c\u65b9\u6cd5\u4e0e\u6b65\u9aa4",
    "\u5de5\u827a\u6d41\u7a0b",
    "\u6eb6\u80f6\u5236\u5907",
    "\u51dd\u80f6\u5236\u5907",
    "\u7eba\u4e1d\u6db2\u5236\u5907",
    "\u7535\u7eba",
    "\u9759\u7535\u7eba\u4e1d",
    "\u70ed\u5904\u7406",
    "\u7145\u70e7",
    "experimental",
    "experimental procedure",
    "experimental details",
    "materials and methods",
    "materials and method",
    "synthesis",
    "sample preparation",
    "electrospinning",
    "calcination",
    "heat treatment",
    "\u6eb6\u80f6\u7684\u5236\u5907",
    "\u53ef\u7eba\u6027\u6eb6\u80f6\u7684\u5236\u5907",
    "鍒濆閾濇憾鑳剁殑鍒跺",
    "閾濇憾鑳剁殑鍒跺",
    "鍓嶉┍浣撶殑鍒跺",
    "鏍峰搧鍒跺",
    "鍒跺杩囩▼",
)

EXPERIMENT_ANCHOR_KEYWORDS = (
    "\u5b9e\u9a8c\u90e8\u5206",
    "\u5b9e\u9a8c\u6750\u6599\u4e0e\u65b9\u6cd5",
    "\u5b9e\u9a8c\u6750\u6599\u53ca\u4eea\u5668",
    "\u5b9e\u9a8c\u539f\u6599",
    "\u5b9e\u9a8c\u8bd5\u5242",
    "\u5b9e\u9a8c\u8fc7\u7a0b",
    "\u6837\u54c1\u5236\u5907",
    "\u5236\u5907\u65b9\u6cd5",
    "\u8868\u5f81\u65b9\u6cd5",
    "鐎圭偤鐛欓柈銊ュ瀻",
    "鐎圭偤鐛欓弶鎰灐娑撳孩鏌熷▔",
    "鐎圭偤鐛欓弶鎰灐閸欏﹣鍗庨崳",
    "鐎圭偤鐛欓弬瑙勭《",
)

SECONDARY_PROCEDURE_KEYWORDS = (
    "\u7eba\u4e1d",
    "\u70ed\u5904\u7406",
    "\u7145\u70e7",
    "\u52a0\u6599",
    "\u914d\u5236",
    "\u6eb6\u89e3",
    "\u53cd\u5e94",
    "闂堟瑧鏁哥痪杞扮",
    "閻撳懐鍎?",
    "缁捐桨绗?",
)

LOW_PRIORITY_KEYWORDS = (
    "\u76ee\u5f55",
    "\u6458\u8981",
    "abstract",
    "\u7eea\u8bba",
    "\u6587\u732e\u7efc\u8ff0",
    "\u7814\u7a76\u73b0\u72b6",
    "\u7ed3\u679c\u4e0e\u8ba8\u8bba",
    "\u7ed3\u679c",
    "\u8ba8\u8bba",
    "\u6027\u80fd\u7814\u7a76",
    "\u673a\u7406\u7814\u7a76",
    "\u7814\u7a76\u610f\u4e49",
    "\u5c0f\u7ed3",
    "results and discussion",
    "results",
    "discussion",
    "conclusion",
    "summary",
    "research progress",
    "review",
    "\u7406\u8bba\u57fa\u7840",
    "\u53c2\u8003\u6587\u732e",
    "\u81f4\u8c22",
    "\u4f5c\u8005\u7b80\u4ecb",
    "鐩綍",
    "鎽樿",
    "缁",
    "鍙傝€冩枃鐚?",
    "鑷磋阿",
    "浣滆€呯畝浠?",
)

ACTION_HINTS = (
    "\u79f0\u53d6",
    "\u52a0\u5165",
    "\u6ef4\u52a0",
    "\u6405\u62cc",
    "\u52a0\u70ed",
    "\u5347\u6e29",
    "\u4fdd\u6e29",
    "\u51b7\u5374",
    "\u8fc7\u6ee4",
    "\u6d17\u6da4",
    "\u5e72\u71e5",
    "\u7145\u70e7",
    "\u7814\u78e8",
    "\u6eb6\u89e3",
    "\u914d\u5236",
    "\u6ce8\u5165",
    "\u7eba\u4e1d",
    "\u6536\u96c6",
    "绉板彇",
    "鍔犲叆",
    "鎼呮媽",
    "鍔犵儹",
    "鍗囨俯",
    "淇濇俯",
    "鍐峰嵈",
    "杩囨护",
    "娲楁钉",
    "骞茬嚗",
)


def select_procedure_sections(
    markdown_text: str,
    *,
    max_chars: int = 12000,
) -> tuple[list[dict[str, Any]], str]:
    sections = parse_markdown_sections(markdown_text)
    scored: list[dict[str, Any]] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        text = str(section.get("text") or "")
        score, reason = _score_procedure_section(title, text)
        scored.append(
            {
                "section_id": section.get("section_id"),
                "title": title,
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "score": score,
                "reason": reason,
                "char_count": len(text),
                "selected_for_process_steps": False,
                "text_preview": text[:160],
                "numeric_prefix": _extract_numeric_prefix(title),
                "text": text,
            }
        )

    anchor_prefixes = {
        prefix
        for item in scored
        for prefix in [_procedure_anchor_prefix(item)]
        if prefix
    }
    explicit_under_anchor = [
        item
        for item in scored
        if int(item["score"]) > 0 and _is_explicit_procedure_title(item) and _is_under_anchor(item, anchor_prefixes)
    ]
    if anchor_prefixes:
        preferred = explicit_under_anchor or [
            item
            for item in scored
            if int(item["score"]) > 0 and _is_under_anchor(item, anchor_prefixes)
        ]
    else:
        preferred = [item for item in scored if int(item["score"]) > 0 and _is_explicit_procedure_title(item)]
    positive = preferred or [item for item in scored if int(item["score"]) > 0]
    if anchor_prefixes:
        positive = [
            item
            for item in positive
            if _is_under_anchor(item, anchor_prefixes)
            or not _looks_like_chapter_one_review_title(_normalize(str(item.get("title") or "")))
        ]
    positive.sort(
        key=lambda item: (
            0 if _is_explicit_procedure_title(item) else 1,
            -int(item.get("score") or 0),
            int(item.get("start_line") or 0),
        )
    )

    selected: list[dict[str, Any]] = []
    total_chars = 0
    for item in positive:
        text = str(item.get("text") or "")
        text_len = len(text)
        if selected and total_chars + text_len > max_chars:
            continue
        selected_item = dict(item)
        selected_item["selected_for_process_steps"] = True
        selected.append(selected_item)
        total_chars += text_len
        if total_chars >= max_chars:
            break

    if anchor_prefixes and any(_is_under_anchor(item, anchor_prefixes) for item in selected):
        selected = [
            item
            for item in selected
            if _is_under_anchor(item, anchor_prefixes)
            or not _looks_like_chapter_one_review_title(_normalize(str(item.get("title") or "")))
        ]

    selected_ids = {item.get("section_id") for item in selected}
    for item in scored:
        if item.get("section_id") in selected_ids:
            item["selected_for_process_steps"] = True

    selected_text = "\n\n".join(
        str(item.get("text") or "").strip()
        for item in selected
        if str(item.get("text") or "").strip()
    ).strip()
    for item in scored:
        item.pop("text", None)
    for item in selected:
        item.pop("text", None)
    return scored, selected_text


def _score_procedure_section(title: str, text: str) -> tuple[int, str]:
    normalized_title = _normalize(title)
    normalized_text = _normalize(text)
    if not normalized_title and not normalized_text:
        return 0, "empty_section"
    if _looks_like_toc_heading(title):
        return -10, "toc_like_heading"
    if any(keyword in normalized_title for keyword in LOW_PRIORITY_KEYWORDS):
        return -5, "low_priority_section"
    if _looks_like_chapter_one_review_title(normalized_title):
        return -4, "chapter_one_review_section"
    for keyword in PRIMARY_PROCEDURE_KEYWORDS:
        if keyword in normalized_title:
            return 10, f"primary_title_keyword:{keyword}"
    for keyword in EXPERIMENT_ANCHOR_KEYWORDS:
        if keyword in normalized_title:
            return 9, f"experiment_anchor_keyword:{keyword}"
    for keyword in SECONDARY_PROCEDURE_KEYWORDS:
        if keyword in normalized_title:
            return 7, f"secondary_title_keyword:{keyword}"

    action_hits = sum(1 for verb in ACTION_HINTS if verb in normalized_text)
    if action_hits >= 3 and any(
        keyword in normalized_text
        for keyword in PRIMARY_PROCEDURE_KEYWORDS + SECONDARY_PROCEDURE_KEYWORDS + EXPERIMENT_ANCHOR_KEYWORDS
    ):
        return 5, "action_dense_section"
    if action_hits >= 1 and any(
        keyword in normalized_text
        for keyword in PRIMARY_PROCEDURE_KEYWORDS + SECONDARY_PROCEDURE_KEYWORDS + EXPERIMENT_ANCHOR_KEYWORDS
    ):
        return 4, "procedure_text_keyword"
    return 0, "not_selected"


def _normalize(text: str) -> str:
    return str(text or "").replace(" ", "").replace("\t", "").strip().lower()


def _extract_numeric_prefix(title: str) -> str | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", str(title or "").strip())
    return match.group(1) if match else None


def _procedure_anchor_prefix(item: dict[str, Any]) -> str | None:
    normalized_title = _normalize(str(item.get("title") or ""))
    if not any(keyword in normalized_title for keyword in EXPERIMENT_ANCHOR_KEYWORDS):
        return None
    prefix = str(item.get("numeric_prefix") or "")
    return prefix or None


def _is_under_anchor(item: dict[str, Any], anchor_prefixes: set[str]) -> bool:
    prefix = str(item.get("numeric_prefix") or "")
    if not prefix:
        return False
    return any(prefix == anchor or prefix.startswith(f"{anchor}.") for anchor in anchor_prefixes)


def _is_explicit_procedure_title(item: dict[str, Any]) -> bool:
    normalized_title = _normalize(str(item.get("title") or ""))
    if _looks_like_chapter_one_review_title(normalized_title):
        return False
    return any(keyword in normalized_title for keyword in PRIMARY_PROCEDURE_KEYWORDS)


def _looks_like_toc_heading(title: str) -> bool:
    stripped = str(title or "").strip()
    if not stripped:
        return False
    return "....." in stripped or "……" in stripped or "... " in stripped


def _looks_like_chapter_one_review_title(normalized_title: str) -> bool:
    if not normalized_title.startswith(("1.", "1.1", "1.2", "1.3", "\u7b2c\u4e00\u7ae0", "绗竴绔?")):
        return False
    if any(keyword in normalized_title for keyword in EXPERIMENT_ANCHOR_KEYWORDS + PRIMARY_PROCEDURE_KEYWORDS):
        return False
    return any(
        keyword in normalized_title
        for keyword in ("\u5236\u5907\u65b9\u6cd5", "\u7814\u7a76\u73b0\u72b6", "\u6587\u732e\u7efc\u8ff0", "review", "鏂囩尞", "鐮旂┒鐜扮姸")
    )
