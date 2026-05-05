from __future__ import annotations

from alumina_sol_extractor.stage3.sections import parse_markdown_sections, score_sections


def test_section_scorer_prefers_experimental_and_spectroscopy_sections() -> None:
    markdown_text = """# 标题

## 绪论
这里只是研究背景综述。

## 2.2 实验部分
铝溶胶制备、pH 调节、反应温度、搅拌速率和老化条件。

## 2.3 结果与讨论
27Al NMR、Ferron、FTIR、XRD、Zeta 电位、可纺性分析。

## 参考文献
[1] 参考文献
"""

    scored = score_sections(
        parse_markdown_sections(markdown_text),
        custom_keywords=["Al13", "NMR", "Ferron", "FTIR", "XRD", "pH", "可纺性"],
    )

    experimental = next(item for item in scored if item["title"] == "2.2 实验部分")
    results = next(item for item in scored if item["title"] == "2.3 结果与讨论")
    references = next(item for item in scored if item["title"] == "参考文献")

    assert experimental["section_score"] > 0
    assert "experimental_methods" in experimental["section_types"]
    assert results["section_score"] > experimental["section_score"]
    assert "spectroscopy_results" in results["section_types"]
    assert references["section_score"] < 0
    assert "references" in references["section_types"]
