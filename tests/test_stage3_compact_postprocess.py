from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _coerce_compact_global_constants_payload


def test_compact_global_constants_coerces_raw_materials_and_characterization_methods() -> None:
    payload = {
        "raw_materials": {
            "aluminum_source": "铝粉",
            "solvent": "蒸馏水",
        },
        "characterization_methods": ["XRD", "FTIR", "SEM"],
    }

    normalized = _coerce_compact_global_constants_payload(payload, ontology={})

    assert isinstance(normalized["raw_materials"], list)
    assert normalized["raw_materials"][0]["role"] == "aluminum_source"
    assert normalized["raw_materials"][0]["name"] == "铝粉"
    assert normalized["raw_materials"][1]["role"] == "solvent"
    assert normalized["characterization_methods"] == [
        {"method": "XRD"},
        {"method": "FTIR"},
        {"method": "SEM"},
    ]
