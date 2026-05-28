from __future__ import annotations

from alumina_sol_extractor.stage4.prompt_templates import get_universal_compact_prompt


def test_universal_compact_prompt_exists() -> None:
    prompt = get_universal_compact_prompt()
    assert prompt.name == "universal_compact_prompt"
    assert prompt.schema_name == "UniversalCompactFigureExtraction"


def test_universal_compact_prompt_contains_type_routing_rules() -> None:
    text = get_universal_compact_prompt().text
    assert "actual_figure_type" in text
    assert "Stage2 figure_class is only a hint" in text
    assert "Stage3 figure_type is only a hint" in text


def test_universal_compact_prompt_contains_all_allowed_types() -> None:
    text = get_universal_compact_prompt().text
    for token in [
        "xrd_pattern",
        "ftir_spectrum",
        "ir_spectrum",
        "raman_spectrum",
        "nmr_spectrum",
        "tg_curve",
        "dsc_curve",
        "tg_dsc_curve",
        "ferron_curve",
        "sem_image",
        "tem_image",
        "microscopy",
        "unknown",
        "non_extractable",
    ]:
        assert token in text


def test_universal_compact_prompt_contains_range_peak_rule() -> None:
    text = get_universal_compact_prompt().text
    assert "do not convert the range to a midpoint" in text


def test_universal_compact_prompt_contains_sem_tem_scale_rule() -> None:
    text = get_universal_compact_prompt().text
    assert "do not estimate diameter or particle size without a clear scale bar" in text


def test_universal_compact_prompt_requires_json_only_output() -> None:
    text = get_universal_compact_prompt().text
    assert "Return exactly one JSON object" in text
    assert "Do not wrap JSON in markdown" in text


def test_universal_compact_prompt_includes_extraction_fields() -> None:
    text = get_universal_compact_prompt().text
    for token in [
        "\"stage2_predicted_figure_type\"",
        "\"stage2_type_used_as_hint\"",
        "\"corrected_from_stage2_type\"",
        "\"extraction\"",
        "\"peaks\"",
        "\"detected_phases\"",
        "\"band_assignments\"",
        "\"mass_loss_steps\"",
        "\"al_species\"",
        "\"morphology_summary\"",
        "\"safe_observations\"",
    ]:
        assert token in text
