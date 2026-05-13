from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type


def test_xrd_prompt_keeps_detected_phases_as_string_list_contract() -> None:
    prompt = get_prompt_for_figure_type("xrd_pattern").text
    assert "detected_phases must be a JSON list of strings." in prompt


def test_vibrational_prompt_preserves_range_in_source_text() -> None:
    prompt = get_prompt_for_figure_type("ftir_spectrum").text
    assert "keep the range in source_text" in prompt


def test_prompt_contract_mentions_warning_arrays_for_xrd_and_microscopy() -> None:
    xrd_prompt = get_prompt_for_figure_type("xrd_pattern").text
    sem_prompt = get_prompt_for_figure_type("sem_image").text
    assert "warnings must be [] if no warnings." in xrd_prompt
    assert "conflict_warnings must be [] if no conflicts." in xrd_prompt
    assert "conflict_warnings must always be a JSON array." in sem_prompt
