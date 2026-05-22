"""Figure taxonomy classification based on cleaned caption/context text."""

from __future__ import annotations

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.taxonomy_config import (
    CAPTION_FTIR_KEYWORDS,
    CAPTION_MECHANICAL_KEYWORDS,
    CAPTION_MICROSCOPY_KEYWORDS,
    CAPTION_PHOTO_KEYWORDS,
    CAPTION_RHEOLOGY_KEYWORDS,
    CAPTION_SCHEMATIC_KEYWORDS,
    CAPTION_SCIENTIFIC_KEYWORDS,
    CAPTION_THERMAL_KEYWORDS,
    CAPTION_XRD_KEYWORDS,
    FORMULA_TEXT_KEYWORDS,
    KEYWORDS,
    MICROSCOPY_MATERIAL_CONTEXT_KEYWORDS,
    NMR_QUANTIFICATION_KEYWORDS,
    NMR_SPECTRUM_KEYWORDS,
    RESNET_CHART_CLASSES,
    RESNET_SCHEMATIC_CLASSES,
    RESNET_TABLE_CLASSES,
    SPINNABILITY_PHOTO_KEYWORDS,
    STRUCTURE_SCHEMATIC_KEYWORDS,
    TEMPERATURE_CURVE_KEYWORDS,
    VISION_ALLOWED_CLASSES,
    keyword_hits,
)

WEAK_CAPTION_MICROSCOPY_CLIP_LABELS = {
    "a sem image",
    "an electron microscope image",
    "a microscopy image",
    "a micrograph",
}


def classification_text(figure: FigureInfo) -> str:
    return " ".join(
        [
            figure.caption or "",
            " ".join(figure.reference_sentences),
            figure.description_text or "",
        ]
    ).lower()


def _supplemental_classification_text(figure: FigureInfo) -> str:
    return " ".join(
        [
            figure.raw_caption or "",
            figure.alt_text or "",
        ]
    ).lower()


def _has_formula_text_context(text: str, caption_text: str) -> bool:
    if not keyword_hits(text, FORMULA_TEXT_KEYWORDS):
        return False
    if keyword_hits(text, CAPTION_SCIENTIFIC_KEYWORDS):
        return False
    if keyword_hits(caption_text, KEYWORDS["schematic_or_flow"]) or keyword_hits(caption_text, CAPTION_SCHEMATIC_KEYWORDS):
        return False
    return True


def _has_material_context(text: str) -> bool:
    return bool(keyword_hits(text, MICROSCOPY_MATERIAL_CONTEXT_KEYWORDS))


def _has_microscopy_material_context(text: str) -> bool:
    return bool(keyword_hits(text, CAPTION_MICROSCOPY_KEYWORDS)) and _has_material_context(text)


