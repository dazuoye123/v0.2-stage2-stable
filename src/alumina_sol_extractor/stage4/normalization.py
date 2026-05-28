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
    _normalize_peak_list_field(normalized, warnings, field_name="peaks")

    if schema_name == "XRDExtraction":
        _normalize_assignment_list_field(
            normalized,
            warnings,
            field_name="phase_assignments",
            warning_code="phase_assignments_item_mapped_from_dict",
        )
        _normalize_detected_phases(normalized, warnings)
        _normalize_text_field_from_dict(
            normalized,
            warnings,
            field_name="crystallinity_trend",
            warning_code="crystallinity_trend_mapped_from_dict",
        )
        _normalize_xrd_peaks(normalized, warnings)
        _normalize_string_field_from_list(normalized, warnings, field_name="sample_name")
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
        _normalize_peak_list_field(normalized, warnings, field_name="endothermic_peaks", temperature_unit="C")
        _normalize_peak_list_field(normalized, warnings, field_name="exothermic_peaks", temperature_unit="C")
        _normalize_event_value_lists(normalized, warnings)
        _normalize_list_field(normalized, warnings, field_name="thermal_events")
    elif schema_name == "VibrationalSpectrumExtraction":
        _normalize_vibrational_peaks(normalized, warnings)
        _normalize_assignment_list_field(
            normalized,
            warnings,
            field_name="band_assignments",
            warning_code="band_assignments_item_mapped_from_dict",
        )
        _normalize_string_field_from_list(normalized, warnings, field_name="sample_name")
    elif schema_name == "NMRExtraction":
        _normalize_nmr_peaks(normalized, warnings)
        _normalize_string_field_from_list(normalized, warnings, field_name="sample_name")
    elif schema_name == "FerronCurveExtraction":
        _normalize_ferron_payload(normalized, warnings)
    elif schema_name == "UnknownFigureExtraction":
        _normalize_list_field(normalized, warnings, field_name="safe_observations")

    return normalized, warnings


def normalize_universal_extraction_payload_for_schema(
    payload: dict[str, Any],
    actual_figure_type: str,
    schema_name: str,
) -> tuple[dict[str, Any], list[str]]:
    normalized, warnings = normalize_vlm_payload_for_schema(payload, schema_name)
    if actual_figure_type == "unknown":
        normalized.setdefault("likely_figure_type", payload.get("likely_figure_type") or payload.get("figure_type"))
    return normalized, warnings


def normalize_universal_shell_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(payload)
    warnings: list[str] = []

    _normalize_list_field(normalized, warnings, field_name="warnings")
    _normalize_list_field(normalized, warnings, field_name="conflict_warnings")

    extraction = normalized.get("extraction")
    if extraction is None:
        normalized["extraction"] = {}
        warnings.append("universal_extraction_normalized_none_to_empty_dict")
    elif not isinstance(extraction, dict):
        normalized["extraction"] = {"raw_notes": str(extraction)}
        warnings.append("universal_extraction_coerced_scalar_to_dict")

    type_confidence = normalized.get("type_confidence")
    if isinstance(type_confidence, str):
        coerced = _coerce_confidence_string(type_confidence)
        if coerced is None:
            normalized["type_confidence"] = None
            warnings.append("type_confidence_cleared_from_invalid_string")
        else:
            normalized["type_confidence"] = coerced
            warnings.append("type_confidence_coerced_from_label")
    elif type_confidence is not None and not isinstance(type_confidence, (int, float)):
        normalized["type_confidence"] = None
        warnings.append("type_confidence_cleared_from_invalid_type")

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


def _normalize_peak_list_field(
    payload: dict[str, Any],
    warnings: list[str],
    *,
    field_name: str,
    temperature_unit: str | None = None,
) -> None:
    if field_name not in payload:
        payload[field_name] = []
        return
    value = payload.get(field_name)
    if value is None:
        payload[field_name] = []
        warnings.append(f"{field_name}_normalized_none_to_empty_list")
        return
    if isinstance(value, dict):
        value = [value]
        warnings.append(f"{field_name}_wrapped_dict_as_list")
    elif isinstance(value, str):
        payload[field_name] = []
        warnings.append(f"{field_name}_string_dropped_to_empty_list")
        warnings.append(f"{field_name}_coerced_to_empty_list")
        return
    elif not isinstance(value, list):
        value = [value]
        warnings.append(f"{field_name}_wrapped_scalar_as_list")

    normalized_items: list[dict[str, Any]] = []
    for item in value:
        normalized = _normalize_peak_like_item(item, warnings, field_name=field_name, temperature_unit=temperature_unit)
        if normalized is not None:
            normalized_items.append(normalized)
    payload[field_name] = normalized_items


