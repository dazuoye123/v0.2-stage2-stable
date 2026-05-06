"""Routing helpers for Stage 4 vision spectra extraction."""

from __future__ import annotations

import re

from .schemas import (
    FerronCurveExtraction,
    MicroscopyExtraction,
    NMRExtraction,
    ThermalAnalysisExtraction,
    UnknownFigureExtraction,
    VibrationalSpectrumExtraction,
    XRDExtraction,
)


_NORMALIZATION_RULES: list[tuple[str, tuple[str, ...]]] = [
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
}


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
    if normalized == "unknown":
        return False
    if not allow_types:
        return normalized in _SCHEMA_BY_FIGURE_TYPE and normalized != "unknown"
    return normalized in {normalize_figure_type(item) for item in allow_types}
