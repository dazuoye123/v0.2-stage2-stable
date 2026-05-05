from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.dspy_modules.runner import _coerce_parameter_record_list
from alumina_sol_extractor.ontology import get_ontology_entry_map
from alumina_sol_extractor.stage3.merge import move_top_level_core_keys_from_global_constants


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_list_valued_spectral_parameters_split_into_scalar_records() -> None:
    ontology = get_ontology_entry_map(PROJECT_ROOT)

    records = _coerce_parameter_record_list(
        {
            "nmr_27Al_peak_position_ppm": [0, 10, 62.5],
            "ftir_peak_position_cm_1": [3400, 1645],
            "xrd_peak_position_2theta_deg": [7, 45.8],
            "pH": 3.6,
            "Al13_fraction_percent": 50,
            "Al_concentration_mol_L": 3.14,
        },
        ontology,
    )

    grouped = {}
    for record in records:
        grouped.setdefault(record["raw_name"], []).append(record)
        assert not isinstance(record["value"], list)

    assert [item["value"] for item in grouped["nmr_27Al_peak_position_ppm"]] == [0, 10, 62.5]
    assert [item["value"] for item in grouped["ftir_peak_position_cm_1"]] == [3400, 1645]
    assert [item["value"] for item in grouped["xrd_peak_position_2theta_deg"]] == [7, 45.8]
    assert grouped["pH"][0]["value"] == 3.6
    assert grouped["Al13_fraction_percent"][0]["value"] == 50
    assert grouped["Al_concentration_mol_L"][0]["value"] == 3.14
    assert "split_list_valued_parameter:index=0;original_length=3" in grouped["nmr_27Al_peak_position_ppm"][0]["normalization_note"]


def test_move_top_level_core_keys_splits_list_valued_spectral_fields() -> None:
    ontology = get_ontology_entry_map(PROJECT_ROOT)

    payload, logs = move_top_level_core_keys_from_global_constants(
        {
            "nmr_27Al_peak_position_ppm": [0, 10, 12, 62.5],
            "scope_note": "shared conditions",
        },
        ontology,
    )

    assert payload["scope_note"] == "shared conditions"
    assert [item["value"] for item in payload["additional_parameter_records"]] == [0, 10, 12, 62.5]
    assert all(not isinstance(item["value"], list) for item in payload["additional_parameter_records"])
    assert any(log["canonical_key"] == "nmr_27Al_peak_position_ppm" for log in logs)
