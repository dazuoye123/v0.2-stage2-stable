from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alumina_sol_extractor.stage3.sections import parse_markdown_sections

FRONT_MATTER_PATTERNS = (
    "目录",
    "摘要",
    "abstract",
    "shandong university",
    "thesis for master degree",
    "thesis for doctoral degree",
    "山东大学",
    "硕士学位论文",
    "博士学位论文",
    "作者姓名",
    "培养单位",
    "指导教师",
    "合作导师",
    "专业学位",
    "专业名称",
    "原创性声明",
    "授权声明",
    "版权声明",
    "符号说明",
    "图目录",
    "表目录",
    "作者简介",
    "攻读学位期间",
    "学位论文",
)

BACK_MATTER_PATTERNS = (
    "参考文献",
    "references",
    "附录",
    "appendix",
    "致谢",
    "作者简介",
    "攻读学位期间",
)

BODY_SECTION_HINTS = (
    "实验",
    "制备",
    "表征",
    "结果与讨论",
    "结果分析",
    "测试",
    "纺丝",
    "煅烧",
    "热处理",
    "nmr",
    "ftir",
    "xrd",
    "sem",
    "tem",
    "ferron",
    "raman",
    "结论",
)

TOC_DOT_PATTERN = re.compile(r"(?:\.{3,}|\u2026{2,}|\. ?\. ?\.)")
TOC_PAGE_PATTERN = re.compile(r"(?:\.{3,}|\u2026{2,}|\s)\d+\s*$")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]+\)")
HTML_IMG_PATTERN = re.compile(r"<img\b[^>]*>", flags=re.IGNORECASE)
DETAILS_TAG_START_PATTERN = re.compile(r"^\s*<details\b", flags=re.IGNORECASE)
DETAILS_TAG_END_PATTERN = re.compile(r"^\s*</details>\s*$", flags=re.IGNORECASE)
SUMMARY_TAG_PATTERN = re.compile(r"^\s*</?summary\b[^>]*>\s*$", flags=re.IGNORECASE)
NUMBERED_TOC_LINE_PATTERN = re.compile(
    r"^\s*(?:#\s*)?(?:\d+(?:\.\d+)*|[一二三四五六七八九十]+(?:章|节)?)\s*.*?\s+\d+\s*$"
)
TITLE_PAGE_LINE_PATTERN = re.compile(
    r"(?:shandong\s+university|thesis\s+for\s+(?:master|doctoral)\s+degree|山东大学|作者姓名|培养单位|指导教师|合作导师|专业学位|专业名称)",
    flags=re.IGNORECASE,
)
STANDALONE_IMAGE_PATH_PATTERN = re.compile(
    r"^\s*(?:(?:[A-Za-z]:)?[\\/]|\.{0,2}[\\/])?.*(?:figures_all|figures_for_vision|images)[\\/].*\.(?:png|jpg|jpeg|webp|gif|bmp|tiff?)\s*$",
    flags=re.IGNORECASE,
)
PLAIN_IMAGE_PATH_PATTERN = re.compile(
    r"^\s*[^<>\s]+(?:figures_all|figures_for_vision|images)[^<>\s]*\.(?:png|jpg|jpeg|webp|gif|bmp|tiff?)\s*$",
    flags=re.IGNORECASE,
)


@dataclass
class TrimResult:
    cleaned_text: str
    report: dict[str, Any]


def generate_cleaned_body_markdown(*, markdown_path: Path | str, paper_output_dir: Path | str) -> TrimResult:
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
        cleaned_text, cleanup_stats = _cleanup_residual_lines(markdown_text)
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
            **cleanup_stats,
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
        decision, reason = _classify_section(title, text, start_line=start_line, total_line_count=total_line_count)
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

    kept_sections = _drop_leading_non_body_sections(kept_sections)

    if not kept_sections:
        warnings.append("no_trimmed_body_sections_kept_fallback_to_original")
        cleaned_text, cleanup_stats = _cleanup_residual_lines(markdown_text)
        kept_titles: list[str] = []
        cut_start_line = 1
        cut_end_line = total_line_count
    else:
        cleaned_parts = [str(section.get("text") or "").strip() for section in kept_sections]
        cleaned_text, cleanup_stats = _cleanup_residual_lines("\n\n".join(part for part in cleaned_parts if part))
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
        **cleanup_stats,
    }
    return TrimResult(cleaned_text=cleaned_text, report=report)


def _classify_section(title: str, text: str, *, start_line: int, total_line_count: int) -> tuple[str, str]:
    normalized_title = _normalize_title(title)
    if not normalized_title:
        if _looks_like_cover_page_block(text):
            return "remove", "cover_page_front_matter"
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
    if any(token in normalized_title for token in ("绪论", "前言", "综述", "引言", "理论基础")):
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
    if _matches_any(_normalize_title(stripped), ("目录", "contents")):
        return True
    if NUMBERED_TOC_LINE_PATTERN.match(stripped) and not stripped.startswith("# 2.2.2 "):
        return True
    return bool(TOC_DOT_PATTERN.search(stripped) and TOC_PAGE_PATTERN.search(stripped))


