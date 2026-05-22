"""Compatibility exports for caption extraction helpers."""

from alumina_sol_extractor.utils.figure_utils import (
    CaptionRecord,
    extract_caption_near_image,
    extract_caption_record,
    split_caption_and_following_text,
)

__all__ = [
    "CaptionRecord",
    "extract_caption_near_image",
    "extract_caption_record",
    "split_caption_and_following_text",
]
