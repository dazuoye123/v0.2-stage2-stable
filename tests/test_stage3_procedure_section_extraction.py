from __future__ import annotations

from alumina_sol_extractor.stage3.procedure_sections import select_procedure_sections


def test_procedure_selector_recognizes_initial_alumina_sol_section() -> None:
    markdown = """# 2.2 实验部分
实验材料及仪器
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水，加热至 70 ℃ 保温 1 h，再升温至 90 ℃ 保温 5.5 h，冷却后得到铝溶胶。
# 2.2.3 测试与表征"""
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


def test_procedure_selector_skips_research_progress_when_real_methods_exist() -> None:
    markdown = """# 1.3 研究进展
这里综述了前人关于氧化铝纤维性能和热处理行为的研究进展，并分析了结果。

# 2.1 实验材料与方法
# 2.1.1 样品制备
称取硝酸铝，加入去离子水，搅拌后纺丝，再于 1200 ℃ 煅烧 2 h。

# 3 结果与讨论
研究了样品的力学性能和显微结构。
"""
    sections, selected_text = select_procedure_sections(markdown)
    selected_titles = [item["title"] for item in sections if item.get("selected_for_process_steps")]
    assert "2.1.1 样品制备" in selected_titles
    assert "1.3 研究进展" not in selected_titles
    assert "称取硝酸铝" in selected_text
    assert "研究了样品的力学性能" not in selected_text


def test_procedure_selector_prefers_english_experimental_methods_over_summary() -> None:
    markdown = """# 1 Introduction
This section reviews prior work.

# 2 Experimental
This section describes the sample preparation workflow.

# 2.1 Materials and methods
PVA was dissolved in water and the solution was stirred for 2 h.

# 4 Summary
This chapter summarizes the findings.
"""
    sections, selected_text = select_procedure_sections(markdown)
    selected_titles = [item["title"] for item in sections if item.get("selected_for_process_steps")]
    assert any(title in selected_titles for title in ("2 Experimental", "2.1 Materials and methods"))
    assert "1 Introduction" not in selected_titles
    assert "4 Summary" not in selected_titles
    assert "PVA was dissolved in water" in selected_text


def test_procedure_selector_keeps_late_experimental_chapters_in_long_thesis() -> None:
    markdown = """# 第一章 绪论
这里是文献综述。

# 2.3 测试与表征
这里是表征方法。

# 3.2 样品制备
称取样品，加入去离子水，搅拌后纺丝。

# 4.2 热处理
以 5 ℃/min 升温至 1000 ℃并保温 2 h。
"""
    sections, selected_text = select_procedure_sections(markdown)
    selected_titles = [item["title"] for item in sections if item.get("selected_for_process_steps")]
    assert "3.2 样品制备" in selected_titles
    assert "4.2 热处理" in selected_titles
    assert "第一章 绪论" not in selected_titles
    assert "称取样品" in selected_text
    assert "升温至 1000 ℃" in selected_text
