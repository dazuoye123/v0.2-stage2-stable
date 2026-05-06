from __future__ import annotations

from alumina_sol_extractor.vision_spectra.io import parse_json_payload
from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_parse_json_payload_accepts_json_with_extra_explanatory_text() -> None:
    payload = parse_json_payload(
        'Here is the extracted JSON:\n```json\n{"figure_id":"图2.18","figure_type":"ftir_spectrum","peaks":[]}\n```\nDone.'
    )
    assert payload["figure_id"] == "图2.18"
    assert payload["figure_type"] == "ftir_spectrum"


def test_live_payload_normalization_coerces_invalid_peaks_and_confidence() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "figure_id": "图2.19",
            "figure_type": "xrd_pattern",
            "peaks": "not-a-list",
            "confidence": "not-a-number",
        },
        figure_type="xrd_pattern",
    )
    assert normalized["peaks"] == []
    assert normalized["confidence"] is None
    assert "peaks_coerced_to_empty_list" in warnings
    assert "confidence_cleared_from_invalid_string" in warnings


def test_live_payload_normalization_maps_peak_alias_fields_and_labels() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "figure_id": "图2.18",
            "figure_type": "ftir_spectrum",
            "confidence": "high",
            "peaks": [
                {
                    "wavenumber": 3400,
                    "assignment": "Al-O-H stretching vibration",
                    "confidence": "medium",
                }
            ],
        },
        figure_type="ftir_spectrum",
    )
    assert normalized["confidence"] == 0.9
    assert normalized["peaks"][0]["position"] == 3400
    assert normalized["peaks"][0]["unit"] == "cm-1"
    assert normalized["peaks"][0]["confidence"] == 0.6
    assert "peak_position_mapped_from_wavenumber" in warnings
    assert "peak_confidence_coerced_from_label" in warnings
