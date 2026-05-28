from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle


SUMMARY_CANDIDATES = ("stage3_summary.json",)
RECORD_CANDIDATES = ("paper_record.json", "stage3_extraction.json", "paper_extraction.schema_v2.json")
PROCEDURE_SECTION_CANDIDATES = ("stage3_procedure_sections.json",)
TRIM_REPORT_CANDIDATES = (
    "stage3_text/markdown_trim_report.json",
    "../stage3_text/markdown_trim_report.json",
    "markdown_trim_report.json",
)
CLEANED_BODY_CANDIDATES = (
    "stage3_text/cleaned_body.md",
    "../stage3_text/cleaned_body.md",
    "cleaned_body.md",
)
JSONL_CANDIDATES = {
    "data_points": ("data_points.jsonl",),
    "process_steps": ("process_steps.jsonl",),
    "evidence_objects": ("evidence_objects.jsonl",),
    "experiment_series": ("experiment_series.jsonl",),
}
FILE_LABELS = {
    "stage3_summary": SUMMARY_CANDIDATES,
    "record": RECORD_CANDIDATES,
    "procedure_sections": PROCEDURE_SECTION_CANDIDATES,
    "trim_report": TRIM_REPORT_CANDIDATES,
    "cleaned_body": CLEANED_BODY_CANDIDATES,
    "data_points_jsonl": JSONL_CANDIDATES["data_points"],
    "process_steps_jsonl": JSONL_CANDIDATES["process_steps"],
    "evidence_objects_jsonl": JSONL_CANDIDATES["evidence_objects"],
    "experiment_series_jsonl": JSONL_CANDIDATES["experiment_series"],
}
ACTION_ZH_FALLBACK = {
    "other": "其他",
    "stir": "搅拌",
    "heat": "升温保温",
    "dry": "干燥",
    "electrospin": "静电纺丝",
    "spin": "纺丝",
    "hydrolyze": "水解",
    "add": "加入",
    "dissolve": "溶解",
    "age": "老化",
    "prepare": "制备",
    "calcine": "煅烧",
    "sinter": "烧结",
    "add_polymer": "加入聚合物",
    "mix": "混合",
    "cool": "冷却",
    "filter": "过滤",
    "impregnate": "浸渍",
    "wash": "洗涤",
    "weigh": "称取",
    "load": "负载",
    "collect": "收集",
    "reduce": "还原",
    "inject": "注入",
}
ACTION_MARKERS = (
    "weigh",
    "add",
    "dropwise",
    "dissolve",
    "mix",
    "stir",
    "age",
    "hydrolyze",
    "filter",
    "wash",
    "dry",
    "prepare",
    "spin",
    "electrospin",
    "calcine",
    "heat",
    "sinter",
    "cool",
    "impregnate",
    "load",
    "reduce",
    "称取",
    "加入",
    "滴加",
    "溶解",
    "混合",
    "搅拌",
    "老化",
    "水解",
    "过滤",
    "洗涤",
    "干燥",
    "制备",
    "纺丝",
    "静电纺丝",
    "煅烧",
    "升温",
    "烧结",
    "冷却",
    "浸渍",
    "负载",
    "还原",
)
STAGE_ROUTE_LABELS = {
    "sol_prep": "溶胶制备",
    "aging_concentration": "老化/浓缩",
    "spinning": "纺丝",
    "drying": "干燥",
    "calcination_sintering": "煅烧/烧结",
    "characterization": "表征/性能",
    "other": "其他",
}
PPT_RECOMMENDED_FIGURES = [
    "stage3_pipeline_funnel",
    "parameter_distribution_top30_bar",
    "canonical_key_category_heatmap",
    "process_step_action_distribution",
    "sample_parameter_matrix_sparsity_heatmap",
]
METHODOLOGY_RECOMMENDED_FIGURES = [
    "stage3_pipeline_funnel",
    "process_route_sankey",
    "process_condition_distribution",
    "canonical_key_category_heatmap",
    "stage3_overview_dashboard",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 3 analysis tables and figures from existing outputs.")
    parser.add_argument("--manifest", default="data/batch_manifest/source_manifest.csv", help="Source manifest CSV path.")
    parser.add_argument("--outputs-dir", default="data/outputs", help="Base outputs directory.")
    parser.add_argument(
        "--output-dir",
        default="data/analysis_outputs_stage3",
        help="Directory for analysis CSV/JSON/figure outputs.",
    )
    parser.add_argument("--stage3-subdir", default="stage3_twopass", help="Stage3 subdirectory name.")
    parser.add_argument("--top-n", default=30, type=int, help="Top N canonical keys/actions to visualize.")
    return parser.parse_args()


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(path_value: str | Path, *, base_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def first_existing(base_dir: Path, candidates: Iterable[str]) -> Path | None:
    for candidate in candidates:
        path = (base_dir / candidate).resolve()
        if path.exists():
            return path
    return None


def read_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path or not path.exists():
        return rows
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def read_text(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        try:
            return float(text)
        except Exception:
            return None
    return None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (list, tuple)):
        return " | ".join(normalize_text(item) for item in value if normalize_text(item))
    if isinstance(value, dict):
        parts = []
        for key in ("value", "text", "name", "label", "quote_or_context"):
            part = normalize_text(value.get(key))
            if part:
                parts.append(part)
        if parts:
            return " | ".join(dict.fromkeys(parts))
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def truncate_text(value: str, limit: int = 160) -> str:
    value = normalize_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def pick_first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def stringify_json(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def top_examples(values: Iterable[str], limit: int = 5) -> str:
    cleaned = [normalize_text(value) for value in values if normalize_text(value)]
    if not cleaned:
        return ""
    counter = Counter(cleaned)
    return " | ".join(item for item, _ in counter.most_common(limit))


def value_as_numeric_and_text(value: Any, *, min_value: Any = None, max_value: Any = None) -> tuple[float | None, str]:
    numeric = safe_float(value)
    if numeric is not None:
        return numeric, ""
    if min_value not in (None, "") or max_value not in (None, ""):
        range_text = " ~ ".join(part for part in [normalize_text(min_value), normalize_text(max_value)] if part)
        return None, range_text
    if isinstance(value, list):
        parts = [normalize_text(item) for item in value if normalize_text(item)]
        return None, " | ".join(parts)
    if isinstance(value, dict):
        return None, normalize_text(value)
    return None, normalize_text(value)


def normalize_evidence_refs(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def evidence_refs_to_text(value: Any) -> str:
    refs = normalize_evidence_refs(value)
    parts: list[str] = []
    for item in refs:
        if isinstance(item, dict):
            rendered = pick_first_non_empty(
                item.get("quote_or_context"),
                item.get("figure_id"),
                item.get("table_id"),
                item.get("section"),
                item.get("source_id"),
            )
            text = normalize_text(rendered)
            if text:
                parts.append(text)
        else:
            text = normalize_text(item)
            if text:
                parts.append(text)
    return " | ".join(dict.fromkeys(parts))


def evidence_ref_count(value: Any) -> int:
    return len([item for item in normalize_evidence_refs(value) if normalize_text(item)])


def action_zh_for(action: str, action_zh: str = "") -> str:
    action_zh = normalize_text(action_zh)
    if action_zh:
        return action_zh
    return ACTION_ZH_FALLBACK.get(normalize_text(action).lower(), action or "其他")


def infer_quality_flag(*, stage3_status: str, summary: dict[str, Any], process_warning: bool) -> str:
    flags = [normalize_text(item) for item in (summary.get("quality_flags") or []) if normalize_text(item)]
    if stage3_status != "success":
        flags.insert(0, "stage3_failed")
    if process_warning:
        flags.append("process_steps_warning")
    if not flags:
        return "ok"
    return "; ".join(dict.fromkeys(flags))


def infer_condition_rows(
    *,
    category: str,
    paper_id: str,
    step: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    action = normalize_text(step.get("action")).lower()
    action_zh = action_zh_for(action, normalize_text(step.get("action_zh")))
    step_order = safe_int(step.get("step_order"), default=0)
    evidence_text = normalize_text(pick_first_non_empty(step.get("evidence_text"), step.get("description")))

    def add_row(condition_key: str, value: Any, unit: Any = "", *, source_kind: str = "step_field") -> None:
        display_value = safe_float(value)
        normalized_value = display_value if display_value is not None else normalize_text(value)
        if normalized_value in ("", None):
            return
        rows.append(
            {
                "category": category,
                "paper_id": paper_id,
                "step_order": step_order,
                "action": action or "other",
                "action_zh": action_zh,
                "condition_key": condition_key,
                "condition_value": normalized_value,
                "condition_unit": normalize_text(unit),
                "source_text": evidence_text,
                "evidence_text": evidence_text,
                "source_kind": source_kind,
            }
        )

    if step.get("temperature_value") not in (None, ""):
        if action == "calcine":
            key = "calcination_temperature"
        elif action == "sinter":
            key = "sintering_temperature"
        elif action == "dry":
            key = "drying_temperature"
        elif action == "age":
            key = "aging_temperature"
        else:
            key = "temperature"
        add_row(key, step.get("temperature_value"), step.get("temperature_unit"), source_kind="temperature_value")

    if step.get("duration_value") not in (None, ""):
        if action in {"calcine", "sinter", "heat"}:
            key = "holding_time"
        elif action == "dry":
            key = "drying_time"
        elif action == "age":
            key = "aging_time"
        else:
            key = "duration"
        add_row(key, step.get("duration_value"), step.get("duration_unit"), source_kind="duration_value")

    if step.get("heating_rate_value") not in (None, ""):
        add_row("heating_rate", step.get("heating_rate_value"), step.get("heating_rate_unit"), source_kind="heating_rate_value")

    explicit_key = normalize_text(step.get("condition_key"))
    if explicit_key:
        add_row(explicit_key, step.get("condition_value"), step.get("condition_unit"), source_kind="condition_key")

    parameters = step.get("parameters")
    if isinstance(parameters, dict):
        for key, value in parameters.items():
            add_row(normalize_text(key), value, "", source_kind="parameters")
    return rows


def map_action_to_route_stage(action: str) -> str:
    action = normalize_text(action).lower()
    if action in {"prepare", "add", "dissolve", "mix", "stir", "hydrolyze", "add_polymer", "weigh"}:
        return "sol_prep"
    if action in {"age", "filter", "cool", "collect"}:
        return "aging_concentration"
    if action in {"spin", "electrospin", "inject"}:
        return "spinning"
    if action in {"dry", "wash"}:
        return "drying"
    if action in {"calcine", "sinter", "heat", "reduce"}:
        return "calcination_sintering"
    if action in {"load", "impregnate"}:
        return "characterization"
    return "other"


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def flatten_dict_leaves(value: Any, *, prefix: str = "") -> list[tuple[str, Any]]:
    leaves: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = normalize_text(key)
            new_prefix = f"{prefix}.{key_text}" if prefix else key_text
            if isinstance(item, dict):
                leaves.extend(flatten_dict_leaves(item, prefix=new_prefix))
            else:
                leaves.append((key_text, item))
    return leaves


def collect_data_points_from_record(record: dict[str, Any], jsonl_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(record.get("data_points"), list):
        return [item for item in record["data_points"] if isinstance(item, dict)]
    rows = list(jsonl_rows)
    experiment_series = record.get("experiment_series")
    if isinstance(experiment_series, list):
        for series in experiment_series:
            if not isinstance(series, dict):
                continue
            series_points = series.get("data_points")
            if isinstance(series_points, list):
                rows.extend(item for item in series_points if isinstance(item, dict))
    return rows


def collect_experiment_series(record: dict[str, Any], jsonl_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(record.get("experiment_series"), list):
        return [item for item in record["experiment_series"] if isinstance(item, dict)]
    return [item for item in jsonl_rows if isinstance(item, dict)]


def collect_process_steps(record: dict[str, Any], jsonl_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(record.get("process_steps"), list):
        return [item for item in record["process_steps"] if isinstance(item, dict)]
    return [item for item in jsonl_rows if isinstance(item, dict)]


def collect_evidence_objects(record: dict[str, Any], jsonl_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(record.get("evidence_objects"), list):
        return [item for item in record["evidence_objects"] if isinstance(item, dict)]
    return [item for item in jsonl_rows if isinstance(item, dict)]


def collect_samples(record: dict[str, Any], experiment_series: list[dict[str, Any]], data_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("samples", "sample_records", "sample_set"):
        value = record.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    for series in experiment_series:
        for key in ("samples", "sample_records", "sample_set"):
            value = series.get(key)
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
    if not candidates:
        for point in data_points:
            sample_id = normalize_text(pick_first_non_empty(point.get("sample_id"), point.get("sample_label")))
            if not sample_id:
                continue
            candidates.append(
                {
                    "sample_id": sample_id,
                    "sample_name": normalize_text(point.get("sample_label")) or sample_id,
                    "sample_role": normalize_text(point.get("sample_role")),
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        sample_id = normalize_text(pick_first_non_empty(item.get("sample_id"), item.get("id"), item.get("sample_name"), item.get("name")))
        if not sample_id:
            continue
        deduped.setdefault(
            sample_id,
            {
                "sample_id": sample_id,
                "sample_name": normalize_text(pick_first_non_empty(item.get("sample_name"), item.get("name"), sample_id)),
                "sample_role": normalize_text(item.get("sample_role")),
            },
        )
    return list(deduped.values())


def extract_parameter_rows(
    *,
    category: str,
    paper_id: str,
    data_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for index, point in enumerate(data_points, start=1):
        sample_id = normalize_text(point.get("sample_id")) or f"{paper_id}_sample_{index}"
        sample_name = normalize_text(point.get("sample_label")) or sample_id
        point_source = normalize_text(
            pick_first_non_empty(
                point.get("source_text"),
                point.get("evidence_text"),
                point.get("context"),
                point.get("source_context"),
                evidence_refs_to_text(point.get("evidence_refs")),
            )
        )
        point_evidence = point.get("evidence_refs")
        needs_manual_review = parse_bool(point.get("needs_manual_review"))

        additional_records = point.get("additional_parameter_records")
        if isinstance(additional_records, list):
            for record in additional_records:
                if not isinstance(record, dict):
                    continue
                canonical_key = normalize_text(
                    pick_first_non_empty(record.get("canonical_key"), record.get("key"), record.get("raw_name"))
                )
                if not canonical_key:
                    continue
                numeric_value, value_text = value_as_numeric_and_text(
                    record.get("value"),
                    min_value=record.get("min_value"),
                    max_value=record.get("max_value"),
                )
                source_text = normalize_text(
                    pick_first_non_empty(
                        record.get("source_text"),
                        record.get("raw_text"),
                        point_source,
                    )
                )
                evidence_refs = normalize_evidence_refs(record.get("evidence_refs") or point_evidence)
                dedupe_key = (
                    sample_id,
                    canonical_key,
                    normalize_text(record.get("raw_name")) or canonical_key,
                    str(numeric_value if numeric_value is not None else ""),
                    value_text,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                rows.append(
                    {
                        "category": category,
                        "paper_id": paper_id,
                        "sample_id": sample_id,
                        "sample_name": sample_name,
                        "canonical_key": canonical_key,
                        "raw_name": normalize_text(record.get("raw_name")) or canonical_key,
                        "value": numeric_value,
                        "value_text": value_text,
                        "unit": normalize_text(record.get("unit")),
                        "source_text": source_text,
                        "evidence_refs": stringify_json(evidence_refs),
                        "needs_manual_review": parse_bool(record.get("needs_manual_review")) or needs_manual_review,
                    }
                )

        for bucket_name in ("process_parameters", "results"):
            bucket = point.get(bucket_name)
            if not isinstance(bucket, dict):
                continue
            for canonical_key, raw_value in flatten_dict_leaves(bucket):
                numeric_value, value_text = value_as_numeric_and_text(raw_value)
                dedupe_key = (
                    sample_id,
                    canonical_key,
                    canonical_key,
                    str(numeric_value if numeric_value is not None else ""),
                    value_text,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                rows.append(
                    {
                        "category": category,
                        "paper_id": paper_id,
                        "sample_id": sample_id,
                        "sample_name": sample_name,
                        "canonical_key": canonical_key,
                        "raw_name": canonical_key,
                        "value": numeric_value,
                        "value_text": value_text,
                        "unit": "",
                        "source_text": point_source,
                        "evidence_refs": stringify_json(normalize_evidence_refs(point_evidence)),
                        "needs_manual_review": needs_manual_review,
                    }
                )
    return rows


def compute_process_step_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not steps:
        return {
            "warning_count": 1,
            "other_ratio": 1.0,
            "missing_evidence_ratio": 1.0,
            "warning": True,
        }
    other_count = 0
    missing_evidence_count = 0
    generic_count = 0
    for step in steps:
        action = normalize_text(step.get("action")).lower()
        evidence_text = normalize_text(step.get("evidence_text"))
        description = normalize_text(step.get("description"))
        source = f"{evidence_text} {description}".strip().lower()
        if action == "other":
            other_count += 1
        if not evidence_text:
            missing_evidence_count += 1
        if source and not any(marker in source for marker in ACTION_MARKERS):
            generic_count += 1
    count = len(steps)
    other_ratio = round(other_count / count, 4)
    missing_ratio = round(missing_evidence_count / count, 4)
    warning = other_ratio >= 0.3 or missing_ratio >= 0.5 or generic_count / count >= 0.25
    return {
        "warning_count": int(warning),
        "other_ratio": other_ratio,
        "missing_evidence_ratio": missing_ratio,
        "warning": warning,
    }


def determine_stage3_status(summary: dict[str, Any] | None) -> str:
    if not isinstance(summary, dict):
        return "failure"
    return "success" if bool(summary.get("schema_valid", True)) else "failure"


def load_stage3_paper(
    *,
    category: str,
    paper_id: str,
    paper_output_dir: Path,
    stage3_subdir: str,
) -> dict[str, Any]:
    stage3_dir = (paper_output_dir / stage3_subdir).resolve()
    file_paths: dict[str, Path | None] = {}
    missing_labels: list[str] = []
    unreadable_labels: list[str] = []

    for label, candidates in FILE_LABELS.items():
        file_paths[label] = first_existing(stage3_dir, candidates)
        if file_paths[label] is None:
            missing_labels.append(label)

    summary = read_json(file_paths["stage3_summary"])
    if file_paths["stage3_summary"] and summary is None:
        unreadable_labels.append("stage3_summary")
    record = read_json(file_paths["record"]) or {}
    if file_paths["record"] and not record:
        unreadable_labels.append("record")
    if not isinstance(record, dict):
        record = {}
    procedure_sections = read_json(file_paths["procedure_sections"])
    if file_paths["procedure_sections"] and procedure_sections is None:
        unreadable_labels.append("procedure_sections")
    trim_report = read_json(file_paths["trim_report"])
    if file_paths["trim_report"] and trim_report is None:
        unreadable_labels.append("trim_report")
    cleaned_body = read_text(file_paths["cleaned_body"])
    if file_paths["cleaned_body"] and cleaned_body == "":
        unreadable_labels.append("cleaned_body")

    data_points_jsonl = read_jsonl(file_paths["data_points_jsonl"])
    process_steps_jsonl = read_jsonl(file_paths["process_steps_jsonl"])
    evidence_objects_jsonl = read_jsonl(file_paths["evidence_objects_jsonl"])
    experiment_series_jsonl = read_jsonl(file_paths["experiment_series_jsonl"])

    experiment_series = collect_experiment_series(record, experiment_series_jsonl)
    data_points = collect_data_points_from_record(record, data_points_jsonl)
    process_steps = collect_process_steps(record, process_steps_jsonl)
    evidence_objects = collect_evidence_objects(record, evidence_objects_jsonl)
    samples = collect_samples(record, experiment_series, data_points)
    parameter_rows = extract_parameter_rows(category=category, paper_id=paper_id, data_points=data_points)
    process_metrics = compute_process_step_metrics(process_steps)

    summary_payload = summary if isinstance(summary, dict) else {}
    cleaned_body_chars = len(cleaned_body) or safe_int(summary_payload.get("cleaned_body_char_count"))
    stage3_status = determine_stage3_status(summary_payload)
    quality_flag = infer_quality_flag(
        stage3_status=stage3_status,
        summary=summary_payload,
        process_warning=process_metrics["warning"],
    )
    canonical_key_errors_count = safe_int(summary_payload.get("canonical_key_errors_count"))
    rejected_parameter_records_count = safe_int(summary_payload.get("rejected_parameter_records_count"))

    return {
        "category": category,
        "paper_id": paper_id,
        "stage3_status": stage3_status,
        "data_point_count": safe_int(summary_payload.get("data_point_count"), len(data_points)) or len(data_points),
        "process_steps_count": safe_int(summary_payload.get("process_steps_count"), len(process_steps)) or len(process_steps),
        "evidence_object_count": safe_int(summary_payload.get("evidence_object_count"), len(evidence_objects))
        or len(evidence_objects),
        "sample_count": len(samples),
        "experiment_series_count": safe_int(summary_payload.get("experiment_series_count"), len(experiment_series))
        or len(experiment_series),
        "canonical_key_errors_count": canonical_key_errors_count,
        "rejected_parameter_records_count": rejected_parameter_records_count,
        "process_steps_warning_count": safe_int(
            summary_payload.get("process_steps_warning_count"),
            process_metrics["warning_count"],
        ),
        "process_steps_other_action_ratio": summary_payload.get(
            "process_steps_other_action_ratio",
            process_metrics["other_ratio"],
        ),
        "process_steps_missing_evidence_ratio": summary_payload.get(
            "process_steps_missing_evidence_ratio",
            process_metrics["missing_evidence_ratio"],
        ),
        "cleaned_body_chars": cleaned_body_chars,
        "input_truncated": parse_bool(summary_payload.get("input_truncated")),
        "truncation_reason": normalize_text(
            pick_first_non_empty(summary_payload.get("truncation_reason"), trim_report.get("reason") if isinstance(trim_report, dict) else "")
        ),
        "pass1_input_chars": safe_int(summary_payload.get("pass1_input_chars")),
        "pass2_input_chars": safe_int(summary_payload.get("pass2_input_chars")),
        "quality_flag": quality_flag,
        "parameters": parameter_rows,
        "data_points": data_points,
        "process_steps": process_steps,
        "samples": samples,
        "evidence_objects": evidence_objects,
        "experiment_series": experiment_series,
        "summary": summary_payload,
        "record": record,
        "procedure_sections": procedure_sections if isinstance(procedure_sections, dict) else {},
        "trim_report": trim_report if isinstance(trim_report, dict) else {},
        "cleaned_body": cleaned_body,
        "missing_labels": sorted(set(missing_labels)),
        "unreadable_labels": sorted(set(unreadable_labels)),
        "stage3_dir": str(stage3_dir),
        "paper_output_dir": str(paper_output_dir),
        "file_paths": {key: str(value) if value else "" for key, value in file_paths.items()},
    }


def make_paper_summary_dataframe(papers: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [
        {
            "category": paper["category"],
            "paper_id": paper["paper_id"],
            "stage3_status": paper["stage3_status"],
            "data_point_count": paper["data_point_count"],
            "process_steps_count": paper["process_steps_count"],
            "evidence_object_count": paper["evidence_object_count"],
            "sample_count": paper["sample_count"],
            "canonical_key_errors_count": paper["canonical_key_errors_count"],
            "rejected_parameter_records_count": paper["rejected_parameter_records_count"],
            "process_steps_warning_count": paper["process_steps_warning_count"],
            "process_steps_other_action_ratio": paper["process_steps_other_action_ratio"],
            "process_steps_missing_evidence_ratio": paper["process_steps_missing_evidence_ratio"],
            "cleaned_body_chars": paper["cleaned_body_chars"],
            "input_truncated": paper["input_truncated"],
            "truncation_reason": paper["truncation_reason"],
            "quality_flag": paper["quality_flag"],
        }
        for paper in papers
    ]
    return pd.DataFrame(rows)


def make_sample_parameter_long_dataframe(papers: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for paper in papers:
        rows.extend(paper["parameters"])
    columns = [
        "category",
        "paper_id",
        "sample_id",
        "sample_name",
        "canonical_key",
        "raw_name",
        "value",
        "value_text",
        "unit",
        "source_text",
        "evidence_refs",
        "needs_manual_review",
    ]
    return pd.DataFrame(rows, columns=columns)


def build_parameter_distribution(df_long: pd.DataFrame) -> pd.DataFrame:
    if df_long.empty:
        return pd.DataFrame(
            columns=[
                "canonical_key",
                "raw_name_examples",
                "count",
                "paper_count",
                "category_count",
                "value_numeric_count",
                "value_text_count",
                "unit_examples",
                "source_text_coverage",
                "evidence_ref_coverage",
            ]
        )
    records = []
    for canonical_key, group in df_long.groupby("canonical_key", dropna=False):
        group = group.copy()
        count = len(group)
        source_coverage = round((group["source_text"].fillna("").astype(str).str.strip() != "").sum() / count, 4)
        evidence_coverage = round((group["evidence_refs"].fillna("").astype(str).str.strip() != "").sum() / count, 4)
        records.append(
            {
                "canonical_key": canonical_key,
                "raw_name_examples": top_examples(group["raw_name"]),
                "count": count,
                "paper_count": int(group["paper_id"].nunique()),
                "category_count": int(group["category"].nunique()),
                "value_numeric_count": int(group["value"].notna().sum()),
                "value_text_count": int(group["value_text"].fillna("").astype(str).str.strip().ne("").sum()),
                "unit_examples": top_examples(group["unit"]),
                "source_text_coverage": source_coverage,
                "evidence_ref_coverage": evidence_coverage,
            }
        )
    return pd.DataFrame(records).sort_values(["count", "paper_count", "canonical_key"], ascending=[False, False, True])


def build_canonical_key_by_category(df_long: pd.DataFrame, paper_summary: pd.DataFrame) -> pd.DataFrame:
    if df_long.empty:
        return pd.DataFrame(columns=["category", "canonical_key", "count", "paper_count", "normalized_frequency"])
    paper_counts = paper_summary.groupby("category")["paper_id"].nunique().to_dict()
    grouped = (
        df_long.groupby(["category", "canonical_key"], dropna=False)
        .agg(count=("canonical_key", "size"), paper_count=("paper_id", "nunique"))
        .reset_index()
    )
    grouped["normalized_frequency"] = grouped.apply(
        lambda row: round(row["count"] / max(paper_counts.get(row["category"], 1), 1), 4),
        axis=1,
    )
    return grouped.sort_values(["category", "count", "canonical_key"], ascending=[True, False, True])


def build_process_step_action_distribution(papers: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for paper in papers:
        for step in paper["process_steps"]:
            rows.append(
                {
                    "category": paper["category"],
                    "paper_id": paper["paper_id"],
                    "action": normalize_text(step.get("action")).lower() or "other",
                    "action_zh": action_zh_for(step.get("action"), normalize_text(step.get("action_zh"))),
                    "temperature": step.get("temperature_value"),
                    "duration": step.get("duration_value"),
                    "heating_rate": step.get("heating_rate_value"),
                    "evidence_text": normalize_text(step.get("evidence_text")),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "action",
                "action_zh",
                "count",
                "paper_count",
                "category_distribution",
                "with_temperature_count",
                "with_duration_count",
                "with_heating_rate_count",
                "with_evidence_text_count",
            ]
        )
    df = pd.DataFrame(rows)
    records = []
    for action, group in df.groupby("action"):
        category_distribution = group["category"].value_counts().to_dict()
        records.append(
            {
                "action": action,
                "action_zh": top_examples(group["action_zh"], limit=1) or action,
                "count": int(len(group)),
                "paper_count": int(group["paper_id"].nunique()),
                "category_distribution": stringify_json(category_distribution),
                "with_temperature_count": int(group["temperature"].notna().sum()),
                "with_duration_count": int(group["duration"].notna().sum()),
                "with_heating_rate_count": int(group["heating_rate"].notna().sum()),
                "with_evidence_text_count": int(group["evidence_text"].astype(str).str.strip().ne("").sum()),
            }
        )
    return pd.DataFrame(records).sort_values(["count", "paper_count", "action"], ascending=[False, False, True])


def build_process_condition_distribution(papers: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for paper in papers:
        for step in paper["process_steps"]:
            rows.extend(infer_condition_rows(category=paper["category"], paper_id=paper["paper_id"], step=step))
    return pd.DataFrame(
        rows,
        columns=[
            "category",
            "paper_id",
            "step_order",
            "action",
            "action_zh",
            "condition_key",
            "condition_value",
            "condition_unit",
            "source_text",
            "evidence_text",
            "source_kind",
        ],
    )


def build_sample_parameter_wide(df_long: pd.DataFrame) -> pd.DataFrame:
    if df_long.empty:
        return pd.DataFrame(columns=["category", "paper_id", "sample_id", "sample_name"])

    def summarize_group(group: pd.DataFrame) -> Any:
        numeric_values = [value for value in group["value"].tolist() if pd.notna(value)]
        text_values = [normalize_text(value) for value in group["value_text"].tolist() if normalize_text(value)]
        if numeric_values:
            unique_values = unique_preserve_order([str(value) for value in numeric_values])
            if len(unique_values) == 1:
                return numeric_values[0]
            if len(unique_values) <= 3:
                return " | ".join(unique_values)
            return f"count:{len(unique_values)}"
        if text_values:
            unique_values = unique_preserve_order(text_values)
            if len(unique_values) <= 3:
                return " | ".join(unique_values)
            return f"count:{len(unique_values)}"
        return ""

    rows = []
    grouped = df_long.groupby(["category", "paper_id", "sample_id", "sample_name", "canonical_key"], dropna=False)
    for (category, paper_id, sample_id, sample_name, canonical_key), group in grouped:
        rows.append(
            {
                "category": category,
                "paper_id": paper_id,
                "sample_id": sample_id,
                "sample_name": sample_name,
                "canonical_key": canonical_key,
                "cell_value": summarize_group(group),
            }
        )
    wide = pd.DataFrame(rows)
    pivot = wide.pivot_table(
        index=["category", "paper_id", "sample_id", "sample_name"],
        columns="canonical_key",
        values="cell_value",
        aggfunc="first",
        fill_value="",
    ).reset_index()
    pivot.columns.name = None
    return pivot


def build_parameter_cooccurrence_edges(df_long: pd.DataFrame) -> pd.DataFrame:
    if df_long.empty:
        return pd.DataFrame(
            columns=[
                "source_canonical_key",
                "target_canonical_key",
                "cooccurrence_count",
                "paper_count",
                "category_distribution",
            ]
        )
    edge_counts: Counter[tuple[str, str]] = Counter()
    edge_papers: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    edge_categories: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    grouped = df_long.groupby(["category", "paper_id", "sample_id"], dropna=False)
    for (category, paper_id, _sample_id), group in grouped:
        keys = sorted({normalize_text(key) for key in group["canonical_key"].tolist() if normalize_text(key)})
        for source_key, target_key in combinations(keys, 2):
            edge = (source_key, target_key)
            edge_counts[edge] += 1
            edge_papers[edge].add(f"{category}::{paper_id}")
            edge_categories[edge][category] += 1
    rows = []
    for (source_key, target_key), count in edge_counts.items():
        rows.append(
            {
                "source_canonical_key": source_key,
                "target_canonical_key": target_key,
                "cooccurrence_count": count,
                "paper_count": len(edge_papers[(source_key, target_key)]),
                "category_distribution": stringify_json(dict(edge_categories[(source_key, target_key)])),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["cooccurrence_count", "paper_count", "source_canonical_key", "target_canonical_key"],
        ascending=[False, False, True, True],
    )


def build_quality_flags(papers: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for paper in papers:
        category = paper["category"]
        paper_id = paper["paper_id"]
        if paper["stage3_status"] != "success":
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "stage3_status_failure",
                    "severity": "high",
                    "details": "Stage3 summary missing, unreadable, or schema_valid=false.",
                    "recommended_action": "check_stage3_summary_and_extraction",
                }
            )
        if paper["data_point_count"] == 0:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "missing_data_points",
                    "severity": "high",
                    "details": "No data_points were materialized for this paper.",
                    "recommended_action": "manual_review_stage3_datapoints",
                }
            )
        if paper["process_steps_count"] == 0:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "missing_process_steps",
                    "severity": "high",
                    "details": "No process_steps were materialized for this paper.",
                    "recommended_action": "manual_review_stage3_process_steps",
                }
            )
        if paper["evidence_object_count"] == 0:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "missing_evidence_objects",
                    "severity": "medium",
                    "details": "No evidence_objects were materialized for this paper.",
                    "recommended_action": "manual_review_stage3_evidence",
                }
            )
        if paper["canonical_key_errors_count"] > 0:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "canonical_key_errors",
                    "severity": "medium",
                    "details": f"canonical_key_errors_count={paper['canonical_key_errors_count']}",
                    "recommended_action": "review_canonical_key_normalization",
                }
            )
        if paper["rejected_parameter_records_count"] > 0:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "rejected_parameter_records",
                    "severity": "medium",
                    "details": f"rejected_parameter_records_count={paper['rejected_parameter_records_count']}",
                    "recommended_action": "review_rejected_parameter_records",
                }
            )
        if float(paper["process_steps_other_action_ratio"] or 0) >= 0.5:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "process_steps_other_action_ratio_high",
                    "severity": "medium",
                    "details": f"process_steps_other_action_ratio={paper['process_steps_other_action_ratio']}",
                    "recommended_action": "review_process_action_normalization",
                }
            )
        if float(paper["process_steps_missing_evidence_ratio"] or 0) >= 0.5:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "process_steps_missing_evidence_ratio_high",
                    "severity": "medium",
                    "details": f"process_steps_missing_evidence_ratio={paper['process_steps_missing_evidence_ratio']}",
                    "recommended_action": "review_process_step_evidence_text",
                }
            )
        if paper["input_truncated"]:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": "input_truncated",
                    "severity": "low",
                    "details": paper["truncation_reason"] or "summary.input_truncated=true",
                    "recommended_action": "inspect_pass1_pass2_input_window",
                }
            )
        for label in paper["missing_labels"]:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": f"missing_file::{label}",
                    "severity": "low",
                    "details": f"Missing expected loader input: {label}",
                    "recommended_action": "check_loader_fallbacks",
                }
            )
        for label in paper["unreadable_labels"]:
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "issue_type": f"unreadable_file::{label}",
                    "severity": "medium",
                    "details": f"File exists but could not be parsed: {label}",
                    "recommended_action": "inspect_file_encoding_or_json_format",
                }
            )
    return pd.DataFrame(rows, columns=["category", "paper_id", "issue_type", "severity", "details", "recommended_action"])


