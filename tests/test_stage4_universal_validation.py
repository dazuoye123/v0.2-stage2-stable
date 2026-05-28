from __future__ import annotations

from alumina_sol_extractor.vision_spectra.extractor import validate_universal_extraction_payload


def test_universal_validation_uses_posterior_schema_for_sem_image() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-1",
        "caption": "SEM image of fibers",
        "source_image_path": "sem.jpg",
        "stage2_figure_class": "xrd_pattern",
        "stage3_figure_type": "xrd_pattern",
        "initial_figure_type": "xrd_pattern",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "sem_image",
        "type_confidence": 0.9,
        "type_reason": "image shows fiber micrograph with scale bar",
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "morphology_summary": "fibrous morphology",
            "object_identity": "fiber",
            "view_type": "surface",
            "morphology_type": "fiber",
            "scale_bar": "2 um",
            "morphology_features": ["smooth fibers"],
            "image_quality_notes": [],
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is True
    assert result["schema_name"] == "MicroscopyExtraction"
    assert result["record"]["figure_type"] == "sem_image"
    assert result["record"]["actual_figure_type"] == "sem_image"
    assert result["record"]["routing_mode"] == "universal_compact"


def test_universal_validation_uses_vibrational_schema_for_unknown_stage2_when_actual_ftir() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-2",
        "caption": "FTIR spectrum of the precursor",
        "source_image_path": "ftir.jpg",
        "stage2_figure_class": "unknown",
        "stage3_figure_type": None,
        "initial_figure_type": "unknown",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "ftir_spectrum",
        "type_confidence": 0.8,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "spectrum_type": "FTIR",
            "peaks": [
                {
                    "position": "1000-1100",
                    "source_text": "1000-1100 cm^-1 broad band",
                    "assignment": "Si-O stretching",
                }
            ],
            "band_assignments": ["Si-O stretching"],
            "trend_summary": "broad band present",
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is True
    assert result["schema_name"] == "VibrationalSpectrumExtraction"
    peak = result["record"]["peaks"][0]
    assert peak["position"] is None
    assert "1000-1100" in peak["source_text"]


def test_universal_validation_unknown_type_falls_back_to_unknown_schema() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-3",
        "caption": "unclear figure",
        "source_image_path": "unknown.jpg",
        "stage2_figure_class": "generic_chart_or_plot",
        "stage3_figure_type": None,
        "initial_figure_type": "unknown",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "unknown",
        "type_confidence": 0.2,
        "type_reason": "image too small",
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "safe_observations": ["contains plotted lines"],
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is True
    assert result["schema_name"] == "UnknownFigureExtraction"
    assert result["record"]["needs_manual_review"] is True
    assert result["record"]["likely_figure_type"] == "unknown"


def test_universal_validation_schema_failure_is_captured_without_crashing() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-4",
        "caption": "27Al NMR spectrum",
        "source_image_path": "nmr.jpg",
        "stage2_figure_class": "nmr_spectrum",
        "stage3_figure_type": "nmr_spectrum",
        "initial_figure_type": "nmr_spectrum",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "nmr_spectrum",
        "type_confidence": 0.8,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "quantitative_values": ["invalid", "shape"],
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is False
    assert result["schema_name"] == "NMRExtraction"
    assert "schema_validation_failed" in result["warnings"]


def test_universal_validation_coerces_string_type_confidence_and_range_fields() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-5",
        "caption": "TEM image",
        "source_image_path": "tem.jpg",
        "stage2_figure_class": "microscopy_image",
        "stage3_figure_type": "microscopy_image",
        "initial_figure_type": "tem_image",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "tem_image",
        "type_confidence": "high",
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "morphology_summary": "particles visible",
            "particle_size_range": [15, 25],
            "particle_size_unit": "nm",
            "scale_bar": "100 nm",
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is True
    assert result["record"]["type_confidence"] == 0.9
    assert result["record"]["particle_size_range"] == "15-25 nm"


def test_universal_validation_normalizes_ferron_species_shapes() -> None:
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-6",
        "caption": "Ferron curve",
        "source_image_path": "ferron.jpg",
        "stage2_figure_class": "ferron_curve",
        "stage3_figure_type": "ferron_curve",
        "initial_figure_type": "ferron_curve",
        "technique": None,
        "context_source": {},
    }
    payload = {
        "actual_figure_type": "ferron_curve",
        "type_confidence": 0.8,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "al_species": ["Ala", "Al13"],
            "species_quantification": {
                "Ala": "mononuclear Al",
                "Al13": "tridecameric polycation (Alb)",
            },
        },
    }

    result = validate_universal_extraction_payload(payload, candidate)

    assert result["ok"] is True
    assert result["schema_name"] == "FerronCurveExtraction"
    assert result["record"]["al_species"][0]["species"] == "Ala"
    assert result["record"]["species_quantification"]["Ala"] is None