def _looks_like_toc_block(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    toc_like = sum(
        1
        for line in lines[:30]
        if _looks_like_toc_title(line) or TOC_PAGE_PATTERN.search(line) or _looks_like_toc_residue_line(line)
    )
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


def _is_numbered_internal_reference_heading(title: str, normalized_title: str, start_line: int, total_line_count: int) -> bool:
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


def _looks_like_early_back_matter_heading(title: str, normalized_title: str, start_line: int, total_line_count: int) -> bool:
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


def _looks_like_cover_page_block(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    cover_hits = sum(1 for line in lines[:25] if TITLE_PAGE_LINE_PATTERN.search(line))
    return cover_hits >= 2


def _drop_leading_non_body_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sections:
        return sections
    for index, section in enumerate(sections):
        title = str(section.get("title") or "").strip()
        text = str(section.get("text") or "")
        if _is_probable_body_section(title, text):
            return sections[index:]
    return sections


def _is_probable_body_section(title: str, text: str) -> bool:
    normalized_title = _normalize_title(title)
    if not normalized_title:
        return False
    if _matches_any(normalized_title, FRONT_MATTER_PATTERNS):
        return False
    if _looks_like_cover_page_block(text) or _looks_like_toc_block(text):
        return False
    if _matches_any(normalized_title, BODY_SECTION_HINTS):
        return True
    if any(token in normalized_title for token in ("绪论", "前言", "引言", "综述", "结果", "讨论", "结论")):
        return True
    if re.match(r"^(第[一二三四五六七八九十百]+章|\d+(?:\.\d+)*)", title.strip()):
        return True
    return False


def _looks_like_toc_residue_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if TOC_DOT_PATTERN.search(stripped) and TOC_PAGE_PATTERN.search(stripped):
        return True
    if NUMBERED_TOC_LINE_PATTERN.match(stripped):
        return True
    return False


def _cleanup_residual_lines(text: str) -> tuple[str, dict[str, int]]:
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    body_started = False
    removed_image_markdown_line_count = 0
    removed_html_img_line_count = 0
    removed_image_path_line_count = 0
    removed_details_image_block_count = 0
    in_details_block = False
    current_details_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if in_details_block:
            current_details_lines.append(line)
            if DETAILS_TAG_END_PATTERN.match(stripped):
                removed_details_image_block_count += 1
                in_details_block = False
                current_details_lines = []
            continue
        if DETAILS_TAG_START_PATTERN.match(stripped):
            in_details_block = True
            current_details_lines = [line]
            continue
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if not body_started:
            if stripped.startswith("![]("):
                continue
            if TITLE_PAGE_LINE_PATTERN.search(stripped):
                continue
            if _looks_like_toc_residue_line(stripped):
                continue
            if stripped.startswith("#"):
                body_started = True

        if _looks_like_toc_residue_line(stripped):
            continue
        if not body_started and TITLE_PAGE_LINE_PATTERN.search(stripped):
            continue

        line, markdown_removed, html_removed = _remove_inline_image_noise(line)
        if markdown_removed:
            removed_image_markdown_line_count += 1
        if html_removed:
            removed_html_img_line_count += 1
        stripped = line.strip()
        if not stripped:
            continue
        if _is_standalone_image_path_line(stripped):
            removed_image_path_line_count += 1
            continue

        cleaned_lines.append(line)
        if stripped.startswith("#"):
            body_started = True

    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()
    return "\n".join(cleaned_lines).strip(), {
        "removed_image_markdown_line_count": removed_image_markdown_line_count,
        "removed_html_img_line_count": removed_html_img_line_count,
        "removed_image_path_line_count": removed_image_path_line_count,
        "removed_details_image_block_count": removed_details_image_block_count,
    }


def _remove_inline_image_noise(line: str) -> tuple[str, bool, bool]:
    cleaned = line
    markdown_removed = False
    html_removed = False
    if MARKDOWN_IMAGE_PATTERN.search(cleaned):
        cleaned = MARKDOWN_IMAGE_PATTERN.sub("", cleaned)
        markdown_removed = True
    if "data:image" in cleaned.lower():
        cleaned = re.sub(r"data:image/[^)\s>]+", "", cleaned, flags=re.IGNORECASE)
        markdown_removed = True
    if HTML_IMG_PATTERN.search(cleaned):
        cleaned = HTML_IMG_PATTERN.sub("", cleaned)
        html_removed = True
    return cleaned.rstrip(), markdown_removed, html_removed


def _is_standalone_image_path_line(line: str) -> bool:
    if line.lower().startswith(("fig.", "figure ", "图")):
        return False
    return bool(STANDALONE_IMAGE_PATH_PATTERN.match(line) or PLAIN_IMAGE_PATH_PATTERN.match(line))
