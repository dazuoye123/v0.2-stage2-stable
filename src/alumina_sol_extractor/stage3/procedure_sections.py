"""Procedure-section selection for Stage 3 process-step extraction."""

from __future__ import annotations

import re
from typing import Any

from .sections import parse_markdown_sections


CHINESE_PRIMARY_TITLES = (
    "实验部分",
    "实验材料",
    "实验方法",
    "实验过程",
    "制备方法",
    "制备过程",
    "样品制备",
    "溶胶制备",
    "前驱体制备",
    "纺丝",
    "静电纺丝",
    "干法纺丝",
    "热处理",
    "煅烧",
    "预烧结",
    "烧结",
    "测试与表征",
)

ENGLISH_PRIMARY_TITLES = (
    "experimental",
    "experimental section",
    "materials and methods",
    "materials",
    "methods",
    "synthesis",
    "preparation",
    "sample preparation",
    "sol preparation",
    "precursor preparation",
    "electrospinning",
    "spinning",
    "calcination",
    "heat treatment",
    "sintering",
    "characterization",
)

PRIMARY_PROCEDURE_KEYWORDS = CHINESE_PRIMARY_TITLES + ENGLISH_PRIMARY_TITLES

EXPERIMENT_ANCHOR_KEYWORDS = (
    "实验部分",
    "实验材料与方法",
    "实验材料及方法",
    "实验原料",
    "实验试剂",
    "实验过程",
    "实验方法",
    "样品制备",
    "制备方法",
    "表征方法",
    "experimental",
    "materials and methods",
    "methods",
    "preparation",
    "synthesis",
    "characterization",
)

SECONDARY_PROCEDURE_KEYWORDS = (
    "配制",
    "溶解",
    "混合",
    "搅拌",
    "滴加",
    "过滤",
    "洗涤",
    "老化",
    "陈化",
    "水解",
    "缩聚",
    "升温",
    "保温",
    "冷却",
    "浸渍",
    "负载",
    "electrospinning",
    "calcination",
    "heat treatment",
    "sintering",
    "drying",
)

LOW_PRIORITY_KEYWORDS = (
    "目录",
    "摘要",
    "绪论",
    "研究背景",
    "研究意义",
    "文献综述",
    "研究进展",
    "小结",
    "总结",
    "结论",
    "参考文献",
    "致谢",
    "作者简介",
    "abstract",
    "introduction",
    "background",
    "literature review",
    "conclusion",
    "conclusions",
    "summary",
    "review",
    "research progress",
    "references",
    "acknowledgement",
    "acknowledgments",
)

RESULTS_DISCUSSION_KEYWORDS = (
    "结果与讨论",
    "结果",
    "讨论",
    "results and discussion",
    "results",
    "discussion",
)

