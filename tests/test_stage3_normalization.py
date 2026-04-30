from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.models.schema_v2 import ParameterRecord
from alumina_sol_extractor.ontology import get_ontology_entry_map
from alumina_sol_extractor.stage3.normalization import (
    normalize_parameter_records,
    reject_noncanonical_records,
    validate_canonical_keys,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_valid_canonical_key_passes() -> None:
    ontology = get_ontology_entry_map(PROJECT_ROOT)
    records = [ParameterRecord(canonical_key="elastic_modulus_GPa", raw_name="弹性模量", value=1.2, unit="GPa")]
    errors = validate_canonical_keys(records, ontology)
    assert errors == []


def test_invalid_canonical_key_is_rejected() -> None:
    ontology = get_ontology_entry_map(PROJECT_ROOT)
    records = [ParameterRecord(canonical_key="mystery_key", raw_name="神秘参数", value=1)]
    accepted, rejected = reject_noncanonical_records(records, ontology)
    assert accepted == []
    assert rejected
    assert rejected[0]["reason"] == "noncanonical_parameter_record"


def test_unit_normalization_converts_supported_units() -> None:
    ontology = get_ontology_entry_map(PROJECT_ROOT)
    records = [
        ParameterRecord(canonical_key="tensile_strength_MPa", raw_name="拉伸强度", value=1.5, unit="GPa"),
        ParameterRecord(canonical_key="aging_time_h", raw_name="老化时间", value=30, unit="min"),
        ParameterRecord(canonical_key="holding_time_h", raw_name="保温时间", value=7200, unit="s"),
    ]
    normalized, logs = normalize_parameter_records(records, ontology)
    assert normalized[0].value == 1500
    assert normalized[0].unit == "MPa"
    assert normalized[1].value == 0.5
    assert normalized[1].unit == "h"
    assert normalized[2].value == 2
    assert normalized[2].unit == "h"
    assert len(logs) == 3
