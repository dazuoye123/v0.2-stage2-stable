"""Archive and send-to-vision selection rules."""

from __future__ import annotations

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.taxonomy_classifier import has_scientific_text
from alumina_sol_extractor.vision.taxonomy_config import (
    MATERIAL_STATE_PHOTO_KEYWORDS,
    SPINNABILITY_PHOTO_KEYWORDS,
    VISION_ALLOWED_CLASSES,
    keyword_hits,
)


def apply_vision_selection(
    figure: FigureInfo,
    text: str,
    *,
    include_material_state_photos: bool,
    include_schematics_for_vision: bool,
    include_spinnability_photos_for_vision: bool,
) -> None:
    """Mutate one figure's archive/vision flags using existing stable rules."""
    existing_exclude_reason = figure.exclude_reason
    figure.keep_for_archive = True
    figure.send_to_vision_model = False
    figure.maybe_useful = False
    figure.exclude_reason = None

    if figure.is_fragment:
        figure.send_to_vision_model = False
        figure.keep = False
        figure.exclude_reason = existing_exclude_reason or (
            "replaced_by_bbox_stitched_figure" if figure.fragment_group_id else "fragment_image"
        )
        figure.keep_reason = figure.exclude_reason
        return

    clip_negative = figure.clip_decision == "negative"
    clip_positive = figure.clip_decision == "positive"
    has_science = has_scientific_text(figure)
    if figure.figure_class in {
        "logo_or_icon",
        "formula_or_text",
        "pure_text_image",
        "qr_code_or_barcode",
        "cover_decoration",
        "table_image",
    }:
        figure.exclude_reason = figure.figure_class
    elif not figure.caption and figure.figure_id.startswith("Unknown Figure") and not clip_positive:
        figure.exclude_reason = "unknown_without_caption"
    elif figure.figure_class == "schematic_or_flow":
        figure.maybe_useful = True
        if include_schematics_for_vision:
            figure.send_to_vision_model = True
            figure.exclude_reason = None
        else:
            figure.exclude_reason = "maybe_useful_schematic"
    elif figure.figure_class == "photo_image" and keyword_hits(text, MATERIAL_STATE_PHOTO_KEYWORDS):
        figure.maybe_useful = True
        if include_material_state_photos:
            figure.send_to_vision_model = True
            figure.exclude_reason = None
        else:
            figure.exclude_reason = "maybe_useful_material_state_photo"
    elif figure.figure_class == "photo_image" and keyword_hits(text, SPINNABILITY_PHOTO_KEYWORDS):
        figure.maybe_useful = True
        if include_spinnability_photos_for_vision:
            figure.send_to_vision_model = True
            figure.exclude_reason = None
        else:
            figure.exclude_reason = "maybe_useful_spinnability_photo"
    elif figure.figure_class in VISION_ALLOWED_CLASSES:
        figure.send_to_vision_model = True
        figure.exclude_reason = None
    elif clip_positive and has_science:
        figure.send_to_vision_model = True
        figure.exclude_reason = None
    elif clip_negative and not has_science:
        figure.exclude_reason = "clip_negative"
    else:
        figure.exclude_reason = "not_selected_for_vision"

    figure.keep = figure.send_to_vision_model
    figure.keep_reason = f"vision_{figure.figure_class}" if figure.send_to_vision_model else figure.exclude_reason
