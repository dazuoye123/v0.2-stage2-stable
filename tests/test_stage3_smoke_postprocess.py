from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.dspy_modules.runner import (
    _detect_mojibake,
    _postprocess_paper_basic_info,
)


def test_paper_basic_info_falls_back_to_title_and_infers_process_route(tmp_path: Path) -> None:
    markdown_text = """# 多晶型氧化铝连续纤维的制备及性能
张三，李四
摘要
采用溶胶-凝胶结合干法纺丝工艺制备氧化铝纤维。
"""
    source_file = tmp_path / "多晶型氧化铝连续纤维的制备及性能_2024.md"
    payload = _postprocess_paper_basic_info(
        payload={
            "abstract_summary": "采用溶胶-凝胶工艺制备氧化铝纤维。",
            "keywords": ["氧化铝", "纺丝"],
        },
        paper_text=markdown_text,
        source_file=source_file,
    )
    assert payload["title"] == "多晶型氧化铝连续纤维的制备及性能"
    assert payload["authors"] == ["张三", "李四"]
    assert payload["year"] == 2024
    assert payload["material_system"] == "alumina-based ceramic fiber"
    assert payload["process_route"] == "sol-gel dry spinning"


def test_paper_basic_info_falls_back_to_filename_when_markdown_starts_with_abstract(tmp_path: Path) -> None:
    markdown_text = """# 摘要
这是一段很长很长的摘要正文，用来模拟 MinerU 没有把论文标题提取出来的情况。
# 1. 实验部分
"""
    source_file = tmp_path / "example_2024.md"
    payload = _postprocess_paper_basic_info(
        payload={"keywords": ["氧化铝", "纺丝"]},
        paper_text=markdown_text,
        source_file=source_file,
    )
    assert payload["title"] == "example_2024"
    assert payload["authors"] == []


def test_detect_mojibake_flags_garbled_text() -> None:
    assert _detect_mojibake("\ufffd\ufffd\ufffd")
    assert not _detect_mojibake("图2-17 氧化铝连续纤维的TEM图")
