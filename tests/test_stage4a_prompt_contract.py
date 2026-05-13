from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type


def test_common_prompt_contract_mentions_json_lists_and_numeric_constraints() -> None:
    prompt = get_prompt_for_figure_type("ftir_spectrum").text
    assert "Return exactly one JSON object." in prompt
    assert "All list fields must be JSON arrays." in prompt
    assert "warnings must always be a JSON array." in prompt
    assert "Numeric fields must be number or null." in prompt


def test_xrd_prompt_requires_phase_assignments_as_json_list() -> None:
    prompt = get_prompt_for_figure_type("xrd_pattern").text
    assert "phase_assignments must be a JSON list" in prompt
    assert "Never output phase_assignments as a single string." in prompt


def test_vibrational_prompt_forbids_range_to_midpoint_conversion() -> None:
    prompt = get_prompt_for_figure_type("ftir_spectrum").text
    assert "Do not map 1000-1100 to 1050." in prompt
    assert "set position=null" in prompt


def test_microscopy_prompt_requires_array_warnings() -> None:
    prompt = get_prompt_for_figure_type("sem_image").text
    assert "warnings must always be a JSON array" in prompt
    assert "Never output warnings=null." in prompt
