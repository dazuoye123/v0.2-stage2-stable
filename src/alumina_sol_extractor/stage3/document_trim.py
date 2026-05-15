"""Stage 3 body-text trimming for thesis-like markdown documents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sections import parse_markdown_sections


FRONT_MATTER_PATTERNS = (
    "\u76ee\u5f55",
    "\u6458\u8981",
    "abstract",
    "\u539f\u521b\u6027\u58f0\u660e",
    "\u6388\u6743\u58f0\u660e",
    "\u7248\u6743\u58f0\u660e",
    "\u7b26\u53f7\u8bf4\u660e",
    "\u56fe\u76ee\u5f55",
    "\u8868\u76ee\u5f55",
    "\u4f5c\u8005\u7b80\u4ecb",
    "\u653b\u8bfb\u5b66\u4f4d\u671f\u95f4",
    "\u5b66\u4f4d\u8bba\u6587",
    "鐩綍",
    "鎽樿",
    "鍘熷垱鎬у０鏄?",
    "鎺堟潈澹版槑",
    "鐗堟潈澹版槑",
    "绗﹀彿璇存槑",
    "鍥剧洰褰?",
    "琛ㄧ洰褰?",
    "浣滆€呯畝浠?",
    "鏀昏瀛︿綅鏈熼棿",
    "瀛︿綅璁烘枃",
)

BACK_MATTER_PATTERNS = (
    "\u53c2\u8003\u6587\u732e",
    "references",
    "\u9644\u5f55",
    "appendix",
    "\u81f4\u8c22",
    "\u4f5c\u8005\u7b80\u4ecb",
    "\u653b\u8bfb\u5b66\u4f4d\u671f\u95f4",
    "鍙傝€冩枃鐚?",
    "闄勫綍",
    "鑷磋阿",
    "浣滆€呯畝浠?",
    "鏀昏瀛︿綅鏈熼棿",
)

BODY_SECTION_HINTS = (
    "\u5b9e\u9a8c",
    "\u5236\u5907",
    "\u8868\u5f81",
    "\u7ed3\u679c\u4e0e\u8ba8\u8bba",
    "\u7ed3\u679c\u5206\u6790",
    "\u6d4b\u8bd5",
    "\u7eba\u4e1d",
    "\u7145\u70e7",
    "\u70ed\u5904\u7406",
    "nmr",
    "ftir",
    "xrd",
    "sem",
    "tem",
    "ferron",
    "raman",
    "\u7ed3\u8bba",
    "瀹為獙",
    "鍒跺",
    "琛ㄥ緛",
    "缁撴灉涓庤璁?",
    "缁撴灉鍒嗘瀽",
    "娴嬭瘯",
    "绾轰笣",
    "鐓呯儳",
    "鐑鐞?",
    "缁撹",
)

TOC_DOT_PATTERN = re.compile(r"(?:\.{3,}|·{3,}|…{2,}|\. ?\. ?\.)")
TOC_PAGE_PATTERN = re.compile(r"(?:\.{3,}|·{3,}|…{2,}|\s)\d+\s*$")


@dataclass
class TrimResult:
    cleaned_text: str
    report: dict[str, Any]


def generate_cleaned_body_markdown(
    *,
    markdown_path: Path | str,
    paper_output_dir: Path | str,
) -> TrimResult:
    markdown_path = Path(markdown_path)
    paper_output_dir = Path(paper_output_dir)
    stage3_text_dir = paper_output_dir / "stage3_text"
    stage3_text_dir.mkdir(parents=True, exist_ok=True)

    raw_text = markdown_path.read_text(encoding="utf-8")
    trimmed = trim_markdown_body(raw_text, input_markdown_path=markdown_path)

    cleaned_body_path = stage3_text_dir / "cleaned_body.md"
    report_path = stage3_text_dir / "markdown_trim_report.json"
    trimmed.report["output_cleaned_body_path"] = str(cleaned_body_path)
    cleaned_body_path.write_text(trimmed.cleaned_text, encoding="utf-8")
    report_path.write_text(json.dumps(trimmed.report, ensure_ascii=False, indent=2), encoding="utf-8")
    return trimmed


def trim_markdown_body(markdown_text: str, *, input_markdown_path: Path | str | None = None) -> TrimResult:
    sections = parse_markdown_sections(markdown_text)
    total_line_count = len(markdown_text.splitlines())
    if not sections:
        cleaned_text = markdown_text.strip()
        report = {
            "input_markdown_path": str(input_markdown_path) if input_markdown_path else None,
            "output_cleaned_body_path": None,
            "original_char_count": len(markdown_text),
            "cleaned_body_char_count": len(cleaned_text),
            "removed_sections": [],
            "kept_sections": [],
            "cut_start_line": 1,
            "cut_end_line": total_line_count,
            "reason": "parse_markdown_sections_empty_fallback_to_original",
            "warnings": ["parse_markdown_sections_returned_empty"],
        }
        return TrimResult(cleaned_text=cleaned_text, report=report)

    kept_sections: list[dict[str, Any]] = []
    removed_sections: list[dict[str, Any]] = []
    warnings: list[str] = []

    back_matter_hit = False
    for section in sections:
        title = str(section.get("title") or "").strip()
        text = str(section.get("text") or "")
        start_line = int(section.get("start_line") or 1)
        decision, reason = _classify_section(
            title,
            text,
            start_line=start_line,
            total_line_count=total_line_count,
        )
        record = {
            "section_id": section.get("section_id"),
            "title": title,
            "start_line": start_line,
            "end_line": section.get("end_line"),
            "reason": reason,
        }
        if back_matter_hit:
            record["reason"] = "after_back_matter_marker"
            removed_sections.append(record)
            continue
        if decision == "back_matter":
            back_matter_hit = True
            removed_sections.append(record)
            continue
        if decision == "remove":
            removed_sections.append(record)
            continue
        kept_sections.append(section)

    if not kept_sections:
        warnings.append("no_trimmed_body_sections_kept_fallback_to_original")
        cleaned_text = markdown_text.strip()
        kept_titles: list[str] = []
        cut_start_line = 1
        cut_end_line = total_line_count
    else:
        cleaned_parts = [str(section.get("text") or "").strip() for section in kept_sections]
        cleaned_text = "\n\n".join(part for part in cleaned_parts if part).strip()
        kept_titles = [str(section.get("title") or "") for section in kept_sections if section.get("title")]
        cut_start_line = int(kept_sections[0].get("start_line") or 1)
        cut_end_line = int(kept_sections[-1].get("end_line") or total_line_count)

    report = {
        "input_markdown_path": str(input_markdown_path) if input_markdown_path else None,
        "output_cleaned_body_path": None,
        "original_char_count": len(markdown_text),
        "cleaned_body_char_count": len(cleaned_text),
        "removed_sections": removed_sections,
        "kept_sections": kept_titles,
        "cut_start_line": cut_start_line,
        "cut_end_line": cut_end_line,
        "reason": "trim_obvious_front_matter_and_back_matter_only",
        "warnings": warnings,
    }
    return TrimResult(cleaned_text=cleaned_text, report=report)


def _classify_section(
    title: str,
    text: str,
    *,
    start_line: int,
    total_line_count: int,
) -> tuple[str, str]:
    normalized_title = _normalize_title(title)
    if not normalized_title:
        if _looks_like_toc_block(text):
            return "remove", "toc_like_front_matter"
        return "keep", "untitled_body_text"

    if _looks_like_toc_title(title) or _looks_like_toc_block(text):
        return "remove", "toc_like_heading"
    if _looks_like_toc_back_matter_heading(title, normalized_title):
        return "remove", "toc_like_back_matter_heading"
    if _matches_any(normalized_title, FRONT_MATTER_PATTERNS):
        return "remove", "front_matter"
    if _matches_any(normalized_title, BACK_MATTER_PATTERNS):
        if _looks_like_early_back_matter_heading(title, normalized_title, start_line, total_line_count):
            return "remove", "early_back_matter_like_section"
        if _is_numbered_internal_reference_heading(title, normalized_title, start_line, total_line_count):
            return "remove", "chapter_level_reference_section"
        return "back_matter", "back_matter_boundary"
    if _matches_any(normalized_title, BODY_SECTION_HINTS):
        return "keep", "body_section_keyword"
    if any(
        token in normalized_title
        for token in (
            "\u7eea\u8bba",
            "\u524d\u8a00",
            "\u7efc\u8ff0",
            "\u5f15\u8a00",
            "\u7406\u8bba\u57fa\u7840",
            "缁",
            "鍓嶈█",
            "缁艰堪",
            "寮曡█",
            "鐞嗚鍩虹",
        )
    ):
        return "keep", "introductory_body_section"
    return "keep", "default_keep"


def _normalize_title(title: str) -> str:
    normalized = str(title or "").replace(" ", "").replace("\t", "").strip().lower()
    normalized = re.sub(r"^[#]+", "", normalized).strip()
    return normalized


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def _looks_like_toc_title(title: str) -> bool:
    stripped = title.strip()
    if not stripped:
        return False
    if _matches_any(_normalize_title(stripped), ("\u76ee\u5f55", "contents", "鐩綍")):
        return True
    return bool(TOC_DOT_PATTERN.search(stripped) and TOC_PAGE_PATTERN.search(stripped))


def _looks_like_toc_block(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    toc_like = sum(1 for line in lines[:30] if _looks_like_toc_title(line) or TOC_PAGE_PATTERN.search(line))
    return toc_like >= 3


def _looks_like_toc_back_matter_heading(title: str, normalized_title: str) -> bool:
    stripped = title.strip()
    if not stripped:
        return False
    if not _matches_any(normalized_title, BACK_MATTER_PATTERNS):
        return False
    if TOC_DOT_PATTERN.search(stripped) and TOC_PAGE_PATTERN.search(stripped):
        return True
    return bool(re.search(r"(?:[.\s]\s*)(?:\d+|[ivxlcdm]+)\s*$", stripped, flags=re.IGNORECASE))


def _is_numbered_internal_reference_heading(
    title: str,
    normalized_title: str,
    start_line: int,
    total_line_count: int,
) -> bool:
    stripped = title.strip()
    if not stripped:
        return False
    if not _matches_any(normalized_title, BACK_MATTER_PATTERNS):
        return False
    if not re.match(r"^\d+(?:\.\d+)*", stripped):
        return False
    if total_line_count <= 0:
        return True
    return (start_line / total_line_count) < 0.7


def _looks_like_early_back_matter_heading(
    title: str,
    normalized_title: str,
    start_line: int,
    total_line_count: int,
) -> bool:
    stripped = title.strip()
    if not stripped or total_line_count <= 0:
        return False
    if not _matches_any(normalized_title, BACK_MATTER_PATTERNS):
        return False
    if start_line / total_line_count >= 0.6:
        return False
    if re.match(r"^\d+(?:\.\d+)*", stripped):
        return False
    return True