def build_stage3_analysis_summary(
    *,
    papers: list[dict[str, Any]],
    paper_summary: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    action_distribution: pd.DataFrame,
    missing_file_counts: dict[str, int],
    unreadable_file_counts: dict[str, int],
) -> dict[str, Any]:
    total_papers = len(papers)
    success_count = int((paper_summary["stage3_status"] == "success").sum()) if not paper_summary.empty else 0
    total_data_points = int(paper_summary["data_point_count"].sum()) if not paper_summary.empty else 0
    total_process_steps = int(paper_summary["process_steps_count"].sum()) if not paper_summary.empty else 0
    total_evidence_objects = int(paper_summary["evidence_object_count"].sum()) if not paper_summary.empty else 0
    papers_with_data_points = int((paper_summary["data_point_count"] > 0).sum()) if not paper_summary.empty else 0
    papers_with_process_steps = int((paper_summary["process_steps_count"] > 0).sum()) if not paper_summary.empty else 0
    papers_with_evidence_objects = int((paper_summary["evidence_object_count"] > 0).sum()) if not paper_summary.empty else 0
    papers_ready_for_stage45 = (
        int(
            (
                (paper_summary["stage3_status"] == "success")
                & (paper_summary["data_point_count"] > 0)
                & (paper_summary["process_steps_count"] > 0)
                & (paper_summary["evidence_object_count"] > 0)
            ).sum()
        )
        if not paper_summary.empty
        else 0
    )
    top_keys = []
    if not parameter_distribution.empty:
        for row in parameter_distribution.head(20).to_dict("records"):
            top_keys.append({"canonical_key": row["canonical_key"], "count": int(row["count"])})
    top_actions = []
    if not action_distribution.empty:
        for row in action_distribution.head(20).to_dict("records"):
            top_actions.append({"action": row["action"], "count": int(row["count"])})
    return {
        "total_papers": total_papers,
        "stage3_success_count": success_count,
        "total_data_points": total_data_points,
        "total_process_steps": total_process_steps,
        "total_evidence_objects": total_evidence_objects,
        "papers_with_data_points": papers_with_data_points,
        "papers_with_process_steps": papers_with_process_steps,
        "papers_with_evidence_objects": papers_with_evidence_objects,
        "papers_ready_for_stage45": papers_ready_for_stage45,
        "unique_canonical_key_count": int(parameter_distribution["canonical_key"].nunique()) if not parameter_distribution.empty else 0,
        "top_canonical_keys": top_keys,
        "top_process_actions": top_actions,
        "missing_process_steps_count": int((paper_summary["process_steps_count"] == 0).sum()) if not paper_summary.empty else 0,
        "missing_data_points_count": int((paper_summary["data_point_count"] == 0).sum()) if not paper_summary.empty else 0,
        "average_data_points_per_paper": round(total_data_points / total_papers, 4) if total_papers else 0.0,
        "average_process_steps_per_paper": round(total_process_steps / total_papers, 4) if total_papers else 0.0,
        "missing_file_counts": missing_file_counts,
        "unreadable_file_counts": unreadable_file_counts,
    }


