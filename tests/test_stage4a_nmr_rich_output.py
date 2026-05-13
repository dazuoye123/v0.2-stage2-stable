from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import NMRExtraction


def test_nmr_prompt_mentions_species_assignment_and_peak_width() -> None:
    prompt = get_prompt_for_figure_type("nmr_spectrum").text
    assert "Assign Al coordination species only when supported" in prompt
    assert "Mark broad or overlapped peaks using peak_width_type." in prompt


def test_nmr_schema_accepts_species_assignment_and_peak_width() -> None:
    record = NMRExtraction(
        figure_id="fig-nmr",
        nucleus="27Al",
        peaks=[
            {
                "position": 62.5,
                "chemical_shift_ppm": 62.5,
                "unit": "ppm",
                "assignment": "tetrahedral Al",
                "species_assignment": "AlIV",
                "peak_width_type": "broad",
                "source": "image_and_text",
                "source_text": "broad resonance around 62.5 ppm",
                "confidence": 0.81,
                "warnings": [],
            }
        ],
        species_summary="AlIV and AlVI both present",
    ).model_dump()
    peak = record["peaks"][0]
    assert peak["species_assignment"] == "AlIV"
    assert peak["peak_width_type"] == "broad"
    assert record["species_summary"] == "AlIV and AlVI both present"
