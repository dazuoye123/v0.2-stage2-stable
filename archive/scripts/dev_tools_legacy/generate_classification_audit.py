"""
Audit script v3 -- mirrors the updated infer_time_condition_type with:
  - word-boundary-safe aging matching
  - calcination_holding_time / sintering_holding_time via L2 action inference
  - measurement_time detection
  - proper priority: generic keys go through L2 before falling back
  - included_in_distribution / exclusion_reason tracking
  - is_process_time flag

Outputs:
  time_condition_classification_audit.csv  -- FULL audit for all time conditions
  (includes ALL rows, not sampled)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import numpy as np
import pandas as pd


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return " | ".join(normalize_text(item) for item in value if normalize_text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def parse_numeric_values(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0 or np.isnan(float(value)) or np.isinf(float(value)):
            return []
        return [float(value)]
    text = normalize_text(value)
    if not text:
        return []
    normalized = text.replace("～", "~").replace("—", "-").replace("–", "-").replace("至", "-")
    normalized = normalized.replace("约", "").replace("≈", "").replace("ca.", "")
    if "|" in normalized:
        parts = [p.strip() for p in normalized.split("|") if p.strip()]
        values: list[float] = []
        for part in parts:
            values.extend(parse_numeric_values(part))
        return values
    range_match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*[-~]\s*([-+]?\d+(?:\.\d+)?)\s*", normalized)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        mid = (low + high) / 2
        return [mid] if mid != 0 else []
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
    if not numbers:
        return []
    if len(numbers) == 1:
        numeric = float(numbers[0])
        return [numeric] if numeric != 0 else []
    if any(sep in normalized for sep in ["-", "~"]) and len(numbers) == 2:
        mid = (float(numbers[0]) + float(numbers[1])) / 2
        return [mid] if mid != 0 else []
    values = [float(n) for n in numbers if float(n) != 0]
    return values


# ============================================================================
# Mirror of FIXED infer_time_condition_type from build_stage3_analysis_v2.py
# ============================================================================

_AGING_EN_PATTERN = re.compile(
    r"\b(ag(?:e|ing|ed)(?:\s+for)?|ageing)\b", re.IGNORECASE
)

_MEASUREMENT_KEYWORDS = [
    "dls", "dynamic light scattering", "correlogram", "correlation function",
    "acquisition", "spectrum acquisition", "scan time", "scanning",
    "measurement time", "test time", "testing time", "characterization time",
    "检测时间", "测试时间", "测量时间", "表征时间", "采集时间",
    "xrd scan", "sem imag", "tem imag", "nmr acquis", "ftir scan",
    "raman acquis", "bet measurement", "dsc scan", "tg scan",
    "rheolog measure", "viscosity measure", "conductivity measure",
]


def _contains_aging_en(text: str) -> bool:
    return bool(_AGING_EN_PATTERN.search(text))


def infer_time_condition_type_with_audit(
    condition_key: str,
    action: str,
    evidence_text: str,
    description: str = "",
) -> tuple[str, str, str, str]:
    """
    Returns (time_type, rule_id, matched_detail, layer).
    Mirrors the FIXED infer_time_condition_type logic exactly.
    """
    key = normalize_text(condition_key).lower()
    action_lower = normalize_text(action).lower()
    combined = f"{key} {evidence_text} {description}".lower()
    combined_en = f"{evidence_text} {description}".lower()

    # ---- L1_PRECISE ----
    if any(t in key for t in ["calcination_holding", "煅烧保温"]):
        return ("calcination_holding_time", "L1_precise_calcination_holding",
                f"condition_key '{condition_key}' contains 'calcination_holding'", "L1_precise")
    if any(t in key for t in ["sintering_holding", "烧结保温"]):
        return ("sintering_holding_time", "L1_precise_sintering_holding",
                f"condition_key '{condition_key}' contains 'sintering_holding'", "L1_precise")
    if any(t in key for t in ["aging_time", "ageing_time", "老化时间", "陈化时间"]):
        matched = [t for t in ["aging_time", "ageing_time", "老化时间", "陈化时间"] if t in key]
        return ("aging_time", "L1_precise_aging",
                f"condition_key '{condition_key}' contains {matched}", "L1_precise")
    if any(t in key for t in ["drying_time", "干燥时间"]):
        return ("drying_time", "L1_precise_drying",
                f"condition_key '{condition_key}' contains 'drying_time'", "L1_precise")
    if any(t in key for t in ["calcination_time", "煅烧时间"]):
        return ("calcination_holding_time", "L1_precise_calcination_time",
                f"condition_key '{condition_key}' contains 'calcination_time'", "L1_precise")
    if any(t in key for t in ["sintering_time", "烧结时间"]):
        return ("sintering_holding_time", "L1_precise_sintering_time",
                f"condition_key '{condition_key}' contains 'sintering_time'", "L1_precise")
    if any(t in key for t in ["hydrolysis_time", "水解时间"]):
        return ("hydrolysis_time", "L1_precise_hydrolysis",
                f"condition_key '{condition_key}' contains 'hydrolysis_time'", "L1_precise")
    if any(t in key for t in ["stirring_time", "stir_time", "搅拌时间"]):
        return ("stirring_time", "L1_precise_stirring",
                f"condition_key '{condition_key}' contains 'stirring_time'/'stir_time'", "L1_precise")

    # ---- L1_MEASURE ----
    if any(t in key for t in ["measurement_time", "acquisition_time",
                               "检测时间", "测试时间", "测量时间", "采集时间"]):
        return ("measurement_time", "L1_precise_measurement",
                f"condition_key '{condition_key}' is a measurement time key", "L1_measure")
    meas_hits = [kw for kw in _MEASUREMENT_KEYWORDS if kw in combined]
    if meas_hits:
        return ("measurement_time", "L1_measurement_context",
                f"measurement context keywords: {meas_hits[:5]}", "L1_measure")

    # ---- Gate: is this a generic time key? ----
    is_generic_time_key = (
        "time" in key or "duration" in key or "时间" in key
        or "holding" in key or "保温" in key or "soaking" in key
        or "时长" in key
    )
    if not is_generic_time_key:
        return ("generic_holding_time", "L3_not_time_key",
                f"condition_key '{condition_key}' does not appear to be a time field", "L3_generic")

    # ---- L2_ACTION: calcination ----
    if action_lower in {"calcine", "calcination"}:
        return ("calcination_holding_time", "L2_action_calcine",
                f"action='{action_lower}' -> calcination_holding_time", "L2_action")
    if any(t in combined for t in ["煅烧", "焙烧", "calcination", "calcined"]):
        hits = [t for t in ["煅烧", "焙烧", "calcination", "calcined"] if t in combined]
        return ("calcination_holding_time", "L2_context_calcine",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L2_ACTION: sintering ----
    if action_lower in {"sinter", "sintering"}:
        return ("sintering_holding_time", "L2_action_sinter",
                f"action='{action_lower}' -> sintering_holding_time", "L2_action")
    if any(t in combined for t in ["烧结", "sintering", "sintered"]):
        hits = [t for t in ["烧结", "sintering", "sintered"] if t in combined]
        return ("sintering_holding_time", "L2_context_sinter",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L2_ACTION: aging (word-boundary-safe) ----
    if action_lower in {"age", "aging", "ageing", "aged"}:
        return ("aging_time", "L2_action_age",
                f"action='{action_lower}' -> aging_time", "L2_action")
    if any(t in combined for t in ["老化", "陈化"]):
        return ("aging_time", "L2_context_age_zh",
                "Chinese keyword '老化'/陈化 in evidence", "L2_action")
    if _contains_aging_en(combined_en):
        return ("aging_time", "L2_context_age_en",
                "word-boundary aging match in evidence_text", "L2_action")

    # ---- L2_ACTION: drying ----
    if action_lower in {"dry", "drying"}:
        return ("drying_time", "L2_action_dry",
                f"action='{action_lower}' -> drying_time", "L2_action")
    if any(t in combined for t in ["干燥", "drying", "dried"]):
        hits = [t for t in ["干燥", "drying", "dried"] if t in combined]
        return ("drying_time", "L2_context_dry",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L2_ACTION: hydrolysis ----
    if action_lower in {"hydrolyze", "hydrolysis"}:
        return ("hydrolysis_time", "L2_action_hydrolyze",
                f"action='{action_lower}' -> hydrolysis_time", "L2_action")
    if any(t in combined for t in ["水解", "hydroly"]):
        hits = [t for t in ["水解", "hydroly"] if t in combined]
        return ("hydrolysis_time", "L2_context_hydrolyze",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L2_ACTION: stirring ----
    if action_lower in {"stir"}:
        return ("stirring_time", "L2_action_stir",
                f"action='{action_lower}' -> stirring_time", "L2_action")
    if any(t in combined for t in ["搅拌", "stirring"]):
        hits = [t for t in ["搅拌", "stirring"] if t in combined]
        return ("stirring_time", "L2_context_stir",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L2_ACTION: heating/holding (genuine heat treatment) ----
    if action_lower in {"heat", "hold", "holding"}:
        return ("holding_time", "L2_action_heat",
                f"action='{action_lower}' -> holding_time", "L2_action")
    if any(t in combined for t in ["保温", "holding", "soaking", "热处理", "加热"]):
        hits = [t for t in ["保温", "holding", "soaking", "热处理", "加热"] if t in combined]
        return ("holding_time", "L2_context_heat",
                f"evidence keywords: {hits}", "L2_action")

    # ---- L3_GENERIC ----
    return ("generic_holding_time", "L3_generic_fallback",
            f"generic time key '{condition_key}', no specific action/context matched", "L3_generic")


def compute_confidence(rule_id: str) -> str:
    if rule_id.startswith("L1_precise"):
        return "high"
    if rule_id.startswith("L2_action") or rule_id.startswith("L2_context"):
        return "medium"
    if rule_id.startswith("L1_measure"):
        return "medium"
    if "L3" in rule_id:
        return "low"
    return "medium"


_PROCESS_TIME_TYPES = frozenset({
    "aging_time", "drying_time", "calcination_holding_time",
    "sintering_holding_time", "hydrolysis_time", "stirring_time",
    "holding_time", "generic_holding_time",
})

# Valid time units
_TIME_UNIT_TOKENS: frozenset[str] = frozenset({
    "s", "sec", "second", "seconds", "秒",
    "min", "minute", "minutes", "分钟", "min.",
    "h", "hr", "hour", "hours", "小时", "hrs",
    "d", "day", "days", "天",
})

_NON_TIME_UNIT_MARKERS: list[str] = [
    "hz", "khz", "mhz",
    "ppm",
    "cm-1", "cm−1", "cm⁻¹",
    "°c", "℃", "k",
    "mol/l", "mol·l-1", "mol·l⁻¹",
    " ml", " l",
    "rpm",
    "mpa", "gpa",
    "nm", "μm", " um",
    "m2/g", "m²/g",
    "hole", "holes",
]

# Extended temperature regex: matches 500degC, 500 °C, 500℃, 500 C, etc.
_TEMPERATURE_AFTER_NUMBER = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:deg(?:rees?\s*)?)?[°℃]?\s*[CcKk](?!\s*/)"
)
# Frequency regex: matches 10000 Hz, 52.148 MHz, etc.
_FREQUENCY_AFTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*[KkMmGg]?[Hh][Zz]")
# RPM regex
_RPM_AFTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*[Rr][Pp][Mm]")


def is_likely_time_value(
    raw_condition_value: str,
    condition_unit: str,
    evidence_text: str,
    condition_key: str = "",
) -> tuple[bool, str]:
    """
    Check if a numeric value extracted from a time-related condition_key
    is actually likely to be a time duration.

    Returns (is_time_likely, exclusion_reason_if_not).

    Priority:
    1. Non-time unit (Hz, degC, rpm, nm, etc.) in condition_unit → REJECT.
    2. Non-time context in raw_condition_value text (e.g. "500degC保温") → REJECT.
    3. Non-time context in evidence_text → REJECT.
    4. Recognized time unit in condition_unit (h, min, s, etc.) → ACCEPT.
    5. No unit, no contradictory context → ACCEPT (treat as likely time).
    """
    unit_norm = (condition_unit or "").strip().lower()
    raw_text = (raw_condition_value or "").strip().lower()
    ev_text = (evidence_text or "").strip().lower()

    # ---- STEP 1: Reject on clearly non-time condition_unit ----
    if unit_norm:
        if any(t in unit_norm for t in ["°c", "℃", "degc", "deg c", "degrees c"]):
            return (False, "non_time_unit_context")
        if any(t in unit_norm for t in ["hz", "khz", "mhz"]):
            return (False, "non_time_unit_context")
        for marker in ["ppm", "cm-1", "cm−1", "cm⁻¹", "rpm",
                       "mol/l", "mol·l", "mpa", "gpa",
                       "m2/g", "m²/g", "nm", "μm"]:
            if marker in unit_norm:
                return (False, "non_time_unit_context")

    # ---- STEP 2: Check raw condition_value text for non-time context ----
    if raw_text:
        if _TEMPERATURE_AFTER_NUMBER.search(raw_text):
            return (False, "non_time_unit_context")
        if any(t in raw_text for t in ["°c", "℃", "degc"]):
            return (False, "non_time_unit_context")
        if _FREQUENCY_AFTER_NUMBER.search(raw_text):
            return (False, "non_time_unit_context")
        if _RPM_AFTER_NUMBER.search(raw_text):
            return (False, "non_time_unit_context")
        for marker in _NON_TIME_UNIT_MARKERS:
            if marker in raw_text:
                return (False, "non_time_unit_context")

    # ---- STEP 3: Check evidence_text for contradictory context ----
    # Even if the unit says "h", the evidence may reveal upstream
    # mis-extraction (e.g. "spectral width 10000 Hz" parsed as 10000h).
    if ev_text:
        has_freq = _FREQUENCY_AFTER_NUMBER.search(ev_text)
        has_temp = _TEMPERATURE_AFTER_NUMBER.search(ev_text)
        has_rpm = _RPM_AFTER_NUMBER.search(ev_text)

        # Parse condition_value as float for proximity checks
        cond_val_num: float | None = None
        try:
            cond_val_num = float(raw_text)
        except (ValueError, TypeError):
            pass

        # If unit claims it's time but evidence shows non-time context,
        # reject when the condition_value itself matches the non-time number.
        if unit_norm in _TIME_UNIT_TOKENS:
            # Unit is valid time unit — evidence must strongly contradict to override
            if has_freq and cond_val_num is not None:
                for m in _FREQUENCY_AFTER_NUMBER.finditer(ev_text):
                    if abs(cond_val_num - float(m.group(1))) < 1e-6:
                        return (False, "non_time_unit_context")
            if has_rpm and cond_val_num is not None:
                for m in _RPM_AFTER_NUMBER.finditer(ev_text):
                    if abs(cond_val_num - float(m.group(1))) < 1e-6:
                        return (False, "non_time_unit_context")
            # For temperature in evidence when unit claims to be time: allow it
            # (e.g. "calcined at 800degC for 2 h" — the time value is fine)
            return (True, "")
        else:
            # Unit is ambiguous/empty — evidence context is critical
            if has_freq and cond_val_num is not None:
                for m in _FREQUENCY_AFTER_NUMBER.finditer(ev_text):
                    if abs(cond_val_num - float(m.group(1))) < 1e-6:
                        return (False, "non_time_unit_context")
            if has_temp and cond_val_num is not None:
                for m in _TEMPERATURE_AFTER_NUMBER.finditer(ev_text):
                    if abs(cond_val_num - float(m.group(1))) < 1e-6:
                        return (False, "non_time_unit_context")
            if has_rpm and cond_val_num is not None:
                for m in _RPM_AFTER_NUMBER.finditer(ev_text):
                    if abs(cond_val_num - float(m.group(1))) < 1e-6:
                        return (False, "non_time_unit_context")

    # ---- STEP 4: Accept if unit is a recognized time unit ----
    if unit_norm in _TIME_UNIT_TOKENS:
        return (True, "")

    # ---- STEP 5: Default accept ----
    return (True, "")


def _check_inclusion(
    val_h: float | None,
    time_type: str,
    rule_id: str,
    orig_text: str,
    raw_condition_value: str = "",
    condition_unit: str = "",
) -> tuple[bool, str]:
    """Returns (included_in_distribution, exclusion_reason)."""
    if val_h is None:
        return (False, "non_numeric_value")
    if val_h <= 0:
        return (False, "zero_or_negative_value")

    # Check for non-time unit context FIRST
    is_time, time_reason = is_likely_time_value(
        raw_condition_value, condition_unit, orig_text,
    )
    if not is_time:
        return (False, "non_time_unit_context")

    # measurement_time > 168h is extreme (check before generic 500h threshold)
    if time_type == "measurement_time" and val_h > 168:
        return (False, "extreme_measurement_time_outlier")

    if val_h > 500:
        return (False, "value_exceeds_500h_threshold")

    # calcination_holding_time > 48h: check if evidence strongly supports calcination
    if time_type == "calcination_holding_time" and val_h > 48:
        has_strong_calcine = any(t in orig_text.lower() for t in [
            "calcination", "calcined", "calcin", "煅烧", "焙烧",
        ])
        if not has_strong_calcine:
            return (False, "calcination_holding_time_exceeds_48h_no_strong_evidence")
        # Still included but flagged for review

    # Catch clearly mis-extracted values: number from non-time context
    # (e.g. "840 holes", "spectral width 10000 Hz", "500degC")
    if val_h >= 50:
        suspicious_patterns = [
            "hole", "holes", "rpm", "spectral width", " hz", "mhz",
            "°c", "temperature", "pore", "weight",
        ]
        text_lower = orig_text.lower()
        if any(kw in text_lower for kw in suspicious_patterns):
            # Check if this looks like a value mis-extracted from a non-time source
            num_str = str(int(val_h)) if val_h == int(val_h) else ""
            is_likely_misextracted = (
                (time_type == "generic_holding_time" and val_h >= 100) or
                (time_type == "measurement_time" and val_h >= 100) or
                (time_type == "calcination_holding_time" and val_h > 200)
            )
            if is_likely_misextracted:
                return (False, "value_likely_misextracted_from_non_time_context")

    return (True, "")


def _is_process_time(time_type: str) -> bool:
    return time_type in _PROCESS_TIME_TYPES


# ============================================================================
# Main audit
# ============================================================================

def generate_time_audit_full(output_dir: Path) -> pd.DataFrame:
    """
    Read process_condition_distribution.csv and generate FULL time type audit.
    Adds included_in_distribution, exclusion_reason, and is_process_time columns.
    """
    print("Generating FULL time condition classification audit...")

    analysis_dir = PROJECT_ROOT / "data" / "analysis_outputs_stage3"
    process_conditions = pd.read_csv(analysis_dir / "process_condition_distribution.csv")

    audit_rows: list[dict[str, Any]] = []
    total_time_conditions = 0
    skipped_non_time = 0

    for _, row in process_conditions.iterrows():
        condition_key = normalize_text(row.get("condition_key"))
        key_lower = condition_key.lower()

        is_time = any(t in key_lower for t in [
            "time", "duration", "时间", "时长", "holding", "保温",
        ])
        if not is_time:
            skipped_non_time += 1
            continue

        total_time_conditions += 1

        raw_value = row.get("condition_value")
        raw_unit = normalize_text(row.get("condition_unit"))
        raw_action = normalize_text(row.get("action"))
        raw_evidence = normalize_text(row.get("evidence_text") or row.get("source_text"))
        raw_description = normalize_text(row.get("description")) if "description" in row else ""

        time_type, rule_id, matched_detail, layer = infer_time_condition_type_with_audit(
            condition_key, raw_action, raw_evidence, raw_description,
        )

        values = parse_numeric_values(raw_value)
        unit_norm = raw_unit.lower().replace("℃", "c").replace("°c", "c").replace("ºc", "c")
        unit_norm = unit_norm.replace("k/min", "c/min")

        source_fields = "condition_key"
        if "L2" in layer:
            source_fields = "condition_key, action, evidence_text"

        is_proc = _is_process_time(time_type)

        if not values:
            included, excl_reason = _check_inclusion(
                None, time_type, rule_id, raw_evidence,
                raw_condition_value=str(raw_value)[:200],
                condition_unit=raw_unit,
            )
            audit_rows.append({
                "paper_id": row.get("paper_id"),
                "source_file": "process_condition_distribution.csv",
                "original_text": raw_evidence[:300],
                "original_key": condition_key,
                "original_action": raw_action if raw_action else "(empty)",
                "original_value_raw": str(raw_value)[:100],
                "normalized_value": None,
                "unit": raw_unit if raw_unit else "(empty)",
                "final_type": time_type,
                "matched_rule_id": rule_id,
                "matched_keywords": matched_detail[:200],
                "source_fields_used": source_fields,
                "classification_layer": layer,
                "confidence": compute_confidence(rule_id),
                "needs_manual_review": "true (non-numeric value)",
                "is_process_time": is_proc,
                "included_in_distribution": included,
                "exclusion_reason": excl_reason,
                "category": row.get("category"),
                "step_order": row.get("step_order", 0),
            })
            continue

        for val in values:
            if "min" in unit_norm and "c/min" not in unit_norm:
                val_h = val / 60.0
            elif "s" in unit_norm and "c/min" not in unit_norm:
                val_h = val / 3600.0
            else:
                val_h = val

            val_h = round(float(val_h), 4)
            included, excl_reason = _check_inclusion(
                val_h, time_type, rule_id, raw_evidence,
                raw_condition_value=str(raw_value)[:200],
                condition_unit=raw_unit,
            )

            review = "false"
            if not included:
                review = f"true (excluded: {excl_reason})"
            elif layer == "L3_generic":
                review = "true (generic fallback)"
            elif time_type == "calcination_holding_time" and val_h > 48:
                review = "true (calcination_holding_time > 48h, review recommended)"

            audit_rows.append({
                "paper_id": row.get("paper_id"),
                "source_file": "process_condition_distribution.csv",
                "original_text": raw_evidence[:300],
                "original_key": condition_key,
                "original_action": raw_action if raw_action else "(empty)",
                "original_value_raw": str(raw_value)[:100],
                "normalized_value": val_h,
                "unit": raw_unit if raw_unit else "(empty)",
                "final_type": time_type,
                "matched_rule_id": rule_id,
                "matched_keywords": matched_detail[:200],
                "source_fields_used": source_fields,
                "classification_layer": layer,
                "confidence": compute_confidence(rule_id),
                "needs_manual_review": review,
                "is_process_time": is_proc,
                "included_in_distribution": included,
                "exclusion_reason": excl_reason,
                "category": row.get("category"),
                "step_order": row.get("step_order", 0),
            })

    df = pd.DataFrame(audit_rows)
    output_path = output_dir / "time_condition_classification_audit.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  Total time conditions found: {total_time_conditions}")
    print(f"  Skipped (non-time keys): {skipped_non_time}")
    print(f"  Audit rows written: {len(df)}")
    print(f"  Output: {output_path}")

    return df


def main() -> None:
    output_dir = PROJECT_ROOT / "data" / "analysis_outputs_stage3_v2"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Generating FULL Time Condition Classification Audit (v3)")
    print("=" * 70)

    df = generate_time_audit_full(output_dir)

    # ---- Summary by time_type ----
    print("\n=== Full Audit Summary (with inclusion/exclusion) ===")
    print(f"Total audit rows: {len(df)}")
    print(f"Unique time_types: {df['final_type'].nunique()}")
    print()
    print(f"{'time_type':<30} {'audit_N':>7} {'dist_N':>7} {'excl_N':>7} {'high':>6} {'med':>6} {'low':>6} {'is_proc':>8}")
    print("-" * 90)

    summary_by_type: dict[str, dict[str, Any]] = {}
    for tt in sorted(df["final_type"].unique()):
        subset = df[df["final_type"] == tt]
        audit_all = len(subset)
        included = subset[subset["included_in_distribution"] == True]
        excluded = subset[subset["included_in_distribution"] == False]
        dist_n = len(included)
        excl_n = len(excluded)
        high = int((subset["confidence"] == "high").sum())
        med = int((subset["confidence"] == "medium").sum())
        low = int((subset["confidence"] == "low").sum())
        is_proc = _is_process_time(tt)

        # Exclusion reasons breakdown
        excl_reasons: dict[str, int] = {}
        for _, erow in excluded.iterrows():
            reason = str(erow.get("exclusion_reason", "unknown"))
            excl_reasons[reason] = excl_reasons.get(reason, 0) + 1

        summary_by_type[tt] = {
            "audit_N": audit_all,
            "distribution_N": dist_n,
            "excluded_N": excl_n,
            "confidence": {"high": high, "medium": med, "low": low},
            "exclusion_reasons": excl_reasons,
            "is_process_time": is_proc,
        }

        print(f"{tt:<30} {audit_all:>7} {dist_n:>7} {excl_n:>7} {high:>6} {med:>6} {low:>6} {str(is_proc):>8}")

    # Per-type exclusion detail
    print("\n=== Exclusion Reasons per Type ===")
    for tt in sorted(summary_by_type.keys()):
        info = summary_by_type[tt]
        if info["excluded_N"] > 0:
            print(f"  {tt}: excluded={info['excluded_N']}")
            for reason, count in sorted(info["exclusion_reasons"].items(), key=lambda x: -x[1]):
                print(f"      {reason}: {count}")

    # Non-numeric values
    nonnum = df[df["normalized_value"].isna()]
    print(f"\n=== Non-numeric value rows: {len(nonnum)} ===")
    for tt in sorted(nonnum["final_type"].unique()):
        subset = nonnum[nonnum["final_type"] == tt]
        print(f"  {tt}: {len(subset)} rows")

    # Show sample evidence_text per type (included only)
    print("\n=== Sample evidence_text per time_type (up to 10, included only) ===")
    included_df = df[df["included_in_distribution"] == True]
    for tt in sorted(included_df["final_type"].unique()):
        print(f"\n--- {tt} (N={len(included_df[included_df['final_type']==tt])}) ---")
        subset = included_df[included_df["final_type"] == tt].head(10)
        for _, row in subset.iterrows():
            text = str(row["original_text"])[:120]
            val = row["normalized_value"]
            action = str(row["original_action"])[:20]
            rule = row["matched_rule_id"]
            incl = row["included_in_distribution"]
            print(f"  [{action}] {text} | val={val:.2f}h | rule={rule} | incl={incl}")

    # Excluded samples (extreme outliers)
    print("\n=== Excluded outlier samples (up to 5 per type) ===")
    excluded_df = df[df["included_in_distribution"] == False]
    for tt in sorted(excluded_df["final_type"].unique()):
        subset = excluded_df[excluded_df["final_type"] == tt]
        if len(subset) == 0:
            continue
        print(f"\n--- {tt} (excluded={len(subset)}) ---")
        for _, row in subset.head(5).iterrows():
            text = str(row["original_text"])[:150]
            val = row["normalized_value"]
            excl = row["exclusion_reason"]
            print(f"  paper={row['paper_id'][:50]} | val={val} | reason={excl}")
            print(f"  text: {text}")

    # Aging word-boundary safety check
    print("\n=== Aging word-boundary safety check ===")
    aging_rows = df[df["final_type"] == "aging_time"]
    aging_l2 = aging_rows[aging_rows["matched_rule_id"].str.contains("L2_context_age_en", na=False)]
    print(f"  Aging via L2_context_age_en (word-boundary match): {len(aging_l2)} rows")
    if len(aging_l2) > 0:
        for _, row in aging_l2.head(5).iterrows():
            print(f"    [{str(row['paper_id'])[:50]}] text: {str(row['original_text'])[:100]}")


if __name__ == "__main__":
    import io as _io
    import sys as _sys
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
