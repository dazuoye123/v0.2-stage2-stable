"""Schema-specific normalization helpers for Stage 4 VLM outputs."""

from __future__ import annotations

import re
from typing import Any


def normalize_vlm_payload_for_schema(payload: dict[str, Any], schema_name: str) -> tuple[dict[str, Any], list[str]]:
    """Normalize half-compliant VLM JSON before Pydantic validation.

    The goal is not to silently accept arbitrary output, but to catch a small
    set of known, explainable shape mismatches.
    """

    normalized = dict(payload)
    warnings: list[str] = []

    _normalize_list_field(normalized, warnings, field_name="warnings")
    _normalize_list_field(normalized, warnings, field_name="conflict_warnings")
    _normalize_list_field(normalized, warnings, field_name="peaks")

    if schema_name == "XRDExtraction":
        _normalize_list_field(normalized, warnings, field_name="phase_assignments")
        _normalize_detected_phases(normalized, warnings)
        _normalize_text_field_from_dict(
            normalized,
            warnings,
            field_name="crystallinity_trend",
            warning_code="crystallinity_trend_mapped_from_dict",
        )
        _normalize_xrd_peaks(normalized, warnings)
    elif schema_name == "MicroscopyExtraction":
        _normalize_scale_bar(normalized, warnings)
        _normalize_microscopy_payload(normalized, warnings)
    elif schema_name == "ThermalAnalysisExtraction":
        _normalize_temperature_list(
            normalized,
            warnings,
            field_name="transition_temperatures",
            warning_code="transition_temperatures_item_mapped_from_dict",
        )
        _normalize_event_value_lists(normalized, warnings)
        _normalize_list_field(normalized, warnings, field_name="thermal_events")
    elif schema_name == "VibrationalSpectrumExtraction":
        _normalize_vibrational_peaks(normalized, warnings)
    elif schema_name == "NMRExtraction":
        _normalize_nmr_peaks(normalized, warnings)
    elif schema_name == "FerronCurveExtraction":
        _normalize_list_field(normalized, warnings, field_name="al_species")
    elif schema_name == "UnknownFigureExtraction":
        _normalize_list_field(normalized, warnings, field_name="safe_observations")

    return normalized, warnings


def _normalize_list_field(payload: dict[str, Any], warnings: list[str], *, field_name: str) -> None:
    if field_name not in payload:
        payload[field_name] = []
        return
    value = payload.get(field_name)
    if value is None:
        payload[field_name] = []
        warnings.append(f"{field_name}_normalized_none_to_empty_list")
        return
    if isinstance(value, list):
        return
    payload[field_name] = [str(value)] if str(value).strip() else []
    warnings.append(f"{field_name}_coerced_to_list")


def _normalize_detected_phases(payload: dict[str, Any], warnings: list[str]) -> None:
    detected_phases = payload.get("detected_phases")
    if detected_phases is None:
        return
    if not isinstance(detected_phases, list):
        payload["detected_phases"] = [str(detected_phases)]
        warnings.append("detected_phases_coerced_to_string_list")
        return

    normalized_phases: list[str] = []
    for item in detected_phases:
        if isinstance(item, str):
            if item:
                normalized_phases.append(item)
            continue
        if isinstance(item, dict):
            phase_name = item.get("phase") or item.get("name") or item.get("label")
            if phase_name:
                normalized_phases.append(str(phase_name))
            else:
                normalized_phases.append(str(item))
            detail_parts: list[str] = []
            for key in ("phase", "name", "label", "source", "confidence", "source_text", "evidence_text"):
                value = item.get(key)
                if value is not None:
                    detail_parts.append(f"{key}={value}")
            suffix = f":{';'.join(detail_parts)}" if detail_parts else ""
            warnings.append(f"detected_phases_item_mapped_from_dict{suffix}")
            continue
        normalized_phases.append(str(item))
        warnings.append("detected_phases_item_coerced_to_string")
    payload["detected_phases"] = normalized_phases


def _normalize_scale_bar(payload: dict[str, Any], warnings: list[str]) -> None:
    scale_bar = payload.get("scale_bar")
    if scale_bar is None or isinstance(scale_bar, str):
        return
    if not isinstance(scale_bar, dict):
        payload["scale_bar"] = str(scale_bar)
        warnings.append("scale_bar_coerced_to_string")
        return

    rendered: str | None = None
    length = scale_bar.get("length")
    unit = scale_bar.get("unit")
    if length is not None and unit:
        rendered = f"{length} {unit}"
    else:
        value = scale_bar.get("value")
        if value is not None and unit:
            rendered = f"{value} {unit}"
        elif scale_bar.get("text"):
            rendered = str(scale_bar.get("text"))
        else:
            rendered = str(scale_bar)

    detail_parts: list[str] = []
    for key in ("length", "value", "unit", "source", "text"):
        value = scale_bar.get(key)
        if value is not None:
            detail_parts.append(f"{key}={value}")
    suffix = f":{';'.join(detail_parts)}" if detail_parts else ""
    warnings.append(f"scale_bar_mapped_from_dict{suffix}")
    payload["scale_bar"] = rendered


