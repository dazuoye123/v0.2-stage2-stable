"""Figure taxonomy classification based on cleaned caption/context text."""

from __future__ import annotations

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.taxonomy_config import (
    CAPTION_FTIR_KEYWORDS,
    CAPTION_MICROSCOPY_KEYWORDS,
    CAPTION_PHOTO_KEYWORDS,
    CAPTION_RHEOLOGY_KEYWORDS,
    CAPTION_SCHEMATIC_KEYWORDS,
    CAPTION_SCIENTIFIC_KEYWORDS,
    CAPTION_THERMAL_KEYWORDS,
    CAPTION_XRD_KEYWORDS,
    KEYWORDS,
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


def classification_text(figure: FigureInfo) -> str:
    return " ".join(
        [
            figure.caption or "",
            " ".join(figure.reference_sentences),
            figure.description_text or "",
        ]
    ).lower()


def classify_figure(figure: FigureInfo, text: str | None = None) -> str:
    text = text if text is not None else classification_text(figure)
    caption_text = (figure.caption or "").lower()
    subfigure_label = (figure.subfigure_label or "").lower()

    if keyword_hits(text, NMR_SPECTRUM_KEYWORDS):
        caption_has_quantification = bool(keyword_hits(caption_text, NMR_QUANTIFICATION_KEYWORDS))
        has_no_standard_caption = not figure.caption or figure.caption_source == "pseudo_caption"
        if ((caption_has_quantification or has_no_standard_caption and keyword_hits(text, NMR_QUANTIFICATION_KEYWORDS)) and subfigure_label != "a"):
            return "nmr_quantification_plot"
        return "nmr_spectrum"
    if keyword_hits(caption_text, KEYWORDS["elemental_mapping"]):
        return "elemental_mapping"
    if keyword_hits(caption_text, CAPTION_PHOTO_KEYWORDS):
        return "photo_image"
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
    if keyword_hits(text, SPINNABILITY_PHOTO_KEYWORDS):
        return "photo_image"
    if keyword_hits(caption_text, KEYWORDS["schematic_or_flow"]) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if keyword_hits(caption_text, CAPTION_SCHEMATIC_KEYWORDS) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if keyword_hits(text, STRUCTURE_SCHEMATIC_KEYWORDS) and not keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"

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
