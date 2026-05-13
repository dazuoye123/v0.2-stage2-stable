from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import VibrationalSpectrumExtraction


def test_vibrational_prompt_mentions_band_types_and_noise_control() -> None:
    prompt = get_prompt_for_figure_type("ftir_spectrum").text
    assert "band_type=broad_band or range_band" in prompt
    assert "Do not map 1000-1100 to 1050." in prompt
    assert "Do not over-extract noise." in prompt


def test_vibrational_schema_accepts_rich_peak_fields() -> None:
    record = VibrationalSpectrumExtraction(
        figure_id="fig-ftir",
        peaks=[
            {
                "position": None,
                "unit": "cm^-1",
                "band_type": "range_band",
                "intensity_level": "strong",
                "assignment": "Al-O-Si stretching",
                "functional_group": "Al-O-Si",
                "phase_or_species": "aluminosilicate",
                "source": "image_and_text",
                "source_text": "1000-1100 cm^-1",
                "confidence": 0.74,
                "warnings": ["range_peak_position_not_numeric"],
            }
        ],
    ).model_dump()
    peak = record["peaks"][0]
    assert peak["band_type"] == "range_band"
    assert peak["functional_group"] == "Al-O-Si"
    assert peak["warnings"] == ["range_peak_position_not_numeric"]
