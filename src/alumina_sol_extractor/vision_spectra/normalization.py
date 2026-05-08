"""Schema-specific normalization helpers for Stage 4 VLM outputs."""

from __future__ import annotations

from typing import Any


def normalize_vlm_payload_for_schema(payload: dict[str, Any], schema_name: str) -> tuple[dict[str, Any], list[str]]:
    """Normalize half-compliant VLM JSON before Pydantic validation.

    The goal is not to silently accept arbitrary output, but to catch a small
    set of known, explainable shape mismatches.
    """

    normalized = dict(payload)
    warnings: list[str] = []

    if schema_name == "XRDExtraction":
        _normalize_detected_phases(normalized, warnings)
        _normalize_text_field_from_dict(
            normalized,
            warnings,
            field_name="crystallinity_trend",
            warning_code="crystallinity_trend_mapped_from_dict",
        )
    elif schema_name == "MicroscopyExtraction":
        _normalize_scale_bar(normalized, warnings)
    elif schema_name == "ThermalAnalysisExtraction":
        _normalize_temperature_list(
            normalized,
            warnings,
            field_name="transition_temperatures",
            warning_code="transition_temperatures_item_mapped_from_dict",
        )

    return normalized, warnings


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


def _coerce_float(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(str(value).strip())
