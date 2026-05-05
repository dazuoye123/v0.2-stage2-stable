from __future__ import annotations

from alumina_sol_extractor.stage3.sections import parse_markdown_sections


def test_parse_markdown_sections_handles_chinese_chapter_and_subsections() -> None:
    markdown_text = """# 标题

## 第二章 高 Al13 团簇含量铝溶胶的可控制备与表征
### 2.2 实验部分
图2.12 给出 Ferron 曲线。
### 2.3.1 结果与讨论
表2.1 记录旋蒸条件。
## 参考文献
[1] Example reference
"""

    sections = parse_markdown_sections(markdown_text)

    titles = [item["title"] for item in sections]
    assert "第二章 高 Al13 团簇含量铝溶胶的可控制备与表征" in titles
    assert "2.2 实验部分" in titles
    assert "2.3.1 结果与讨论" in titles
    assert "参考文献" in titles

    chapter = next(item for item in sections if item["title"] == "第二章 高 Al13 团簇含量铝溶胶的可控制备与表征")
    assert "图2.12" in chapter["figure_mentions"]
    assert "表2.1" in chapter["table_mentions"]
