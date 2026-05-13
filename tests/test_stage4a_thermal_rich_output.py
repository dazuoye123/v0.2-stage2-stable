from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import ThermalAnalysisExtraction


def test_thermal_prompt_mentions_thermal_events() -> None:
    prompt = get_prompt_for_figure_type("tg_curve").text
    assert "thermal events" in prompt
    assert "mass-loss steps and residue" in prompt


def test_thermal_schema_accepts_thermal_events() -> None:
    record = ThermalAnalysisExtraction(
        figure_id="fig-tg",
        thermal_events=[
            {
                "event_type": "mass_loss",
                "temperature_onset": 100,
                "temperature_peak": 150,
                "temperature_end": 220,
                "temperature_unit": "C",
                "mass_loss_percent": 12.5,
                "assignment": "dehydration",
                "source": "image_and_text",
                "source_text": "first mass-loss step around 150 C",
                "confidence": 0.8,
                "warnings": [],
            }
        ],
        total_mass_loss_percent=66,
        final_residue_percent=34,
    ).model_dump()
    event = record["thermal_events"][0]
    assert event["event_type"] == "mass_loss"
    assert event["mass_loss_percent"] == 12.5
    assert record["total_mass_loss_percent"] == 66
