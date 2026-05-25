from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _build_rule_based_process_steps_v2


def test_rule_based_process_step_fallback_builds_steps_from_procedure_sentences() -> None:
    procedure_text = (
        "称取一定量九水合硝酸铝和铝粉。"
        "加入去离子水。"
        "搅拌混合液。"
        "加热至 70 ℃ 保温 1 h。"
        "冷却后得到铝溶胶。"
    )
    steps = _build_rule_based_process_steps_v2(procedure_text)
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
    steps = _build_rule_based_process_steps_v2(review_text)
    assert steps == []


def test_rule_based_process_step_fallback_extracts_english_experimental_steps_with_conditions() -> None:
    procedure_text = (
        "Aluminum sec-butoxide was dissolved in ethanol and stirred for 2 h. "
        "Nitric acid was added dropwise. The sol was electrospun at 14 kV and 0.5 mL/h. "
        "The fibers were calcined at 1200 °C for 2 h with a heating rate of 2 °C/min."
    )
    steps = _build_rule_based_process_steps_v2(procedure_text)

    assert len(steps) >= 4
    assert any(step["action"] == "dissolve" for step in steps)
    assert any(step["action"] == "electrospin" for step in steps)
    assert any(step["action"] == "calcine" for step in steps)
    assert any(step.get("temperature_value") == 1200.0 for step in steps)
    assert any(step.get("duration_value") == 2.0 for step in steps)
    assert any(step.get("heating_rate_value") == 2.0 for step in steps)
    assert all(step["action"] != "other" for step in steps)
