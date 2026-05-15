from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.stage3.document_trim import generate_cleaned_body_markdown, trim_markdown_body


def test_trim_markdown_body_removes_toc_abstract_and_references_but_keeps_methods() -> None:
    markdown = """# 目录
2.2.2 初始铝溶胶的制备 ........ 20
1.5 参考文献 ........ 12

# 摘要
摘要正文
# 2.2 实验部分
实验材料及仪器。
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水。
# 参考文献
[1] demo
"""
    result = trim_markdown_body(markdown)
    assert "# 目录" not in result.cleaned_text
    assert "# 摘要" not in result.cleaned_text
    assert "[1] demo" not in result.cleaned_text
    assert "2.2.2 初始铝溶胶的制备" in result.cleaned_text
    assert "称取一定量九水合硝酸铝和铝粉" in result.cleaned_text


def test_trim_markdown_body_does_not_cut_document_at_chapter_level_references() -> None:
    markdown = """# 1.4 文献综述
这里是第一章综述内容。
# 1.5 参考文献
[1] chapter one refs
# 第二章 实验
# 2.2 实验部分
# 2.2.2 初始铝溶胶的制备
称取九水合硝酸铝和铝粉，加入去离子水。
# 参考文献
[2] global refs
"""
    result = trim_markdown_body(markdown)
    assert "# 第二章 实验" in result.cleaned_text
    assert "2.2.2 初始铝溶胶的制备" in result.cleaned_text
    assert "[2] global refs" not in result.cleaned_text


def test_generate_cleaned_body_markdown_writes_report_and_body(tmp_path: Path) -> None:
    markdown_path = tmp_path / "paper.md"
    output_dir = tmp_path / "paper_output"
    markdown_path.write_text(
        "# 2.2.2 初始铝溶胶的制备\n称取九水合硝酸铝和铝粉，加入去离子水。\n# 参考文献\n[1] demo",
        encoding="utf-8",
    )

    result = generate_cleaned_body_markdown(markdown_path=markdown_path, paper_output_dir=output_dir)

    cleaned_body_path = output_dir / "stage3_text" / "cleaned_body.md"
    report_path = output_dir / "stage3_text" / "markdown_trim_report.json"
    assert cleaned_body_path.exists()
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["input_markdown_path"] == str(markdown_path)
    assert report["output_cleaned_body_path"] == str(cleaned_body_path)
    assert "初始铝溶胶的制备" in result.cleaned_text
