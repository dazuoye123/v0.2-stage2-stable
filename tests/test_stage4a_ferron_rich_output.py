from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import FerronCurveExtraction


def test_ferron_prompt_mentions_species_and_equation() -> None:
    prompt = get_prompt_for_figure_type("ferron_curve").text
    assert "Ala/Alb/Alc/Al13 fractions" in prompt
    assert "Preserve fitted equation and R2 when visible." in prompt


def test_ferron_schema_accepts_species_rows() -> None:
    record = FerronCurveExtraction(
        figure_id="fig-ferron",
        curve_type="ferron_curve",
        al_species=[
            {
                "species": "Al13",
                "fraction_percent": 68.0,
                "source": "text",
                "source_text": "Al13 fraction 68%",
                "confidence": 0.88,
            }
        ],
        equation="y = 0.12x + 0.03",
        r_squared=0.992,
        method_summary="Ferron assay at 370 nm",
    ).model_dump()
    assert record["al_species"][0]["species"] == "Al13"
    assert record["equation"] == "y = 0.12x + 0.03"
    assert record["r_squared"] == 0.992
