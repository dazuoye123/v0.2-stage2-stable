from __future__ import annotations

from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord
from alumina_sol_extractor.stage3.validators import validate_core_parameter_without_evidence


def test_core_parameter_without_evidence_emits_warning() -> None:
    record = PaperExtractionRecord.model_validate(
        {
            "experiment_series": [
                {
                    "series_id": "ES-01",
                    "data_points": [
                        {
                            "sample_id": "dp-1",
                            "additional_parameter_records": [
                                {
                                    "canonical_key": "viscosity_Pa_s",
                                    "raw_name": "viscosity",
                                    "value": 400,
                                    "unit": "Pa*s",
                                    "evidence_refs": [],
                                },
                                {
                                    "canonical_key": "spinnability",
                                    "raw_name": "spinnability",
                                    "value": "good",
                                    "unit": "categorical",
                                    "evidence_refs": [{"source_id": "fig3-10__ev01", "figure_id": "fig3-10"}],
                                },
                            ],
                        }
                    ],
                }
            ]
        }
    )
    ontology = {
        "viscosity_Pa_s": {"is_core_statistical_field": True},
        "spinnability": {"is_core_statistical_field": True},
    }
    issues = validate_core_parameter_without_evidence(record, ontology)
    assert len(issues) == 1
    assert issues[0]["canonical_key"] == "viscosity_Pa_s"
    assert issues[0]["scope"] == "data_point:dp-1"
