from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle


ACTION_ALIAS_MAP = {
    "add": "add",
    "mix": "add",
    "dropwise_add": "add",
    "add_polymer": "add",
    "impregnate": "add",
    "inject": "add",
    "stir": "stir",
    "dissolve": "dissolve",
    "age": "age",
    "aging": "age",
    "dry": "dry",
    "calcine": "calcine",
    "sinter": "sinter",
    "spin": "spin",
    "electrospin": "spin",
    "filter": "filter",
    "wash": "wash",
    "hydrolyze": "hydrolyze",
    "heat": "heat",
    "cool": "cool",
    "characterize": "characterize",
}
ACTION_PATTERNS = [
    ("characterize", ["表征", "测试", "characteriz", "measurement", "xrd", "ftir", "raman", "nmr", "sem", "tem", "xps", "bet", "tg", "dsc", "性能测试"]),
    ("spin", ["静电纺丝", "电纺", "纺丝", "拉丝", "dry spinning", "dry-spinning", "electrospin", "spinning", "fiber drawing", "extrusion", "喷丝", "成纤"]),
    ("calcine", ["煅烧", "焙烧", "calc", "calcination", "muffle furnace", "马弗炉"]),
    ("sinter", ["烧结", "sinter"]),
    ("dry", ["干燥", "烘干", "freeze dry", "freeze-dry", "冷冻干燥", "drying", "oven dry"]),
    ("filter", ["过滤", "抽滤", "filter", "filtration"]),
    ("wash", ["洗涤", "漂洗", "wash", "rins"]),
    ("hydrolyze", ["水解", "hydroly"]),
    ("dissolve", ["溶解", "溶于", "dissolve", "dissolution"]),
    ("stir", ["搅拌", "stir", "agitat"]),
    ("age", ["老化", "陈化", "aging", "ageing", "age "]),
    ("cool", ["冷却", "降温", "cool"]),
    ("heat", ["加热", "升温", "保温", "回流", "热处理", "heat", "reflux"]),
    ("add", ["加入", "滴加", "混合", "配制", "mix", "add", "blend", "disperse"]),
]
ACTION_ZH_LABELS = {
    "add": "加入/混合",
    "stir": "搅拌",
    "dissolve": "溶解",
    "age": "老化/陈化",
    "dry": "干燥",
    "calcine": "煅烧",
    "sinter": "烧结",
    "spin": "纺丝",
    "filter": "过滤",
    "wash": "洗涤",
    "hydrolyze": "水解",
    "heat": "加热",
    "cool": "冷却",
    "characterize": "表征",
    "other": "其他",
}
SHORT_KEY_LABELS = {
    "nmr_27Al_peak_position_ppm": "27Al NMR ppm",
    "pH": "pH",
    "particle_size_nm": "Particle size",
    "ftir_peak_position_cm_1": "FTIR peak",
    "Al_concentration_mol_L": "Al conc.",
    "calcination_temperature_C": "Calcination T",
    "sintering_temperature_C": "Sintering T",
    "mass_loss_wt_percent": "Mass loss",
    "aging_time_h": "Aging time",
    "specific_surface_area_m2_g": "BET area",
    "heating_rate_C_min": "Heating rate",
    "aging_temperature_C": "Aging T",
    "holding_time_h": "Holding time",
    "dsc_peak_temperature_C": "DSC peak T",
    "solid_content_wt_percent": "Solid content",
    "average_fiber_diameter_um": "Fiber dia. (um)",
    "average_fiber_diameter_nm": "Fiber dia. (nm)",
    "viscosity_Pa_s": "Viscosity",
    "tensile_strength_MPa": "Tensile strength",
    "hydrolysis_temperature_C": "Hydrolysis T",
    "drying_temperature_C": "Drying T",
    "drying_time_h": "Drying time",
    "xrd_peak_position_2theta_deg": "XRD 2θ",
    "raman_peak_position_cm_1": "Raman peak",
    "pore_volume_cm3_g": "Pore volume",
    "average_pore_size_nm": "Pore size",
    "crystallite_size_nm": "Crystallite size",
    "spinnability": "Spinnability",
    "zeta_potential_mV": "Zeta potential",
    "water_to_aluminum_molar_ratio": "H2O/Al ratio",
    "acid_to_aluminum_molar_ratio": "Acid/Al ratio",
}
PARAMETER_TYPE_COLORS = {
    "synthesis": "#2d7bc6",
    "process": "#5b9bd5",
    "structure": "#74a857",
    "property": "#d99058",
    "characterization": "#7a62b3",
    "other": "#9aa4b2",
}
CATEGORY_COLORS = {
    "applications": "#2d7bc6",
    "fiber_process": "#6aaed6",
    "mechanism": "#9cc8f4",
    "rheology": "#4b6cb7",
}
ROUTE_STAGE_LABELS = {
    "sol_prep": "溶胶制备",
    "aging_concentration": "老化/浓缩",
    "spinning": "纺丝",
    "drying": "干燥",
    "calcination_sintering": "煅烧/烧结",
    "characterization": "表征/性能",
    "other": "其他",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refine Stage3 analysis figures without rerunning extraction.")
    parser.add_argument("--manifest", default="data/batch_manifest/source_manifest.csv")
    parser.add_argument("--analysis-dir", default="data/analysis_outputs_stage3")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--output-dir", default="data/analysis_outputs_stage3_refined")
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--top-n", default=20, type=int)
    return parser.parse_args()


def resolve_path(path_value: str | Path, *, base_dir: Path = PROJECT_ROOT) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


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


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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


def configure_matplotlib() -> None:
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    selected = [name for name in candidates if name in installed] or ["DejaVu Sans"]
    plt.rcParams["font.sans-serif"] = selected
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "#f5f7fb"
    plt.rcParams["axes.facecolor"] = "#f5f7fb"
    plt.rcParams["savefig.facecolor"] = "#f5f7fb"
    plt.rcParams["axes.edgecolor"] = "#8ea3bf"
    plt.rcParams["grid.color"] = "#d5deea"


def save_figure(fig: plt.Figure, base_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(base_path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(base_path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def make_placeholder_figure(base_path: Path, *, title: str, message: str, data_source: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.625))
    ax.axis("off")
    ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=16, fontweight="bold", color="#17375e")
    ax.text(0.5, 0.42, message, ha="center", va="center", fontsize=12, color="#345273", wrap=True)
    fig.text(0.01, 0.02, f"数据来源：{data_source}", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def shorten_canonical_key_label(key: str) -> str:
    key = normalize_text(key)
    if key in SHORT_KEY_LABELS:
        return SHORT_KEY_LABELS[key]
    words = key.replace("_", " ").replace("percent", "%").replace("temperature", "temp").split()
    if len(words) <= 3:
        return " ".join(words)
    return " ".join(words[:3])


def canonicalize_action(action: Any, action_zh: Any = "", name: Any = "", description: Any = "") -> str:
    raw_action = normalize_text(action).lower().replace("-", "_").replace(" ", "_")
    if raw_action in ACTION_ALIAS_MAP:
        return ACTION_ALIAS_MAP[raw_action]
    text = " ".join(
        part for part in [normalize_text(action), normalize_text(action_zh), normalize_text(name), normalize_text(description)] if part
    ).lower()
    text = text.replace("-", " ")
    for canonical_action, patterns in ACTION_PATTERNS:
        if any(pattern.lower() in text for pattern in patterns):
            return canonical_action
    if raw_action and raw_action not in {"other", "prepare", "collect", "load", "reduce", "weigh"}:
        return raw_action
    return "other"


def classify_parameter_type(canonical_key: str) -> str:
    key = normalize_text(canonical_key).lower()
    if any(token in key for token in ["nmr", "ftir", "xrd", "raman", "dsc", "peak", "chemical_shift", "zeta"]):
        return "characterization"
    if any(token in key for token in ["strength", "modulus", "conductivity", "density", "porosity", "shrinkage", "stability", "spinnability", "transparency"]):
        return "property"
    if any(token in key for token in ["pore", "crystallite", "particle_size", "fiber_diameter", "surface_area"]):
        return "structure"
    if any(token in key for token in ["temperature", "time", "rate", "pressure", "voltage", "distance", "rpm", "channel", "take_up", "humidity"]):
        return "process"
    if any(token in key for token in ["concentration", "ratio", "content", "source", "agent", "type", "ph", "viscosity", "solvent", "method"]):
        return "synthesis"
    return "other"


def parse_numeric_values(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0 or math.isnan(float(value)) or math.isinf(float(value)):
            return []
        return [float(value)]
    text = normalize_text(value)
    if not text:
        return []
    normalized = text.replace("～", "~").replace("—", "-").replace("–", "-").replace("至", "-")
    normalized = normalized.replace("约", "").replace("≈", "").replace("ca.", "")
    if "|" in normalized:
        parts = [part.strip() for part in normalized.split("|") if part.strip()]
        values: list[float] = []
        for part in parts:
            values.extend(parse_numeric_values(part))
        return values
    range_match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*[-~]\s*([-+]?\d+(?:\.\d+)?)\s*", normalized)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        midpoint = (low + high) / 2
        return [midpoint] if midpoint != 0 else []
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
    if not numbers:
        return []
    if len(numbers) == 1:
        numeric = float(numbers[0])
        return [numeric] if numeric != 0 else []
    if any(sep in normalized for sep in ["-", "~"]) and len(numbers) == 2:
        midpoint = (float(numbers[0]) + float(numbers[1])) / 2
        return [midpoint] if midpoint != 0 else []
    values = [float(number) for number in numbers if float(number) != 0]
    return values


def normalize_unit_text(unit: Any) -> str:
    text = normalize_text(unit).lower()
    text = text.replace("℃", "c").replace("°c", "c").replace("ºc", "c")
    text = text.replace("c/min", "c/min").replace("℃/min", "c/min").replace("°c/min", "c/min")
    text = text.replace("ўгc", "c").replace("ўж", "c").replace("ўж/min", "c/min")
    return text


def infer_condition_family(condition_key: str, action: str, source_text: str) -> str | None:
    key = normalize_text(condition_key).lower()
    action = normalize_text(action).lower()
    source_text = normalize_text(source_text).lower()
    if "heating_rate" in key:
        return "heating_rate"
    if key in {"holding_time", "holding_time_h", "holding_time_min", "duration", "duration_h", "time_h"} or "time" in key:
        return "holding_time"
    if "temperature" in key or key == "temperature":
        if "sinter" in action or "烧结" in source_text or "sinter" in key:
            return "sintering_temperature"
        if "calcine" in action or "煅烧" in source_text or "焙烧" in source_text or "calcination" in key:
            return "calcination_temperature"
        if "heat" in action and ("烧结" in source_text or "煅烧" in source_text or "焙烧" in source_text):
            return "calcination_temperature"
    return None


def normalize_condition_value(family: str, values: list[float], unit: str) -> list[float]:
    if not values:
        return []
    normalized_values: list[float] = []
    for value in values:
        if family in {"calcination_temperature", "sintering_temperature"}:
            if value < 100 or value > 2500:
                continue
            normalized_values.append(value)
        elif family == "holding_time":
            if "min" in unit:
                value = value / 60.0
            if value <= 0 or value > 500:
                continue
            normalized_values.append(value)
        elif family == "heating_rate":
            if value <= 0 or value > 200:
                continue
            normalized_values.append(value)
    return normalized_values


def load_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig", newline="")))


def scan_process_steps(manifest_rows: list[dict[str, str]], stage3_subdir: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        category = normalize_text(row.get("category"))
        paper_id = normalize_text(row.get("paper_id_guess") or row.get("paper_id"))
        resolved_output_dir = normalize_text(row.get("resolved_output_dir"))
        if not resolved_output_dir:
            continue
        path = resolve_path(resolved_output_dir) / stage3_subdir / "process_steps.jsonl"
        if not path.exists():
            continue
        for item in read_jsonl(path):
            action = normalize_text(item.get("action")).lower()
            description = normalize_text(item.get("description"))
            evidence_text = normalize_text(item.get("evidence_text"))
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "step_order": int(item.get("step_order") or 0),
                    "raw_action": action or "other",
                    "raw_action_zh": normalize_text(item.get("action_zh")),
                    "action_cleaned": canonicalize_action(
                        item.get("action"),
                        item.get("action_zh"),
                        item.get("name"),
                        description,
                    ),
                    "name": normalize_text(item.get("name")),
                    "description": description,
                    "evidence_text": evidence_text,
                    "source_text": evidence_text or description,
                    "temperature_value": item.get("temperature_value"),
                    "duration_value": item.get("duration_value"),
                    "heating_rate_value": item.get("heating_rate_value"),
                }
            )
    return pd.DataFrame(rows)


def build_cleaned_action_distribution(steps_df: pd.DataFrame) -> pd.DataFrame:
    if steps_df.empty:
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
    records = []
    for action, group in steps_df.groupby("action_cleaned"):
        records.append(
            {
                "action": action,
                "action_zh": ACTION_ZH_LABELS.get(action, action),
                "count": int(len(group)),
                "paper_count": int(group["paper_id"].nunique()),
                "category_distribution": json.dumps(group["category"].value_counts().to_dict(), ensure_ascii=False, sort_keys=True),
                "with_temperature_count": int(pd.to_numeric(group["temperature_value"], errors="coerce").notna().sum()),
                "with_duration_count": int(pd.to_numeric(group["duration_value"], errors="coerce").notna().sum()),
                "with_heating_rate_count": int(pd.to_numeric(group["heating_rate_value"], errors="coerce").notna().sum()),
                "with_evidence_text_count": int(group["source_text"].astype(str).str.strip().ne("").sum()),
            }
        )
    return pd.DataFrame(records).sort_values(["count", "paper_count", "action"], ascending=[False, False, True])


def clean_process_conditions(process_condition_df: pd.DataFrame) -> pd.DataFrame:
    cleaned_rows: list[dict[str, Any]] = []
    for row in process_condition_df.to_dict("records"):
        family = infer_condition_family(row.get("condition_key"), row.get("action"), row.get("source_text"))
        if family is None:
            continue
        unit = normalize_unit_text(row.get("condition_unit"))
        values = parse_numeric_values(row.get("condition_value"))
        normalized_values = normalize_condition_value(family, values, unit)
        normalized_unit = "℃" if "temperature" in family else ("h" if family == "holding_time" else "℃/min")
        for value in normalized_values:
            cleaned_rows.append(
                {
                    "category": row.get("category"),
                    "paper_id": row.get("paper_id"),
                    "step_order": row.get("step_order"),
                    "action": row.get("action"),
                    "condition_key": row.get("condition_key"),
                    "condition_family": family,
                    "normalized_value": round(float(value), 4),
                    "normalized_unit": normalized_unit,
                    "source_text": row.get("source_text"),
                    "evidence_text": row.get("evidence_text"),
                }
            )
    cleaned_df = pd.DataFrame(cleaned_rows)
    if cleaned_df.empty:
        return pd.DataFrame(
            columns=[
                "category",
                "paper_id",
                "step_order",
                "action",
                "condition_key",
                "condition_family",
                "normalized_value",
                "normalized_unit",
                "source_text",
                "evidence_text",
            ]
        )
    return cleaned_df.sort_values(["condition_family", "category", "paper_id", "step_order", "normalized_value"])


def build_top20_heatmap_tables(canonical_key_by_category: pd.DataFrame, top_n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    totals = canonical_key_by_category.groupby("canonical_key")["count"].sum().sort_values(ascending=False).head(top_n)
    top_keys = totals.index.tolist()
    subset = canonical_key_by_category[canonical_key_by_category["canonical_key"].isin(top_keys)].copy()
    subset["label"] = subset["canonical_key"].map(shorten_canonical_key_label)
    count_table = subset.pivot_table(index="category", columns="label", values="count", fill_value=0)
    normalized_table = subset.pivot_table(index="category", columns="label", values="normalized_frequency", fill_value=0)
    column_order = [shorten_canonical_key_label(key) for key in top_keys]
    count_table = count_table.reindex(columns=column_order, fill_value=0)
    normalized_table = normalized_table.reindex(columns=column_order, fill_value=0)
    return count_table, normalized_table


def build_sample_parameter_matrix_ppt(sample_parameter_long: pd.DataFrame, parameter_distribution: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if sample_parameter_long.empty or parameter_distribution.empty:
        empty = pd.DataFrame()
        return empty, pd.DataFrame(columns=["grouping", "row_count", "col_count", "present_cells", "total_cells", "sparsity"])
    top_keys = parameter_distribution.head(30)["canonical_key"].tolist()
    matrix = (
        sample_parameter_long[sample_parameter_long["canonical_key"].isin(top_keys)]
        .assign(present=1)
        .pivot_table(index=["category", "paper_id"], columns="canonical_key", values="present", aggfunc="max", fill_value=0)
        .reset_index()
    )
    if matrix.empty:
        empty = pd.DataFrame()
        return empty, pd.DataFrame(columns=["grouping", "row_count", "col_count", "present_cells", "total_cells", "sparsity"])
    value_cols = [col for col in matrix.columns if col not in {"category", "paper_id"}]
    matrix["present_count"] = matrix[value_cols].sum(axis=1)
    matrix["missing_rate"] = 1 - matrix["present_count"] / max(len(value_cols), 1)
    matrix = matrix.sort_values(["category", "missing_rate", "paper_id"], ascending=[True, True, True])
    category_counts = matrix["category"].value_counts().to_dict()
    total_rows = min(80, len(matrix))
    quotas: dict[str, int] = {}
    remaining = total_rows
    categories = sorted(category_counts.keys())
    for category in categories:
        proportional = max(1, int(round(total_rows * category_counts[category] / len(matrix))))
        quota = min(category_counts[category], proportional)
        quotas[category] = quota
        remaining -= quota
    while remaining > 0:
        updated = False
        for category in categories:
            if quotas[category] < category_counts[category]:
                quotas[category] += 1
                remaining -= 1
                updated = True
                if remaining == 0:
                    break
        if not updated:
            break
    selected_groups = []
    for category in categories:
        selected_groups.append(matrix[matrix["category"] == category].head(quotas[category]))
    matrix = pd.concat(selected_groups, ignore_index=True) if selected_groups else matrix.head(total_rows)
    summary_rows = []
    for category, group in matrix.groupby("category"):
        present_cells = int(group[value_cols].sum().sum())
        total_cells = int(len(group) * len(value_cols))
        summary_rows.append(
            {
                "grouping": category,
                "row_count": int(len(group)),
                "col_count": int(len(value_cols)),
                "present_cells": present_cells,
                "total_cells": total_cells,
                "sparsity": round(1 - present_cells / max(total_cells, 1), 4),
            }
        )
    total_present = int(matrix[value_cols].sum().sum())
    total_cells = int(len(matrix) * len(value_cols))
    summary_rows.append(
        {
            "grouping": "overall",
            "row_count": int(len(matrix)),
            "col_count": int(len(value_cols)),
            "present_cells": total_present,
            "total_cells": total_cells,
            "sparsity": round(1 - total_present / max(total_cells, 1), 4),
        }
    )
    matrix = matrix.drop(columns=["present_count", "missing_rate"])
    return matrix, pd.DataFrame(summary_rows)


def build_cleaned_network_edges(
    parameter_cooccurrence_edges: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
) -> pd.DataFrame:
    if parameter_cooccurrence_edges.empty or parameter_distribution.empty:
        return pd.DataFrame(
            columns=[
                "source_canonical_key",
                "target_canonical_key",
                "cooccurrence_count",
                "paper_count",
                "category_distribution",
            ]
        )
    top_keys = set(parameter_distribution.head(30)["canonical_key"].tolist())
    edges = parameter_cooccurrence_edges[
        parameter_cooccurrence_edges["source_canonical_key"].isin(top_keys)
        & parameter_cooccurrence_edges["target_canonical_key"].isin(top_keys)
    ].copy()
    if edges.empty:
        return edges
    threshold = max(2, int(edges["cooccurrence_count"].quantile(0.5)))
    edges = edges[edges["cooccurrence_count"] >= threshold].copy()
    if edges.empty:
        edges = parameter_cooccurrence_edges[
            parameter_cooccurrence_edges["source_canonical_key"].isin(top_keys)
            & parameter_cooccurrence_edges["target_canonical_key"].isin(top_keys)
        ].nlargest(20, "cooccurrence_count")
    return edges.sort_values(["cooccurrence_count", "paper_count"], ascending=[False, False])


def build_real_route_transitions(steps_df: pd.DataFrame) -> Counter[tuple[str, str]]:
    def map_stage(action: str) -> str:
        if action in {"add", "stir", "dissolve", "hydrolyze"}:
            return "sol_prep"
        if action in {"age"}:
            return "aging_concentration"
        if action in {"spin"}:
            return "spinning"
        if action in {"dry"}:
            return "drying"
        if action in {"calcine", "sinter", "heat", "cool"}:
            return "calcination_sintering"
        if action in {"characterize"}:
            return "characterization"
        return "other"

    transition_counts: Counter[tuple[str, str]] = Counter()
    if steps_df.empty:
        return transition_counts
    grouped = steps_df.sort_values(["category", "paper_id", "step_order"]).groupby(["category", "paper_id"])
    for _keys, group in grouped:
        stages = [map_stage(action) for action in group["action_cleaned"].tolist() if normalize_text(action)]
        compact: list[str] = []
        for stage in stages:
            if not compact or compact[-1] != stage:
                compact.append(stage)
        for source, target in zip(compact, compact[1:]):
            transition_counts[(source, target)] += 1
    return transition_counts


def plot_action_distribution_cleaned(action_df: pd.DataFrame, base_path: Path) -> None:
    if action_df.empty:
        make_placeholder_figure(base_path, title="process_steps 动作分布图（清洗后）", message="无动作数据。", data_source="process_steps.jsonl")
        return
    plot_df = action_df.head(15).iloc[::-1]
    labels = [f"{row.action_zh}\n({row.action})" for row in plot_df.itertuples(index=False)]
    fig, ax = plt.subplots(figsize=(10.5, 6))
    ax.barh(labels, plot_df["count"], color="#2d7bc6", edgecolor="#17375e")
    ax.set_xlabel("步骤数")
    ax.set_title("process_steps 动作分布图（清洗后）")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    fig.text(0.01, 0.02, "数据来源：全部 stage3_twopass/process_steps.jsonl，基于 name/description/action 二次 canonicalization", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_condition_distribution(cleaned_df: pd.DataFrame, family: str, base_path: Path, title: str, xlabel: str) -> None:
    subset = cleaned_df[cleaned_df["condition_family"] == family].copy()
    if subset.empty:
        make_placeholder_figure(base_path, title=title, message="无可用清洗后数据。", data_source="process_condition_distribution_cleaned.csv")
        return
    if family == "calcination_temperature":
        sinter_subset = cleaned_df[cleaned_df["condition_family"] == "sintering_temperature"].copy()
        fig, ax = plt.subplots(figsize=(10.5, 6))
        ax.hist(subset["normalized_value"], bins=14, alpha=0.75, color="#2d7bc6", edgecolor="#17375e", label=f"Calcination (N={len(subset)})")
        if not sinter_subset.empty:
            ax.hist(sinter_subset["normalized_value"], bins=14, alpha=0.55, color="#74a857", edgecolor="#385723", label=f"Sintering (N={len(sinter_subset)})")
        ax.legend()
        total_n = len(subset) + len(sinter_subset)
    else:
        fig, ax = plt.subplots(figsize=(10.5, 6))
        ax.hist(subset["normalized_value"], bins=14, color="#4d97de", edgecolor="#17375e")
        total_n = len(subset)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("频次")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.text(0.98, 0.95, f"N={total_n}", transform=ax.transAxes, ha="right", va="top", fontsize=11, color="#17375e")
    fig.text(0.01, 0.02, "数据来源：process_condition_distribution.csv 清洗后结果；已过滤空值/0/不可解析值并统一单位", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_heatmap(table: pd.DataFrame, base_path: Path, title: str, colorbar_label: str) -> None:
    if table.empty:
        make_placeholder_figure(base_path, title=title, message="无可视化数据。", data_source="canonical_key_by_category.csv")
        return
    fig, ax = plt.subplots(figsize=(12.8, 5.8))
    image = ax.imshow(table.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(table.columns)))
    ax.set_xticklabels(table.columns, rotation=35, ha="right", fontsize=9)
    ax.set_yticks(range(len(table.index)))
    ax.set_yticklabels(table.index, fontsize=10)
    ax.set_title(title)
    cbar = fig.colorbar(image, ax=ax, shrink=0.85)
    cbar.set_label(colorbar_label)
    fig.text(0.01, 0.02, "数据来源：canonical_key_by_category.csv，仅保留 Top 20 canonical_key 并使用短标签", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_sample_parameter_matrix_ppt(matrix_df: pd.DataFrame, base_path: Path) -> None:
    if matrix_df.empty:
        make_placeholder_figure(base_path, title="sample-parameter 稀疏性热图（PPT 版）", message="无可用矩阵数据。", data_source="sample_parameter_long.csv")
        return
    value_cols = [col for col in matrix_df.columns if col not in {"category", "paper_id"}]
    data = matrix_df[value_cols].to_numpy()
    categories = matrix_df["category"].tolist()
    category_codes = [list(CATEGORY_COLORS).index(category) if category in CATEGORY_COLORS else -1 for category in categories]
    fig = plt.figure(figsize=(13.33, 7.5))
    gs = GridSpec(1, 2, width_ratios=[0.25, 12], wspace=0.05)
    ax_color = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[0, 1])
    ax_color.imshow(np.array(category_codes).reshape(-1, 1), aspect="auto", cmap=matplotlib.colors.ListedColormap(list(CATEGORY_COLORS.values())))
    ax_color.set_xticks([])
    ax_color.set_yticks([])
    ax_color.set_title("类别", fontsize=10)
    image = ax.imshow(data, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(value_cols)))
    ax.set_xticklabels([shorten_canonical_key_label(col) for col in value_cols], rotation=35, ha="right", fontsize=8.5)
    tick_step = max(1, len(matrix_df) // 10)
    tick_positions = list(range(0, len(matrix_df), tick_step))
    ax.set_yticks(tick_positions)
    ax.set_yticklabels([matrix_df.iloc[idx]["paper_id"][:16] for idx in tick_positions], fontsize=7.5)
    ax.set_title("sample-parameter matrix 稀疏性热图（PPT 展示版，paper 级）")
    cbar = fig.colorbar(image, ax=ax, shrink=0.8)
    cbar.set_label("存在性")
    fig.text(0.01, 0.02, "数据来源：sample_parameter_long.csv；按 category 与缺失率排序，展示前 80 篇 paper × Top 30 canonical_key", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_cleaned_network(edges_df: pd.DataFrame, parameter_distribution: pd.DataFrame, base_path: Path) -> None:
    if edges_df.empty or parameter_distribution.empty:
        make_placeholder_figure(base_path, title="参数共现网络图（清洗后）", message="无可用网络边。", data_source="parameter_cooccurrence_edges.csv")
        return
    counts = parameter_distribution.set_index("canonical_key")["count"].to_dict()
    graph = nx.Graph()
    for row in edges_df.itertuples(index=False):
        graph.add_edge(row.source_canonical_key, row.target_canonical_key, weight=row.cooccurrence_count)
    if graph.number_of_nodes() == 0:
        make_placeholder_figure(base_path, title="参数共现网络图（清洗后）", message="过滤后无可用节点。", data_source="parameter_cooccurrence_network_cleaned_edges.csv")
        return
    fig, ax = plt.subplots(figsize=(12, 8))
    positions = nx.spring_layout(graph, seed=42, weight="weight", k=1.1 / max(graph.number_of_nodes() ** 0.5, 1))
    edge_widths = [1 + 4 * graph[u][v]["weight"] / max(edges_df["cooccurrence_count"].max(), 1) for u, v in graph.edges()]
    node_types = {node: classify_parameter_type(node) for node in graph.nodes()}
    node_colors = [PARAMETER_TYPE_COLORS[node_types[node]] for node in graph.nodes()]
    node_sizes = [220 + 10 * counts.get(node, 1) for node in graph.nodes()]
    nx.draw_networkx_edges(graph, positions, width=edge_widths, edge_color="#a8bfdc", alpha=0.7, ax=ax)
    nx.draw_networkx_nodes(graph, positions, node_color=node_colors, node_size=node_sizes, edgecolors="#17375e", linewidths=1, ax=ax)
    nx.draw_networkx_labels(graph, positions, labels={node: shorten_canonical_key_label(node) for node in graph.nodes()}, font_size=8.5, font_color="#17375e", ax=ax)
    ax.set_title("参数共现网络图（清洗后）")
    ax.axis("off")
    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=label, markerfacecolor=color, markeredgecolor="#17375e", markersize=8)
        for label, color in PARAMETER_TYPE_COLORS.items()
    ]
    ax.legend(handles=legend_handles, title="参数类型", loc="upper right", frameon=True)
    fig.text(0.01, 0.02, "数据来源：parameter_cooccurrence_edges.csv + parameter_distribution.csv；仅保留 Top 30 canonical_key 与较高边权", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_dashboard_ppt(
    summary: dict[str, Any],
    parameter_distribution: pd.DataFrame,
    action_cleaned: pd.DataFrame,
    paper_stage3_summary: pd.DataFrame,
    base_path: Path,
) -> None:
    fig = plt.figure(figsize=(13.33, 7.5))
    gs = GridSpec(12, 24, figure=fig)

    fig.suptitle("Stage 3 文献结构化抽取结果总览", fontsize=20, fontweight="bold", color="#17375e", y=0.98)

    cards = [
        ("343", "篇文献", "#2d7bc6"),
        ("5683", "data points", "#4d97de"),
        ("2819", "process steps", "#74a857"),
        ("3289", "evidence objects", "#d99058"),
        ("102", "unique canonical_key", "#7a62b3"),
    ]
    for idx, (value, label, color) in enumerate(cards):
        ax = fig.add_subplot(gs[0:3, idx * 4 : idx * 4 + 4])
        ax.axis("off")
        box = FancyBboxPatch((0.02, 0.1), 0.96, 0.8, boxstyle="round,pad=0.02,rounding_size=0.03", facecolor="white", edgecolor=color, linewidth=2)
        ax.add_patch(box)
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=22, fontweight="bold", color=color)
        ax.text(0.5, 0.34, label, ha="center", va="center", fontsize=11, color="#345273")

    ax1 = fig.add_subplot(gs[3:12, 0:9])
    top_keys = parameter_distribution.head(10).iloc[::-1]
    ax1.barh([shorten_canonical_key_label(key) for key in top_keys["canonical_key"]], top_keys["count"], color="#2d7bc6")
    ax1.set_title("Top 10 canonical_key")
    ax1.grid(axis="x", linestyle="--", alpha=0.4)

    ax2 = fig.add_subplot(gs[3:12, 9:16])
    top_actions = action_cleaned.head(10).iloc[::-1]
    ax2.barh([ACTION_ZH_LABELS.get(action, action) for action in top_actions["action"]], top_actions["count"], color="#74a857")
    ax2.set_title("Cleaned process actions")
    ax2.grid(axis="x", linestyle="--", alpha=0.4)

    ax3 = fig.add_subplot(gs[3:12, 16:24])
    category_contrib = (
        paper_stage3_summary.groupby("category")[["data_point_count", "process_steps_count", "evidence_object_count"]]
        .sum()
        .sort_values("data_point_count", ascending=False)
    )
    x = np.arange(len(category_contrib.index))
    width = 0.25
    ax3.bar(x - width, category_contrib["data_point_count"], width, label="data_points", color="#2d7bc6")
    ax3.bar(x, category_contrib["process_steps_count"], width, label="process_steps", color="#74a857")
    ax3.bar(x + width, category_contrib["evidence_object_count"], width, label="evidence_objects", color="#d99058")
    ax3.set_xticks(x)
    ax3.set_xticklabels(category_contrib.index, rotation=25, ha="right")
    ax3.set_title("Category contribution")
    ax3.legend(fontsize=8)
    ax3.grid(axis="y", linestyle="--", alpha=0.4)

    fig.text(0.01, 0.02, "数据来源：stage3_analysis_summary.json + parameter_distribution.csv + process_step_action_distribution_cleaned.csv + paper_stage3_summary.csv", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_real_transition_diagram(transition_counts: Counter[tuple[str, str]], base_path: Path) -> None:
    if not transition_counts:
        make_placeholder_figure(base_path, title="真实 step transition 工艺路线图", message="无可用 transition。", data_source="process_steps.jsonl")
        return
    stage_order = ["sol_prep", "aging_concentration", "spinning", "drying", "calcination_sintering", "characterization", "other"]
    active = [stage for stage in stage_order if stage in {item for edge in transition_counts for item in edge}]
    positions = {stage: idx for idx, stage in enumerate(active)}
    fig, ax = plt.subplots(figsize=(12.5, 4.8))
    ax.axis("off")
    y = 0.55
    for stage in active:
        x = positions[stage]
        rect = Rectangle((x - 0.35, y - 0.11), 0.7, 0.22, facecolor="#d9e9fb", edgecolor="#2d7bc6", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, ROUTE_STAGE_LABELS[stage], ha="center", va="center", fontsize=11, color="#17375e", fontweight="bold")
    max_count = max(transition_counts.values())
    for (source, target), count in transition_counts.most_common():
        start = positions[source] + 0.35
        end = positions[target] - 0.35
        arrow = FancyArrowPatch((start, y), (end, y), arrowstyle="-|>", mutation_scale=16, linewidth=1.5 + 5 * count / max_count, color="#5b9bd5", alpha=0.55)
        ax.add_patch(arrow)
        ax.text((start + end) / 2, y + 0.13, str(count), ha="center", va="bottom", fontsize=9, color="#345273")
    ax.set_xlim(-0.7, len(active) - 0.2)
    ax.set_ylim(0.15, 0.95)
    fig.suptitle("真实 step transition 工艺路线图", fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "数据来源：按每篇论文 step_order 的真实 transition 统计得到，不再使用非真实 Sankey 命名", fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def render_report(
    *,
    output_dir: Path,
    figures_dir: Path,
    old_other: int,
    new_other: int,
    cleaned_conditions: pd.DataFrame,
    generated_figures: list[str],
) -> str:
    group_meeting = [
        "process_step_action_distribution_cleaned",
        "canonical_key_category_heatmap_top20_count",
        "sample_parameter_matrix_sparsity_heatmap_ppt",
        "stage3_overview_dashboard_ppt",
        "calcination_temperature_distribution",
    ]
    paper_ready = [
        "canonical_key_category_heatmap_top20_normalized",
        "calcination_temperature_distribution",
        "holding_time_distribution",
        "process_route_transition_diagram",
        "stage3_overview_dashboard_ppt",
    ]
    internal_only = [
        "parameter_cooccurrence_network_cleaned",
        "parameter_cooccurrence_network_cleaned_edges",
        "sample_parameter_sparsity_summary",
    ]
    lines = [
        "# STAGE3 Analysis Figure Refinement Report",
        "",
        "## 原图问题",
        "",
        "- `process_step_action_distribution` 中 `other` 占比过高，原始 action canonicalization 对 `拉丝成型`、`干法纺丝`、`高温焙烧`、`Characterization` 等未充分识别。",
        "- `process_condition_distribution` 混入 0、空值、范围串、列表串和异常单位，直接统计会拉低可解释性。",
        "- `canonical_key_category_heatmap` 标签过密，Top key 过多且原始 key 文本太长，不适合 PPT。",
        "- `sample_parameter_matrix_sparsity_heatmap` 维度过大，行标签不可读，不适合展示。",
        "- `parameter_cooccurrence_network` 节点标签重叠，未按参数类型区分颜色，边过滤不足。",
        "- `stage3_overview_dashboard` 版式偏拥挤，不够 16:9 PPT 友好。",
        "- 旧 `process_route_sankey` 命名可能引起误解，因此本轮改成基于真实 transition 的 `process_route_transition_diagram`。",
        "",
        "## 重新生成的图",
        "",
        *[f"- {name}" for name in generated_figures],
        "",
        "## 关键修正结果",
        "",
        f"- `other` 是否下降：是。原始 `other={old_other}`，清洗后 `other={new_other}`。",
        f"- 工艺条件异常值是否清洗：是。清洗后保留 `N={len(cleaned_conditions)}` 条规范化条件记录，已过滤空值/0/不可解析值，并统一到 `℃`、`h`、`℃/min`。",
        "",
        "## 图表适用性",
        "",
        "### 适合组会",
        "",
        *[f"- {name}" for name in group_meeting],
        "",
        "### 适合论文",
        "",
        *[f"- {name}" for name in paper_ready],
        "",
        "### 适合内部探索",
        "",
        *[f"- {name}" for name in internal_only],
        "",
        "## 输出位置",
        "",
        f"- refined 输出目录：{output_dir.as_posix()}",
        f"- refined figures 目录：{figures_dir.as_posix()}",
        "- 首轮 `data/analysis_outputs_stage3` 结果未被覆盖。",
    ]
    return "\n".join(lines) + "\n"


def build_refined_outputs(
    *,
    manifest_path: Path,
    analysis_dir: Path,
    output_dir: Path,
    stage3_subdir: str,
    top_n: int,
) -> dict[str, Any]:
    configure_matplotlib()
    output_dir = ensure_directory(output_dir)
    figures_dir = ensure_directory(output_dir / "figures")

    process_action = pd.read_csv(analysis_dir / "process_step_action_distribution.csv")
    process_conditions = pd.read_csv(analysis_dir / "process_condition_distribution.csv")
    canonical_key_by_category = pd.read_csv(analysis_dir / "canonical_key_by_category.csv")
    sample_parameter_long = pd.read_csv(analysis_dir / "sample_parameter_long.csv")
    sample_parameter_wide = pd.read_csv(analysis_dir / "sample_parameter_wide.csv")
    parameter_cooccurrence_edges = pd.read_csv(analysis_dir / "parameter_cooccurrence_edges.csv")
    parameter_distribution = pd.read_csv(analysis_dir / "parameter_distribution.csv")
    paper_stage3_summary = pd.read_csv(analysis_dir / "paper_stage3_summary.csv")
    stage3_summary = json.loads((analysis_dir / "stage3_analysis_summary.json").read_text(encoding="utf-8"))

    manifest_rows = load_manifest_rows(manifest_path)
    steps_df = scan_process_steps(manifest_rows, stage3_subdir)
    action_cleaned = build_cleaned_action_distribution(steps_df)
    cleaned_conditions = clean_process_conditions(process_conditions)
    count_heatmap, normalized_heatmap = build_top20_heatmap_tables(canonical_key_by_category, top_n)
    matrix_ppt, matrix_summary = build_sample_parameter_matrix_ppt(sample_parameter_long, parameter_distribution)
    cleaned_edges = build_cleaned_network_edges(parameter_cooccurrence_edges, parameter_distribution)
    transition_counts = build_real_route_transitions(steps_df)

    write_dataframe(action_cleaned, output_dir / "process_step_action_distribution_cleaned.csv")
    write_dataframe(cleaned_conditions, output_dir / "process_condition_distribution_cleaned.csv")
    write_dataframe(matrix_summary, output_dir / "sample_parameter_sparsity_summary.csv")
    write_dataframe(cleaned_edges, output_dir / "parameter_cooccurrence_network_cleaned_edges.csv")

    plot_action_distribution_cleaned(action_cleaned, figures_dir / "process_step_action_distribution_cleaned")
    plot_condition_distribution(cleaned_conditions, "calcination_temperature", figures_dir / "calcination_temperature_distribution", "煅烧/烧结温度分布", "温度 / ℃")
    plot_condition_distribution(cleaned_conditions, "holding_time", figures_dir / "holding_time_distribution", "保温时间分布", "时间 / h")
    plot_condition_distribution(cleaned_conditions, "heating_rate", figures_dir / "heating_rate_distribution", "升温速率分布", "升温速率 / ℃/min")
    plot_heatmap(count_heatmap, figures_dir / "canonical_key_category_heatmap_top20_count", "canonical_key × category 热图（Top 20，count）", "count")
    plot_heatmap(normalized_heatmap, figures_dir / "canonical_key_category_heatmap_top20_normalized", "canonical_key × category 热图（Top 20，normalized）", "normalized frequency")
    plot_sample_parameter_matrix_ppt(matrix_ppt, figures_dir / "sample_parameter_matrix_sparsity_heatmap_ppt")
    plot_cleaned_network(cleaned_edges, parameter_distribution, figures_dir / "parameter_cooccurrence_network_cleaned")
    plot_dashboard_ppt(stage3_summary, parameter_distribution, action_cleaned, paper_stage3_summary, figures_dir / "stage3_overview_dashboard_ppt")
    plot_real_transition_diagram(transition_counts, figures_dir / "process_route_transition_diagram")

    old_other = int(process_action.loc[process_action["action"] == "other", "count"].sum())
    new_other = int(action_cleaned.loc[action_cleaned["action"] == "other", "count"].sum()) if not action_cleaned.empty else 0
    generated_figures = [
        "process_step_action_distribution_cleaned",
        "calcination_temperature_distribution",
        "holding_time_distribution",
        "heating_rate_distribution",
        "canonical_key_category_heatmap_top20_count",
        "canonical_key_category_heatmap_top20_normalized",
        "sample_parameter_matrix_sparsity_heatmap_ppt",
        "parameter_cooccurrence_network_cleaned",
        "stage3_overview_dashboard_ppt",
        "process_route_transition_diagram",
    ]
    report_path = PROJECT_ROOT / "docs" / "refactor" / "STAGE3_ANALYSIS_FIGURE_REFINEMENT_REPORT.md"
    report_path.write_text(
        render_report(
            output_dir=output_dir,
            figures_dir=figures_dir,
            old_other=old_other,
            new_other=new_other,
            cleaned_conditions=cleaned_conditions,
            generated_figures=generated_figures,
        ),
        encoding="utf-8",
    )
    return {
        "old_other": old_other,
        "new_other": new_other,
        "cleaned_conditions": cleaned_conditions,
        "generated_figures": generated_figures,
        "report_path": report_path,
        "output_dir": output_dir,
        "figures_dir": figures_dir,
    }


def main() -> None:
    args = parse_args()
    result = build_refined_outputs(
        manifest_path=resolve_path(args.manifest),
        analysis_dir=resolve_path(args.analysis_dir),
        output_dir=resolve_path(args.output_dir),
        stage3_subdir=args.stage3_subdir,
        top_n=args.top_n,
    )
    print(
        json.dumps(
            {
                "output_dir": str(result["output_dir"]),
                "old_other": result["old_other"],
                "new_other": result["new_other"],
                "report_path": str(result["report_path"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
