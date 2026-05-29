from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "refine_stage3_analysis_figures.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("stage3_figure_refinement", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonicalize_action_recovers_other_spin() -> None:
    module = _load_module()
    action = module.canonicalize_action("other", "其他", "干法纺丝", "将原液倒入液料罐进行干式喷吹纺丝。")
    assert action == "spin"


def test_clean_process_conditions_filters_zero_and_normalizes_hours() -> None:
    module = _load_module()
    df = pd.DataFrame(
        [
            {"category": "fiber_process", "paper_id": "p1", "step_order": 1, "action": "calcine", "condition_key": "calcination_temperature_C", "condition_value": "800-1000", "condition_unit": "", "source_text": "", "evidence_text": ""},
            {"category": "fiber_process", "paper_id": "p1", "step_order": 1, "action": "heat", "condition_key": "holding_time", "condition_value": "120", "condition_unit": "min", "source_text": "", "evidence_text": ""},
            {"category": "fiber_process", "paper_id": "p1", "step_order": 1, "action": "heat", "condition_key": "heating_rate", "condition_value": 0, "condition_unit": "℃/min", "source_text": "", "evidence_text": ""},
        ]
    )
    cleaned = module.clean_process_conditions(df)
    assert len(cleaned) == 2
    temp_row = cleaned[cleaned["condition_family"] == "calcination_temperature"].iloc[0]
    time_row = cleaned[cleaned["condition_family"] == "holding_time"].iloc[0]
    assert temp_row["normalized_value"] == 900.0
    assert time_row["normalized_value"] == 2.0
    assert "heating_rate" not in cleaned["condition_family"].tolist()


def test_build_cleaned_network_edges_applies_threshold() -> None:
    module = _load_module()
    edges = pd.DataFrame(
        [
            {"source_canonical_key": "pH", "target_canonical_key": "viscosity_Pa_s", "cooccurrence_count": 5, "paper_count": 3, "category_distribution": "{}"},
            {"source_canonical_key": "pH", "target_canonical_key": "particle_size_nm", "cooccurrence_count": 1, "paper_count": 1, "category_distribution": "{}"},
        ]
    )
    params = pd.DataFrame(
        [
            {"canonical_key": "pH", "count": 20},
            {"canonical_key": "viscosity_Pa_s", "count": 18},
            {"canonical_key": "particle_size_nm", "count": 17},
        ]
    )
    cleaned = module.build_cleaned_network_edges(edges, params)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["cooccurrence_count"] == 5


def test_build_sample_parameter_matrix_ppt_limits_to_80_rows() -> None:
    module = _load_module()
    rows = []
    for idx in range(100):
        rows.append(
            {
                "category": "fiber_process" if idx < 50 else "mechanism",
                "paper_id": f"paper_{idx:03d}",
                "sample_id": f"sample_{idx:03d}",
                "sample_name": f"Sample {idx}",
                "canonical_key": "pH" if idx % 2 == 0 else "viscosity_Pa_s",
                "raw_name": "raw",
                "value": 1.0,
                "value_text": "",
                "unit": "",
                "source_text": "support",
                "evidence_refs": "[]",
                "needs_manual_review": False,
            }
        )
    sample_long = pd.DataFrame(rows)
    parameter_distribution = pd.DataFrame(
        [
            {"canonical_key": "pH", "count": 50},
            {"canonical_key": "viscosity_Pa_s", "count": 50},
        ]
    )
    matrix, summary = module.build_sample_parameter_matrix_ppt(sample_long, parameter_distribution)
    assert len(matrix) == 80
    assert "overall" in summary["grouping"].tolist()
