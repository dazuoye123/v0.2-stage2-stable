from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _coerce_data_points_payload


def test_dict_data_points_payload_is_wrapped_into_list() -> None:
    payload = {
        "viscosity_Pa_s": 400,
        "feed_pressure_MPa": 8.8,
        "sample_label": "sample-a",
    }
    ontology = {
        "viscosity_Pa_s": {"standard_unit": "Pa·s", "category": "sol_property"},
        "feed_pressure_MPa": {"standard_unit": "MPa", "category": "processing"},
    }
    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-01"},
        ontology=ontology,
        series_index=0,
    )
    assert parse_issue is None
    assert len(records) == 1
    assert records[0]["sample_id"] == "ES-01-dp-1"
    assert records[0]["process_parameters"]["viscosity_Pa_s"] == 400
    assert records[0]["process_parameters"]["feed_pressure_MPa"] == 8.8
    assert len(records[0]["additional_parameter_records"]) == 2


def test_data_points_field_list_is_used_directly() -> None:
    payload = {
        "data_points": [
            {
                "sample_id": "dp-1",
                "independent_variable_values": [],
                "process_parameters": {},
                "results": {},
                "evidence_refs": [],
                "additional_parameter_records": [],
                "extended_data": {},
            }
        ]
    }
    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-01"},
        ontology={},
        series_index=0,
    )
    assert parse_issue is None
    assert len(records) == 1
    assert records[0]["sample_id"] == "dp-1"


def test_structured_dict_fields_are_coerced_to_lists() -> None:
    payload = {
        "sample_id": "dp-2",
        "independent_variable_values": {"viscosity_Pa_s": 400},
        "process_parameters": None,
        "results": None,
        "evidence_refs": None,
        "additional_parameter_records": None,
        "extended_data": None,
    }
    ontology = {
        "viscosity_Pa_s": {"standard_unit": "Pa·s", "category": "sol_property"},
    }
    records, parse_issue = _coerce_data_points_payload(
        payload=payload,
        series={"series_id": "ES-01"},
        ontology=ontology,
        series_index=0,
    )
    assert parse_issue is None
    assert len(records) == 1
    assert isinstance(records[0]["independent_variable_values"], list)
    assert records[0]["independent_variable_values"][0]["raw_name"] == "viscosity_Pa_s"
    assert records[0]["additional_parameter_records"] == []
