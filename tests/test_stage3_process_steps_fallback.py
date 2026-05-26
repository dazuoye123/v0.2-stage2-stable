from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _build_rule_based_process_steps_v3


def test_rule_based_process_step_fallback_builds_steps_from_procedure_sentences() -> None:
    procedure_text = (
        "称取一定量九水合硝酸铝和铝粉。"
        "加入去离子水。"
        "搅拌混合液。"
        "加热至 70 ℃ 保温 1 h。"
        "冷却后得到铝溶胶。"
    )
    steps = _build_rule_based_process_steps_v3(procedure_text)
    assert len(steps) >= 4
    assert all(step["evidence_text"] for step in steps)
    assert all(step["needs_manual_review"] is True for step in steps)
    assert any(step["action_zh"] == "称取" for step in steps)
    assert any(step["action_zh"] == "加入" for step in steps)
    assert any(step["action"] == "heat" for step in steps)
    assert any(step["action_zh"] == "冷却" for step in steps)


def test_rule_based_process_step_fallback_does_not_materialize_review_statements() -> None:
    review_text = (
        "本文研究了氧化铝纤维的性能。"
        "分析了热演化行为和研究意义。"
        "综述了相关研究进展。"
    )
    steps = _build_rule_based_process_steps_v3(review_text)
    assert steps == []


def test_rule_based_process_step_fallback_extracts_english_experimental_steps_with_conditions() -> None:
    procedure_text = (
        "Aluminum sec-butoxide was dissolved in ethanol and stirred for 2 h. "
        "Nitric acid was added dropwise. The sol was electrospun at 14 kV and 0.5 mL/h. "
        "The fibers were calcined at 1200 °C for 2 h with a heating rate of 2 °C/min."
    )
    steps = _build_rule_based_process_steps_v3(procedure_text)

    assert len(steps) >= 4
    assert any(step["action"] == "dissolve" for step in steps)
    assert any(step["action"] == "electrospin" for step in steps)
    assert any(step["action"] == "calcine" for step in steps)
    assert any(step.get("temperature_value") == 1200.0 for step in steps)
    assert any(step.get("duration_value") == 2.0 for step in steps)
    assert any(step.get("heating_rate_value") == 2.0 for step in steps)
    assert all(step["action"] != "other" for step in steps)


def test_rule_based_process_step_fallback_extracts_heat_rate_duration_and_temperature() -> None:
    procedure_text = "将样品以 5 ℃/min 升温至 1000 ℃并保温 2 h。"
    steps = _build_rule_based_process_steps_v3(procedure_text)

    assert len(steps) >= 1
    assert any(step["action"] in {"heat", "calcine"} for step in steps)
    assert any(step.get("temperature_value") == 1000.0 for step in steps)
    assert any(step.get("duration_value") == 2.0 for step in steps)
    assert any(step.get("heating_rate_value") == 5.0 for step in steps)


def test_rule_based_process_step_fallback_splits_stir_and_electrospin_sentence() -> None:
    procedure_text = "The solution was stirred for 2 h and electrospun at 15 kV."
    steps = _build_rule_based_process_steps_v3(procedure_text)

    assert any(step["action"] == "stir" and step.get("duration_value") == 2.0 for step in steps)
    assert any(step["action"] == "electrospin" and step.get("condition_key") == "applied_voltage_kV" and step.get("condition_value") == 15.0 for step in steps)


def test_rule_based_process_step_fallback_extracts_dissolve_reagent_and_temperature() -> None:
    procedure_text = "PVA was dissolved in water at 80 °C."
    steps = _build_rule_based_process_steps_v3(procedure_text)

    assert len(steps) >= 1
    assert any(step["action"] == "dissolve" for step in steps)
    assert any(step.get("reagent_name") == "PVA" for step in steps)
    assert any(step.get("temperature_value") == 80.0 for step in steps)


def test_rule_based_process_step_fallback_ignores_headings_and_table_link_lines() -> None:
    procedure_text = """# Experimental
CSV: [table_001.csv](path/to/table_001.csv)
| column | value |
The solution was stirred for 2 h.
"""
    steps = _build_rule_based_process_steps_v3(procedure_text)

    assert len(steps) == 1
    assert steps[0]["action"] == "stir"