ACTION_HINTS = (
    "称取",
    "加入",
    "滴加",
    "溶解",
    "混合",
    "搅拌",
    "陈化",
    "老化",
    "水解",
    "缩聚",
    "调节pH",
    "过滤",
    "洗涤",
    "干燥",
    "纺丝",
    "静电纺丝",
    "干法纺丝",
    "离心甩丝",
    "预烧结",
    "煅烧",
    "升温",
    "保温",
    "烧结",
    "冷却",
    "浸渍",
    "负载",
    "还原",
    "weigh",
    "add",
    "dropwise add",
    "dissolve",
    "mix",
    "stir",
    "age",
    "hydrolyze",
    "reflux",
    "filter",
    "wash",
    "dry",
    "prepare",
    "synthesize",
    "spin",
    "electrospin",
    "calcine",
    "heat",
    "heat treat",
    "sinter",
    "cool",
    "impregnate",
    "load",
    "reduce",
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
                "text_preview": text[:240],
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
        if _raw_title_looks_like_chapter_one_review(str(item.get("title") or "")):
            continue
        if not text.strip():
            continue
        text_len = len(text)
        if selected and total_chars + text_len > max_chars:
            continue
        selected_item = dict(item)
        selected_item["selected_for_process_steps"] = True
        selected.append(selected_item)
        total_chars += text_len
        if total_chars >= max_chars:
            break

    supplemental_candidates = [
        item
        for item in scored
        if item not in selected
        and not _looks_like_chapter_one_review_title(_normalize(str(item.get("title") or "")))
        and _looks_like_procedure_title(_normalize(str(item.get("title") or "")))
        and _section_text_has_action_signals(str(item.get("text") or ""))
    ]
    supplemental_candidates.sort(key=lambda item: (int(item.get("start_line") or 0), -int(item.get("score") or 0)))
    for item in supplemental_candidates:
        text = str(item.get("text") or "")
        text_len = len(text)
        if text_len <= 0 or total_chars + text_len > max_chars:
            continue
        selected_item = dict(item)
        selected_item["selected_for_process_steps"] = True
        selected.append(selected_item)
        total_chars += text_len

    selected = [
        item
        for item in selected
        if not _raw_title_looks_like_chapter_one_review(str(item.get("title") or ""))
    ]

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
        return -6, "low_priority_section"
    if _looks_like_chapter_one_review_title(normalized_title):
        return -5, "chapter_one_review_section"
    for keyword in PRIMARY_PROCEDURE_KEYWORDS:
        if keyword in normalized_title:
            return 12, f"primary_title_keyword:{keyword}"
    for keyword in EXPERIMENT_ANCHOR_KEYWORDS:
        if keyword in normalized_title:
            return 10, f"experiment_anchor_keyword:{keyword}"
    for keyword in SECONDARY_PROCEDURE_KEYWORDS:
        if keyword in normalized_title:
            return 8, f"secondary_title_keyword:{keyword}"
    if _looks_like_procedure_title(normalized_title):
        return 8, "procedure_like_title"

    action_hits = sum(1 for verb in ACTION_HINTS if verb in normalized_text)
    if any(keyword in normalized_title for keyword in RESULTS_DISCUSSION_KEYWORDS):
        if action_hits >= 4:
            return 3, "results_section_with_dense_actions"
        return -1, "results_discussion_deprioritized"

    if action_hits >= 4 and any(
        keyword in normalized_text
        for keyword in PRIMARY_PROCEDURE_KEYWORDS + SECONDARY_PROCEDURE_KEYWORDS + EXPERIMENT_ANCHOR_KEYWORDS
    ):
        return 6, "action_dense_section"
    if action_hits >= 2 and any(
        keyword in normalized_text
        for keyword in PRIMARY_PROCEDURE_KEYWORDS + SECONDARY_PROCEDURE_KEYWORDS + EXPERIMENT_ANCHOR_KEYWORDS
    ):
        return 5, "procedure_text_keyword"
    if action_hits >= 2 and any(token in normalized_text for token in ("temperature", "℃", "°c", "h", "min", "rpm", "kv", "保温", "升温", "搅拌", "加入", "称取")):
        return 4, "action_condition_dense_section"
    return 0, "not_selected"


def _normalize(text: str) -> str:
    return str(text or "").replace(" ", "").replace("\t", "").strip().lower()


def _extract_numeric_prefix(title: str) -> str | None:
    match = re.match(r"^\s*(?:第\s*)?(\d+(?:\.\d+)*)", str(title or "").strip())
    return match.group(1) if match else None


def _procedure_anchor_prefix(item: dict[str, Any]) -> str | None:
    normalized_title = _normalize(str(item.get("title") or ""))
    if not any(keyword in normalized_title for keyword in EXPERIMENT_ANCHOR_KEYWORDS):
        return None
    prefix = str(item.get("numeric_prefix") or "")
    return prefix or None


def _is_under_anchor(item: dict[str, Any], anchor_prefixes: set[str]) -> bool:
    if not anchor_prefixes:
        return False
    prefix = str(item.get("numeric_prefix") or "")
    if not prefix:
        return False
    return any(prefix == anchor or prefix.startswith(f"{anchor}.") for anchor in anchor_prefixes)


def _is_explicit_procedure_title(item: dict[str, Any]) -> bool:
    normalized_title = _normalize(str(item.get("title") or ""))
    if _looks_like_chapter_one_review_title(normalized_title):
        return False
    return any(keyword in normalized_title for keyword in PRIMARY_PROCEDURE_KEYWORDS + EXPERIMENT_ANCHOR_KEYWORDS) or _looks_like_procedure_title(normalized_title)


def _looks_like_toc_heading(title: str) -> bool:
    stripped = str(title or "").strip()
    if not stripped:
        return False
    return "....." in stripped or "... " in stripped


def _looks_like_chapter_one_review_title(normalized_title: str) -> bool:
    if not normalized_title.startswith(("1", "第一章", "chapter1")):
        return False
    if any(keyword in normalized_title for keyword in EXPERIMENT_ANCHOR_KEYWORDS):
        return False
    return any(
        keyword in normalized_title
        for keyword in ("研究现状", "文献综述", "review", "researchprogress", "绪论", "背景", "introduction")
    ) or "制备方法" in normalized_title


def _looks_like_procedure_title(normalized_title: str) -> bool:
    title = normalized_title.lower()
    fuzzy_markers = (
        "制备",
        "热处理",
        "煅烧",
        "烧结",
        "电纺",
        "纺丝",
        "表征",
        "材料与方法",
        "实验过程",
        "实验方法",
        "experimental",
        "materialsandmethods",
        "samplepreparation",
        "electrospinning",
        "heattreatment",
        "calcination",
        "characterization",
    )
    return any(marker in title for marker in fuzzy_markers)


def _section_text_has_action_signals(text: str) -> bool:
    normalized_text = _normalize(text)
    action_hits = sum(1 for verb in ACTION_HINTS if verb in normalized_text)
    return action_hits >= 2


def _raw_title_looks_like_chapter_one_review(title: str) -> bool:
    stripped = str(title or "").strip().lower()
    if not re.match(r"^(?:1(?:\.\d+)*|第一章|chapter\s*1)", stripped):
        return False
    if any(token in stripped for token in ("实验", "experimental", "materials and methods", "methods")):
        return False
    return any(token in stripped for token in ("制备方法", "研究进展", "文献综述", "绪论", "introduction", "review"))
