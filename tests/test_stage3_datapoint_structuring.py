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


def test_two_pass_flat_key_value_bundle_is_merged_into_one_parameter_record() -> None:
    payload = {
        "sample_id": "dp-3",
        "key": "viscosity_Pa_s",
        "value": 0.5,
        "unit": "Pa*s",
        "context": "室温黏度约 0.5 Pa*s",
        "evidence_id": "图2-1",
    }
    ontology = {
        "viscosity_Pa_s": {"standard_unit": "Pa*s", "category": "precursor_solution"},
    }

    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-03"},
        ontology=ontology,
        series_index=0,
    )

    assert parse_issue is None
    assert len(records) == 1
    record = records[0]
    assert record["process_parameters"]["precursor_solution"]["viscosity_Pa_s"] == 0.5
    assert len(record["additional_parameter_records"]) == 1
    parameter = record["additional_parameter_records"][0]
    assert parameter["canonical_key"] == "viscosity_Pa_s"
    assert parameter["raw_name"] == "viscosity_Pa_s"
    assert parameter["value"] == 0.5
    assert parameter["unit"] == "Pa*s"
    assert parameter["raw_text"] == "室温黏度约 0.5 Pa*s"
    assert parameter["evidence_refs"][0]["figure_id"] == "图2-1"


def test_two_pass_split_key_value_rows_are_merged_into_one_parameter_record() -> None:
    ontology = {
        "xrd_peak_position_2theta_deg": {"standard_unit": "deg", "category": "structure"},
    }
    payload = {
        "sample_id": "dp-4",
        "additional_parameter_records": [
            {"raw_name": "key", "value": "xrd_peak_position_2theta_deg"},
            {"raw_name": "value", "value": 26.4},
            {"raw_name": "unit", "value": "deg"},
            {"raw_name": "context", "value": "2θ = 26.4°"},
            {"raw_name": "evidence_id", "value": "Fig. 3"},
        ],
        "process_parameters": {},
        "results": {},
        "independent_variable_values": [],
        "evidence_refs": [],
        "extended_data": {},
    }

    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-04"},
        ontology=ontology,
        series_index=0,
    )

    assert parse_issue is None
    assert len(records) == 1
    merged = records[0]["additional_parameter_records"]
    assert len(merged) == 1
    assert merged[0]["canonical_key"] == "xrd_peak_position_2theta_deg"
    assert merged[0]["raw_name"] == "xrd_peak_position_2theta_deg"
    assert merged[0]["value"] == 26.4
    assert merged[0]["unit"] == "deg"
    assert merged[0]["raw_text"] == "2θ = 26.4°"


def test_two_pass_split_key_value_rows_support_evidence_ref_alias() -> None:
    ontology = {
        "ftir_peak_position_cm_1": {"standard_unit": "cm^-1", "category": "structure"},
    }
    payload = {
        "sample_id": "dp-5",
        "additional_parameter_records": [
            {"raw_name": "key", "value": "ftir_peak_position_cm_1"},
            {"raw_name": "value", "value": 203},
            {"raw_name": "unit", "value": "cm^-1"},
            {"raw_name": "context", "value": "Δν = 203 cm^-1"},
            {"raw_name": "evidence_ref", "value": "图2.8"},
        ],
        "process_parameters": {},
        "results": {},
        "independent_variable_values": [],
        "evidence_refs": [],
        "extended_data": {},
    }

    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-05"},
        ontology=ontology,
        series_index=0,
    )

    assert parse_issue is None
    merged = records[0]["additional_parameter_records"]
    assert len(merged) == 1
    assert merged[0]["canonical_key"] == "ftir_peak_position_cm_1"
    assert merged[0]["evidence_refs"][0]["figure_id"] == "图2.8"


def test_two_pass_split_key_value_rows_merge_sample_and_series_name_aliases() -> None:
    ontology = {
        "viscosity_Pa_s": {"standard_unit": "Pa*s", "category": "precursor_solution"},
    }
    payload = {
        "sample_id": "dp-6",
        "additional_parameter_records": [
            {"raw_name": "key", "value": "viscosity_Pa_s"},
            {"raw_name": "value", "value": 0.8},
            {"raw_name": "unit", "value": "Pa*s"},
            {"raw_name": "context", "value": "黏度约 0.8 Pa*s"},
            {"raw_name": "sample", "value": "S1"},
            {"raw_name": "series_name", "value": "Series Alpha"},
            {"raw_name": "evidence_ref", "value": "Fig. 2"},
        ],
        "process_parameters": {},
        "results": {},
        "independent_variable_values": [],
        "evidence_refs": [],
        "extended_data": {},
    }

    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-06"},
        ontology=ontology,
        series_index=0,
    )

    assert parse_issue is None
    assert len(records) == 1
    merged = records[0]["additional_parameter_records"]
    assert len(merged) == 1
    assert merged[0]["raw_name"] == "viscosity_Pa_s"
