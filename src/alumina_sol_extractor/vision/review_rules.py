"""Review and false-candidate rules kept separate from taxonomy selection."""

from __future__ import annotations

import re

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.taxonomy_classifier import classification_text
from alumina_sol_extractor.vision.taxonomy_config import (
    CAPTION_OCR_ANCHOR_KEYWORDS,
    CAPTION_OCR_SUSPECT_PHRASES,
    FALSE_CANDIDATE_KEYWORDS,
    KEYWORDS,
    keyword_hits,
)


def is_false_candidate(figure: FigureInfo) -> bool:
    if figure.send_to_vision_model:
        return False
    if figure.is_fragment:
        return False
    if figure.exclude_reason == "replaced_by_bbox_stitched_figure":
        return False
    if figure.figure_class == "schematic_or_flow":
        return False
    return bool(keyword_hits(classification_text(figure), FALSE_CANDIDATE_KEYWORDS))


def is_review_candidate(figure: FigureInfo) -> bool:
    if figure.is_fragment:
        return False
    if figure.exclude_reason == "replaced_by_bbox_stitched_figure":
        return False
    return figure.review_reason is not None or is_caption_ocr_suspect(figure)


def review_reason_for_figure(figure: FigureInfo, text: str | None = None) -> str | None:
    text = text if text is not None else classification_text(figure)
    if is_caption_ocr_suspect(figure):
        return "caption_ocr_suspect"
    if figure.caption_truncation_reason == "multiple_figure_ids_caption_assignment_uncertain":
        return "multiple_figure_ids_caption_assignment_uncertain"
    if figure.caption_truncation_reason == "multiple_figure_ids_in_caption":
        return "multiple_figure_ids_in_caption"
    if figure.caption_cleaned and figure.caption_truncation_reason:
        return "caption_truncated"
    if keyword_hits(text, KEYWORDS["elemental_mapping"]) and figure.figure_class != "elemental_mapping":
        return "taxonomy_conflict"
    if figure.figure_class == "other":
        return "figure_class_other"
    if keyword_hits(text, FALSE_CANDIDATE_KEYWORDS) and not figure.send_to_vision_model and not figure.is_fragment:
        return "scientific_figure_not_sent_to_vision"
    return None


def is_caption_ocr_suspect(figure: FigureInfo) -> bool:
    caption = (figure.caption or figure.raw_caption or "").strip()
    if not caption:
        return False
    if any(phrase in caption for phrase in CAPTION_OCR_SUSPECT_PHRASES):
        return True
    anchor_hits = sum(1 for keyword in CAPTION_OCR_ANCHOR_KEYWORDS if keyword in caption)
    if anchor_hits >= 2:
        return True
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", caption)
    if len(chinese_chars) >= 18:
        common_caption_terms = [
            "\u56fe",
            "\u8c31",
            "\u66f2\u7ebf",
            "\u793a\u610f",
            "\u7ed3\u6784",
            "\u5f62\u8c8c",
            "\u6eb6\u80f6",
            "\u51dd\u80f6",
            "\u7ea4\u7ef4",
            "\u6e29\u5ea6",
            "\u6838\u78c1",
            "\u7ea2\u5916",
            "\u8d28\u8c31",
        ]
        if anchor_hits and not any(term in caption for term in common_caption_terms):
            return True
    return False
