"""Technique-aware unit normalization helpers for spectra-derived parameters."""

from __future__ import annotations

from typing import Any

_PEAK_UNIT_BY_FIGURE_TYPE = {
    "ftir_spectrum": "cm-1",
    "ir_spectrum": "cm-1",
    "raman_spectrum": "cm-1",
    "xrd_pattern": "2theta_deg",
    "nmr_spectrum": "ppm",
}

_PEAK_UNIT_BY_CANONICAL_KEY = {
    "ftir_peak_position_cm_1": "cm-1",
    "raman_peak_position_cm_1": "cm-1",
    "xrd_peak_position_2theta_deg": "2theta_deg",
    "nmr_27Al_peak_position_ppm": "ppm",
}


def normalize_unit_text(unit: Any) -> str | None:
    unit_text = _string_or_none(unit)
    if unit_text in {None, "None", "null", "dimensionless", "nan"}:
        return None
    normalized = {
        "ml/h": "mL/h",
        "ml / h": "mL/h",
        "c/min": "C/min",
        "?c/min": "C/min",
        "?/min": "C/min",
        "c": "C",
        "?c": "C",
        "?": "C",
        "cm^-1": "cm-1",
        "wt%": "wt%",
    }
    lookup = normalized.get(unit_text.lower())
    return lookup or unit_text


def infer_peak_unit(
    *,
    figure_type: Any = None,
    canonical_key: Any = None,
    technique: Any = None,
) -> str | None:
    key_text = _string_or_none(canonical_key)
    if key_text in _PEAK_UNIT_BY_CANONICAL_KEY:
        return _PEAK_UNIT_BY_CANONICAL_KEY[key_text]

    figure_text = _string_or_none(figure_type)
    if figure_text in _PEAK_UNIT_BY_FIGURE_TYPE:
        return _PEAK_UNIT_BY_FIGURE_TYPE[figure_text]

    technique_text = (_string_or_none(technique) or "").casefold()
    if "xrd" in technique_text:
        return "2theta_deg"
    if "nmr" in technique_text:
        return "ppm"
    if "ftir" in technique_text or technique_text == "ir" or "raman" in technique_text:
        return "cm-1"
    return None


def normalize_parameter_unit(unit: Any, canonical_key: Any = None) -> str | None:
    return infer_peak_unit(canonical_key=canonical_key) or normalize_unit_text(unit)


def coerce_peak_unit(
    unit: Any,
    *,
    figure_type: Any = None,
    canonical_key: Any = None,
    technique: Any = None,
) -> str | None:
    return infer_peak_unit(
        figure_type=figure_type,
        canonical_key=canonical_key,
        technique=technique,
    ) or normalize_unit_text(unit)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
