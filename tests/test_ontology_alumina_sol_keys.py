from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.ontology import get_canonical_keys, normalize_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alumina_sol_canonical_keys_exist() -> None:
    keys = set(get_canonical_keys(PROJECT_ROOT))
    expected = {
        "Al_to_AlN_molar_ratio",
        "Al_concentration_mol_L",
        "hydrolysis_temperature_C",
        "peptization_time_h",
        "nmr_27Al_peak_position_ppm",
        "Al13_fraction_percent",
        "sol_stability_time_h",
        "spinnability",
    }
    assert expected.issubset(keys)


def test_alumina_sol_alias_mapping() -> None:
    assert normalize_key("铝浓度", PROJECT_ROOT) == "Al_concentration_mol_L"
    assert normalize_key("Al:AlN", PROJECT_ROOT) == "Al_to_AlN_molar_ratio"
    assert normalize_key("铝硝比", PROJECT_ROOT) == "Al_to_AlN_molar_ratio"
    assert normalize_key("水铝比", PROJECT_ROOT) == "water_to_aluminum_molar_ratio"
    assert normalize_key("胶溶时间", PROJECT_ROOT) == "peptization_time_h"
    assert normalize_key("老化时间", PROJECT_ROOT) == "aging_time_h"
    assert normalize_key("27Al NMR峰位", PROJECT_ROOT) == "nmr_27Al_peak_position_ppm"
    assert normalize_key("Al13", PROJECT_ROOT) == "Al13_fraction_percent"
    assert normalize_key("可纺性", PROJECT_ROOT) == "spinnability"


def test_unknown_alias_returns_none() -> None:
    assert normalize_key("不存在的神秘参数", PROJECT_ROOT) is None
