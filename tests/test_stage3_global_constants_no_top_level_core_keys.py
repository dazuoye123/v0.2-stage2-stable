from __future__ import annotations

from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord
from alumina_sol_extractor.stage3.merge import move_top_level_core_keys_from_global_constants
from alumina_sol_extractor.stage3.validators import validate_no_top_level_core_keys_in_global_constants


def test_top_level_core_keys_are_moved_to_additional_parameter_records() -> None:
    ontology = {
        "viscosity_Pa_s": {
            "standard_unit": "Pa·s",
            "is_core_statistical_field": True,
            "zh_name": "粘度",
        }
    }
    payload, logs = move_top_level_core_keys_from_global_constants(
        {"scope_note": "shared", "viscosity_Pa_s": 400},
        ontology,
    )
    assert "viscosity_Pa_s" not in payload
    assert payload["additional_parameter_records"][0]["canonical_key"] == "viscosity_Pa_s"
    assert logs[0]["type"] == "moved_top_level_core_key"


def test_validator_warns_when_top_level_core_key_remains() -> None:
    ontology = {
        "viscosity_Pa_s": {"is_core_statistical_field": True},
    }
    record = PaperExtractionRecord.model_validate(
        {
            "global_constants": {
                "scope_note": "shared",
                "viscosity_Pa_s": 400,
            }
        }
    )
    issues = validate_no_top_level_core_keys_in_global_constants(record, ontology)
    assert len(issues) == 1
    assert issues[0]["canonical_key"] == "viscosity_Pa_s"
