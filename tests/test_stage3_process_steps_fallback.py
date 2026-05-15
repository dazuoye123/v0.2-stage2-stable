from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _build_rule_based_process_steps


def test_rule_based_process_step_fallback_builds_steps_from_procedure_sentences() -> None:
    procedure_text = (
        "称取一定量九水合硝酸铝和铝粉。"
        "加入去离子水。"
        "搅拌混合液。"
        "加热至 70 ℃ 保温 1 h。"
        "冷却后得到铝溶胶。"
    )
    steps = _build_rule_based_process_steps(procedure_text)
    assert len(steps) >= 4
    assert all(step["evidence_text"] for step in steps)
    assert all(step["needs_manual_review"] is True for step in steps)
    assert any(step["action_zh"] == "称取" for step in steps)
    assert any(step["action_zh"] == "加入" for step in steps)
    assert any(step["action_zh"] == "加热" for step in steps)
    assert any(step["action_zh"] == "冷却" for step in steps)
