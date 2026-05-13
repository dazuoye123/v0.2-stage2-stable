from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import XRDExtraction


def test_xrd_prompt_mentions_all_visually_resolvable_peaks() -> None:
    prompt = get_prompt_for_figure_type("xrd_pattern").text
    assert "Extract all visually resolvable peaks, not only the strongest peaks." in prompt
    assert "Include weak peaks only if they are distinct from noise." in prompt
    assert "Sort peaks by increasing 2theta." in prompt


def test_xrd_schema_accepts_rich_peak_fields() -> None:
    record = XRDExtraction(
        figure_id="fig-xrd",
        peaks=[
            {
                "position": 25.8,
                "unit": "2theta_deg",
                "intensity_level": "strong",
                "is_primary_peak": True,
                "source": "image",
                "source_text": "main peak near 25.8",
                "confidence": 0.92,
                "warnings": [],
            }
        ],
        detected_phases=["mullite"],
        phase_assignments=["Matches mullite pattern"],
        reference_ticks_visible=True,
        visible_peak_count_estimate=8,
    ).model_dump()
    peak = record["peaks"][0]
    assert peak["intensity_level"] == "strong"
    assert peak["is_primary_peak"] is True
    assert record["reference_ticks_visible"] is True
    assert record["visible_peak_count_estimate"] == 8
