"""Routing helpers for Stage 4 vision spectra extraction."""

from __future__ import annotations

import re

from .schemas import (
    FerronCurveExtraction,
    MicroscopyExtraction,
    NMRExtraction,
    ThermalAnalysisExtraction,
    UniversalFigureExtraction,
    UnknownFigureExtraction,
    VibrationalSpectrumExtraction,
    XRDExtraction,
)


_NORMALIZATION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("non_extractable", ("non_extractable", "non-extractable", "not extractable", "not_extractable")),
    ("tg_dsc_curve", ("tg-dsc", "tg/dsc", "tg dsc")),
    ("ftir_spectrum", ("ftir", "infrared", "ir", "红外", "傅里叶红外")),
    ("raman_spectrum", ("raman", "拉曼")),
    ("nmr_spectrum", ("27al", "nmr", "核磁")),
    ("xrd_pattern", ("xrd", "diffraction", "衍射")),
    ("ferron_curve", ("ferron", "al-ferron")),
    ("tg_curve", ("tga", "tg curve", "tg ")),
    ("dsc_curve", ("dsc",)),
    ("sem_image", ("sem",)),
    ("tem_image", ("tem",)),
    ("microscopy", ("microscopy", "显微")),
]

_SCHEMA_BY_FIGURE_TYPE = {
    "nmr_spectrum": NMRExtraction,
    "ftir_spectrum": VibrationalSpectrumExtraction,
    "ir_spectrum": VibrationalSpectrumExtraction,
    "raman_spectrum": VibrationalSpectrumExtraction,
    "xrd_pattern": XRDExtraction,
    "ferron_curve": FerronCurveExtraction,
    "tg_curve": ThermalAnalysisExtraction,
    "dsc_curve": ThermalAnalysisExtraction,
    "tg_dsc_curve": ThermalAnalysisExtraction,
    "sem_image": MicroscopyExtraction,
    "tem_image": MicroscopyExtraction,
    "microscopy": MicroscopyExtraction,
    "unknown": UnknownFigureExtraction,
    "non_extractable": UnknownFigureExtraction,
}

_SCIENTIFIC_CONTEXT_KEYWORDS = (
    "xrd",
    "ftir",
    "ir",
    "raman",
    "nmr",
    "tg",
    "tga",
    "dsc",
    "dta",
    "sem",
    "tem",
    "ferron",
    "rheology",
    "diffraction",
    "spectrum",
    "micrograph",
    "morphology",
)
_WEAK_STAGE2_CLASSES = {"unknown", "generic_chart_or_plot", "photo_image", "other"}


def normalize_figure_type(raw_type: str | None, caption: str | None = None) -> str:
    raw_text = " ".join(part for part in [(raw_type or ""), (caption or "")] if part).strip().lower()
    if not raw_text:
        return "unknown"
    for normalized, keywords in _NORMALIZATION_RULES:
        if normalized == raw_text:
            return normalized
        if any(keyword in raw_text for keyword in keywords):
            return normalized
    normalized_raw = re.sub(r"\s+", "_", raw_text)
    if normalized_raw in _SCHEMA_BY_FIGURE_TYPE:
        return normalized_raw
    return "unknown"


def get_schema_for_figure_type(figure_type: str | None):
    normalized = normalize_figure_type(figure_type)
    return _SCHEMA_BY_FIGURE_TYPE.get(normalized, UnknownFigureExtraction)


def should_process_figure(figure_type: str | None, allow_types: set[str] | None = None) -> bool:
    normalized = normalize_figure_type(figure_type)
    if normalized in {"unknown", "non_extractable"}:
        return False
    if not allow_types:
        return normalized in _SCHEMA_BY_FIGURE_TYPE and normalized != "unknown"
    return normalized in {normalize_figure_type(item) for item in allow_types}


def caption_or_context_is_scientific(*values: str | None) -> bool:
    text = " ".join((value or "") for value in values).strip().lower()
    if not text:
        return False
    return any(keyword in text for keyword in _SCIENTIFIC_CONTEXT_KEYWORDS)


def describe_universal_candidate(
    *,
    initial_figure_type: str | None,
    stage2_figure_class: str | None,
    stage3_figure_type: str | None,
    caption: str | None,
    context_text: str | None = None,
    allow_types: set[str] | None = None,
) -> tuple[bool, str, str]:
    normalized_initial = normalize_figure_type(initial_figure_type)
    normalized_stage2 = normalize_figure_type(stage2_figure_class)
    normalized_stage3 = normalize_figure_type(stage3_figure_type)
    raw_stage2 = (stage2_figure_class or "").strip().lower()
    scientific_caption = caption_or_context_is_scientific(caption, context_text)

    if normalized_initial not in {"unknown", "non_extractable"}:
        if raw_stage2 in _WEAK_STAGE2_CLASSES and scientific_caption:
            return True, "stage2_unknown_caption_scientific", "medium"
        if normalized_stage2 == normalized_stage3 == normalized_initial:
            return True, "stage3_stage2_caption_agree", "low"
        if normalized_stage2 != "unknown" and normalized_stage3 != "unknown" and normalized_stage2 != normalized_stage3:
            return True, "stage2_caption_mismatch", "high"
        return True, "weak_type_but_scientific_context" if scientific_caption else "default_schema_specific", "medium"

    if raw_stage2 in _WEAK_STAGE2_CLASSES and scientific_caption:
        return True, "stage2_unknown_caption_scientific", "medium"
    if scientific_caption:
        return True, "weak_type_but_scientific_context", "high"

    allowed = {normalize_figure_type(item) for item in allow_types or set()}
    if allowed and normalized_stage3 in allowed and normalized_stage3 not in {"unknown", "non_extractable"}:
        return True, "default_schema_specific", "medium"
    return False, "default_schema_specific", "high"


__all__ = [
    "UniversalFigureExtraction",
    "caption_or_context_is_scientific",
    "describe_universal_candidate",
    "get_schema_for_figure_type",
    "normalize_figure_type",
    "should_process_figure",
]
