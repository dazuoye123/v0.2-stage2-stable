"""
Stage 3 Analysis Outputs V2 — Comprehensive fix script.

Produces all required charts and data files into data/analysis_outputs_stage3_v2/.
Reads from existing data/outputs/ (process_steps.jsonl etc.) and
data/analysis_outputs_stage3/ CSVs.

Does NOT call VLM, does NOT rerun Stage 4A, does NOT do PDF image understanding.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import warnings
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
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle


# ============================================================================
# Action canonicalization — comprehensive three-layer rules
# ============================================================================

# Layer 1: exact alias map
ACTION_ALIAS_MAP: dict[str, str] = {
    "add": "add", "mix": "add", "dropwise_add": "add", "add_polymer": "add",
    "impregnate": "add", "inject": "add", "load": "add", "weigh": "add",
    "prepare": "add", "blend": "add", "disperse": "add", "配制": "add",
    "称取": "add", "称量": "add",
    "stir": "stir", "agitate": "stir", "搅拌": "stir", "agitat": "stir",
    "dissolve": "dissolve", "溶解": "dissolve", "dissolution": "dissolve",
    "hydrolyze": "hydrolyze", "水解": "hydrolyze", "hydroly": "hydrolyze",
    "peptize": "peptize", "胶溶": "peptize", "peptiz": "peptize",
    "age": "age", "aging": "age", "ageing": "age", "老化": "age", "陈化": "age",
    "concentrate": "concentrate", "evaporate": "concentrate",
    "rotary_evaporate": "concentrate", "浓缩": "concentrate", "旋蒸": "concentrate",
    "gel": "gelation", "gelation": "gelation", "凝胶": "gelation", "凝胶化": "gelation",
    "filter": "filter", "过滤": "filter", "filtration": "filter", "抽滤": "filter",
    "wash": "wash", "洗涤": "wash", "漂洗": "wash", "rins": "wash",
    "dry": "dry", "干燥": "dry", "烘干": "dry", "drying": "dry", "freeze_dry": "dry",
    "freeze-dry": "dry", "冷冻干燥": "dry",
    "calcine": "calcine", "煅烧": "calcine", "焙烧": "calcine", "calcination": "calcine",
    "sinter": "sinter", "烧结": "sinter", "sintering": "sinter",
    "heat": "heat", "加热": "heat", "升温": "heat", "保温": "heat",
    "hold": "heat", "soaking": "heat", "holding": "heat",
    "cool": "cool", "冷却": "cool", "降温": "cool", "淬火": "cool",
    "spin": "spin", "electrospin": "spin", "纺丝": "spin", "静电纺丝": "spin",
    "拉丝": "spin", "spinning": "spin", "fiber_drawing": "spin", "extrusion": "spin",
    "dry_spinning": "spin", "dry-spinning": "spin", "喷丝": "spin", "成纤": "spin",
    "collect": "collect", "收集": "collect", "取样": "collect",
    "characterize": "characterize", "test": "characterize",
    "表征": "characterize", "测试": "characterize",
    "measurement": "characterize", "检测": "characterize",
    "reduce": "heat", "还原": "heat",
}

# Layer 2: regex/pattern matching (action_text + name + description + action_zh)
ACTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("spin", ["静电纺丝", "电纺", "纺丝", "拉丝", "dry spinning", "dry-spinning",
              "electrospin", "spinning", "fiber drawing", "extrusion", "喷丝",
              "成纤", "电纺丝", "湿法纺丝", "干法纺丝", "force spinning"]),
    ("calcine", ["煅烧", "焙烧", "calcination", "calcined", "calcining",
                 "muffle furnace", "马弗炉", "高温炉"]),
    ("sinter", ["烧结", "sintering", "sintered"]),
    ("dry", ["干燥", "烘干", "freeze dry", "freeze-dry", "冷冻干燥",
             "drying", "oven dry", "烘箱", "真空干燥", "dried", "风干"]),
    ("concentrate", ["浓缩", "旋蒸", "rotary evaporat", "蒸发浓缩",
                     "旋转蒸发", "减压蒸馏", "蒸馏浓缩", "concentrat",
                     "evaporat", "减压浓缩"]),
    ("gelation", ["凝胶", "gelation", "gelling", "gelation", "胶凝",
                  "sol-gel transition"]),
    ("peptize", ["胶溶", "peptiz", "解胶"]),
    ("filter", ["过滤", "抽滤", "filter", "filtration"]),
    ("wash", ["洗涤", "漂洗", "wash", "rins", "水洗", "醇洗"]),
    ("hydrolyze", ["水解", "hydrolysis", "hydrolyz"]),
    ("dissolve", ["溶解", "溶于", "dissolve", "dissolution", "solubil"]),
    ("stir", ["搅拌", "stir", "agitat", "磁力搅拌", "机械搅拌", "超声搅拌"]),
    ("age", ["老化", "陈化", "aging", "ageing", "age ", "室温放置", "静置",
             "恒温老化"]),
    ("cool", ["冷却", "降温", "cool", "淬火", "骤冷"]),
    ("heat", ["加热", "升温", "保温", "回流", "热处理", "heat", "reflux",
              "soaking", "holding", "保温处理", "升温保温", "高温处理",
              "预热", "恒温", "水浴加热", "油浴"]),
    ("characterize", ["表征", "测试", "characteriz", "measurement",
                      "xrd", "ftir", "raman", "nmr", "sem", "tem",
                      "xps", "bet", "tg", "dsc", "性能测试", "检测",
                      "分析", "测定", "观察", "扫描"]),
    ("add", ["加入", "滴加", "混合", "配制", "mix", "add", "blend",
             "disperse", "称取", "称量", "weigh", "浸渍", "impregnat",
             "负载", "load", "注入", "inject", "引入", "添加", "掺杂"]),
    ("peptize", ["peptiz", "胶溶", "解胶"]),
]

# Layer 3: Chinese/English display labels
ACTION_ZH_LABELS: dict[str, str] = {
    "add": "加入/混合",
    "stir": "搅拌",
    "dissolve": "溶解",
    "hydrolyze": "水解",
    "peptize": "胶溶",
    "age": "老化/陈化",
    "concentrate": "浓缩/旋蒸",
    "gelation": "凝胶化",
    "filter": "过滤",
    "wash": "洗涤",
    "dry": "干燥",
    "calcine": "煅烧",
    "sinter": "烧结",
    "heat": "加热/保温",
    "cool": "冷却",
    "spin": "纺丝",
    "collect": "收集",
    "characterize": "表征/测试",
    "other": "其他",
}

# ============================================================================
# Parameter type classification
# ============================================================================

PARAMETER_TYPE_COLORS: dict[str, str] = {
    "synthesis": "#2d7bc6",
    "process": "#5b9bd5",
    "structure": "#74a857",
    "property": "#d99058",
    "characterization": "#7a62b3",
    "other": "#9aa4b2",
}

CATEGORY_COLORS: dict[str, str] = {
    "applications": "#2d7bc6",
    "fiber_process": "#6aaed6",
    "mechanism": "#9cc8f4",
    "rheology": "#4b6cb7",
}

SHORT_KEY_LABELS: dict[str, str] = {
    "nmr_27Al_peak_position_ppm": "27Al NMR / ppm",
    "pH": "pH",
    "particle_size_nm": "粒径 / nm",
    "ftir_peak_position_cm_1": "FTIR峰位 / cm⁻¹",
    "Al_concentration_mol_L": "Al浓度 / mol·L⁻¹",
    "calcination_temperature_C": "煅烧温度 / °C",
    "sintering_temperature_C": "烧结温度 / °C",
    "mass_loss_wt_percent": "质量损失 / wt%",
    "aging_time_h": "老化时间 / h",
    "specific_surface_area_m2_g": "BET比表面积 / m²·g⁻¹",
    "heating_rate_C_min": "升温速率 / °C·min⁻¹",
    "aging_temperature_C": "老化温度 / °C",
    "holding_time_h": "保温时间 / h",
    "dsc_peak_temperature_C": "DSC峰温 / °C",
    "solid_content_wt_percent": "固含量 / wt%",
    "average_fiber_diameter_um": "纤维直径(μm)",
    "average_fiber_diameter_nm": "纤维直径(nm)",
    "viscosity_Pa_s": "粘度 / Pa·s",
    "tensile_strength_MPa": "拉伸强度 / MPa",
    "hydrolysis_temperature_C": "水解温度 / °C",
    "drying_temperature_C": "干燥温度 / °C",
    "drying_time_h": "干燥时间 / h",
    "xrd_peak_position_2theta_deg": "XRD 2θ / °",
    "raman_peak_position_cm_1": "Raman峰位 / cm⁻¹",
    "pore_volume_cm3_g": "孔容 / cm³·g⁻¹",
    "average_pore_size_nm": "孔径 / nm",
    "crystallite_size_nm": "晶粒尺寸 / nm",
    "spinnability": "可纺性",
    "zeta_potential_mV": "Zeta电位 / mV",
    "water_to_aluminum_molar_ratio": "H₂O/Al比",
    "acid_to_aluminum_molar_ratio": "酸/Al比",
    "stirring_time_h": "搅拌时间 / h",
    "hydrolysis_time_h": "水解时间 / h",
    "calcination_holding_time_h": "煅烧保温 / h",
    "sintering_holding_time_h": "烧结保温 / h",
    "elastic_modulus_GPa": "弹性模量 / GPa",
    "elongation_at_break_percent": "断裂伸长率 / %",
    "thermal_conductivity_W_mK": "热导率 / W·m⁻¹·K⁻¹",
    "porosity_percent": "孔隙率 / %",
    "shrinkage_percent": "收缩率 / %",
    "density_g_cm3": "密度 / g·cm⁻³",
}

ROUTE_STAGE_LABELS: dict[str, str] = {
    "sol_prep": "溶胶制备",
    "aging_concentration": "老化/浓缩",
    "spinning": "纺丝",
    "drying": "干燥",
    "calcination_sintering": "煅烧/烧结",
    "characterization": "表征/性能",
    "other": "其他",
}


# ============================================================================
# Utility functions
# ============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage3 Analysis V2 outputs with comprehensive fixes.")
    parser.add_argument("--manifest", default="data/batch_manifest/source_manifest.csv")
    parser.add_argument("--analysis-dir", default="data/analysis_outputs_stage3")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--output-dir", default="data/analysis_outputs_stage3_v2")
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--top-n", default=30, type=int)
    parser.add_argument("--paper-limit", default=50, type=int, help="Max papers for matrix heatmap rows")
    return parser.parse_args()


def resolve_path(path_value: str | Path, *, base_dir: Path = PROJECT_ROOT) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


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
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
        "Source Han Sans SC", "Arial Unicode MS", "DejaVu Sans",
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


def shorten_label(key: str) -> str:
    key = normalize_text(key)
    if key in SHORT_KEY_LABELS:
        return SHORT_KEY_LABELS[key]
    words = key.replace("_", " ").replace("percent", "%").replace("temperature", "temp").split()
    return " ".join(words[:3]) if len(words) > 3 else " ".join(words)


def classify_parameter_type(canonical_key: str) -> str:
    key = normalize_text(canonical_key).lower()
    if any(t in key for t in ["nmr", "ftir", "xrd", "raman", "dsc", "peak", "chemical_shift", "zeta"]):
        return "characterization"
    if any(t in key for t in ["strength", "modulus", "conductivity", "density", "porosity",
                               "shrinkage", "stability", "spinnability", "transparency", "elongation",
                               "tensile", "elastic", "mass_loss", "thermal_conductivity"]):
        return "property"
    if any(t in key for t in ["pore", "crystallite", "particle_size", "fiber_diameter",
                               "surface_area", "diameter", "size_nm", "size_um"]):
        return "structure"
    if any(t in key for t in ["temperature", "time", "rate", "pressure", "voltage",
                               "distance", "rpm", "channel", "take_up", "humidity",
                               "holding", "heating_rate", "duration"]):
        return "process"
    if any(t in key for t in ["concentration", "ratio", "content", "source", "agent",
                               "type", "ph", "viscosity", "solvent", "method", "molar",
                               "solid_content", "water_to", "acid_to", "al_concentration"]):
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


def normalize_unit_text(unit: Any) -> str:
    text = normalize_text(unit).lower()
    text = text.replace("℃", "c").replace("°c", "c").replace("ºc", "c")
    text = text.replace("c/min", "c/min").replace("℃/min", "c/min").replace("°c/min", "c/min")
    text = text.replace("k/min", "c/min")
    return text


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ============================================================================
# Action canonicalization (three-layer)
# ============================================================================

def canonicalize_action(
    action: Any,
    action_zh: Any = "",
    name: Any = "",
    description: Any = "",
    evidence_text: Any = "",
) -> str:
    raw_action = normalize_text(action).lower().replace("-", "_").replace(" ", "_")
    if raw_action in ACTION_ALIAS_MAP:
        return ACTION_ALIAS_MAP[raw_action]
    combined_text = " ".join(
        part for part in [
            normalize_text(action), normalize_text(action_zh),
            normalize_text(name), normalize_text(description),
            normalize_text(evidence_text),
        ] if part
    ).lower().replace("-", " ")
    for canonical_action, patterns in ACTION_PATTERNS:
        if any(pattern.lower() in combined_text for pattern in patterns):
            return canonical_action
    if raw_action and raw_action not in {"other", "prepare", "collect", "load", "reduce", "weigh"}:
        # last-resort: check if raw_action itself contains any known action word
        for known in ["add", "mix", "stir", "heat", "dry", "age", "calcine", "sinter",
                       "spin", "filter", "wash", "dissolve", "hydrolyze", "cool", "gel",
                       "peptize", "concentrate", "evaporate", "characterize", "collect"]:
            if known in raw_action:
                return ACTION_ALIAS_MAP.get(known, known)
        return raw_action
    return "other"


# ============================================================================
# Time condition splitting
# ============================================================================

# Aging-related English patterns with word boundaries — must NOT match
# "averaging", "managing", "packaging", "paging", "damaging" etc.
_AGING_EN_PATTERN = re.compile(
    r"\b(ag(?:e|ing|ed)(?:\s+for)?|ageing)\b", re.IGNORECASE
)


def _contains_aging_en(text: str) -> bool:
    """Check for English aging-related terms with word-boundary safety."""
    return bool(_AGING_EN_PATTERN.search(text))


# Measurement/characterization keywords that indicate the time is NOT a
# process holding time but rather a measurement/acquisition duration.
_MEASUREMENT_KEYWORDS = [
    "dls", "dynamic light scattering", "correlogram", "correlation function",
    "acquisition", "spectrum acquisition", "scan time", "scanning",
    "measurement time", "test time", "testing time", "characterization time",
    "检测时间", "测试时间", "测量时间", "表征时间", "采集时间",
    "xrd scan", "sem imag", "tem imag", "nmr acquis", "ftir scan",
    "raman acquis", "bet measurement", "dsc scan", "tg scan",
    "rheolog measure", "viscosity measure", "conductivity measure",
]


def _is_measurement_context(combined_text: str) -> bool:
    return any(kw in combined_text for kw in _MEASUREMENT_KEYWORDS)


def infer_time_condition_type(
    condition_key: str,
    action: str,
    evidence_text: str,
    description: str = "",
) -> str:
    """
    Split time/duration conditions into specific sub-types.

    Priority:
      L1_PRECISE  — condition_key contains a SPECIFIC sub-type indicator
                     (e.g. aging_time, calcination_holding). High confidence.
      L1_MEASURE  — condition_key or context indicates measurement/acquisition
                     time. Returns measurement_time.
      L2_ACTION   — condition_key is a GENERIC time field (holding_time,
                     duration, time, 时间, 保温时间, soaking_time).
                     Infer sub-type from action + evidence_text.
      L3_GENERIC  — fallback when nothing specific matches.
    """
    key = normalize_text(condition_key).lower()
    action_lower = normalize_text(action).lower()
    combined = f"{key} {evidence_text} {description}".lower()
    combined_en = f"{evidence_text} {description}".lower()

    # ---- L1_PRECISE: condition_key contains a SPECIFIC sub-type indicator ----
    # These are unambiguous — the key itself declares the time type.

    if any(t in key for t in ["calcination_holding", "煅烧保温"]):
        return "calcination_holding_time"
    if any(t in key for t in ["sintering_holding", "烧结保温"]):
        return "sintering_holding_time"
    if any(t in key for t in ["aging_time", "ageing_time", "老化时间", "陈化时间"]):
        return "aging_time"
    if any(t in key for t in ["drying_time", "干燥时间"]):
        return "drying_time"
    if any(t in key for t in ["calcination_time", "煅烧时间"]):
        return "calcination_holding_time"
    if any(t in key for t in ["sintering_time", "烧结时间"]):
        return "sintering_holding_time"
    if any(t in key for t in ["hydrolysis_time", "水解时间"]):
        return "hydrolysis_time"
    if any(t in key for t in ["stirring_time", "stir_time", "搅拌时间"]):
        return "stirring_time"

    # ---- L1_MEASURE: measurement/characterization time ----
    if any(t in key for t in ["measurement_time", "acquisition_time",
                               "检测时间", "测试时间", "测量时间", "采集时间"]):
        return "measurement_time"
    if _is_measurement_context(combined):
        return "measurement_time"

    # ---- L2_ACTION: generic time key → infer from action + context ----
    # holding_time, 保温时间, soaking_time are GENERIC and must NOT
    # short-circuit — they should be refined by action context first.
    is_generic_time_key = (
        "time" in key or "duration" in key or "时间" in key
        or "holding" in key or "保温" in key or "soaking" in key
        or "时长" in key
    )
    if not is_generic_time_key:
        return "generic_holding_time"

    # Check calcination FIRST (before generic holding/heat)
    if action_lower in {"calcine", "calcination"} or any(
        t in combined for t in ["煅烧", "焙烧", "calcination", "calcined"]
    ):
        return "calcination_holding_time"

    # Check sintering
    if action_lower in {"sinter", "sintering"} or any(
        t in combined for t in ["烧结", "sintering", "sintered"]
    ):
        return "sintering_holding_time"

    # Check aging — use word-boundary-safe English matching
    if action_lower in {"age", "aging", "ageing", "aged"}:
        return "aging_time"
    if any(t in combined for t in ["老化", "陈化"]):
        return "aging_time"
    if _contains_aging_en(combined_en):
        return "aging_time"

    # Check drying
    if action_lower in {"dry", "drying"} or any(
        t in combined for t in ["干燥", "drying", "dried"]
    ):
        return "drying_time"

    # Check hydrolysis
    if action_lower in {"hydrolyze", "hydrolysis"} or any(
        t in combined for t in ["水解", "hydroly"]
    ):
        return "hydrolysis_time"

    # Check stirring
    if action_lower in {"stir"} or any(
        t in combined for t in ["搅拌", "stirring"]
    ):
        return "stirring_time"

    # Check heating/holding (only when it's genuinely about heat treatment)
    if action_lower in {"heat", "hold", "holding"} or any(
        t in combined for t in ["保温", "holding", "soaking", "热处理", "加热"]
    ):
        return "holding_time"

    # ---- L3_GENERIC: nothing specific matched ----
    return "generic_holding_time"


# ============================================================================
# Data loading
# ============================================================================

def load_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(manifest_path.open("r", encoding="utf-8-sig", newline="")))


def scan_process_steps_from_source(
    manifest_rows: list[dict[str, str]],
    stage3_subdir: str,
) -> pd.DataFrame:
    """Read process_steps.jsonl directly for best canonicalization."""
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
            action_raw = normalize_text(item.get("action")).lower()
            action_zh_raw = normalize_text(item.get("action_zh"))
            name_raw = normalize_text(item.get("name"))
            description_raw = normalize_text(item.get("description"))
            evidence_raw = normalize_text(item.get("evidence_text"))
            cleaned_action = canonicalize_action(
                action_raw, action_zh_raw, name_raw, description_raw, evidence_raw,
            )
            rows.append({
                "category": category,
                "paper_id": paper_id,
                "step_order": int(item.get("step_order") or 0),
                "raw_action": action_raw or "other",
                "raw_action_zh": action_zh_raw,
                "action_cleaned": cleaned_action,
                "name": name_raw,
                "description": description_raw,
                "evidence_text": evidence_raw,
                "temperature_value": item.get("temperature_value"),
                "temperature_unit": item.get("temperature_unit"),
                "duration_value": item.get("duration_value"),
                "duration_unit": item.get("duration_unit"),
                "heating_rate_value": item.get("heating_rate_value"),
                "heating_rate_unit": item.get("heating_rate_unit"),
            })
    return pd.DataFrame(rows)


# ============================================================================
# 1. Cleaned action distribution
# ============================================================================

def build_cleaned_action_distribution(steps_df: pd.DataFrame) -> pd.DataFrame:
    if steps_df.empty:
        return pd.DataFrame(columns=[
            "action", "action_zh", "count", "paper_count",
            "with_temperature_count", "with_duration_count",
            "with_heating_rate_count", "with_evidence_text_count",
        ])
    records = []
    for action, group in steps_df.groupby("action_cleaned"):
        records.append({
            "action": action,
            "action_zh": ACTION_ZH_LABELS.get(action, action),
            "count": int(len(group)),
            "paper_count": int(group["paper_id"].nunique()),
            "category_distribution": json.dumps(
                group["category"].value_counts().to_dict(), ensure_ascii=False, sort_keys=True,
            ),
            "with_temperature_count": int(pd.to_numeric(group["temperature_value"], errors="coerce").notna().sum()),
            "with_duration_count": int(pd.to_numeric(group["duration_value"], errors="coerce").notna().sum()),
            "with_heating_rate_count": int(pd.to_numeric(group["heating_rate_value"], errors="coerce").notna().sum()),
            "with_evidence_text_count": int(group["evidence_text"].astype(str).str.strip().ne("").sum()),
        })
    return pd.DataFrame(records).sort_values(["count", "paper_count", "action"], ascending=[False, False, True])


def plot_action_distribution_v2(action_df: pd.DataFrame, base_path: Path) -> None:
    if action_df.empty:
        make_placeholder_figure(base_path, title="process_steps 动作分布图（V2清洗后）",
                                message="无动作数据。", data_source="process_steps.jsonl")
        return
    total = action_df["count"].sum()
    top15 = action_df.head(15)
    other_count = int(action_df["count"].iloc[15:].sum()) if len(action_df) > 15 else 0

    plot_records = []
    for _, row in top15.iterrows():
        plot_records.append({
            "label": f"{row['action_zh']} ({row['action']})",
            "count": row["count"],
            "pct": row["count"] / total * 100,
        })
    if other_count > 0:
        plot_records.append({
            "label": f"其他合并 ({other_count} steps)",
            "count": other_count,
            "pct": other_count / total * 100,
        })

    plot_df = pd.DataFrame(plot_records).iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(12, max(6.5, len(plot_df) * 0.42)))
    colors = ["#2d7bc6"] * len(plot_df)
    if other_count > 0:
        colors[-1] = "#9aa4b2"  # gray for "other merged"

    ax.barh(plot_df["label"], plot_df["count"], color=colors, edgecolor="#17375e", linewidth=0.6)
    for i, (count, pct) in enumerate(zip(plot_df["count"], plot_df["pct"])):
        ax.text(count + max(plot_df["count"]) * 0.01, i, f"{count} ({pct:.1f}%)",
                va="center", fontsize=8.5, color="#17375e")

    ax.set_xlabel("步骤数 Count", fontsize=11)
    ax.set_title(f"工艺步骤动作分布 (N={total}, 15类+其余合并)", fontsize=14, fontweight="bold", color="#17375e")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    fig.text(0.01, 0.02, "数据来源：process_steps.jsonl，基于 name/description/action/evidence_text 三层规则 canonicalization",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 2. Time condition distributions by type
# ============================================================================

def _is_process_time_type(time_type: str) -> bool:
    """Return True if this time type is a process (not measurement) time."""
    return time_type != "measurement_time"


# Valid time units
_TIME_UNIT_TOKENS: frozenset[str] = frozenset({
    "s", "sec", "second", "seconds", "秒",
    "min", "minute", "minutes", "分钟", "min.",
    "h", "hr", "hour", "hours", "小时", "hrs",
    "d", "day", "days", "天",
})

# Units / contexts that must NEVER be treated as time values
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

# Regex: number immediately followed by °C / ℃ / K (temperature, not time)
_TEMPERATURE_AFTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*[°℃]?\s*[CcKk](?!\s*/)")
# Regex: number followed by Hz/kHz/MHz (frequency, not time)
_FREQUENCY_AFTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*[KkMmGg]?[Hh][Zz]")
# Regex: number followed by rpm
_RPM_AFTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*[Rr][Pp][Mm]")


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


def _check_time_inclusion(
    val_h: float, time_type: str, evidence_text: str,
    raw_condition_value: str = "", condition_unit: str = "",
) -> tuple[bool, str]:
    """Returns (included, exclusion_reason)."""
    if val_h <= 0:
        return (False, "zero_or_negative_value")

    # Check for non-time unit context FIRST
    is_time, time_reason = is_likely_time_value(
        raw_condition_value, condition_unit, evidence_text,
    )
    if not is_time:
        return (False, "non_time_unit_context")

    # measurement_time > 168h is extreme (check before generic 500h threshold)
    if time_type == "measurement_time" and val_h > 168:
        return (False, "extreme_measurement_time_outlier")
    if val_h > 500:
        return (False, "value_exceeds_500h_threshold")
    if time_type == "calcination_holding_time" and val_h > 48:
        has_strong = any(t in evidence_text.lower() for t in [
            "calcination", "calcined", "calcin", "煅烧", "焙烧",
        ])
        if not has_strong:
            return (False, "calcination_holding_time_exceeds_48h_no_strong_evidence")
    if val_h >= 50:
        text_lower = evidence_text.lower()
        suspicious = any(kw in text_lower for kw in [
            "hole", "holes", "rpm", "spectral width", " hz", "mhz",
            "°c", "temperature", "pore",
        ])
        if suspicious:
            is_misextracted = (
                (time_type == "generic_holding_time" and val_h >= 100) or
                (time_type == "measurement_time" and val_h >= 100) or
                (time_type == "calcination_holding_time" and val_h > 200)
            )
            if is_misextracted:
                return (False, "value_likely_misextracted_from_non_time_context")
    return (True, "")


def build_time_condition_distribution(
    steps_df: pd.DataFrame,
    process_condition_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """
    Extract time/duration conditions split by type.
    Returns (time_condition_df, outliers_list).
    Distribution CSV includes only included records.
    Outliers track all excluded records with reasons.
    """
    cleaned_rows: list[dict[str, Any]] = []
    outliers: list[dict[str, Any]] = []

    for _, row in process_condition_df.iterrows():
        condition_key = normalize_text(row.get("condition_key"))
        condition_value = row.get("condition_value")
        condition_unit = normalize_text(row.get("condition_unit"))
        action = normalize_text(row.get("action"))
        evidence_text = normalize_text(row.get("evidence_text") or row.get("source_text"))
        description = normalize_text(row.get("description")) if "description" in row else ""

        key_lower = condition_key.lower()
        is_time = any(t in key_lower for t in [
            "time", "duration", "时间", "时长", "holding", "保温",
        ])
        if not is_time:
            continue

        time_type = infer_time_condition_type(condition_key, action, evidence_text, description)
        values = parse_numeric_values(condition_value)
        unit_norm = normalize_unit_text(condition_unit)

        if not values:
            outliers.append({
                "time_type": time_type,
                "paper_id": row.get("paper_id"),
                "condition_key": condition_key,
                "raw_value": str(condition_value)[:100],
                "value_h": None,
                "action": action,
                "exclusion_reason": "non_numeric_value",
                "needs_manual_review": True,
                "source_text": evidence_text[:200],
            })
            continue

        for val in values:
            if "min" in unit_norm and "c/min" not in unit_norm:
                val = val / 60.0
            elif "s" in unit_norm and "c/min" not in unit_norm:
                val = val / 3600.0

            val_h = round(float(val), 4)
            included, excl_reason = _check_time_inclusion(
                val_h, time_type, evidence_text,
                raw_condition_value=str(condition_value)[:200],
                condition_unit=condition_unit,
            )

            if not included:
                outliers.append({
                    "time_type": time_type,
                    "paper_id": row.get("paper_id"),
                    "condition_key": condition_key,
                    "raw_value": str(condition_value)[:100],
                    "value_h": val_h,
                    "action": action,
                    "exclusion_reason": excl_reason,
                    "needs_manual_review": True,
                    "source_text": evidence_text[:200],
                })
                continue

            cleaned_rows.append({
                "category": row.get("category"),
                "paper_id": row.get("paper_id"),
                "step_order": row.get("step_order", 0),
                "action": action,
                "condition_key_original": condition_key,
                "time_type": time_type,
                "value_h": val_h,
                "unit_original": condition_unit,
                "source_text": evidence_text,
                "is_process_time": _is_process_time_type(time_type),
            })

    time_df = pd.DataFrame(cleaned_rows)
    if time_df.empty:
        return pd.DataFrame(columns=[
            "category", "paper_id", "step_order", "action",
            "condition_key_original", "time_type", "value_h",
            "unit_original", "source_text", "is_process_time",
        ]), outliers

    return time_df.sort_values(["time_type", "value_h"]), outliers


def plot_time_condition_by_type(time_df: pd.DataFrame, base_path: Path) -> None:
    if time_df.empty:
        make_placeholder_figure(base_path, title="时间参数按类型分布",
                                message="无可用的时间条件数据。", data_source="process_condition_distribution.csv")
        return

    type_labels_map = {
        "aging_time": "老化时间",
        "drying_time": "干燥时间",
        "calcination_holding_time": "煅烧保温时间",
        "sintering_holding_time": "烧结保温时间",
        "hydrolysis_time": "水解时间",
        "stirring_time": "搅拌时间",
        "holding_time": "保温时间",
        "measurement_time": "表征/测试耗时",
        "generic_holding_time": "未判定持续时间",
    }
    type_order = [
        "aging_time", "drying_time", "calcination_holding_time",
        "sintering_holding_time", "hydrolysis_time", "stirring_time",
        "holding_time", "measurement_time", "generic_holding_time",
    ]

    present_types = [t for t in type_order if t in time_df["time_type"].values]
    if not present_types:
        make_placeholder_figure(base_path, title="时间参数按类型分布",
                                message="无可用时间类型。", data_source="process_condition_distribution.csv")
        return

    n_types = len(present_types)
    has_measurement = "measurement_time" in present_types
    n_proc_types = len([t for t in present_types if t != "measurement_time"])

    fig, axes = plt.subplots(1, n_types, figsize=(max(14, n_types * 3.5), 5))
    if n_types == 1:
        axes = [axes]

    process_color = "#4d97de"
    measure_color = "#d9a85d"  # gold/tan for measurement time

    for ax, time_type in zip(axes, present_types):
        subset = time_df[time_df["time_type"] == time_type]["value_h"]
        if subset.empty:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", color="#345273")
            ax.set_title(type_labels_map.get(time_type, time_type))
            continue

        is_measure = time_type == "measurement_time"
        color = measure_color if is_measure else process_color

        use_log = subset.max() / max(subset.min(), 0.01) > 50
        bins = np.logspace(np.log10(max(subset.min(), 0.01)), np.log10(subset.max()), 15) if use_log else 15

        ax.hist(subset, bins=bins, color=color, edgecolor="#17375e", alpha=0.85)
        if use_log:
            ax.set_xscale("log")
            ax.set_xlabel("时间 / h (log scale)")
        else:
            ax.set_xlabel("时间 / h")

        label = type_labels_map.get(time_type, time_type)
        n_text = f"N={len(subset)}"
        if is_measure:
            label = f"{label}\n(测试耗时)"
        ax.set_title(f"{label}\n({n_text})", fontsize=9)
        ax.set_ylabel("频次")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        stats_text = f"median={subset.median():.1f}h\nmean={subset.mean():.1f}h"
        ax.text(0.98, 0.95, stats_text, transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color="#345273",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))

    fig.suptitle("时间参数按类型分布（已拆分aging/drying/calcination/sintering/hydrolysis/stirring/holding）",
                 fontsize=14, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02,
             "数据来源：process_condition_distribution.csv | "
             "金色=表征/测试耗时(不计入工艺时间) | generic_holding_time=未判定持续时间(fallback类型)",
             fontsize=8.5, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 3. Heating rate distribution
# ============================================================================

def build_heating_rate_distribution(
    process_condition_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract heating_rate conditions, unify units to °C/min.
    Returns (heating_rate_df, outliers_df).
    """
    rows: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []

    for _, row in process_condition_df.iterrows():
        key = normalize_text(row.get("condition_key")).lower()
        if "heating_rate" not in key:
            continue

        values = parse_numeric_values(row.get("condition_value"))
        unit_norm = normalize_unit_text(row.get("condition_unit"))

        for val in values:
            if val <= 0:
                filtered.append({"paper_id": row.get("paper_id"), "raw_value": row.get("condition_value"),
                                 "unit": row.get("condition_unit"), "reason": "zero_or_negative",
                                 "source_text": normalize_text(row.get("source_text"))[:100]})
                continue
            if val > 200:
                filtered.append({"paper_id": row.get("paper_id"), "raw_value": row.get("condition_value"),
                                 "unit": row.get("condition_unit"), "reason": ">200_C_per_min_anomalous",
                                 "source_text": normalize_text(row.get("source_text"))[:100]})
                continue

            # K/min ≈ °C/min
            rows.append({
                "category": row.get("category"),
                "paper_id": row.get("paper_id"),
                "step_order": row.get("step_order", 0),
                "action": normalize_text(row.get("action")),
                "heating_rate_C_per_min": round(float(val), 4),
                "original_unit": row.get("condition_unit"),
                "source_text": normalize_text(row.get("source_text")),
            })

    hr_df = pd.DataFrame(rows)
    outliers_df = pd.DataFrame(filtered)
    return hr_df, outliers_df


