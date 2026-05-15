"""Rule-based section parsing and scoring for Stage 3 long-document smoke tests."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


FIGURE_PATTERN = re.compile(r"(?:图|fig(?:ure)?\.?)\s*([0-9]+(?:\.[0-9]+)?)", flags=re.IGNORECASE)
TABLE_PATTERN = re.compile(r"(?:表|table|tab\.?)\s*([0-9]+(?:\.[0-9]+)?)", flags=re.IGNORECASE)

HIGH_PRIORITY_KEYWORDS = {
    "实验部分": 6,
    "实验材料": 5,
    "制备": 5,
    "合成": 5,
    "反应": 4,
    "铝溶胶": 6,
    "前驱体": 5,
    "表征": 5,
    "结果与讨论": 6,
    "可纺性": 6,
    "??????": 6,
    "??????": 5,
    "???": 5,
    "???": 5,
    "???": 4,
    "???": 5,
    "???": 4,
    "???": 4,
    "ph": 5,
    "al13": 6,
    "al30": 4,
    "nmr": 5,
    "27al": 5,
    "ferron": 5,
    "al-ferron": 6,
    "ftir": 5,
    "xrd": 5,
    "raman": 5,
    "zeta": 4,
    "?????": 4,
    "?????": 6,
    "???": 5,
    "????????": 6,
    "????????": 5,
    "?????": 6,
    "?????": 5,
}

LOW_PRIORITY_KEYWORDS = {
    "目录": -6,
    "原创性声明": -6,
    "授权声明": -6,
    "摘要": -6,
    "参考文献": -8,
    "致谢": -6,
    "绪论": -2,
    "文献综述": -4,
    "研究现状": -3,
    "???": -6,
    "????????": -6,
    "??????": -6,
    "???": -6,
    "???????": -8,
    "???": -2,
    "??????": -4,
    "??????": -3,
}



def parse_markdown_sections(markdown_text: str) -> list[dict[str, Any]]:
    """Parse cleaned markdown into a lightweight section map."""

    lines = markdown_text.splitlines()
    headings: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        heading = _parse_heading(raw_line.strip(), line_number)
        if heading:
            headings.append(heading)

    if not headings:
        return [_build_section_record("full_text", "full_text", 0, 1, len(lines), lines)]

    sections: list[dict[str, Any]] = []
    first_heading_line = headings[0]["start_line"]
    if first_heading_line > 1:
        sections.append(_build_section_record("front_matter", "Front Matter", 0, 1, first_heading_line - 1, lines))

    for index, heading in enumerate(headings):
        start_line = heading["start_line"]
        end_line = len(lines)
        for candidate in headings[index + 1 :]:
            if int(candidate["level"]) <= int(heading["level"]):
                end_line = candidate["start_line"] - 1
                break
        sections.append(
            _build_section_record(
                heading["section_id"],
                heading["title"],
                heading["level"],
                start_line,
                end_line,
                lines,
            )
        )
    return sections


def score_sections(
    sections: list[dict[str, Any]],
    *,
    custom_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Attach deterministic section scores and labels without using an LLM."""

    keyword_weights = {keyword.lower(): weight for keyword, weight in HIGH_PRIORITY_KEYWORDS.items()}
    for keyword in custom_keywords or []:
        normalized = str(keyword or "").strip().lower()
        if normalized:
            keyword_weights.setdefault(normalized, 4)

    scored: list[dict[str, Any]] = []
    for section in sections:
        title = str(section.get("title") or "")
        body = str(section.get("text") or "")
        haystack = f"{title}\n{body[:6000]}"
        normalized_haystack = haystack.lower()
        score = 0
        reasons: list[str] = []
        section_types = _infer_section_types(title, body)
        if _looks_like_title_page_section(section):
            section_types = ["metadata"]

        for keyword, weight in keyword_weights.items():
            if keyword and keyword in normalized_haystack:
                score += weight
                reasons.append(f"+{weight}:{keyword}")
        for keyword, penalty in LOW_PRIORITY_KEYWORDS.items():
            if keyword.lower() in normalized_haystack:
                score += penalty
                reasons.append(f"{penalty}:{keyword}")

        if "references" in section_types or "noise" in section_types:
            score = min(score, -5)
        if "metadata" in section_types:
            score = min(score, 1)
            reasons.append("title_page_metadata_cap")
        if "experimental_methods" in section_types:
            score += 4
            reasons.append("+4:experimental_methods")
        if "results_discussion" in section_types:
            score += 6
            reasons.append("+6:results_discussion")
        if "spectroscopy_results" in section_types:
            score += 6
            reasons.append("+6:spectroscopy_results")
        if "results_discussion" in section_types and "spectroscopy_results" in section_types:
            score += 12
            reasons.append("+12:results_discussion_with_spectroscopy")

        scored.append(
            {
                **section,
                "section_score": score,
                "section_types": section_types,
                "recommended_extractors": _recommended_extractors(section_types),
                "reason": "; ".join(reasons) if reasons else "neutral",
            }
        )
    return scored