def pick_font_family() -> list[str]:
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    selected = [name for name in candidates if name in installed]
    return selected or ["DejaVu Sans"]


def configure_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = pick_font_family()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "#f7f9fc"
    plt.rcParams["axes.facecolor"] = "#f7f9fc"
    plt.rcParams["savefig.facecolor"] = "#f7f9fc"
    plt.rcParams["axes.edgecolor"] = "#8ea3bf"
    plt.rcParams["grid.color"] = "#d6deea"


def save_figure(fig: plt.Figure, base_path: Path) -> None:
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(base_path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(base_path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def make_placeholder_figure(base_path: Path, *, title: str, message: str, data_source: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axis("off")
    ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=15, fontweight="bold", color="#17375e")
    ax.text(0.5, 0.42, message, ha="center", va="center", fontsize=11, color="#345273", wrap=True)
    fig.text(0.01, 0.02, f"数据来源：{data_source}", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_stage3_pipeline_funnel(summary: dict[str, Any], base_path: Path) -> None:
    stages = [
        ("总文献数", summary["total_papers"]),
        ("Stage3 成功数", summary["stage3_success_count"]),
        ("有 data_points", summary["papers_with_data_points"]),
        ("有 process_steps", summary["papers_with_process_steps"]),
        ("有 evidence_objects", summary["papers_with_evidence_objects"]),
        ("可进入后续 Stage4/5", summary["papers_ready_for_stage45"]),
    ]
    max_value = max(value for _, value in stages) if stages else 0
    if max_value <= 0:
        make_placeholder_figure(base_path, title="Stage3 全文献处理总览漏斗图", message="无可用数据。", data_source="stage3_summary.json")
        return
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#0e5ea8", "#2d7bc6", "#4d97de", "#71b2ec", "#9cc8f4", "#c6ddfb"]
    y_positions = np.arange(len(stages))[::-1]
    widths = [value / max_value for _, value in stages]
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, len(stages) - 0.5)
    ax.axis("off")
    for idx, ((label, value), y_pos, width, color) in enumerate(zip(stages, y_positions, widths, colors)):
        left = (1 - width) / 2
        rect = Rectangle((left, y_pos - 0.35), width, 0.7, facecolor=color, edgecolor="#ffffff", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(0.5, y_pos, f"{label}: {value}", ha="center", va="center", fontsize=12, color="white", fontweight="bold")
        if idx < len(stages) - 1:
            ax.plot([0.5, 0.5], [y_pos - 0.35, y_pos - 0.65], color="#5d7fa6", linewidth=1.2)
    fig.suptitle("Stage3 全文献处理总览漏斗图", fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：source_manifest.csv + stage3_summary.json", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_parameter_distribution_topn(parameter_distribution: pd.DataFrame, base_path: Path, top_n: int) -> None:
    if parameter_distribution.empty:
        make_placeholder_figure(base_path, title="参数 canonical_key Top 分布", message="无参数记录可用于绘图。", data_source="sample_parameter_long.csv")
        return
    plot_df = parameter_distribution.head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, max(6, top_n * 0.28)))
    ax.barh(plot_df["canonical_key"], plot_df["count"], color="#2d7bc6", edgecolor="#17375e")
    ax.set_xlabel("出现次数 Count")
    ax.set_ylabel("canonical_key")
    ax.set_title(f"参数 canonical_key Top {min(top_n, len(parameter_distribution))} 分布")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    fig.text(0.01, 0.02, "数据来源：sample_parameter_long.csv 聚合得到 parameter_distribution.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_canonical_key_category_heatmap(canonical_by_category: pd.DataFrame, base_path: Path, top_n: int) -> None:
    if canonical_by_category.empty:
        make_placeholder_figure(base_path, title="不同类别 canonical_key 覆盖热图", message="无 canonical_key 分类统计数据。", data_source="canonical_key_by_category.csv")
        return
    top_keys = (
        canonical_by_category.groupby("canonical_key")["count"].sum().sort_values(ascending=False).head(top_n).index.tolist()
    )
    heatmap_df = canonical_by_category[canonical_by_category["canonical_key"].isin(top_keys)].pivot_table(
        index="category",
        columns="canonical_key",
        values="normalized_frequency",
        fill_value=0,
    )
    if heatmap_df.empty:
        make_placeholder_figure(base_path, title="不同类别 canonical_key 覆盖热图", message="Top canonical_key 透视表为空。", data_source="canonical_key_by_category.csv")
        return
    fig, ax = plt.subplots(figsize=(max(10, len(heatmap_df.columns) * 0.55), max(4.5, len(heatmap_df.index) * 0.5)))
    image = ax.imshow(heatmap_df.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(heatmap_df.columns)))
    ax.set_xticklabels(heatmap_df.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(heatmap_df.index)))
    ax.set_yticklabels(heatmap_df.index, fontsize=10)
    ax.set_title("不同类别的 canonical_key 覆盖热图")
    fig.colorbar(image, ax=ax, shrink=0.85, label="归一化频率")
    fig.text(0.01, 0.02, "数据来源：canonical_key_by_category.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_process_step_action_distribution(action_distribution: pd.DataFrame, base_path: Path, top_n: int) -> None:
    if action_distribution.empty:
        make_placeholder_figure(base_path, title="process_steps 动作分布图", message="无 process_steps 动作数据。", data_source="process_step_action_distribution.csv")
        return
    plot_df = action_distribution.head(top_n).iloc[::-1]
    labels = [
        f"{row.action_zh}\n({row.action})"
        for row in plot_df.itertuples(index=False)
    ]
    fig, ax = plt.subplots(figsize=(11, max(6, len(plot_df) * 0.35)))
    ax.barh(labels, plot_df["count"], color="#4d97de", edgecolor="#17375e")
    ax.set_xlabel("步骤数 Count")
    ax.set_title("process_steps 动作分布图")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    fig.text(0.01, 0.02, "数据来源：process_step_action_distribution.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_process_route_flow(papers: list[dict[str, Any]], base_path: Path) -> None:
    transition_counts: Counter[tuple[str, str]] = Counter()
    for paper in papers:
        ordered_steps = sorted(
            paper["process_steps"],
            key=lambda item: (safe_int(item.get("step_order"), 0), normalize_text(item.get("step_id")), normalize_text(item.get("action"))),
        )
        route = [map_action_to_route_stage(step.get("action")) for step in ordered_steps if normalize_text(step.get("action"))]
        route = [stage for stage in route if stage]
        if not route:
            continue
        compact_route = []
        for stage in route:
            if not compact_route or compact_route[-1] != stage:
                compact_route.append(stage)
        for source_stage, target_stage in zip(compact_route, compact_route[1:]):
            transition_counts[(source_stage, target_stage)] += 1
    if not transition_counts:
        make_placeholder_figure(base_path, title="工艺路线 Sankey/流程图", message="无可用工艺步骤序列。", data_source="process_steps.jsonl / paper_extraction.schema_v2.json")
        return
    stage_order = [
        "sol_prep",
        "aging_concentration",
        "spinning",
        "drying",
        "calcination_sintering",
        "characterization",
        "other",
    ]
    active_stages = [stage for stage in stage_order if stage in {key for edge in transition_counts for key in edge}]
    x_positions = {stage: index for index, stage in enumerate(active_stages)}
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.axis("off")
    node_y = 0.55
    for stage in active_stages:
        x = x_positions[stage]
        rect = Rectangle((x - 0.38, node_y - 0.12), 0.76, 0.24, facecolor="#d9e9fb", edgecolor="#2d7bc6", linewidth=1.6)
        ax.add_patch(rect)
        ax.text(x, node_y, STAGE_ROUTE_LABELS[stage], ha="center", va="center", fontsize=11, color="#17375e", fontweight="bold")
    max_count = max(transition_counts.values())
    for (source_stage, target_stage), count in transition_counts.most_common():
        start_x = x_positions[source_stage] + 0.38
        end_x = x_positions[target_stage] - 0.38
        arrow = FancyArrowPatch(
            (start_x, node_y),
            (end_x, node_y),
            connectionstyle="arc3,rad=0.0",
            arrowstyle="-|>",
            linewidth=1.2 + 6 * count / max_count,
            color="#4d97de",
            alpha=0.55,
            mutation_scale=16,
        )
        ax.add_patch(arrow)
        ax.text((start_x + end_x) / 2, node_y + 0.14, str(count), ha="center", va="bottom", fontsize=9, color="#345273")
    ax.set_xlim(-0.8, len(active_stages) - 0.2)
    ax.set_ylim(0, 1)
    fig.suptitle("工艺路线 Sankey/流程图（简化）", fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：各论文 process_steps 的 step_order 序列映射到高层工艺阶段", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_process_condition_distribution(process_conditions: pd.DataFrame, base_path: Path) -> None:
    if process_conditions.empty:
        make_placeholder_figure(base_path, title="工艺条件分布图", message="无条件字段可用于统计。", data_source="process_condition_distribution.csv")
        return

    def extract_numeric(keys: set[str]) -> pd.Series:
        subset = process_conditions[process_conditions["condition_key"].isin(keys)].copy()
        subset["condition_value_numeric"] = pd.to_numeric(subset["condition_value"], errors="coerce")
        subset = subset.dropna(subset=["condition_value_numeric"])
        return subset["condition_value_numeric"]

    calc_temp = extract_numeric({"calcination_temperature", "sintering_temperature", "temperature"})
    duration = extract_numeric({"holding_time", "duration", "drying_time", "aging_time"})
    heating_rate = extract_numeric({"heating_rate"})

    if calc_temp.empty and duration.empty and heating_rate.empty:
        make_placeholder_figure(base_path, title="工艺条件分布图", message="条件值存在但无法转换为数值分布。", data_source="process_condition_distribution.csv")
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    panels = [
        (axes[0], calc_temp, "温度分布", "温度"),
        (axes[1], duration, "时间分布", "时间"),
        (axes[2], heating_rate, "升温速率分布", "升温速率"),
    ]
    for ax, series, title, xlabel in panels:
        if series.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{title}\n数据不足", ha="center", va="center", color="#345273")
            continue
        ax.hist(series, bins=min(12, max(5, int(math.sqrt(len(series))))), color="#4d97de", edgecolor="#17375e")
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("频次")
        ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.suptitle("工艺条件分布图", fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：process_condition_distribution.csv 中温度/时间/升温速率条件", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_sample_parameter_matrix_sparsity(
    df_long: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    base_path: Path,
    top_n: int,
) -> None:
    if df_long.empty or parameter_distribution.empty:
        make_placeholder_figure(base_path, title="sample-parameter 稀疏性热图", message="无 sample parameter 数据。", data_source="sample_parameter_long.csv")
        return
    top_keys = parameter_distribution.head(top_n)["canonical_key"].tolist()
    matrix_df = (
        df_long.assign(present=1)
        .pivot_table(index="paper_id", columns="canonical_key", values="present", aggfunc="max", fill_value=0)
    )
    matrix_df = matrix_df.reindex(columns=top_keys, fill_value=0)
    if matrix_df.empty:
        make_placeholder_figure(base_path, title="sample-parameter 稀疏性热图", message="矩阵透视结果为空。", data_source="sample_parameter_long.csv")
        return
    fig_height = max(6, min(18, matrix_df.shape[0] * 0.12 + 2))
    fig, ax = plt.subplots(figsize=(max(10, matrix_df.shape[1] * 0.45), fig_height))
    image = ax.imshow(matrix_df.values, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(matrix_df.columns)))
    ax.set_xticklabels(matrix_df.columns, rotation=45, ha="right", fontsize=9)
    y_ticks = list(range(0, len(matrix_df.index), max(1, len(matrix_df.index) // 20 or 1)))
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([matrix_df.index[idx] for idx in y_ticks], fontsize=8)
    ax.set_title("sample-parameter matrix 稀疏性热图（paper 级）")
    fig.colorbar(image, ax=ax, shrink=0.85, label="存在性")
    fig.text(0.01, 0.02, "数据来源：sample_parameter_long.csv，按 paper × canonical_key 聚合为存在矩阵", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_parameter_cooccurrence_network(
    edges: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    base_path: Path,
    top_n: int,
) -> None:
    if edges.empty or parameter_distribution.empty:
        make_placeholder_figure(base_path, title="参数共现网络图", message="无参数共现边。", data_source="parameter_cooccurrence_edges.csv")
        return
    top_keys = set(parameter_distribution.head(top_n)["canonical_key"].tolist())
    network_edges = edges[
        edges["source_canonical_key"].isin(top_keys) & edges["target_canonical_key"].isin(top_keys)
    ].copy()
    network_edges = network_edges.head(max(top_n * 3, 20))
    if network_edges.empty:
        make_placeholder_figure(base_path, title="参数共现网络图", message="Top canonical_key 范围内无共现边。", data_source="parameter_cooccurrence_edges.csv")
        return
    node_sizes = parameter_distribution.set_index("canonical_key")["count"].to_dict()
    graph = nx.Graph()
    for row in network_edges.itertuples(index=False):
        graph.add_edge(row.source_canonical_key, row.target_canonical_key, weight=row.cooccurrence_count)
    fig, ax = plt.subplots(figsize=(10.5, 8))
    positions = nx.spring_layout(graph, seed=42, weight="weight", k=1.1 / max(1, graph.number_of_nodes() ** 0.5))
    edge_widths = [1 + 4 * graph[u][v]["weight"] / max(network_edges["cooccurrence_count"].max(), 1) for u, v in graph.edges()]
    nx.draw_networkx_edges(graph, positions, width=edge_widths, edge_color="#7aa9dc", alpha=0.6, ax=ax)
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_size=[220 + 18 * node_sizes.get(node, 1) for node in graph.nodes()],
        node_color="#2d7bc6",
        edgecolors="#17375e",
        linewidths=1.0,
        ax=ax,
    )
    nx.draw_networkx_labels(graph, positions, font_size=9, font_color="#17375e", ax=ax)
    ax.set_title("参数共现网络图")
    ax.axis("off")
    fig.text(0.01, 0.02, "数据来源：sample_parameter_long.csv 构建 sample 级 canonical_key 共现边", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_stage3_quality_distribution(paper_summary: pd.DataFrame, base_path: Path) -> None:
    if paper_summary.empty:
        make_placeholder_figure(base_path, title="Stage3 质量分布图", message="无论文级统计数据。", data_source="paper_stage3_summary.csv")
        return
    metrics = ["data_point_count", "process_steps_count", "evidence_object_count"]
    titles = ["data_points 分布", "process_steps 分布", "evidence_objects 分布"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for ax, metric, title in zip(axes, metrics, titles):
        series = pd.to_numeric(paper_summary[metric], errors="coerce").dropna()
        if series.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{title}\n数据不足", ha="center", va="center", color="#345273")
            continue
        ax.hist(series, bins=min(15, max(5, int(math.sqrt(len(series))))), color="#71b2ec", edgecolor="#17375e")
        ax.set_title(title)
        ax.set_xlabel(metric)
        ax.set_ylabel("文献数")
        ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.suptitle("Stage3 质量分布图", fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：paper_stage3_summary.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_category_contribution_summary(paper_summary: pd.DataFrame, base_path: Path) -> None:
    if paper_summary.empty:
        make_placeholder_figure(base_path, title="文献类别贡献图", message="无 category 汇总数据。", data_source="paper_stage3_summary.csv")
        return
    grouped = (
        paper_summary.groupby("category")[["data_point_count", "process_steps_count", "evidence_object_count"]].sum().sort_values("data_point_count", ascending=False)
    )
    if grouped.empty:
        make_placeholder_figure(base_path, title="文献类别贡献图", message="类别汇总结果为空。", data_source="paper_stage3_summary.csv")
        return
    fig, ax = plt.subplots(figsize=(11, max(5, len(grouped) * 0.4)))
    x = np.arange(len(grouped.index))
    width = 0.25
    ax.bar(x - width, grouped["data_point_count"], width, label="data_points", color="#2d7bc6")
    ax.bar(x, grouped["process_steps_count"], width, label="process_steps", color="#71b2ec")
    ax.bar(x + width, grouped["evidence_object_count"], width, label="evidence_objects", color="#a6c8ef")
    ax.set_xticks(x)
    ax.set_xticklabels(grouped.index, rotation=30, ha="right")
    ax.set_ylabel("数量")
    ax.set_title("文献类别贡献图")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.text(0.01, 0.02, "数据来源：paper_stage3_summary.csv 按 category 聚合", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_overview_dashboard(
    *,
    summary: dict[str, Any],
    parameter_distribution: pd.DataFrame,
    action_distribution: pd.DataFrame,
    paper_summary: pd.DataFrame,
    base_path: Path,
    top_n: int,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    stages = [
        ("总文献数", summary["total_papers"]),
        ("Stage3 成功", summary["stage3_success_count"]),
        ("有 data_points", summary["total_papers"] - summary["missing_data_points_count"]),
        ("有 process_steps", summary["total_papers"] - summary["missing_process_steps_count"]),
    ]
    ax = axes[0, 0]
    if any(value > 0 for _, value in stages):
        ax.barh([label for label, _ in stages][::-1], [value for _, value in stages][::-1], color="#2d7bc6")
        ax.set_title("Stage3 处理漏斗")
        ax.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "无漏斗数据", ha="center", va="center", color="#345273")

    ax = axes[0, 1]
    if not parameter_distribution.empty:
        top_df = parameter_distribution.head(min(10, top_n)).iloc[::-1]
        ax.barh(top_df["canonical_key"], top_df["count"], color="#4d97de")
        ax.set_title("Top canonical_key")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "无参数分布数据", ha="center", va="center", color="#345273")

    ax = axes[1, 0]
    if not action_distribution.empty:
        top_actions = action_distribution.head(min(10, top_n)).iloc[::-1]
        labels = [f"{row.action_zh}\n({row.action})" for row in top_actions.itertuples(index=False)]
        ax.barh(labels, top_actions["count"], color="#71b2ec")
        ax.set_title("process_steps 动作分布")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "无动作分布数据", ha="center", va="center", color="#345273")

    ax = axes[1, 1]
    if not paper_summary.empty:
        grouped = paper_summary.groupby("category")["data_point_count"].sum().sort_values(ascending=False).head(10)
        ax.barh(grouped.index[::-1], grouped.values[::-1], color="#9cc8f4")
        ax.set_title("category 贡献")
        ax.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "无类别贡献数据", ha="center", va="center", color="#345273")

    fig.suptitle("Stage 3 文献结构化抽取结果总览", fontsize=18, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：paper_stage3_summary.csv + parameter_distribution.csv + process_step_action_distribution.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def format_top_items(items: list[dict[str, Any]], key_name: str) -> list[str]:
    lines = []
    for item in items:
        lines.append(f"- {item.get(key_name)}: {item.get('count')}")
    return lines or ["- 无"]


def render_report(
    *,
    summary: dict[str, Any],
    paper_summary: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    action_distribution: pd.DataFrame,
    figures_generated: list[str],
    placeholder_figures: list[str],
    tables_generated: list[str],
    output_dir: Path,
    issue_paper_count: int,
) -> str:
    parsed_count = len(paper_summary)
    top_keys_lines = format_top_items(summary["top_canonical_keys"][:20], "canonical_key")
    top_action_lines = format_top_items(summary["top_process_actions"][:20], "action")
    figure_sources = {
        "stage3_pipeline_funnel": "source_manifest.csv + stage3_summary.json",
        "parameter_distribution_top30_bar": "sample_parameter_long.csv / parameter_distribution.csv",
        "canonical_key_category_heatmap": "canonical_key_by_category.csv",
        "process_step_action_distribution": "process_step_action_distribution.csv",
        "process_route_sankey": "process_steps 按 step_order 映射后的高层阶段转移",
        "process_condition_distribution": "process_condition_distribution.csv",
        "sample_parameter_matrix_sparsity_heatmap": "sample_parameter_long.csv 聚合存在矩阵",
        "parameter_cooccurrence_network": "parameter_cooccurrence_edges.csv",
        "stage3_quality_distribution": "paper_stage3_summary.csv",
        "category_contribution_summary": "paper_stage3_summary.csv 按 category 聚合",
        "stage3_overview_dashboard": "漏斗 + 参数分布 + 动作分布 + category 贡献综合汇总",
    }
    lines = [
        "# STAGE3 Analysis Outputs Build Report",
        "",
        "## 执行约束",
        "",
        "- 是否调用 LLM：没有",
        "- 是否调用 VLM：没有",
        "- 是否重跑 Stage3：没有",
        "- 是否运行 Stage4A：没有",
        "- 是否运行 Stage5：没有",
        "- 是否运行 MinerU：没有",
        "",
        "## 构建结果",
        "",
        f"- 读取了多少篇 stage3_twopass：{summary['total_papers']}",
        f"- 成功解析多少篇：{parsed_count}",
        f"- 缺失/不可读多少篇：{issue_paper_count}",
        f"- 总 data_points 数：{summary['total_data_points']}",
        f"- 总 process_steps 数：{summary['total_process_steps']}",
        f"- 总 evidence_objects 数：{summary['total_evidence_objects']}",
        f"- unique canonical_key 数：{summary['unique_canonical_key_count']}",
        "",
        "## Top 20 canonical_key",
        "",
        *top_keys_lines,
        "",
        "## Top 20 process action",
        "",
        *top_action_lines,
        "",
        "## 已生成图表",
        "",
        *[f"- {figure_name}" for figure_name in figures_generated],
        "",
        "## 图表数据来源",
        "",
        *[f"- {name}: {figure_sources.get(name, '见脚本生成逻辑')}" for name in figures_generated],
        "",
        "## 数据不足说明",
        "",
    ]
    if placeholder_figures:
        lines.extend(f"- {name}: 生成了占位空图/说明图。" for name in placeholder_figures)
    else:
        lines.append("- 无；全部图均使用实际 Stage3 数据生成。")
    lines.extend(
        [
            "",
            "## 已生成表格",
            "",
            *[f"- {table_name}" for table_name in tables_generated],
            "",
            "## 组会展示推荐",
            "",
            *[f"- {name}" for name in PPT_RECOMMENDED_FIGURES],
            "",
            "## 论文方法学图推荐",
            "",
            *[f"- {name}" for name in METHODOLOGY_RECOMMENDED_FIGURES],
            "",
            "## Stage4A / Stage5 后续可补强内容",
            "",
            "- 融合 Stage4A 光谱/显微视觉结果后的参数-证据跨模态覆盖图。",
            "- 融合 Stage5 link-aware 数据后的 sample-parameter-evidence 三部图。",
            "- 参数与谱图峰位、图像表征类别之间的跨模态共现网络。",
            "- 进入最终数据集前后的漏斗对比图和质量提升对比图。",
            "- 面向论文方法学的“文本抽取到证据链接再到结构化数据集”全流程图。",
            "",
            "## Generated Outputs",
            "",
            f"- 主要生成目录：{output_dir.as_posix()}",
            "- 这些 CSV/JSON/PNG/SVG 为 generated outputs，本次默认保留本地，不要求全部 commit。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_analysis_outputs(
    *,
    manifest_path: Path,
    outputs_dir: Path,
    output_dir: Path,
    stage3_subdir: str,
    top_n: int,
    report_path: Path | None = None,
) -> dict[str, Any]:
    configure_matplotlib()
    output_dir = ensure_directory(output_dir)
    figures_dir = ensure_directory(output_dir / "figures")
    if report_path is None:
        report_path = ensure_directory(PROJECT_ROOT / "docs" / "refactor") / "STAGE3_ANALYSIS_OUTPUTS_BUILD_REPORT.md"
    else:
        report_path.parent.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig", newline="")))
    papers: list[dict[str, Any]] = []
    missing_file_counts = Counter()
    unreadable_file_counts = Counter()

    for row in rows:
        category = normalize_text(row.get("category"))
        paper_id = normalize_text(pick_first_non_empty(row.get("paper_id"), row.get("paper_id_guess")))
        if not category or not paper_id:
            continue
        output_dir_hint = normalize_text(pick_first_non_empty(row.get("resolved_output_dir"), row.get("output_dir")))
        if output_dir_hint:
            paper_output_dir = resolve_path(output_dir_hint, base_dir=PROJECT_ROOT)
        else:
            paper_output_dir = (outputs_dir / category / paper_id).resolve()
        stage3_dir = paper_output_dir / stage3_subdir
        if not stage3_dir.exists():
            continue
        paper = load_stage3_paper(
            category=category,
            paper_id=paper_id,
            paper_output_dir=paper_output_dir,
            stage3_subdir=stage3_subdir,
        )
        papers.append(paper)
        missing_file_counts.update(paper["missing_labels"])
        unreadable_file_counts.update(paper["unreadable_labels"])

    paper_summary = make_paper_summary_dataframe(papers)
    sample_parameter_long = make_sample_parameter_long_dataframe(papers)
    parameter_distribution = build_parameter_distribution(sample_parameter_long)
    canonical_key_by_category = build_canonical_key_by_category(sample_parameter_long, paper_summary)
    process_action_distribution = build_process_step_action_distribution(papers)
    process_condition_distribution = build_process_condition_distribution(papers)
    sample_parameter_wide = build_sample_parameter_wide(sample_parameter_long)
    cooccurrence_edges = build_parameter_cooccurrence_edges(sample_parameter_long)
    quality_flags = build_quality_flags(papers)
    analysis_summary = build_stage3_analysis_summary(
        papers=papers,
        paper_summary=paper_summary,
        parameter_distribution=parameter_distribution,
        action_distribution=process_action_distribution,
        missing_file_counts=dict(missing_file_counts),
        unreadable_file_counts=dict(unreadable_file_counts),
    )
    issue_paper_count = sum(
        1
        for paper in papers
        if paper["stage3_status"] != "success" or paper["missing_labels"] or paper["unreadable_labels"]
    )

    tables = {
        "paper_stage3_summary.csv": paper_summary,
        "parameter_distribution.csv": parameter_distribution,
        "canonical_key_by_category.csv": canonical_key_by_category,
        "process_step_action_distribution.csv": process_action_distribution,
        "process_condition_distribution.csv": process_condition_distribution,
        "sample_parameter_long.csv": sample_parameter_long,
        "sample_parameter_wide.csv": sample_parameter_wide,
        "parameter_cooccurrence_edges.csv": cooccurrence_edges,
        "stage3_quality_flags.csv": quality_flags,
    }
    for filename, dataframe in tables.items():
        write_dataframe(dataframe, output_dir / filename)
    (output_dir / "stage3_analysis_summary.json").write_text(
        json.dumps(analysis_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    figure_builders = [
        ("stage3_pipeline_funnel", lambda: plot_stage3_pipeline_funnel(analysis_summary, figures_dir / "stage3_pipeline_funnel")),
        (
            "parameter_distribution_top30_bar",
            lambda: plot_parameter_distribution_topn(parameter_distribution, figures_dir / "parameter_distribution_top30_bar", top_n),
        ),
        (
            "canonical_key_category_heatmap",
            lambda: plot_canonical_key_category_heatmap(canonical_key_by_category, figures_dir / "canonical_key_category_heatmap", top_n),
        ),
        (
            "process_step_action_distribution",
            lambda: plot_process_step_action_distribution(process_action_distribution, figures_dir / "process_step_action_distribution", top_n),
        ),
        ("process_route_sankey", lambda: plot_process_route_flow(papers, figures_dir / "process_route_sankey")),
        (
            "process_condition_distribution",
            lambda: plot_process_condition_distribution(process_condition_distribution, figures_dir / "process_condition_distribution"),
        ),
        (
            "sample_parameter_matrix_sparsity_heatmap",
            lambda: plot_sample_parameter_matrix_sparsity(sample_parameter_long, parameter_distribution, figures_dir / "sample_parameter_matrix_sparsity_heatmap", top_n),
        ),
        (
            "parameter_cooccurrence_network",
            lambda: plot_parameter_cooccurrence_network(cooccurrence_edges, parameter_distribution, figures_dir / "parameter_cooccurrence_network", top_n),
        ),
        (
            "stage3_quality_distribution",
            lambda: plot_stage3_quality_distribution(paper_summary, figures_dir / "stage3_quality_distribution"),
        ),
        (
            "category_contribution_summary",
            lambda: plot_category_contribution_summary(paper_summary, figures_dir / "category_contribution_summary"),
        ),
        (
            "stage3_overview_dashboard",
            lambda: plot_overview_dashboard(
                summary=analysis_summary,
                parameter_distribution=parameter_distribution,
                action_distribution=process_action_distribution,
                paper_summary=paper_summary,
                base_path=figures_dir / "stage3_overview_dashboard",
                top_n=top_n,
            ),
        ),
    ]
    figures_generated: list[str] = []
    placeholder_figures: list[str] = []
    for figure_name, builder in figure_builders:
        existing_before = (figures_dir / figure_name).with_suffix(".png").exists()
        builder()
        figures_generated.append(figure_name)
        output_text = read_text((figures_dir / figure_name).with_suffix(".svg"))
        if "占位空图" in output_text or "数据不足" in output_text or "无可用数据" in output_text:
            placeholder_figures.append(figure_name)

    report_text = render_report(
        summary=analysis_summary,
        paper_summary=paper_summary,
        parameter_distribution=parameter_distribution,
        action_distribution=process_action_distribution,
        figures_generated=figures_generated,
        placeholder_figures=placeholder_figures,
        tables_generated=list(tables.keys()) + ["stage3_analysis_summary.json"],
        output_dir=output_dir,
        issue_paper_count=issue_paper_count,
    )
    report_path.write_text(report_text, encoding="utf-8")

    return {
        "papers": papers,
        "paper_summary": paper_summary,
        "parameter_distribution": parameter_distribution,
        "canonical_key_by_category": canonical_key_by_category,
        "process_action_distribution": process_action_distribution,
        "process_condition_distribution": process_condition_distribution,
        "sample_parameter_long": sample_parameter_long,
        "sample_parameter_wide": sample_parameter_wide,
        "cooccurrence_edges": cooccurrence_edges,
        "quality_flags": quality_flags,
        "analysis_summary": analysis_summary,
        "figures_generated": figures_generated,
        "placeholder_figures": placeholder_figures,
        "report_path": report_path,
        "output_dir": output_dir,
        "figures_dir": figures_dir,
    }


def main() -> None:
    args = parse_args()
    manifest_path = resolve_path(args.manifest, base_dir=PROJECT_ROOT)
    outputs_dir = resolve_path(args.outputs_dir, base_dir=PROJECT_ROOT)
    output_dir = resolve_path(args.output_dir, base_dir=PROJECT_ROOT)
    result = build_analysis_outputs(
        manifest_path=manifest_path,
        outputs_dir=outputs_dir,
        output_dir=output_dir,
        stage3_subdir=args.stage3_subdir,
        top_n=args.top_n,
        report_path=PROJECT_ROOT / "docs" / "refactor" / "STAGE3_ANALYSIS_OUTPUTS_BUILD_REPORT.md",
    )
    summary = result["analysis_summary"]
    print(json.dumps(
        {
            "total_papers": summary["total_papers"],
            "stage3_success_count": summary["stage3_success_count"],
            "total_data_points": summary["total_data_points"],
            "total_process_steps": summary["total_process_steps"],
            "total_evidence_objects": summary["total_evidence_objects"],
            "report_path": str(result["report_path"]),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