def _normalize_assignment_list_field(
    payload: dict[str, Any],
    warnings: list[str],
    *,
    field_name: str,
    warning_code: str,
) -> None:
    value = payload.get(field_name)
    if value is None:
        payload[field_name] = []
        return
    if isinstance(value, str):
        stripped = value.strip()
        payload[field_name] = [stripped] if stripped else []
        if stripped:
            warnings.append(f"{field_name}_wrapped_string_as_list")
            warnings.append(f"{field_name}_coerced_to_list")
        return
    if isinstance(value, dict):
        value = [value]
        warnings.append(f"{field_name}_wrapped_dict_as_list")
    elif not isinstance(value, list):
        payload[field_name] = [str(value)]
        warnings.append(f"{field_name}_coerced_scalar_to_string_list")
        return

    normalized_items: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                normalized_items.append(stripped)
            continue
        if isinstance(item, dict):
            rendered = _render_assignment_dict(item)
            if rendered:
                normalized_items.append(rendered)
                warnings.append(warning_code)
            continue
        rendered = str(item).strip()
        if rendered:
            normalized_items.append(rendered)
            warnings.append(f"{field_name}_item_coerced_to_string")
    payload[field_name] = normalized_items


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
        if isinstance(value, dict):
            value = [value]
            payload[field_name] = value
            warnings.append(f"{field_name}_wrapped_dict_as_list")
        elif isinstance(value, str):
            payload[field_name] = []
            warnings.append(f"{field_name}_string_dropped_to_empty_list")
            continue
        if isinstance(value, list):
            normalized_items: list[Any] = []
            changed = False
            for item in value:
                if isinstance(item, str):
                    warnings.append(f"{field_name}_string_item_dropped")
                    changed = True
                    continue
                if not isinstance(item, dict):
                    normalized_items.append(item)
                    continue
                normalized_item = dict(item)
                event_type = normalized_item.get("event_type") or normalized_item.get("type")
                if event_type is not None and "event_type" not in normalized_item:
                    normalized_item["event_type"] = event_type
                    changed = True
                for key in ("temperature", "peak_temperature", "transition_temperature"):
                    raw = normalized_item.get(key)
                    if isinstance(raw, dict):
                        extracted = raw.get("temperature") or raw.get("value") or raw.get("temp")
                        if extracted is not None:
                            normalized_item[key] = _coerce_float(extracted)
                            warnings.append(f"{field_name}_{key}_mapped_from_dict")
                            changed = True
                    elif raw is not None and key == "temperature":
                        normalized_item.setdefault("temperature_peak", _safe_coerce_float(raw))
                        changed = True
                for key in ("mass_loss_percent", "weight_loss_percent", "residue_percent"):
                    raw = normalized_item.get(key)
                    if isinstance(raw, dict):
                        extracted = raw.get("value") or raw.get("percent")
                        if extracted is not None:
                            normalized_item[key] = _coerce_float(extracted)
                            warnings.append(f"{field_name}_{key}_mapped_from_dict")
                            changed = True
                normalized_item = _normalize_thermal_event_record(normalized_item, warnings)
                normalized_items.append(normalized_item)
            if changed:
                payload[field_name] = normalized_items