def classify_figure(figure: FigureInfo, text: str | None = None) -> str:
    text = text if text is not None else classification_text(figure)
    supplemental_text = _supplemental_classification_text(figure)
    full_text = " ".join(part for part in [text, supplemental_text] if part).strip()
    caption_text = (figure.caption or "").lower()
    subfigure_label = (figure.subfigure_label or "").lower()
    caption_looks_like_photo = bool(keyword_hits(caption_text, CAPTION_PHOTO_KEYWORDS))
    weak_caption_source = (figure.caption_source or "none") in {"pseudo_caption", "none"}

    if keyword_hits(text, NMR_SPECTRUM_KEYWORDS):
        caption_has_quantification = bool(keyword_hits(caption_text, NMR_QUANTIFICATION_KEYWORDS))
        has_no_standard_caption = not figure.caption or figure.caption_source == "pseudo_caption"
        if ((caption_has_quantification or has_no_standard_caption and keyword_hits(text, NMR_QUANTIFICATION_KEYWORDS)) and subfigure_label != "a"):
            return "nmr_quantification_plot"
        return "nmr_spectrum"
    if keyword_hits(caption_text, KEYWORDS["elemental_mapping"]):
        return "elemental_mapping"
    if keyword_hits(caption_text, CAPTION_XRD_KEYWORDS):
        return "xrd_pattern"
    if keyword_hits(caption_text, CAPTION_FTIR_KEYWORDS):
        return "ftir_spectrum"
    if keyword_hits(caption_text, KEYWORDS["raman_spectrum"]):
        return "raman_spectrum"
    if keyword_hits(caption_text, CAPTION_THERMAL_KEYWORDS):
        return "thermal_analysis_plot"
    if keyword_hits(caption_text, CAPTION_MICROSCOPY_KEYWORDS):
        return "microscopy_image"
    if keyword_hits(caption_text, CAPTION_MECHANICAL_KEYWORDS):
        return "mechanical_property_plot"
    if not caption_looks_like_photo and keyword_hits(text, CAPTION_XRD_KEYWORDS):
        return "xrd_pattern"
    if not caption_looks_like_photo and keyword_hits(text, CAPTION_FTIR_KEYWORDS):
        return "ftir_spectrum"
    if not caption_looks_like_photo and keyword_hits(text, CAPTION_THERMAL_KEYWORDS):
        return "thermal_analysis_plot"
    if _has_microscopy_material_context(full_text):
        return "microscopy_image"
    if not caption_looks_like_photo and keyword_hits(text, CAPTION_MECHANICAL_KEYWORDS):
        return "mechanical_property_plot"
    if keyword_hits(text, KEYWORDS["elemental_mapping"]):
        return "elemental_mapping"
    if keyword_hits(caption_text, CAPTION_RHEOLOGY_KEYWORDS):
        return "rheology_curve"
    if keyword_hits(text, TEMPERATURE_CURVE_KEYWORDS):
        return "temperature_curve"
    if keyword_hits(text, KEYWORDS["process_parameter_plot"]):
        return "process_parameter_plot"
    if keyword_hits(text, KEYWORDS["mechanical_property_plot"]):
        return "mechanical_property_plot"
    if keyword_hits(text, KEYWORDS["mechanical_curve"]):
        return "mechanical_curve"
    if caption_looks_like_photo:
        return "photo_image"
    if keyword_hits(text, SPINNABILITY_PHOTO_KEYWORDS):
        return "photo_image"
    if keyword_hits(caption_text, KEYWORDS["schematic_or_flow"]) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if keyword_hits(caption_text, CAPTION_SCHEMATIC_KEYWORDS) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if keyword_hits(text, STRUCTURE_SCHEMATIC_KEYWORDS) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if _has_formula_text_context(full_text, caption_text):
        return "formula_or_text"
    if weak_caption_source:
        clip_label = (figure.clip_label or "").lower()
        if clip_label in WEAK_CAPTION_MICROSCOPY_CLIP_LABELS and _has_material_context(full_text):
            return "microscopy_image"
        if keyword_hits(full_text, CAPTION_MICROSCOPY_KEYWORDS) and _has_material_context(full_text):
            return "microscopy_image"
        if keyword_hits(full_text, CAPTION_XRD_KEYWORDS):
            return "xrd_pattern"

    for class_name in [
        "nmr_quantification_plot",
        "nmr_spectrum",
        "elemental_mapping",
        "mass_spectrum",
        "microscopy_image",
        "ferron_curve",
        "calibration_curve",
        "xrd_pattern",
        "ftir_spectrum",
        "raman_spectrum",
        "thermal_analysis_plot",
        "temperature_curve",
        "particle_size_plot",
        "zeta_potential_plot",
        "photo_image",
        "mechanical_curve",
        "mechanical_property_plot",
        "process_parameter_plot",
        "schematic_or_flow",
        "table_image",
        "logo_or_icon",
        "formula_or_text",
    ]:
        if keyword_hits(text, KEYWORDS[class_name]):
            return class_name

    if figure.clip_decision == "negative":
        if figure.clip_label in {"a publisher logo", "a school logo", "a small icon or symbol"}:
            return "logo_or_icon"
        if figure.clip_label in {"a mathematical formula", "a single equation", "text sentences"}:
            return "formula_or_text"
        if figure.clip_label == "a table with text and numbers":
            return "table_image"
        if figure.clip_label in {"a barcode or qr code"}:
            return "qr_code_or_barcode"
        if figure.clip_label in {"a cover page image", "a decorative image"}:
            return "cover_decoration"

    if figure.resnet_raw_class in RESNET_TABLE_CLASSES:
        return "table_image"
    if figure.resnet_raw_class in RESNET_SCHEMATIC_CLASSES and keyword_hits(text, KEYWORDS["schematic_or_flow"]):
        return "schematic_or_flow"
    if figure.resnet_raw_class in RESNET_CHART_CLASSES or figure.clip_label in {
        "a scientific graph or plot",
        "a spectrum plot",
        "a thermal analysis curve",
        "a rheology curve",
        "a particle size distribution plot",
        "a zeta potential plot",
    }:
        return "generic_chart_or_plot"
    return "other"


def has_scientific_text(figure: FigureInfo) -> bool:
    text = classification_text(figure)
    science_classes = [name for name in VISION_ALLOWED_CLASSES if name in KEYWORDS]
    return any(keyword_hits(text, KEYWORDS[name]) for name in science_classes)