def _normalize_text_field_from_dict(
    payload: dict[str, Any],
    warnings: list[str],
    *,
    field_name: str,
    warning_code: str,
) -> None:
    value = payload.get(field_name)
    if value is None or isinstance(value, str):
        return
    if not isinstance(value, dict):
        payload[field_name] = str(value)
        warnings.append(f"{warning_code}:coerced_to_string")
        return

    rendered = (
        value.get("description")
        or value.get("text")
        or value.get("summary")
        or str(value)
    )
    detail_parts: list[str] = []
    for key in ("description", "text", "summary", "source", "confidence"):
        detail_value = value.get(key)
        if detail_value is not None:
            detail_parts.append(f"{key}={detail_value}")
    suffix = f":{';'.join(detail_parts)}" if detail_parts else ""
    warnings.append(f"{warning_code}{suffix}")
    payload[field_name] = str(rendered)


def _normalize_temperature_list(
    payload: dict[str, Any],
    warnings: list[str],
    *,
    field_name: str,
    warning_code: str,
) -> None:
    value = payload.get(field_name)
    if value is None:
        return
    if not isinstance(value, list):
        payload[field_name] = [_coerce_float(value)]
        warnings.append(f"{warning_code}:coerced_non_list_value")
        return

    normalized_values: list[float] = []
    for item in value:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            normalized_values.append(float(item))
            continue
        if isinstance(item, dict):
            extracted = item.get("temperature")
            if extracted is None:
                extracted = item.get("value")
            if extracted is None:
                extracted = item.get("temp")
            if extracted is not None:
                normalized_values.append(_coerce_float(extracted))
                detail_parts: list[str] = []
                for key in ("temperature", "value", "temp", "description", "source"):
                    detail_value = item.get(key)
                    if detail_value is not None:
                        detail_parts.append(f"{key}={detail_value}")
                suffix = f":{';'.join(detail_parts)}" if detail_parts else ""
                warnings.append(f"{warning_code}{suffix}")
                continue
        normalized_values.append(_coerce_float(item))
        warnings.append(f"{warning_code}:coerced_unstructured_item")
    payload[field_name] = normalized_values


def _normalize_event_value_lists(payload: dict[str, Any], warnings: list[str]) -> None:
    for field_name in ("mass_loss_steps", "thermal_events"):
        value = payload.get(field_name)
        if value is None:
            continue
        if isinstance(value, list):
            normalized_items: list[Any] = []
            changed = False
            for item in value:
                if not isinstance(item, dict):
                    normalized_items.append(item)
                    continue
                normalized_item = dict(item)
                for key in ("temperature", "peak_temperature", "transition_temperature"):
                    raw = normalized_item.get(key)
                    if isinstance(raw, dict):
                        extracted = raw.get("temperature") or raw.get("value") or raw.get("temp")
                        if extracted is not None:
                            normalized_item[key] = _coerce_float(extracted)
                            warnings.append(f"{field_name}_{key}_mapped_from_dict")
                            changed = True
                for key in ("mass_loss_percent", "weight_loss_percent", "residue_percent"):
                    raw = normalized_item.get(key)
                    if isinstance(raw, dict):
                        extracted = raw.get("value") or raw.get("percent")
                        if extracted is not None:
                            normalized_item[key] = _coerce_float(extracted)
                            warnings.append(f"{field_name}_{key}_mapped_from_dict")
                            changed = True
                normalized_items.append(normalized_item)
            if changed:
                payload[field_name] = normalized_items


