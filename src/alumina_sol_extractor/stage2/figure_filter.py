"""Compatibility facade for figure taxonomy, vision selection, and review.

The stable public API remains here, but the implementation is now split into:
- ``taxonomy_config.py``
- ``taxonomy_classifier.py``
- ``vision_selector.py``
- ``review_rules.py``
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.review_rules import (
    is_caption_ocr_suspect,
    is_false_candidate,
    is_review_candidate,
    review_reason_for_figure,
)
from alumina_sol_extractor.vision.taxonomy_classifier import (
    classification_text as _classification_text,
    classify_figure,
    has_scientific_text,
)
from alumina_sol_extractor.vision.taxonomy_config import (
    FIGURE_CLASSES,
    KEYWORDS,
    SIMPLIFIED_CLASSES,
    all_keywords as _all_keywords,
    keyword_hits as _keyword_hits,
    keyword_matches as _keyword_matches,
)
from alumina_sol_extractor.vision.vision_selector import apply_vision_selection


class FigureFilter:
    """Assign final class and send-to-vision flag."""

    def __init__(
        self,
        include_material_state_photos: bool = True,
        include_schematics_for_vision: bool = False,
        include_spinnability_photos_for_vision: bool = True,
    ) -> None:
        self.include_material_state_photos = include_material_state_photos
        self.include_schematics_for_vision = include_schematics_for_vision
        self.include_spinnability_photos_for_vision = include_spinnability_photos_for_vision

    def apply(self, figures: list[FigureInfo]) -> list[FigureInfo]:
        for figure in figures:
            self.apply_one(figure)
        return figures

    def apply_one(self, figure: FigureInfo) -> FigureInfo:
        text = _classification_text(figure)
        figure.keyword_hits = _keyword_hits(text, _all_keywords())
        figure.figure_class = classify_figure(figure, text)
        apply_vision_selection(
            figure,
            text,
            include_material_state_photos=self.include_material_state_photos,
            include_schematics_for_vision=self.include_schematics_for_vision,
            include_spinnability_photos_for_vision=self.include_spinnability_photos_for_vision,
        )
        figure.review_reason = review_reason_for_figure(figure, text)
        return figure


def image_size(image_path: str | None) -> tuple[int | None, int | None]:
    if not image_path:
        return None, None
    path = Path(image_path)
    if not path.exists():
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


__all__ = [
    "FIGURE_CLASSES",
    "SIMPLIFIED_CLASSES",
    "FigureFilter",
    "classify_figure",
    "has_scientific_text",
    "is_caption_ocr_suspect",
    "is_false_candidate",
    "is_review_candidate",
    "review_reason_for_figure",
    "_classification_text",
    "_all_keywords",
    "_keyword_hits",
    "_keyword_matches",
    "KEYWORDS",
]
