from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _coerce_data_points_payload


def test_flat_datapoint_fields_are_structured_into_sections() -> None:
    payload = {
        "sample_id": "dp-1",
        "spinning_channel_temperature_C": 25,
        "feed_pressure_MPa": 8.8,
        "relative_humidity_percent": 31,
        "spinneret_hole_count": 400,
        "viscosity_Pa_s": 400,
        "peo_content_wt_percent": 3.5,
        "aging_temperature_C": 26,
        "average_fiber_diameter_um": 12,
        "tensile_strength_MPa": 2100,
        "spinnability": "good",
        "unknown_result_flag": "keep",
    }
    ontology = {
        "spinning_channel_temperature_C": {"standard_unit": "C", "category": "forming"},
        "feed_pressure_MPa": {"standard_unit": "MPa", "category": "forming"},
        "relative_humidity_percent": {"standard_unit": "%", "category": "forming"},
        "spinneret_hole_count": {"standard_unit": "count", "category": "forming"},
        "viscosity_Pa_s": {"standard_unit": "Pa*s", "category": "precursor_solution"},
        "peo_content_wt_percent": {"standard_unit": "wt%", "category": "precursor_solution"},
        "aging_temperature_C": {"standard_unit": "C", "category": "precursor_solution"},
        "average_fiber_diameter_um": {"standard_unit": "um", "category": "structure"},
        "tensile_strength_MPa": {"standard_unit": "MPa", "category": "mechanical"},
        "spinnability": {"standard_unit": "categorical", "category": "forming"},
    }
    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-01"},
        ontology=ontology,
        series_index=0,
    )
    assert parse_issue is None
    assert len(records) == 1
    record = records[0]
    assert record["process_parameters"]["forming"]["spinning_channel_temperature_C"] == 25
    assert record["process_parameters"]["forming"]["feed_pressure_MPa"] == 8.8
    assert record["process_parameters"]["forming"]["relative_humidity_percent"] == 31
    assert record["process_parameters"]["forming"]["spinneret_hole_count"] == 400
    assert record["process_parameters"]["precursor_solution"]["viscosity_Pa_s"] == 400
    assert record["process_parameters"]["precursor_solution"]["peo_content_wt_percent"] == 3.5
    assert record["process_parameters"]["precursor_solution"]["aging_temperature_C"] == 26
    assert record["results"]["microstructure_and_pores"]["average_fiber_diameter_um"] == 12
    assert record["results"]["mechanical_properties"]["tensile_strength_MPa"] == 2100
    assert record["results"]["formability"]["spinnability"] == "good"
    assert record["extended_data"]["unclassified_results"]["unknown_result_flag"] == "keep"


def test_flat_datapoint_dict_value_is_preserved_without_breaking_parameter_records() -> None:
    payload = {
        "sample_id": "dp-2",
        "Alb_species_distribution": {
            "monomeric_Al": 0.04,
            "Al13^7+": 0.36,
            "Al30_18+": 1.49,
        },
    }
    ontology = {
        "Alb_species_distribution": {"standard_unit": None, "category": "structure"},
    }

    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-02"},
        ontology=ontology,
        series_index=0,
    )

    assert parse_issue is None
    assert len(records) == 1
    additional = records[0]["additional_parameter_records"]
    assert len(additional) == 1
    assert additional[0]["value"] is None
    assert "Al13^7+" in str(additional[0]["raw_text"] or "")
    assert "raw_dict_value_preserved_unmaterialized" in str(additional[0]["normalization_note"] or "")
