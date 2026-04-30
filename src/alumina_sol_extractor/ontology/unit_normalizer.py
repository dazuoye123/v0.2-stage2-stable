"""Unit normalization helpers for Stage 3."""

from __future__ import annotations

from typing import Any


def normalize_unit_value(
    value: float | int | str | None,
    unit: str | None,
    target_unit: str | None = None,
) -> dict[str, Any]:
    """Normalize a value/unit pair conservatively.

    Returns a dict with:
    - value
    - unit
    - normalization_note
    """

    note: str | None = None
    if value is None or unit is None or target_unit is None or unit == target_unit:
        return {"value": value, "unit": target_unit or unit, "normalization_note": note}

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return {
            "value": value,
            "unit": unit,
            "normalization_note": "non_numeric_value_kept_raw",
        }

    source = unit.strip()
    target = target_unit.strip()
    converted = _convert_numeric_value(numeric_value, source, target)
    if converted is None:
        return {
            "value": value,
            "unit": unit,
            "normalization_note": f"unsupported_conversion:{source}->{target}",
        }

    note = f"converted:{source}->{target}"
    return {"value": converted, "unit": target, "normalization_note": note}


def _convert_numeric_value(value: float, source: str, target: str) -> float | None:
    if source == "GPa" and target == "MPa":
        return value * 1000
    if source == "kPa" and target == "MPa":
        return value / 1000
    if source in {"℃/h", "°C/h", "C/h"} and target in {"℃/min", "°C/min", "C/min"}:
        return value / 60
    if source == "min" and target == "h":
        return value / 60
    if source == "s" and target == "h":
        return value / 3600
    if source == "cm" and target == "m":
        return value / 100
    if source in {"μm", "um"} and target == "nm":
        return value * 1000
    if source == "nm" and target in {"μm", "um"}:
        return value / 1000
    return None
