from __future__ import annotations

from alumina_sol_extractor.stage3.procedure_sections import select_procedure_sections


def test_procedure_selector_recognizes_initial_alumina_sol_section() -> None:
    markdown = """# 2.2 实验部分
实验材料及仪器。
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水，加热至 70 ℃ 保温 1 h，再升温至 90 ℃ 保温 5.5 h，冷却后得到铝溶胶。
# 2.2.3 测试与表征
"""
    sections, selected_text = select_procedure_sections(markdown)
    selected_titles = [item["title"] for item in sections if item.get("selected_for_process_steps")]
    assert "2.2.2 初始铝溶胶的制备" in selected_titles
    assert "称取一定量九水合硝酸铝和铝粉" in selected_text
    assert "加热至 70 ℃ 保温 1 h" in selected_text
    assert "升温至 90 ℃ 保温 5.5 h" in selected_text
    assert "冷却后得到铝溶胶" in selected_text


def test_procedure_selector_prefers_true_methods_over_chapter_one_review() -> None:
    markdown = """# 1.1.3 制备方法
这里是文献综述中的工艺介绍，不是本文实验步骤。
# 2.2 实验部分
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水，加热至 70 ℃ 保温 1 h，再升温至 90 ℃ 保温 5.5 h，冷却后得到铝溶胶。
"""
    sections, selected_text = select_procedure_sections(markdown)
    selected_titles = [item["title"] for item in sections if item.get("selected_for_process_steps")]
    assert "2.2.2 初始铝溶胶的制备" in selected_titles
    assert "1.1.3 制备方法" not in selected_titles
    assert "冷却后得到铝溶胶" in selected_text
