from __future__ import annotations

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_xrd_detected_phases_dicts_are_normalized_to_strings() -> None:
    payload = {
        "detected_phases": [
            {"phase": "莫来石", "source": "image_and_text", "confidence": "high"},
            {"name": "刚玉"},
            {"label": "石英"},
        ]
    }
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="xrd_pattern",
        schema_name="XRDExtraction",
    )
    assert normalized["detected_phases"] == ["莫来石", "刚玉", "石英"]
    assert any(item.startswith("detected_phases_item_mapped_from_dict") for item in warnings)


def test_xrd_detected_phases_strings_are_preserved() -> None:
    payload = {"detected_phases": ["莫来石", "刚玉"]}
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="xrd_pattern",
        schema_name="XRDExtraction",
    )
    assert normalized["detected_phases"] == ["莫来石", "刚玉"]
    assert warnings == []


def test_microscopy_scale_bar_dict_is_normalized_to_string() -> None:
    payload = {"scale_bar": {"length": 200, "unit": "nm", "source": "image"}}
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="tem_image",
        schema_name="MicroscopyExtraction",
    )
    assert normalized["scale_bar"] == "200 nm"
    assert any(item.startswith("scale_bar_mapped_from_dict") for item in warnings)


def test_microscopy_scale_bar_string_is_preserved() -> None:
    payload = {"scale_bar": "200 nm"}
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="tem_image",
        schema_name="MicroscopyExtraction",
    )
    assert normalized["scale_bar"] == "200 nm"
    assert warnings == []


def test_existing_peak_normalization_still_works_for_nmr() -> None:
    payload = {"peaks": [{"position_ppm": 62.5, "confidence": "high"}], "confidence": "medium"}
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        payload,
        figure_type="nmr_spectrum",
        schema_name="NMRExtraction",
    )
    assert normalized["peaks"][0]["position"] == 62.5
    assert normalized["peaks"][0]["unit"] == "ppm"
    assert normalized["confidence"] == 0.6
    assert "peak_position_mapped_from_position_ppm" in warnings