_RANGE_PATTERN = re.compile(
    r"^\s*(?P<left>-?\d+(?:\.\d+)?)\s*(?:-|–|~|to)\s*(?P<right>-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


def _append_item_warning(item: dict[str, Any], warning: str) -> None:
    existing = item.get("warnings")
    if existing is None:
        item["warnings"] = [warning]
        return
    if isinstance(existing, list):
        if warning not in existing:
            existing.append(warning)
        return
    item["warnings"] = [str(existing), warning]


def _normalize_vibrational_peaks(payload: dict[str, Any], warnings: list[str]) -> None:
    peaks = payload.get("peaks")
    if not isinstance(peaks, list):
        return
    normalized_peaks: list[Any] = []
    for item in peaks:
        if not isinstance(item, dict):
            normalized_peaks.append(item)
            continue
        peak = dict(item)
        peak["warnings"] = _coerce_list_of_strings(peak.get("warnings"))
        if not peak.get("band_type"):
            peak["band_type"] = "unknown"
        if not peak.get("intensity_level"):
            peak["intensity_level"] = "unknown"
        position = peak.get("position")
        if isinstance(position, str):
            stripped = position.strip()
            if _RANGE_PATTERN.match(stripped):
                source_text = str(peak.get("source_text") or "").strip()
                raw_text = stripped
                if raw_text and raw_text not in source_text:
                    peak["source_text"] = f"{source_text}; {raw_text}".strip("; ").strip()
                peak["position"] = None
                if not peak.get("unit"):
                    peak["unit"] = "cm^-1"
                if peak.get("band_type") in (None, "", "unknown"):
                    peak["band_type"] = "range_band"
                _append_item_warning(peak, f"range_peak_position_not_numeric:{stripped}")
                warnings.append(f"range_peak_position_not_numeric:{stripped}")
            else:
                try:
                    peak["position"] = float(stripped)
                except ValueError:
                    peak["position"] = None
                    _append_item_warning(peak, f"non_numeric_peak_position:{stripped}")
                    warnings.append(f"non_numeric_peak_position:{stripped}")
        normalized_peaks.append(peak)
    payload["peaks"] = normalized_peaks


def _normalize_xrd_peaks(payload: dict[str, Any], warnings: list[str]) -> None:
    peaks = payload.get("peaks")
    if not isinstance(peaks, list):
        payload["peaks"] = []
        return
    normalized: list[dict[str, Any]] = []
    for item in peaks:
        if not isinstance(item, dict):
            continue
        peak = dict(item)
        peak["warnings"] = _coerce_list_of_strings(peak.get("warnings"))
        if not peak.get("intensity_level"):
            peak["intensity_level"] = "unknown"
        position = peak.get("position")
        if isinstance(position, str):
            try:
                peak["position"] = float(position.strip())
            except ValueError:
                peak["position"] = None
                _append_item_warning(peak, f"non_numeric_peak_position:{position}")
                warnings.append(f"xrd_peak_non_numeric_position:{position}")
        normalized.append(peak)

    normalized.sort(key=lambda peak: (peak.get("position") is None, peak.get("position") if peak.get("position") is not None else float("inf")))
    payload["peaks"] = normalized
    visible_peak_count_estimate = payload.get("visible_peak_count_estimate")
    if visible_peak_count_estimate is None and normalized:
        payload["visible_peak_count_estimate"] = len(normalized)


def _normalize_nmr_peaks(payload: dict[str, Any], warnings: list[str]) -> None:
    peaks = payload.get("peaks")
    if not isinstance(peaks, list):
        return
    normalized: list[dict[str, Any]] = []
    for item in peaks:
        if not isinstance(item, dict):
            continue
        peak = dict(item)
        peak["warnings"] = _coerce_list_of_strings(peak.get("warnings"))
        if peak.get("chemical_shift_ppm") is None and peak.get("position") is not None:
            peak["chemical_shift_ppm"] = peak.get("position")
        if not peak.get("peak_width_type"):
            peak["peak_width_type"] = "unknown"
        normalized.append(peak)
    payload["peaks"] = normalized


def _normalize_microscopy_payload(payload: dict[str, Any], warnings: list[str]) -> None:
    for field_name in ("morphology_features", "image_quality_notes"):
        _normalize_list_field(payload, warnings, field_name=field_name)
    for estimate_field, range_field in (
        ("diameter_estimate", "diameter_range"),
        ("particle_size_estimate", "particle_size_range"),
    ):
        basis_field = "diameter_basis" if estimate_field == "diameter_estimate" else "particle_size_basis"
        value = payload.get(estimate_field)
        if isinstance(value, str):
            stripped = value.strip()
            if _RANGE_PATTERN.match(stripped):
                payload[range_field] = stripped
                payload[estimate_field] = None
                warnings.append(f"{estimate_field}_range_moved_to_{range_field}")
            else:
                try:
                    payload[estimate_field] = float(stripped)
                except ValueError:
                    payload[range_field] = stripped
                    payload[estimate_field] = None
                    warnings.append(f"{estimate_field}_non_numeric_moved_to_{range_field}")
        if payload.get(estimate_field) is None and not payload.get(basis_field):
            payload.setdefault(basis_field, "not_measurable")


def _coerce_list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    text = str(value).strip()
    return [text] if text else []


def _coerce_float(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(str(value).strip())