_RANGE_PATTERN = re.compile(
    r"^\s*(?P<left>-?\d+(?:\.\d+)?)\s*(?:-|–|~|to)\s*(?P<right>-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_NON_EXACT_RANGE_TEXT_PATTERN = re.compile(
    r"(?P<left>-?\d+(?:\.\d+)?)\s*(?:-|–|—|~|to)\s*(?P<right>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_APPROXIMATE_SINGLE_VALUE_PATTERN = re.compile(
    r"^\s*(?:~|≈|about|ca\.?|approx(?:imately)?)\s*-?\d+(?:\.\d+)?\s*$",
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


def _nullify_peak_position_from_non_exact_text(
    peak: dict[str, Any],
    warnings: list[str],
    *,
    raw_text: str,
    default_unit: str | None,
    warning_code: str = "range_peak_position_not_numeric",
) -> None:
    source_text = str(peak.get("source_text") or "").strip()
    if raw_text and raw_text not in source_text:
        peak["source_text"] = f"{source_text}; {raw_text}".strip("; ").strip()
    peak["position"] = None
    if default_unit and not peak.get("unit"):
        peak["unit"] = default_unit
    if peak.get("band_type") in (None, "", "unknown"):
        peak["band_type"] = "range_band"
    warning = f"{warning_code}:{raw_text}"
    _append_item_warning(peak, warning)
    warnings.append(warning)


def _source_text_requires_null_position(source_text: str) -> bool:
    stripped = source_text.strip()
    if not stripped:
        return False
    return bool(_NON_EXACT_RANGE_TEXT_PATTERN.search(stripped) or _APPROXIMATE_SINGLE_VALUE_PATTERN.match(stripped))


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
                _nullify_peak_position_from_non_exact_text(
                    peak,
                    warnings,
                    raw_text=stripped,
                    default_unit="cm^-1",
                )
            else:
                try:
                    peak["position"] = float(stripped)
                except ValueError:
                    peak["position"] = None
                    _append_item_warning(peak, f"non_numeric_peak_position:{stripped}")
                    warnings.append(f"non_numeric_peak_position:{stripped}")
        source_text = str(peak.get("source_text") or "").strip()
        if source_text and _source_text_requires_null_position(source_text):
            _nullify_peak_position_from_non_exact_text(
                peak,
                warnings,
                raw_text=source_text,
                default_unit="cm^-1",
            )
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
        source_text = str(peak.get("source_text") or "").strip()
        if source_text and _source_text_requires_null_position(source_text):
            _nullify_peak_position_from_non_exact_text(
                peak,
                warnings,
                raw_text=source_text,
                default_unit="2theta_deg",
            )
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
        range_value = payload.get(range_field)
        if isinstance(range_value, dict):
            rendered = _render_numeric_range(range_value, payload.get("diameter_unit") if "diameter" in range_field else payload.get("particle_size_unit"))
            payload[range_field] = rendered
            warnings.append(f"{range_field}_mapped_from_dict")
        elif isinstance(range_value, list):
            rendered = _render_numeric_range(range_value, payload.get("diameter_unit") if "diameter" in range_field else payload.get("particle_size_unit"))
            if rendered is None:
                payload[range_field] = None
                warnings.append(f"{range_field}_list_dropped")
            else:
                payload[range_field] = rendered
                warnings.append(f"{range_field}_mapped_from_list")
        if payload.get(estimate_field) is None and not payload.get(basis_field):
            payload.setdefault(basis_field, "not_measurable")


def _normalize_string_field_from_list(payload: dict[str, Any], warnings: list[str], *, field_name: str) -> None:
    value = payload.get(field_name)
    if value is None or isinstance(value, str):
        return
    if isinstance(value, list):
        joined = "; ".join(str(item) for item in value if item not in (None, ""))
        payload[field_name] = joined or None
        warnings.append(f"{field_name}_joined_from_list")
        return
    payload[field_name] = str(value)
    warnings.append(f"{field_name}_coerced_to_string")


def _normalize_ferron_payload(payload: dict[str, Any], warnings: list[str]) -> None:
    value = payload.get("al_species")
    if value is None:
        payload["al_species"] = []
    elif isinstance(value, str):
        payload["al_species"] = [{"species": value.strip() or None}]
        warnings.append("al_species_wrapped_string_as_species_record")
    elif isinstance(value, dict):
        payload["al_species"] = [_normalize_ferron_species_item(value, warnings)]
        warnings.append("al_species_wrapped_dict_as_list")
    elif isinstance(value, list):
        normalized_items: list[dict[str, Any]] = []
        for item in value:
            normalized = _normalize_ferron_species_item(item, warnings)
            if normalized is not None:
                normalized_items.append(normalized)
        payload["al_species"] = normalized_items
    else:
        payload["al_species"] = []
        warnings.append("al_species_dropped_from_invalid_type")

    species_quantification = payload.get("species_quantification")
    if species_quantification is None:
        payload["species_quantification"] = {}
    elif isinstance(species_quantification, dict):
        normalized_quantification: dict[str, float | None] = {}
        for key, raw_value in species_quantification.items():
            if raw_value in (None, ""):
                normalized_quantification[str(key)] = None
                continue
            coerced = _safe_coerce_float(raw_value)
            if coerced is None:
                normalized_quantification[str(key)] = None
                warnings.append(f"species_quantification_{key}_cleared_from_non_numeric")
            else:
                normalized_quantification[str(key)] = coerced
        payload["species_quantification"] = normalized_quantification
    else:
        payload["species_quantification"] = {}
        warnings.append("species_quantification_dropped_from_invalid_type")

    _normalize_string_field_from_list(payload, warnings, field_name="sample_name")


def _normalize_ferron_species_item(item: Any, warnings: list[str]) -> dict[str, Any] | None:
    if item is None:
        return None
    if isinstance(item, str):
        stripped = item.strip()
        if not stripped:
            return None
        warnings.append("al_species_item_wrapped_string_as_species_record")
        return {"species": stripped}
    if not isinstance(item, dict):
        text = str(item).strip()
        if not text:
            return None
        warnings.append("al_species_item_coerced_to_species_record")
        return {"species": text}

    normalized = dict(item)
    species = normalized.get("species") or normalized.get("assignment") or normalized.get("label") or normalized.get("name")
    if species is not None:
        normalized["species"] = str(species)
    fraction = normalized.get("fraction_percent")
    if fraction is not None:
        coerced = _safe_coerce_float(fraction)
        if coerced is None:
            normalized["fraction_percent"] = None
            warnings.append("al_species_fraction_percent_cleared_from_non_numeric")
        else:
            normalized["fraction_percent"] = coerced
    confidence = normalized.get("confidence")
    if isinstance(confidence, str):
        coerced = _coerce_confidence_string(confidence)
        if coerced is None:
            normalized["confidence"] = None
            warnings.append("al_species_confidence_cleared_from_invalid_string")
        else:
            normalized["confidence"] = coerced
            warnings.append("al_species_confidence_coerced_from_label")
    return normalized


def _render_assignment_dict(item: dict[str, Any]) -> str | None:
    primary = item.get("assignment") or item.get("description") or item.get("phase") or item.get("species")
    location = (
        item.get("wavenumber")
        or item.get("position")
        or item.get("peak_position")
        or item.get("two_theta")
        or item.get("chemical_shift")
        or item.get("chemical_shift_ppm")
    )
    if primary and location:
        return f"{location}: {primary}"
    if primary:
        return str(primary)
    if location:
        return str(location)
    source_text = item.get("source_text") or item.get("notes")
    return str(source_text) if source_text else None


def _render_numeric_range(value: Any, unit: str | None) -> str | None:
    low = high = None
    if isinstance(value, dict):
        low = value.get("min") if value.get("min") is not None else value.get("start")
        high = value.get("max") if value.get("max") is not None else value.get("end")
        unit = value.get("unit") or unit
    elif isinstance(value, list) and len(value) >= 2:
        low, high = value[0], value[1]
    if low is None or high is None:
        return None
    low_text = _format_number_or_text(low)
    high_text = _format_number_or_text(high)
    suffix = f" {unit}" if unit else ""
    return f"{low_text}-{high_text}{suffix}"


def _normalize_peak_like_item(
    item: Any,
    warnings: list[str],
    *,
    field_name: str,
    temperature_unit: str | None = None,
) -> dict[str, Any] | None:
    if isinstance(item, dict):
        peak = dict(item)
    elif isinstance(item, (int, float)) and not isinstance(item, bool):
        peak = {"position": float(item), "source_text": str(item)}
        if temperature_unit:
            peak["unit"] = temperature_unit
        warnings.append(f"{field_name}_numeric_item_mapped_to_peak_record")
    elif isinstance(item, str):
        stripped = item.strip()
        if not stripped:
            return None
        peak = {"position": None, "source_text": stripped, "warnings": [f"{field_name}_string_item_preserved_as_source_text"]}
        warnings.append(f"{field_name}_string_item_preserved_as_source_text")
    else:
        return None

    if peak.get("warnings") is None:
        peak["warnings"] = []
    elif not isinstance(peak.get("warnings"), list):
        peak["warnings"] = [str(peak.get("warnings"))]
    if temperature_unit and not peak.get("unit"):
        peak["unit"] = temperature_unit
    if "assignment" not in peak:
        assignment = peak.get("description") or peak.get("phase") or peak.get("species_assignment")
        if assignment:
            peak["assignment"] = assignment
    position = peak.get("position")
    if position is None:
        alt_position = peak.get("temperature") or peak.get("peak_temperature") or peak.get("wavenumber") or peak.get("two_theta")
        if alt_position is not None:
            numeric = _safe_coerce_float(alt_position)
            if numeric is not None:
                peak["position"] = numeric
            else:
                peak["position"] = None
                if alt_position not in (None, ""):
                    source = str(peak.get("source_text") or "").strip()
                    snippet = str(alt_position)
                    if snippet not in source:
                        peak["source_text"] = f"{source}; {snippet}".strip("; ")
                        _append_item_warning(peak, f"non_numeric_peak_position:{snippet}")
    elif isinstance(position, str):
        stripped = position.strip()
        if _RANGE_PATTERN.match(stripped):
            _nullify_peak_position_from_non_exact_text(
                peak,
                warnings,
                raw_text=stripped,
                default_unit=temperature_unit,
            )
        else:
            numeric = _safe_coerce_float(stripped)
            if numeric is None:
                peak["position"] = None
                _append_item_warning(peak, f"non_numeric_peak_position:{stripped}")
                warnings.append(f"{field_name}_non_numeric_position:{stripped}")
            else:
                peak["position"] = numeric
    source_text = str(peak.get("source_text") or "").strip()
    if source_text and _source_text_requires_null_position(source_text):
        _nullify_peak_position_from_non_exact_text(
            peak,
            warnings,
            raw_text=source_text,
            default_unit=temperature_unit,
        )
    return peak


def _normalize_thermal_event_record(item: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    normalized = dict(item)
    if normalized.get("event_type") is None and normalized.get("type") is not None:
        normalized["event_type"] = normalized.get("type")
    mapping = {
        "temperature": "temperature_peak",
        "peak_temperature": "temperature_peak",
        "temp_peak": "temperature_peak",
        "onset": "temperature_onset",
        "temperature_onset": "temperature_onset",
        "end": "temperature_end",
        "temperature_end": "temperature_end",
        "description": "assignment",
    }
    for source_key, target_key in mapping.items():
        value = normalized.get(source_key)
        if value is None:
            continue
        if target_key.startswith("temperature_"):
            coerced = _safe_coerce_float(value)
            if coerced is not None:
                normalized[target_key] = coerced
            else:
                source = str(normalized.get("source_text") or "").strip()
                snippet = str(value)
                if snippet and snippet not in source:
                    normalized["source_text"] = f"{source}; {snippet}".strip("; ")
                    warnings.append(f"thermal_event_{source_key}_range_preserved_in_source_text")
            if normalized.get("temperature_unit") is None:
                normalized["temperature_unit"] = "C"
        elif target_key == "assignment" and normalized.get("assignment") is None:
            normalized["assignment"] = str(value)
    return normalized


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


def _safe_coerce_float(value: Any) -> float | None:
    try:
        return _coerce_float(value)
    except Exception:  # noqa: BLE001
        return None


def _coerce_confidence_string(value: str) -> float | None:
    stripped = value.strip().lower()
    if not stripped:
        return None
    mapping = {
        "high": 0.9,
        "medium": 0.6,
        "moderate": 0.6,
        "low": 0.3,
    }
    if stripped in mapping:
        return mapping[stripped]
    return _safe_coerce_float(stripped)


def _format_number_or_text(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else str(numeric)
    return str(value)