def select_sections(
    scored_sections: list[dict[str, Any]],
    *,
    max_sections: int = 6,
) -> list[dict[str, Any]]:
    """Select the highest-value sections while preserving document order."""

    eligible = [
        section
        for section in scored_sections
        if "references" not in section.get("section_types", [])
        and "noise" not in section.get("section_types", [])
        and int(section.get("section_score") or 0) > 0
    ]
    ranked = sorted(
        eligible,
        key=lambda item: (int(item.get("section_score") or 0), -int(item.get("start_line") or 0)),
        reverse=True,
    )
    dominant_chapters = infer_selected_chapter_numbers(ranked[: max(1, min(3, len(ranked)))])
    if dominant_chapters:
        chapter_aligned = [
            section
            for section in ranked
            if not _section_chapter_numbers(section)
            or _section_chapter_numbers(section).intersection(dominant_chapters)
        ]
        if chapter_aligned:
            ranked = chapter_aligned
    ranked = ranked[: max(1, max_sections)]
    selected_ids = {item["section_id"] for item in ranked}
    return [section for section in scored_sections if section["section_id"] in selected_ids]


def build_selected_sections_markdown(selected_sections: list[dict[str, Any]]) -> str:
    """Join selected sections into the markdown text sent to Stage 3."""

    ordered = sorted(selected_sections, key=lambda item: int(item.get("start_line") or 0))
    blocks = [str(section.get("text") or "").strip() for section in ordered if str(section.get("text") or "").strip()]
    return "\n\n".join(blocks).strip()


def infer_selected_chapter_numbers(selected_sections: list[dict[str, Any]]) -> set[str]:
    """Infer dominant chapter numbers from selected section titles and mentions."""

    chapter_numbers: Counter[str] = Counter()
    for section in selected_sections:
        title = str(section.get("title") or "")
        chapter_match = re.search(r"第([一二三四五六七八九十0-9]+)章", title)
        if chapter_match:
            chapter_numbers[_normalize_chapter_token(chapter_match.group(1))] += 2
        for token in re.findall(r"\b(\d+)(?:\.\d+)*\b", title):
            chapter_numbers[token] += 1
        for mention in list(section.get("figure_mentions") or []) + list(section.get("table_mentions") or []):
            match = re.search(r"(\d+)(?:\.\d+)?", str(mention))
            if match:
                chapter_numbers[match.group(1)] += 1
    if not chapter_numbers:
        return set()
    max_count = max(chapter_numbers.values())
    return {key for key, value in chapter_numbers.items() if value == max_count or value >= max_count - 1}


def _build_section_record(
    section_id: str,
    title: str,
    level: int,
    start_line: int,
    end_line: int,
    lines: list[str],
) -> dict[str, Any]:
    text_lines = lines[start_line - 1 : end_line]
    text = "\n".join(text_lines).strip()
    return {
        "section_id": section_id,
        "title": title,
        "level": level,
        "start_line": start_line,
        "end_line": end_line,
        "char_count": len(text),
        "text_preview": text[:240],
        "text": text,
        "figure_mentions": _extract_mentions(text, FIGURE_PATTERN, prefix="图"),
        "table_mentions": _extract_mentions(text, TABLE_PATTERN, prefix="表"),
    }


def _parse_heading(line: str, line_number: int) -> dict[str, Any] | None:
    if not line:
        return None
    if line.startswith("#"):
        level = len(line) - len(line.lstrip("#"))
        title = line.lstrip("#").strip()
        if not title:
            return None
        return {
            "section_id": _make_section_id(title, line_number),
            "title": title,
            "level": level,
            "start_line": line_number,
        }

    normalized = line.strip()
    if normalized in {"摘要", "ABSTRACT", "Abstract", "结论", "Conclusion", "参考文献", "References", "致谢"}:
        return {
            "section_id": _make_section_id(normalized, line_number),
            "title": normalized,
            "level": 1,
            "start_line": line_number,
        }

    if re.match(r"^第[一二三四五六七八九十0-9]+章(?:\s+.*)?$", normalized) or re.match(
        r"^[0-9]+(?:\.[0-9]+)+(?:\s+.+)?$",
        normalized,
    ):
        token = normalized.split()[0]
        level = 1 if token.startswith("第") else min(4, token.count(".") + 1)
        return {
            "section_id": _make_section_id(normalized, line_number),
            "title": normalized,
            "level": level,
            "start_line": line_number,
        }
    return None


