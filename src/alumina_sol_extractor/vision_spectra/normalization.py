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
    elif schema_name == "MicroscopyExtraction":
        _normalize_scale_bar(normalized, warnings)

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
