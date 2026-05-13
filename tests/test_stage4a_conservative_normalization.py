from __future__ import annotations

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_xrd_phase_assignments_string_is_wrapped_to_list() -> None:
    payload = {
        "phase_assignments": "matches mullite",
        "warnings": None,
        "conflict_warnings": None,
        "peaks": [
            {"position": 40.2},
            {"position": 25.8, "intensity_level": "strong"},
        ],
    }
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="xrd_pattern",
        schema_name="XRDExtraction",
    )
    assert normalized["phase_assignments"] == ["matches mullite"]
    assert normalized["warnings"] == []
    assert normalized["conflict_warnings"] == []
    assert [peak["position"] for peak in normalized["peaks"]] == [25.8, 40.2]
    assert normalized["peaks"][1]["intensity_level"] == "unknown"
    assert "phase_assignments_coerced_to_list" in warnings


def test_vibrational_range_peak_position_becomes_null_without_midpoint() -> None:
    payload = {
        "peaks": [
            {
                "position": "1000-1100",
                "unit": "cm^-1",
                "assignment": "broad Al-O-Si absorption band",
                "source_text": "1000-1100 cm^-1",
            }
        ]
    }
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="ftir_spectrum",
        schema_name="VibrationalSpectrumExtraction",
    )
    peak = normalized["peaks"][0]
    assert peak["position"] is None
    assert peak["source_text"] == "1000-1100 cm^-1"
    assert peak["unit"] == "cm^-1"
    assert not any(peak["position"] == 1050 for peak in normalized["peaks"])
    assert "range_peak_position_not_numeric:1000-1100" in warnings


def test_microscopy_warnings_none_becomes_empty_lists() -> None:
    payload = {
        "warnings": None,
        "conflict_warnings": None,
        "scale_bar": {"value": 200, "unit": "nm"},
    }
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="sem_image",
        schema_name="MicroscopyExtraction",
    )
    assert normalized["warnings"] == []
    assert normalized["conflict_warnings"] == []
    assert normalized["scale_bar"] == "200 nm"
    assert "warnings_normalized_none_to_empty_list" in warnings
    assert "conflict_warnings_normalized_none_to_empty_list" in warnings


def test_thermal_events_none_becomes_empty_list() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"thermal_events": None, "warnings": None, "conflict_warnings": None},
        figure_type="tg_curve",
        schema_name="ThermalAnalysisExtraction",
    )
    assert normalized["thermal_events"] == []
    assert "thermal_events_normalized_none_to_empty_list" in warnings