def plot_heating_rate_distribution(hr_df: pd.DataFrame, outliers_df: pd.DataFrame, base_path: Path) -> None:
    if hr_df.empty:
        make_placeholder_figure(base_path, title="升温速率分布",
                                message="无可用的升温速率数据。", data_source="process_condition_distribution.csv")
        return

    vals = hr_df["heating_rate_C_per_min"]
    n_filtered = len(outliers_df) if not outliers_df.empty else 0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [3, 1]})

    # Main histogram
    bins = min(20, max(8, int(math.sqrt(len(vals)))))
    ax1.hist(vals, bins=bins, color="#2d7bc6", edgecolor="#17375e", alpha=0.85)
    ax1.axvline(vals.median(), color="#d99058", linestyle="--", linewidth=1.5, label=f"median={vals.median():.1f}")
    ax1.axvline(vals.mean(), color="#74a857", linestyle="--", linewidth=1.5, label=f"mean={vals.mean():.1f}")
    ax1.set_xlabel("升温速率 / °C·min⁻¹")
    ax1.set_ylabel("频次")
    ax1.set_title(f"升温速率分布 (N={len(vals)})")
    ax1.legend(fontsize=9)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    # Summary stats box
    ax2.axis("off")
    stats_lines = [
        f"N = {len(vals)}",
        f"Median = {vals.median():.1f} °C/min",
        f"Mean = {vals.mean():.1f} °C/min",
        f"Std = {vals.std():.1f} °C/min",
        f"Min = {vals.min():.1f} °C/min",
        f"Max = {vals.max():.1f} °C/min",
        f"Q1 = {vals.quantile(0.25):.1f} °C/min",
        f"Q3 = {vals.quantile(0.75):.1f} °C/min",
        f"",
        f"过滤: {n_filtered} 条",
        "(0/负值/不可解析)",
    ]
    for i, line in enumerate(stats_lines):
        ax2.text(0.1, 0.95 - i * 0.06, line, transform=ax2.transAxes,
                 fontsize=9.5, color="#17375e", va="top", fontfamily="monospace")

    fig.suptitle("升温速率分布（单位统一为 °C/min，已过滤异常值）",
                 fontsize=14, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, f"数据来源：process_condition_distribution.csv；过滤0/空/不可解析/{n_filtered}条异常",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 4. Calcination / Sintering temperature distribution
# ============================================================================

def build_temperature_distributions(
    process_condition_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extract calcination and sintering temperatures separately.
    Returns (calcination_df, sintering_df, outliers_df).
    """
    calc_rows: list[dict[str, Any]] = []
    sinter_rows: list[dict[str, Any]] = []
    outliers: list[dict[str, Any]] = []

    for _, row in process_condition_df.iterrows():
        key = normalize_text(row.get("condition_key")).lower()
        action = normalize_text(row.get("action")).lower()
        evidence = normalize_text(row.get("source_text")).lower()

        is_calcine = any(t in key for t in ["calcination_temperature", "煅烧温度"]) or \
                     (("temperature" in key or key == "temperature") and
                      any(t in action + evidence for t in ["calcine", "煅烧", "焙烧", "calcination"]))
        is_sinter = any(t in key for t in ["sintering_temperature", "烧结温度"]) or \
                    (("temperature" in key or key == "temperature") and
                     any(t in action + evidence for t in ["sinter", "烧结", "sintering"]))

        if not (is_calcine or is_sinter):
            continue

        target_list = calc_rows if is_calcine else sinter_rows
        values = parse_numeric_values(row.get("condition_value"))
        unit_norm = normalize_unit_text(row.get("condition_unit"))

        for val in values:
            if val <= 0:
                outliers.append({"paper_id": row.get("paper_id"), "type": "calcination" if is_calcine else "sintering",
                                 "raw_value": row.get("condition_value"), "unit": row.get("condition_unit"),
                                 "reason": "zero_or_negative",
                                 "source_text": normalize_text(row.get("source_text"))[:100]})
                continue
            if val < 100 or val > 2500:
                outliers.append({"paper_id": row.get("paper_id"), "type": "calcination" if is_calcine else "sintering",
                                 "raw_value": row.get("condition_value"), "unit": row.get("condition_unit"),
                                 "reason": f"out_of_range_{val}" if val < 100 else ">2500C_anomalous",
                                 "source_text": normalize_text(row.get("source_text"))[:100]})
                continue

            target_list.append({
                "category": row.get("category"),
                "paper_id": row.get("paper_id"),
                "step_order": row.get("step_order", 0),
                "action": action,
                "temperature_C": round(float(val), 1),
                "original_unit": row.get("condition_unit"),
                "source_text": normalize_text(row.get("source_text")),
            })

    calc_df = pd.DataFrame(calc_rows)
    sinter_df = pd.DataFrame(sinter_rows)
    outliers_df = pd.DataFrame(outliers)
    return calc_df, sinter_df, outliers_df


def plot_calcination_temperature(calc_df: pd.DataFrame, base_path: Path) -> None:
    if calc_df.empty:
        make_placeholder_figure(base_path, title="煅烧温度分布",
                                message="无可用煅烧温度数据。", data_source="process_condition_distribution.csv")
        return
    vals = calc_df["temperature_C"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(vals, bins=14, color="#2d7bc6", edgecolor="#17375e", alpha=0.85)
    ax.axvline(vals.median(), color="#d99058", linestyle="--", linewidth=1.5, label=f"median={vals.median():.0f}°C")
    ax.set_xlabel("温度 / °C")
    ax.set_ylabel("频次")
    ax.set_title(f"煅烧温度分布 (N={len(vals)})")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.text(0.01, 0.02, "数据来源：process_condition_distribution.csv；单位统一为°C，已过滤空值/0/不可解析值",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_sintering_temperature(sinter_df: pd.DataFrame, base_path: Path) -> None:
    if sinter_df.empty:
        make_placeholder_figure(base_path, title="烧结温度分布",
                                message="无可用烧结温度数据。", data_source="process_condition_distribution.csv")
        return
    vals = sinter_df["temperature_C"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(vals, bins=14, color="#74a857", edgecolor="#385723", alpha=0.85)
    ax.axvline(vals.median(), color="#d99058", linestyle="--", linewidth=1.5, label=f"median={vals.median():.0f}°C")
    ax.set_xlabel("温度 / °C")
    ax.set_ylabel("频次")
    ax.set_title(f"烧结温度分布 (N={len(vals)})")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.text(0.01, 0.02, "数据来源：process_condition_distribution.csv；单位统一为°C，已过滤空值/0/不可解析值",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


def plot_calcination_sintering_overlay(calc_df: pd.DataFrame, sinter_df: pd.DataFrame, base_path: Path) -> None:
    if calc_df.empty and sinter_df.empty:
        make_placeholder_figure(base_path, title="煅烧/烧结温度对比",
                                message="无可用的煅烧/烧结温度数据。", data_source="process_condition_distribution.csv")
        return

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bins = np.linspace(
        min(calc_df["temperature_C"].min() if not calc_df.empty else 100,
            sinter_df["temperature_C"].min() if not sinter_df.empty else 100),
        max(calc_df["temperature_C"].max() if not calc_df.empty else 2500,
            sinter_df["temperature_C"].max() if not sinter_df.empty else 2500),
        16,
    )

    if not calc_df.empty:
        ax.hist(calc_df["temperature_C"], bins=bins, alpha=0.65, color="#2d7bc6",
                edgecolor="#17375e", label=f"煅烧 (N={len(calc_df)})")
    if not sinter_df.empty:
        ax.hist(sinter_df["temperature_C"], bins=bins, alpha=0.55, color="#74a857",
                edgecolor="#385723", label=f"烧结 (N={len(sinter_df)})")

    ax.set_xlabel("温度 / °C")
    ax.set_ylabel("频次")
    ax.set_title("煅烧 vs 烧结温度分布对比")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.text(0.01, 0.02, "数据来源：process_condition_distribution.csv；统一单位°C，过滤空值/0/不可解析值",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 5. Real step transition diagram
# ============================================================================

def map_action_to_stage(action: str) -> str:
    if action in {"add", "stir", "dissolve", "hydrolyze", "peptize", "gelation"}:
        return "sol_prep"
    if action in {"age", "concentrate", "filter", "cool"}:
        return "aging_concentration"
    if action in {"spin", "collect"}:
        return "spinning"
    if action in {"dry", "wash"}:
        return "drying"
    if action in {"calcine", "sinter", "heat"}:
        return "calcination_sintering"
    if action in {"characterize"}:
        return "characterization"
    return "other"


def build_real_transitions(steps_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute real step_order transitions per paper.
    Returns transition_edges DataFrame with source_action, target_action, count, paper_count.
    """
    if steps_df.empty:
        return pd.DataFrame(columns=["source_action", "target_action", "count", "paper_count"])

    transition_counts: Counter[tuple[str, str]] = Counter()
    transition_papers: defaultdict[tuple[str, str], set[str]] = defaultdict(set)

    grouped = steps_df.sort_values(["category", "paper_id", "step_order"]).groupby(["category", "paper_id"])
    for _keys, group in grouped:
        actions = group["action_cleaned"].tolist()
        # Compact: remove consecutive duplicates
        compact = []
        for a in actions:
            a_norm = normalize_text(a)
            if not a_norm:
                continue
            if not compact or compact[-1] != a_norm:
                compact.append(a_norm)
        for src, tgt in zip(compact, compact[1:]):
            transition_counts[(src, tgt)] += 1
            transition_papers[(src, tgt)].add(_keys[1])  # paper_id

    rows = []
    for (src, tgt), count in transition_counts.most_common():
        rows.append({
            "source_action": src,
            "target_action": tgt,
            "count": count,
            "paper_count": len(transition_papers[(src, tgt)]),
        })
    return pd.DataFrame(rows)


def plot_transition_diagram(transitions_df: pd.DataFrame, base_path: Path) -> None:
    if transitions_df.empty:
        make_placeholder_figure(base_path, title="真实 step transition 工艺路线图",
                                message="无可用 transition 数据。", data_source="process_steps.jsonl")
        return

    # Map to high-level stages
    stage_transitions: Counter[tuple[str, str]] = Counter()
    for _, row in transitions_df.iterrows():
        src_stage = map_action_to_stage(row["source_action"])
        tgt_stage = map_action_to_stage(row["target_action"])
        stage_transitions[(src_stage, tgt_stage)] += row["count"]

    if not stage_transitions:
        make_placeholder_figure(base_path, title="真实 step transition 工艺路线图",
                                message="无可映射的 stage transition。", data_source="process_steps.jsonl")
        return

    stage_order = [
        "sol_prep", "aging_concentration", "spinning",
        "drying", "calcination_sintering", "characterization", "other",
    ]
    active = [s for s in stage_order if s in {item for edge in stage_transitions for item in edge}]
    positions = {stage: idx for idx, stage in enumerate(active)}

    fig, ax = plt.subplots(figsize=(13.5, 5))
    ax.axis("off")
    y = 0.55

    # Draw stage nodes
    for stage in active:
        x = positions[stage]
        rect = Rectangle((x - 0.38, y - 0.13), 0.76, 0.26,
                         facecolor="#d9e9fb", edgecolor="#2d7bc6", linewidth=1.8)
        ax.add_patch(rect)
        ax.text(x, y, ROUTE_STAGE_LABELS[stage], ha="center", va="center",
                fontsize=11, color="#17375e", fontweight="bold")

    max_count = max(stage_transitions.values())

    # Separate forward and backward transitions
    forward_edges = []
    backward_edges = []
    for (src, tgt), count in stage_transitions.most_common():
        if positions.get(src, -1) < positions.get(tgt, 999):
            forward_edges.append((src, tgt, count))
        else:
            backward_edges.append((src, tgt, count))

    # Draw forward edges (main flow) — straight arrows
    for src, tgt, count in forward_edges:
        start_x = positions[src] + 0.38
        end_x = positions[tgt] - 0.38
        linewidth = 1.2 + 5 * count / max_count
        arrow = FancyArrowPatch((start_x, y), (end_x, y),
                               arrowstyle="-|>", mutation_scale=16,
                               linewidth=linewidth, color="#5b9bd5", alpha=0.6)
        ax.add_patch(arrow)
        # Offset text vertically to avoid overlap
        offset = 0.13
        ax.text((start_x + end_x) / 2, y + offset, str(count),
                ha="center", va="bottom", fontsize=8.5, color="#345273",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

    # Draw backward edges (loops/skips) — curved arcs below
    for src, tgt, count in backward_edges:
        start_x = positions[src] + 0.38
        end_x = positions[tgt] - 0.38
        linewidth = 0.8 + 3 * count / max_count
        arrow = FancyArrowPatch((start_x, y), (end_x, y),
                               connectionstyle="arc3,rad=-0.25",
                               arrowstyle="-|>", mutation_scale=12,
                               linewidth=linewidth, color="#d99058", alpha=0.4,
                               linestyle="--")
        ax.add_patch(arrow)
        ax.text((start_x + end_x) / 2, y - 0.22, str(count),
                ha="center", va="top", fontsize=7.5, color="#a0522d",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

    ax.set_xlim(-0.8, len(active) - 0.2)
    ax.set_ylim(0.05, 0.95)
    fig.suptitle("真实 step transition 工艺路线图（基于 step_order 统计）",
                 fontsize=16, fontweight="bold", color="#17375e")
    fig.text(0.01, 0.02, "实线箭头=正向流程，虚线箭头=逆向/跳跃；数字=transition 计数；基于 process_steps step_order 真实统计",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 6. Parameter cooccurrence network (improved)
# ============================================================================

def build_cleaned_network(
    cooccurrence_edges: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    sample_parameter_long: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build cleaned cooccurrence network: top 30 keys, threshold edges,
    color by parameter type.
    Returns (top_edges_df, network_summary_dict).
    """
    if cooccurrence_edges.empty or parameter_distribution.empty:
        empty_df = pd.DataFrame(columns=[
            "source_canonical_key", "target_canonical_key",
            "cooccurrence_count", "paper_count", "category_distribution",
        ])
        return empty_df, {"n_nodes": 0, "n_edges": 0, "max_component_size": 0, "top_edges": []}

    top_keys = set(parameter_distribution.head(30)["canonical_key"].tolist())
    edges = cooccurrence_edges[
        cooccurrence_edges["source_canonical_key"].isin(top_keys) &
        cooccurrence_edges["target_canonical_key"].isin(top_keys)
    ].copy()

    if edges.empty:
        return edges, {"n_nodes": 0, "n_edges": 0, "max_component_size": 0, "top_edges": []}

    # Threshold: median cooccurrence or min 2
    threshold = max(2, int(edges["cooccurrence_count"].quantile(0.40)))
    edges = edges[edges["cooccurrence_count"] >= threshold].copy()

    # Fallback: top 25 edges
    if edges.empty:
        edges = cooccurrence_edges[
            cooccurrence_edges["source_canonical_key"].isin(top_keys) &
            cooccurrence_edges["target_canonical_key"].isin(top_keys)
        ].nlargest(25, "cooccurrence_count")

    edges = edges.sort_values(["cooccurrence_count", "paper_count"], ascending=[False, False])

    # Build network summary
    G = nx.Graph()
    for row in edges.itertuples(index=False):
        G.add_edge(row.source_canonical_key, row.target_canonical_key, weight=row.cooccurrence_count)

    components = list(nx.connected_components(G))
    max_comp_size = max(len(c) for c in components) if components else 0

    top_edge_list = []
    for row in edges.head(10).itertuples(index=False):
        top_edge_list.append({
            "source": row.source_canonical_key,
            "target": row.target_canonical_key,
            "cooccurrence_count": int(row.cooccurrence_count),
        })

    network_summary = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "max_component_size": max_comp_size,
        "n_components": len(components),
        "top_edges": top_edge_list,
        "threshold_used": threshold,
    }

    return edges, network_summary


def plot_cleaned_network(
    edges_df: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    network_summary: dict[str, Any],
    base_path: Path,
) -> None:
    if edges_df.empty:
        make_placeholder_figure(base_path, title="参数共现网络图（V2清洗后）",
                                message="无可用网络边。", data_source="parameter_cooccurrence_edges.csv")
        return

    counts = parameter_distribution.set_index("canonical_key")["count"].to_dict()
    G = nx.Graph()
    for row in edges_df.itertuples(index=False):
        G.add_edge(row.source_canonical_key, row.target_canonical_key, weight=row.cooccurrence_count)

    if G.number_of_nodes() == 0:
        make_placeholder_figure(base_path, title="参数共现网络图（V2清洗后）",
                                message="过滤后无可用节点。", data_source="parameter_cooccurrence_edges.csv")
        return

    fig, ax = plt.subplots(figsize=(13, 9))
    pos = nx.spring_layout(G, seed=42, weight="weight", k=1.2 / max(G.number_of_nodes() ** 0.5, 1), iterations=150)

    edge_widths = [0.8 + 5 * G[u][v]["weight"] / max(edges_df["cooccurrence_count"].max(), 1) for u, v in G.edges()]
    node_types = {node: classify_parameter_type(node) for node in G.nodes()}
    node_colors = [PARAMETER_TYPE_COLORS[node_types[node]] for node in G.nodes()]
    node_sizes = [280 + 12 * counts.get(node, 1) for node in G.nodes()]

    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color="#a8bfdc", alpha=0.7, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes,
                          edgecolors="#17375e", linewidths=1.2, ax=ax)
    nx.draw_networkx_labels(G, pos, labels={node: shorten_label(node) for node in G.nodes()},
                           font_size=7.5, font_color="#17375e", font_weight="bold", ax=ax)

    ax.set_title(f"参数共现网络 (节点={G.number_of_nodes()}, 边={G.number_of_edges()})",
                fontsize=14, fontweight="bold", color="#17375e")
    ax.axis("off")

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", label=f"{label}",
                   markerfacecolor=color, markeredgecolor="#17375e", markersize=9)
        for label, color in PARAMETER_TYPE_COLORS.items()
    ]
    ax.legend(handles=legend_handles, title="参数类型", loc="upper right", frameon=True, fontsize=8)

    fig.text(0.01, 0.02, f"数据来源：parameter_cooccurrence_edges.csv + parameter_distribution.csv；"
             f"Top 30 keys, 边权≥{network_summary.get('threshold_used', 'N/A')}",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 7. Sample-parameter matrix sparsity heatmap (PPT version)
# ============================================================================

def build_sample_parameter_matrix_ppt_v2(
    sample_parameter_long: pd.DataFrame,
    parameter_distribution: pd.DataFrame,
    paper_limit: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if sample_parameter_long.empty or parameter_distribution.empty:
        empty = pd.DataFrame()
        return empty, {"matrix_shape": [0, 0], "density": 0, "top_parameters": [], "top_papers": []}

    top_keys = parameter_distribution.head(30)["canonical_key"].tolist()

    # Classify keys by parameter type and sort within type
    key_types = {k: classify_parameter_type(k) for k in top_keys}
    type_order = ["synthesis", "process", "structure", "property", "characterization", "other"]
    sorted_keys = sorted(top_keys, key=lambda k: (type_order.index(key_types.get(k, "other")), k))

    matrix = (
        sample_parameter_long[sample_parameter_long["canonical_key"].isin(sorted_keys)]
        .assign(present=1)
        .pivot_table(index=["category", "paper_id"], columns="canonical_key",
                     values="present", aggfunc="max", fill_value=0)
        .reset_index()
    )

    if matrix.empty:
        empty = pd.DataFrame()
        return empty, {"matrix_shape": [0, 0], "density": 0, "top_parameters": [], "top_papers": []}

    value_cols = [c for c in matrix.columns if c not in {"category", "paper_id"}]
    # Reorder columns
    value_cols = [c for c in sorted_keys if c in value_cols]

    matrix["present_count"] = matrix[value_cols].sum(axis=1)
    matrix["missing_rate"] = 1 - matrix["present_count"] / max(len(value_cols), 1)
    matrix = matrix.sort_values(["category", "missing_rate", "paper_id"], ascending=[True, True, True])

    # Proportional sampling per category
    cat_counts = matrix["category"].value_counts().to_dict()
    total_rows = min(paper_limit, len(matrix))
    quotas: dict[str, int] = {}
    remaining = total_rows
    for cat in sorted(cat_counts.keys()):
        proportional = max(1, int(round(total_rows * cat_counts[cat] / len(matrix))))
        quota = min(cat_counts[cat], proportional)
        quotas[cat] = quota
        remaining -= quota
    while remaining > 0:
        for cat in sorted(cat_counts.keys()):
            if quotas.get(cat, 0) < cat_counts.get(cat, 0):
                quotas[cat] += 1
                remaining -= 1
                if remaining == 0:
                    break

    selected = []
    for cat in sorted(cat_counts.keys()):
        selected.append(matrix[matrix["category"] == cat].head(quotas.get(cat, 0)))
    matrix = pd.concat(selected, ignore_index=True) if selected else matrix.head(total_rows)

    matrix = matrix.drop(columns=["present_count", "missing_rate"])

    total_present = int(matrix[value_cols].sum().sum())
    total_cells = int(len(matrix) * len(value_cols))
    density = round(total_present / max(total_cells, 1), 4)

    # Top parameters by coverage
    param_coverage = {col: int(matrix[col].sum()) for col in value_cols}
    top_params = sorted(param_coverage.items(), key=lambda x: -x[1])[:10]

    # Top papers by coverage
    paper_coverage = matrix.assign(coverage=matrix[value_cols].sum(axis=1))
    paper_coverage = paper_coverage.sort_values("coverage", ascending=False)
    top_papers_list = [
        {"paper_id": row["paper_id"], "filled_params": int(row["coverage"])}
        for _, row in paper_coverage.head(10).iterrows()
    ]

    matrix_summary = {
        "matrix_shape": [len(matrix), len(value_cols)],
        "density": density,
        "top_parameters": [{"key": k, "filled_papers": v} for k, v in top_params],
        "top_papers": top_papers_list,
    }

    return matrix, matrix_summary


def plot_sample_parameter_matrix_v2(matrix_df: pd.DataFrame, base_path: Path) -> None:
    if matrix_df.empty:
        make_placeholder_figure(base_path, title="sample-parameter 稀疏性热图（PPT版 V2）",
                                message="无可用矩阵数据。", data_source="sample_parameter_long.csv")
        return

    value_cols = [c for c in matrix_df.columns if c not in {"category", "paper_id"}]
    data = matrix_df[value_cols].to_numpy()
    categories = matrix_df["category"].tolist()

    cat_list = list(CATEGORY_COLORS.keys())
    cat_codes = [cat_list.index(c) if c in cat_list else -1 for c in categories]

    fig = plt.figure(figsize=(13.33, 7.5))
    gs = GridSpec(1, 2, width_ratios=[0.25, 12], wspace=0.05)

    ax_color = fig.add_subplot(gs[0, 0])
    ax_color.imshow(np.array(cat_codes).reshape(-1, 1), aspect="auto",
                    cmap=matplotlib.colors.ListedColormap(list(CATEGORY_COLORS.values())))
    ax_color.set_xticks([])
    ax_color.set_yticks([])
    ax_color.set_title("类别", fontsize=10)

    ax = fig.add_subplot(gs[0, 1])
    image = ax.imshow(data, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(value_cols)))
    ax.set_xticklabels([shorten_label(c) for c in value_cols], rotation=35, ha="right", fontsize=8)

    tick_step = max(1, len(matrix_df) // 12)
    tick_positions = list(range(0, len(matrix_df), tick_step))
    ax.set_yticks(tick_positions)
    ax.set_yticklabels([matrix_df.iloc[idx]["paper_id"][:18] for idx in tick_positions], fontsize=7)

    total_present = int(data.sum())
    total_cells = int(data.size)
    ax.set_title(f"sample-parameter matrix 稀疏性热图 (行={len(matrix_df)}, 列={len(value_cols)}, "
                f"填充率={total_present}/{total_cells}={total_present/max(total_cells,1):.1%})")

    cbar = fig.colorbar(image, ax=ax, shrink=0.8)
    cbar.set_label("存在性 (1=有数据)")

    fig.text(0.01, 0.02, "数据来源：sample_parameter_long.csv；按 category 排序，优先展示填充率高的 paper；列按 parameter type 排序",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 8. Canonical key × category heatmap (count + normalized)
# ============================================================================

def plot_count_and_normalized_heatmaps(
    canonical_key_by_category: pd.DataFrame,
    count_base_path: Path,
    norm_base_path: Path,
    top_n: int,
) -> None:
    if canonical_key_by_category.empty:
        make_placeholder_figure(count_base_path, title="canonical_key × category 热图（count）",
                                message="无数据。", data_source="canonical_key_by_category.csv")
        make_placeholder_figure(norm_base_path, title="canonical_key × category 热图（normalized）",
                                message="无数据。", data_source="canonical_key_by_category.csv")
        return

    totals = canonical_key_by_category.groupby("canonical_key")["count"].sum().sort_values(ascending=False).head(top_n)
    top_keys = totals.index.tolist()
    subset = canonical_key_by_category[canonical_key_by_category["canonical_key"].isin(top_keys)].copy()
    subset["label"] = subset["canonical_key"].map(shorten_label)

    count_table = subset.pivot_table(index="category", columns="label", values="count", fill_value=0)
    norm_table = subset.pivot_table(index="category", columns="label", values="normalized_frequency", fill_value=0)

    col_order = [shorten_label(k) for k in top_keys]
    count_table = count_table.reindex(columns=[c for c in col_order if c in count_table.columns], fill_value=0)
    norm_table = norm_table.reindex(columns=[c for c in col_order if c in norm_table.columns], fill_value=0)

    # Count heatmap
    fig1, ax1 = plt.subplots(figsize=(13, 5.5))
    im1 = ax1.imshow(count_table.values, cmap="Blues", aspect="auto")
    ax1.set_xticks(range(len(count_table.columns)))
    ax1.set_xticklabels(count_table.columns, rotation=35, ha="right", fontsize=8.5)
    ax1.set_yticks(range(len(count_table.index)))
    ax1.set_yticklabels(count_table.index, fontsize=10)
    ax1.set_title(f"canonical_key × category 出现频次 (Top {top_n})")
    cbar1 = fig1.colorbar(im1, ax=ax1, shrink=0.85)
    cbar1.set_label("count")
    # Add count annotations
    for i in range(len(count_table.index)):
        for j in range(len(count_table.columns)):
            val = count_table.values[i, j]
            if val > 0:
                ax1.text(j, i, str(int(val)), ha="center", va="center", fontsize=7, color="white" if val > count_table.values.max() * 0.5 else "#17375e")
    fig1.text(0.01, 0.02, "数据来源：canonical_key_by_category.csv；显示绝对频次；标签使用短名称",
              fontsize=9, color="#4f6b8a")
    save_figure(fig1, count_base_path)

    # Normalized heatmap
    fig2, ax2 = plt.subplots(figsize=(13, 5.5))
    im2 = ax2.imshow(norm_table.values, cmap="YlOrRd", aspect="auto")
    ax2.set_xticks(range(len(norm_table.columns)))
    ax2.set_xticklabels(norm_table.columns, rotation=35, ha="right", fontsize=8.5)
    ax2.set_yticks(range(len(norm_table.index)))
    ax2.set_yticklabels(norm_table.index, fontsize=10)
    ax2.set_title(f"canonical_key × category 归一化富集 (Top {top_n}, 类别内归一化)")
    cbar2 = fig2.colorbar(im2, ax=ax2, shrink=0.85)
    cbar2.set_label("normalized frequency (per category)")
    for i in range(len(norm_table.index)):
        for j in range(len(norm_table.columns)):
            val = norm_table.values[i, j]
            if val > 0:
                ax2.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if val > norm_table.values.max() * 0.6 else "#17375e")
    fig2.text(0.01, 0.02, "数据来源：canonical_key_by_category.csv；类别内归一化频次，消除样本量差异",
              fontsize=9, color="#4f6b8a")
    save_figure(fig2, norm_base_path)


# ============================================================================
# 9. Stage 3 overview dashboard (16:9 PPT)
# ============================================================================

def plot_overview_dashboard_v2(
    summary: dict[str, Any],
    parameter_distribution: pd.DataFrame,
    action_cleaned: pd.DataFrame,
    paper_summary: pd.DataFrame,
    base_path: Path,
) -> None:
    fig = plt.figure(figsize=(13.33, 7.5))
    gs = GridSpec(12, 28, figure=fig)

    fig.suptitle("Stage 3 文献结构化抽取 - 结果总览", fontsize=22, fontweight="bold", color="#17375e", y=0.985)

    # Top KPI cards row
    kpi_cards = [
        (str(summary.get("total_papers", "?")), "篇文献", "#2d7bc6"),
        (str(summary.get("total_data_points", "?")), "data points", "#4d97de"),
        (str(summary.get("total_process_steps", "?")), "process steps", "#74a857"),
        (str(summary.get("total_evidence_objects", "?")), "evidence objects", "#d99058"),
        (str(summary.get("unique_canonical_key_count", "?")), "unique keys", "#7a62b3"),
        (str(int(action_cleaned["action"].nunique()) if not action_cleaned.empty else "?"),
         "cleaned actions", "#2d7bc6"),
    ]
    for idx, (value, label, color) in enumerate(kpi_cards):
        ax = fig.add_subplot(gs[0:2, idx * 4 + (idx // 3) * 2: idx * 4 + (idx // 3) * 2 + 4])
        ax.axis("off")
        box = FancyBboxPatch((0.02, 0.05), 0.96, 0.9, boxstyle="round,pad=0.02,rounding_size=0.03",
                            facecolor="white", edgecolor=color, linewidth=2)
        ax.add_patch(box)
        ax.text(0.5, 0.63, value, ha="center", va="center", fontsize=20, fontweight="bold", color=color)
        ax.text(0.5, 0.32, label, ha="center", va="center", fontsize=10, color="#345273")

    # Top canonical keys
    ax1 = fig.add_subplot(gs[3:12, 0:10])
    if not parameter_distribution.empty:
        top_keys = parameter_distribution.head(12).iloc[::-1]
        labels = [shorten_label(k) for k in top_keys["canonical_key"]]
        ax1.barh(labels, top_keys["count"], color="#2d7bc6", height=0.7)
        ax1.set_title("Top 12 canonical_key", fontsize=11, fontweight="bold")
        ax1.tick_params(axis="y", labelsize=8)
        ax1.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax1.text(0.5, 0.5, "无数据", ha="center", va="center")

    # Cleaned action distribution
    ax2 = fig.add_subplot(gs[3:12, 10:20])
    if not action_cleaned.empty:
        top_acts = action_cleaned.head(12).iloc[::-1]
        labels = [f"{ACTION_ZH_LABELS.get(a, a)}" for a in top_acts["action"]]
        ax2.barh(labels, top_acts["count"], color="#74a857", height=0.7)
        ax2.set_title("Top 12 清洗后工艺动作", fontsize=11, fontweight="bold")
        ax2.tick_params(axis="y", labelsize=8)
        ax2.grid(axis="x", linestyle="--", alpha=0.4)
    else:
        ax2.text(0.5, 0.5, "无数据", ha="center", va="center")

    # Category contribution
    ax3 = fig.add_subplot(gs[3:12, 20:28])
    if not paper_summary.empty:
        cat_contrib = (
            paper_summary.groupby("category")[["data_point_count", "process_steps_count", "evidence_object_count"]]
            .sum().sort_values("data_point_count", ascending=False)
        )
        x = np.arange(len(cat_contrib.index))
        w = 0.25
        ax3.bar(x - w, cat_contrib["data_point_count"], w, label="data_points", color="#2d7bc6")
        ax3.bar(x, cat_contrib["process_steps_count"], w, label="process_steps", color="#74a857")
        ax3.bar(x + w, cat_contrib["evidence_object_count"], w, label="evidence", color="#d99058")
        ax3.set_xticks(x)
        ax3.set_xticklabels(cat_contrib.index, rotation=25, ha="right", fontsize=8)
        ax3.set_title("类别贡献", fontsize=11, fontweight="bold")
        ax3.legend(fontsize=7)
        ax3.grid(axis="y", linestyle="--", alpha=0.4)
    else:
        ax3.text(0.5, 0.5, "无数据", ha="center", va="center")

    fig.text(0.01, 0.015, "数据来源：Stage 3 batch extraction → process_steps.jsonl / schema_v2.json → 聚合统计",
             fontsize=9, color="#4f6b8a")
    save_figure(fig, base_path)


# ============================================================================
# 10. Main build function
# ============================================================================

def build_analysis_v2(
    manifest_path: Path,
    analysis_dir: Path,
    outputs_dir: Path,
    output_dir: Path,
    stage3_subdir: str,
    top_n: int,
    paper_limit: int,
) -> dict[str, Any]:
    configure_matplotlib()
    output_dir = ensure_directory(output_dir)
    figures_dir = ensure_directory(output_dir / "figures")

    # --- Load input data ---
    print("Loading input data...")
    manifest_rows = load_manifest_rows(manifest_path)

    # Read existing CSVs
    process_action_orig = pd.read_csv(analysis_dir / "process_step_action_distribution.csv")
    process_conditions_orig = pd.read_csv(analysis_dir / "process_condition_distribution.csv")
    canonical_key_by_category = pd.read_csv(analysis_dir / "canonical_key_by_category.csv")
    sample_parameter_long = pd.read_csv(analysis_dir / "sample_parameter_long.csv")
    parameter_cooccurrence_edges = pd.read_csv(analysis_dir / "parameter_cooccurrence_edges.csv")
    parameter_distribution = pd.read_csv(analysis_dir / "parameter_distribution.csv")
    paper_stage3_summary = pd.read_csv(analysis_dir / "paper_stage3_summary.csv")
    stage3_summary = json.loads((analysis_dir / "stage3_analysis_summary.json").read_text(encoding="utf-8"))

    # Re-scan process steps for better canonicalization
    print("Scanning process_steps.jsonl for action canonicalization...")
    steps_df = scan_process_steps_from_source(manifest_rows, stage3_subdir)

    # ========================================================================
    # 1. Action distribution - cleaned
    # ========================================================================
    print("Building cleaned action distribution...")
    action_cleaned = build_cleaned_action_distribution(steps_df)
    write_dataframe(action_cleaned, output_dir / "process_step_action_distribution_cleaned.csv")
    plot_action_distribution_v2(action_cleaned, figures_dir / "process_step_action_distribution_cleaned")

    old_other = int(process_action_orig.loc[process_action_orig["action"] == "other", "count"].sum()) if "other" in process_action_orig["action"].values else 0
    new_other = int(action_cleaned.loc[action_cleaned["action"] == "other", "count"].sum()) if not action_cleaned.empty else 0

    # ========================================================================
    # 2. Time condition distributions by type
    # ========================================================================
    print("Building time condition distributions...")
    time_cond_df, time_outliers = build_time_condition_distribution(steps_df, process_conditions_orig)
    write_dataframe(time_cond_df, output_dir / "time_condition_distribution_by_type.csv")
    if time_outliers:
        pd.DataFrame(time_outliers).to_csv(output_dir / "time_condition_outliers.csv", index=False, encoding="utf-8-sig")
    plot_time_condition_by_type(time_cond_df, figures_dir / "time_condition_distribution_by_type")

    # ========================================================================
    # 3. Heating rate distribution
    # ========================================================================
    print("Building heating rate distribution...")
    hr_df, hr_outliers = build_heating_rate_distribution(process_conditions_orig)
    write_dataframe(hr_df, output_dir / "heating_rate_cleaned.csv")
    if not hr_outliers.empty:
        write_dataframe(hr_outliers, output_dir / "heating_rate_outliers.csv")
    plot_heating_rate_distribution(hr_df, hr_outliers, figures_dir / "heating_rate_distribution")

    # ========================================================================
    # 4. Calcination / Sintering temperature distributions
    # ========================================================================
    print("Building calcination/sintering temperature distributions...")
    calc_df, sinter_df, temp_outliers = build_temperature_distributions(process_conditions_orig)
    write_dataframe(calc_df, output_dir / "calcination_temperature_cleaned.csv")
    write_dataframe(sinter_df, output_dir / "sintering_temperature_cleaned.csv")
    if not temp_outliers.empty:
        write_dataframe(temp_outliers, output_dir / "temperature_outliers.csv")
    plot_calcination_temperature(calc_df, figures_dir / "calcination_temperature_distribution")
    plot_sintering_temperature(sinter_df, figures_dir / "sintering_temperature_distribution")
    plot_calcination_sintering_overlay(calc_df, sinter_df, figures_dir / "calcination_sintering_temperature_overlay")

    # ========================================================================
    # 5. Real step transition diagram
    # ========================================================================
    print("Building real step transition diagram...")
    transitions_df = build_real_transitions(steps_df)
    write_dataframe(transitions_df, output_dir / "transition_edges.csv")
    plot_transition_diagram(transitions_df, figures_dir / "process_route_transition_diagram")

    # ========================================================================
    # 6. Parameter cooccurrence network
    # ========================================================================
    print("Building parameter cooccurrence network...")
    network_edges, network_summary = build_cleaned_network(
        parameter_cooccurrence_edges, parameter_distribution, sample_parameter_long,
    )
    write_dataframe(network_edges, output_dir / "parameter_cooccurrence_edges_top.csv")
    (output_dir / "network_summary.json").write_text(
        json.dumps(network_summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    plot_cleaned_network(network_edges, parameter_distribution, network_summary,
                        figures_dir / "parameter_cooccurrence_network_cleaned")

    # ========================================================================
    # 7. Sample-parameter matrix sparsity heatmap
    # ========================================================================
    print("Building sample-parameter matrix heatmap...")
    matrix_df, matrix_summary = build_sample_parameter_matrix_ppt_v2(
        sample_parameter_long, parameter_distribution, paper_limit,
    )
    (output_dir / "sample_parameter_matrix_summary.json").write_text(
        json.dumps(matrix_summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    plot_sample_parameter_matrix_v2(matrix_df, figures_dir / "sample_parameter_matrix_sparsity_heatmap_ppt")

    # ========================================================================
    # 8. Canonical key × category heatmaps
    # ========================================================================
    print("Building canonical key × category heatmaps...")
    plot_count_and_normalized_heatmaps(
        canonical_key_by_category,
        figures_dir / "canonical_key_category_heatmap_top20_count",
        figures_dir / "canonical_key_category_heatmap_top20_normalized",
        min(20, top_n),
    )
    # Also save the CSV summary
    totals = canonical_key_by_category.groupby("canonical_key")["count"].sum().sort_values(ascending=False)
    top_keys = totals.head(min(20, top_n)).index.tolist()
    subset = canonical_key_by_category[canonical_key_by_category["canonical_key"].isin(top_keys)].copy()
    write_dataframe(subset, output_dir / "canonical_key_category_summary.csv")

    # ========================================================================
    # 9. Overview dashboard
    # ========================================================================
    print("Building overview dashboard...")
    plot_overview_dashboard_v2(
        stage3_summary, parameter_distribution, action_cleaned, paper_stage3_summary,
        figures_dir / "stage3_overview_dashboard",
    )

    # ========================================================================
    # 10. Generate comprehensive summary
    # ========================================================================
    print("Generating comprehensive summary...")

    # ========================================================================
    # Build per-type time condition statistics
    # ========================================================================
    time_type_stats: dict[str, dict[str, Any]] = {}
    type_order = [
        "aging_time", "drying_time", "calcination_holding_time",
        "sintering_holding_time", "hydrolysis_time", "stirring_time",
        "holding_time", "measurement_time", "generic_holding_time",
    ]

    for tt in type_order:
        in_dist = time_cond_df[time_cond_df["time_type"] == tt] if not time_cond_df.empty else pd.DataFrame()
        in_outliers = [o for o in time_outliers if o.get("time_type") == tt]
        dist_n = len(in_dist)
        excl_n = len(in_outliers)
        audit_n = dist_n + excl_n

        # Count exclusion reasons
        excl_reasons: dict[str, int] = {}
        for o in in_outliers:
            reason = o.get("exclusion_reason", "unknown")
            excl_reasons[reason] = excl_reasons.get(reason, 0) + 1

        # Confidence counts from the time_cond distribution (these are all included rows)
        # We estimate: L1_precise -> high, L2_action/L2_context -> medium, others -> low
        # For excluded rows, their confidence stays as classified
        is_proc = _is_process_time_type(tt)

        time_type_stats[tt] = {
            "audit_N": audit_n,
            "distribution_N": dist_n,
            "excluded_N": excl_n,
            "exclusion_reasons": excl_reasons,
            "is_process_time": is_proc,
            "note": ("" if is_proc else "表征/测试耗时，不计入制备工艺时间"),
            "generic_note": ("fallback类型，未判定具体工艺阶段，不能直接解释为某一具体工艺阶段"
                            if tt == "generic_holding_time" else ""),
        }

    n_time_excluded = sum(st["excluded_N"] for st in time_type_stats.values())

    top_params = []
    if not parameter_distribution.empty:
        for _, row in parameter_distribution.head(15).iterrows():
            top_params.append({"canonical_key": row["canonical_key"], "count": int(row["count"])})

    top_actions_list = []
    if not action_cleaned.empty:
        for _, row in action_cleaned.head(15).iterrows():
            top_actions_list.append({"action": row["action"], "action_zh": row["action_zh"], "count": int(row["count"])})

    top_categories = []
    if not paper_stage3_summary.empty:
        cat_counts = paper_stage3_summary.groupby("category")["data_point_count"].sum().sort_values(ascending=False)
        for cat, cnt in cat_counts.items():
            top_categories.append({"category": cat, "data_point_count": int(cnt)})

    generated_figures = [
        "process_step_action_distribution_cleaned",
        "time_condition_distribution_by_type",
        "heating_rate_distribution",
        "calcination_temperature_distribution",
        "sintering_temperature_distribution",
        "calcination_sintering_temperature_overlay",
        "process_route_transition_diagram",
        "parameter_cooccurrence_network_cleaned",
        "sample_parameter_matrix_sparsity_heatmap_ppt",
        "canonical_key_category_heatmap_top20_count",
        "canonical_key_category_heatmap_top20_normalized",
        "stage3_overview_dashboard",
    ]

    data_files_generated = [
        "process_step_action_distribution_cleaned.csv",
        "time_condition_distribution_by_type.csv",
        "time_condition_outliers.csv",
        "time_condition_classification_audit.csv",
        "heating_rate_cleaned.csv",
        "heating_rate_outliers.csv",
        "calcination_temperature_cleaned.csv",
        "sintering_temperature_cleaned.csv",
        "temperature_outliers.csv",
        "transition_edges.csv",
        "parameter_cooccurrence_edges_top.csv",
        "network_summary.json",
        "sample_parameter_matrix_summary.json",
        "canonical_key_category_summary.csv",
    ]

    figure_data_sources = {
        "process_step_action_distribution_cleaned": "process_steps.jsonl (re-scanned) + process_step_action_distribution_cleaned.csv",
        "time_condition_distribution_by_type": "process_condition_distribution.csv → time_condition_distribution_by_type.csv",
        "heating_rate_distribution": "process_condition_distribution.csv → heating_rate_cleaned.csv + heating_rate_outliers.csv",
        "calcination_temperature_distribution": "process_condition_distribution.csv → calcination_temperature_cleaned.csv",
        "sintering_temperature_distribution": "process_condition_distribution.csv → sintering_temperature_cleaned.csv",
        "calcination_sintering_temperature_overlay": "calcination_temperature_cleaned.csv + sintering_temperature_cleaned.csv",
        "process_route_transition_diagram": "process_steps.jsonl (step_order) → transition_edges.csv",
        "parameter_cooccurrence_network_cleaned": "parameter_cooccurrence_edges.csv + parameter_distribution.csv → parameter_cooccurrence_edges_top.csv",
        "sample_parameter_matrix_sparsity_heatmap_ppt": "sample_parameter_long.csv → sample_parameter_matrix_summary.json",
        "canonical_key_category_heatmap_top20_count": "canonical_key_by_category.csv → canonical_key_category_summary.csv",
        "canonical_key_category_heatmap_top20_normalized": "canonical_key_by_category.csv → canonical_key_category_summary.csv",
        "stage3_overview_dashboard": "stage3_analysis_summary.json + paper_stage3_summary.csv + 上述各数据文件",
    }

    figure_n_values = {}
    if not action_cleaned.empty:
        figure_n_values["process_step_action_distribution_cleaned"] = int(action_cleaned["count"].sum())
    if not time_cond_df.empty:
        figure_n_values["time_condition_distribution_by_type"] = len(time_cond_df)
    if not hr_df.empty:
        figure_n_values["heating_rate_distribution"] = len(hr_df)
    if not calc_df.empty:
        figure_n_values["calcination_temperature_distribution"] = len(calc_df)
    if not sinter_df.empty:
        figure_n_values["sintering_temperature_distribution"] = len(sinter_df)
    figure_n_values["calcination_sintering_temperature_overlay"] = len(calc_df) + len(sinter_df)
    if not transitions_df.empty:
        figure_n_values["process_route_transition_diagram"] = int(transitions_df["count"].sum())
    figure_n_values["parameter_cooccurrence_network_cleaned"] = network_summary["n_nodes"]
    if not matrix_df.empty:
        value_cols_m = [c for c in matrix_df.columns if c not in {"category", "paper_id"}]
        figure_n_values["sample_parameter_matrix_sparsity_heatmap_ppt"] = f"{len(matrix_df)} papers × {len(value_cols_m)} keys"
    figure_n_values["canonical_key_category_heatmap_top20_count"] = stage3_summary.get("total_data_points", "?")
    figure_n_values["canonical_key_category_heatmap_top20_normalized"] = stage3_summary.get("total_data_points", "?")
    figure_n_values["stage3_overview_dashboard"] = stage3_summary.get("total_papers", "?")

    # Exclusion reasons breakdown across all types
    all_excl_reasons: dict[str, int] = {}
    for st in time_type_stats.values():
        for reason, count in st["exclusion_reasons"].items():
            all_excl_reasons[reason] = all_excl_reasons.get(reason, 0) + count

    filtered_summary = {
        "time_condition_total_excluded": n_time_excluded,
        "time_condition_exclusion_reasons": all_excl_reasons,
        "temperature_outliers": len(temp_outliers),
        "heating_rate_outliers": len(hr_outliers) if not hr_outliers.empty else 0,
    }

    warnings_list = []
    if new_other > 0.1 * action_cleaned["count"].sum() if not action_cleaned.empty else False:
        warnings_list.append(f"other_action_still_{new_other}_steps: 清洗后 other 仍较高，需进一步检查 process_steps 原始数据")
    if n_time_excluded > 0:
        warnings_list.append(f"time_condition_excluded_{n_time_excluded}: {n_time_excluded} 条时间数据被排除(详见 time_condition_statistics)")
    if len(temp_outliers) > 0:
        warnings_list.append(f"temperature_outliers_{len(temp_outliers)}: {len(temp_outliers)} 条温度异常值")
    if not hr_outliers.empty and len(hr_outliers) > 0:
        warnings_list.append(f"heating_rate_outliers_{len(hr_outliers)}: {len(hr_outliers)} 条升温速率异常值")

    v2_summary = {
        "title": "Stage 3 Analysis Outputs V2 — Comprehensive Summary",
        "input_files": {
            "manifest": str(manifest_path),
            "analysis_input_dir": str(analysis_dir),
            "outputs_dir": str(outputs_dir),
        },
        "output_directory": str(output_dir),
        "figures_directory": str(figures_dir),
        "figures_generated": [
            {"name": name, "data_source": figure_data_sources.get(name, ""), "N": figure_n_values.get(name, "N/A")}
            for name in generated_figures
        ],
        "data_files_generated": [str(output_dir / f) for f in data_files_generated],
        "time_condition_statistics": time_type_stats,
        "filtered_counts": filtered_summary,
        "action_canonicalization": {
            "old_other_count": old_other,
            "new_other_count": new_other,
            "total_steps": int(action_cleaned["count"].sum()) if not action_cleaned.empty else 0,
            "other_reduction": f"{(old_other - new_other) / max(old_other, 1) * 100:.1f}%" if old_other > 0 else "N/A",
            "unique_actions_original": int(process_action_orig["action"].nunique()),
            "unique_actions_cleaned": int(action_cleaned["action"].nunique()) if not action_cleaned.empty else 0,
        },
        "top_parameters": top_params,
        "top_actions": top_actions_list,
        "top_categories": top_categories,
        "warnings": warnings_list,
        "limitations": [
            "未调用 VLM 或 LLM 进行二次审核",
            "未重跑 Stage 4A / Stage 5",
            "未进行 PDF 图像理解",
            "action canonicalization 基于字符串匹配，极少数模糊动作可能仍归入 other",
            "温度/时间过滤阈值 (100-2500degC, 0-500h) 为经验值，极端工艺可能被误过滤",
            "generic_holding_time 为 fallback 类型，未判定具体工艺阶段",
            "measurement_time 为表征/测试耗时，不计入制备工艺时间",
        ],
    }

    (output_dir / "analysis_outputs_stage3_summary.json").write_text(
        json.dumps(v2_summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    print(f"\nDone! Output written to: {output_dir}")
    print(f"  Figures: {figures_dir}")
    print(f"  old other={old_other} → new other={new_other}")
    print(f"  Generated {len(generated_figures)} figures")
    print(f"  Generated {len(data_files_generated)} data files")

    return v2_summary


def main() -> None:
    args = parse_args()
    result = build_analysis_v2(
        manifest_path=resolve_path(args.manifest),
        analysis_dir=resolve_path(args.analysis_dir),
        outputs_dir=resolve_path(args.outputs_dir),
        output_dir=resolve_path(args.output_dir),
        stage3_subdir=args.stage3_subdir,
        top_n=args.top_n,
        paper_limit=args.paper_limit,
    )
    print(json.dumps({
        "output_dir": str(result["output_directory"]),
        "figures": len(result["figures_generated"]),
        "new_other": result["action_canonicalization"]["new_other_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
