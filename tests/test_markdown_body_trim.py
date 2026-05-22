from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.markdown_processing.body_trim import (
    generate_cleaned_body_markdown as generate_cleaned_body_markdown_new,
)
from alumina_sol_extractor.markdown_processing.pipeline import ensure_cleaned_body_markdown
from alumina_sol_extractor.stage3.document_trim import generate_cleaned_body_markdown, trim_markdown_body


def test_trim_markdown_body_removes_cover_toc_and_references_but_keeps_methods() -> None:
    markdown = """![](cover.jpg)
# 山东大学
# SHANDONG UNIVERSITY
# Thesis for Master Degree
作者姓名 牛延强
培养单位 化学与化工学院

# 目录
2.2.2 初始铝溶胶的制备 ........ 20
1.5 参考文献 ........ 12

# 摘要
摘要正文

# 2.2 实验部分
实验材料及仪器
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水。
# 参考文献
[1] demo
"""
    result = trim_markdown_body(markdown)

    lines = [line for line in result.cleaned_text.splitlines() if line.strip()]
    assert lines[0] == "# 2.2 实验部分"
    assert "# 山东大学" not in result.cleaned_text
    assert "# SHANDONG UNIVERSITY" not in result.cleaned_text
    assert "# Thesis for Master Degree" not in result.cleaned_text
    assert "作者姓名 牛延强" not in result.cleaned_text
    assert "培养单位 化学与化工学院" not in result.cleaned_text
    assert "2.2.2 初始铝溶胶的制备 ........ 20" not in result.cleaned_text
    assert "# 目录" not in result.cleaned_text
    assert "# 摘要" not in result.cleaned_text
    assert "[1] demo" not in result.cleaned_text
    assert "# 2.2.2 初始铝溶胶的制备" in result.cleaned_text
    assert "称取一定量九水合硝酸铝和铝粉，加入去离子水。" in result.cleaned_text


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
    assert "# 2.2.2 初始铝溶胶的制备" in result.cleaned_text
    assert "[2] global refs" not in result.cleaned_text


def test_generate_cleaned_body_markdown_writes_report_and_body(tmp_path: Path) -> None:
    markdown_path = tmp_path / "paper.md"
    output_dir = tmp_path / "paper_output"
    markdown_path.write_text(
        "# 山东大学\n# SHANDONG UNIVERSITY\n# 2.2.2 初始铝溶胶的制备\n称取九水合硝酸铝和铝粉，加入去离子水。\n# 参考文献\n[1] demo",
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
    assert report["cleaned_body_char_count"] == len(result.cleaned_text)
    assert result.cleaned_text.startswith("# 2.2.2 初始铝溶胶的制备")
    assert "山东大学" not in result.cleaned_text


def test_trim_markdown_body_removes_numbered_toc_residue_but_keeps_real_heading() -> None:
    markdown = """# 第一章 绪论
2.2.2 初始铝溶胶的制备 20
3.2.2 铝溶胶的分类比较 45

# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水。
"""
    result = trim_markdown_body(markdown)
    assert "2.2.2 初始铝溶胶的制备 20" not in result.cleaned_text
    assert "3.2.2 铝溶胶的分类比较 45" not in result.cleaned_text
    assert "# 2.2.2 初始铝溶胶的制备" in result.cleaned_text


def test_new_body_trim_module_writes_cleaned_body_without_overwriting_source_markdown(tmp_path: Path) -> None:
    markdown_path = tmp_path / "data" / "markdown" / "paper.md"
    output_dir = tmp_path / "data" / "outputs" / "paper"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    original_text = (
        "# 山东大学\n"
        "# 目录\n"
        "2.2.2 初始铝溶胶的制备 ........ 20\n"
        "# 2.2.2 初始铝溶胶的制备\n"
        "称取一定量九水合硝酸铝和铝粉，加入去离子水。\n"
        "# 参考文献\n"
        "[1] demo\n"
    )
    markdown_path.write_text(original_text, encoding="utf-8")

    result = generate_cleaned_body_markdown_new(markdown_path=markdown_path, paper_output_dir=output_dir)

    cleaned_body_path = output_dir / "stage3_text" / "cleaned_body.md"
    assert cleaned_body_path.exists()
    assert cleaned_body_path == output_dir / "stage3_text" / "cleaned_body.md"
    assert "# 2.2.2 初始铝溶胶的制备" in result.cleaned_text
    assert markdown_path.read_text(encoding="utf-8") == original_text


def test_stage3_document_trim_old_import_remains_compatible() -> None:
    assert generate_cleaned_body_markdown is generate_cleaned_body_markdown_new


def test_ensure_cleaned_body_markdown_preserves_output_location_and_supports_force(tmp_path: Path) -> None:
    markdown_path = tmp_path / "data" / "markdown" / "paper.md"
    output_dir = tmp_path / "data" / "outputs" / "paper"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "# 山东大学\n# 2.2 实验部分\n# 2.2.2 初始铝溶胶的制备\n称取九水合硝酸铝。\n# 参考文献\n[1] demo",
        encoding="utf-8",
    )

    cleaned_body_path, report_path = ensure_cleaned_body_markdown(markdown_path, output_dir)
    assert cleaned_body_path == output_dir / "stage3_text" / "cleaned_body.md"
    assert report_path == output_dir / "stage3_text" / "markdown_trim_report.json"
    assert cleaned_body_path.exists()
    assert report_path.exists()

    cleaned_body_path.write_text("stale", encoding="utf-8")
    cleaned_body_path, report_path = ensure_cleaned_body_markdown(markdown_path, output_dir, force=True)
    assert cleaned_body_path.read_text(encoding="utf-8").startswith("# 2.2 实验部分")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["output_cleaned_body_path"] == str(cleaned_body_path)


def test_trim_markdown_body_removes_image_lines_but_keeps_figure_captions() -> None:
    markdown = """# 2.2 实验部分
![](figures_all/a.png)
<img src="figures_all/b.png" alt="sample" />
data:image/png;base64,AAAA
figures_for_vision/c.jpg
Fig. 2 SEM images of alumina fibers
图3-2 乙基纤维素分子式
"""
    result = trim_markdown_body(markdown)

    assert "![](" not in result.cleaned_text
    assert "<img" not in result.cleaned_text.lower()
    assert "data:image" not in result.cleaned_text.lower()
    assert "figures_for_vision/c.jpg" not in result.cleaned_text
    assert "Fig. 2 SEM images of alumina fibers" in result.cleaned_text
    assert "图3-2 乙基纤维素分子式" in result.cleaned_text
    assert result.report["removed_image_markdown_line_count"] >= 2
    assert result.report["removed_html_img_line_count"] >= 1
    assert result.report["removed_image_path_line_count"] >= 1