def _make_section_id(title: str, line_number: int) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", title).strip("_").lower() or f"section_{line_number}"
    return f"{slug}_{line_number}"


def _extract_mentions(text: str, pattern: re.Pattern[str], *, prefix: str) -> list[str]:
    mentions: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        token = match.group(1)
        mention = f"{prefix}{token}"
        if mention not in seen:
            seen.add(mention)
            mentions.append(mention)
    return mentions


def _infer_section_types(title: str, text: str) -> list[str]:
    lowered_title = title.lower()
    lowered_text = text.lower()
    section_types: list[str] = []

    if any(token in lowered_title for token in ["参考文献", "references"]):
        return ["references"]
    if any(token in lowered_title for token in ["目录", "声明", "致谢"]):
        return ["noise"]
    if any(token in lowered_title for token in ["摘要", "abstract"]):
        section_types.append("abstract")
    if any(token in lowered_title for token in ["实验", "experimental", "materials and methods", "methods"]):
        section_types.append("experimental_methods")
    if any(token in lowered_title for token in ["制备", "合成", "synthesis"]):
        section_types.append("synthesis_conditions")
    if any(token in lowered_title for token in ["结果", "讨论", "results", "discussion"]):
        section_types.append("results_discussion")
    if any(token in lowered_title for token in ["结论", "小结", "conclusion"]):
        section_types.append("conclusion")
    if any(token in lowered_title for token in ["绪论", "背景", "introduction"]):
        section_types.append("background")

    spectroscopy_tokens = ["nmr", "27al", "ftir", "xrd", "raman", "ferron", "al-ferron"]
    if any(token in lowered_text for token in spectroscopy_tokens):
        section_types.append("spectroscopy_results")
    if any(token in lowered_text for token in ["tem", "sem", "zeta", "固含量", "可纺性", "spinnability", "表征"]):
        section_types.append("characterization_methods")

    if not section_types:
        section_types.append("metadata" if "front matter" in lowered_title else "background")
    return list(dict.fromkeys(section_types))


def _recommended_extractors(section_types: list[str]) -> list[str]:
    mapping = {
        "abstract": ["paper_basic_info", "global_constants"],
        "experimental_methods": ["global_constants", "experiment_series", "data_points"],
        "synthesis_conditions": ["global_constants", "experiment_series", "data_points"],
        "results_discussion": ["experiment_series", "data_points", "evidence_objects"],
        "spectroscopy_results": ["data_points", "evidence_objects"],
        "characterization_methods": ["global_constants", "evidence_objects"],
        "conclusion": ["global_constants"],
    }
    extractors: list[str] = []
    for section_type in section_types:
        for extractor in mapping.get(section_type, []):
            if extractor not in extractors:
                extractors.append(extractor)
    return extractors


def _normalize_chapter_token(token: str) -> str:
    chinese_to_digit = {
        "一": "1",
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "七": "7",
        "八": "8",
        "九": "9",
        "十": "10",
    }
    return chinese_to_digit.get(token, token)


def _section_chapter_numbers(section: dict[str, Any]) -> set[str]:
    title = str(section.get("title") or "")
    numbers: set[str] = set()
    chapter_match = re.search(r"第([一二三四五六七八九十0-9]+)章", title)
    if chapter_match:
        numbers.add(_normalize_chapter_token(chapter_match.group(1)))
    for token in re.findall(r"\b(\d+)(?:\.\d+)*\b", title):
        numbers.add(token)
    return numbers


def _looks_like_title_page_section(section: dict[str, Any]) -> bool:
    title = str(section.get("title") or "")
    if int(section.get("start_line") or 0) > 2:
        return False
    normalized = title.lower()
    if title.startswith("第") or re.match(r"^[0-9]+(?:\.[0-9]+)+", title):
        return False
    if any(token in normalized for token in ["摘要", "abstract", "introduction", "绪论", "参考文献"]):
        return False
    return True
