"""Caption body truncation test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.utils.figure_utils import split_caption_and_following_text  # noqa: E402


def test_caption_body_truncation() -> None:
    text = "图3-16所制纤维往复线性摩擦测试照片 测试发现，试样1没有发生断裂。"
    caption, refs = split_caption_and_following_text(text, "图3-16")
    assert caption == "图3-16所制纤维往复线性摩擦测试照片"
    assert refs and "测试发现" in refs[0]

    text = "图3-17所制纤维摩擦10000次后的损伤形貌(a)1#；(b)2#；(c)3# 从动摩擦系数测试结果来看，所制氧化铝连续纤维摩擦系数趋于稳定。"
    caption, refs = split_caption_and_following_text(text, "图3-17")
    assert caption == "图3-17所制纤维摩擦10000次后的损伤形貌(a)1#；(b)2#；(c)3#"
    assert refs and "从动摩擦系数测试结果来看" in refs[0]


if __name__ == "__main__":
    test_caption_body_truncation()
    print("caption body truncation test passed")
