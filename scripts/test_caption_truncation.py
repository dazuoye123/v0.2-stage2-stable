"""Caption truncation tests."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.utils.figure_utils import (  # noqa: E402
    split_caption_and_following_text,
    split_caption_and_references,
)


def test_caption_body_split() -> None:
    text = "\u56fe3.2\u9ad8 pH \u94dd\u6eb6\u80f6\u8c03\u8282\u524d\u540e\u6838\u78c1\u8c31\u56fe \u7531\u56fe3.2\u53ef\u77e5\uff0c\u5904\u7406\u540e\u8c31\u5cf0\u53d1\u751f\u53d8\u5316\u3002"
    caption, refs = split_caption_and_references(text)
    assert caption == "\u56fe3.2\u9ad8 pH \u94dd\u6eb6\u80f6\u8c03\u8282\u524d\u540e\u6838\u78c1\u8c31\u56fe"
    assert refs and "\u7531\u56fe3.2\u53ef\u77e5" in refs[0]


def test_caption_body_split_with_subfigure_label() -> None:
    text = "\u56fe2.6\u4e0d\u540c\u6405\u62cc\u901f\u5ea6\u5408\u6210\u7684\u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe(a)\u548c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u56fe(b) \u7531\u56fe2.6(a)\u53ef\u89c1\uff0c\u6838\u78c1\u7ed3\u679c\u5dee\u522b\u4e0d\u5927\u3002"
    caption, refs = split_caption_and_references(text)
    assert caption == "\u56fe2.6\u4e0d\u540c\u6405\u62cc\u901f\u5ea6\u5408\u6210\u7684\u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe(a)\u548c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u56fe(b)"
    assert refs and "\u7531\u56fe2.6(a)\u53ef\u89c1" in refs[0]


def test_caption_does_not_absorb_table_reference() -> None:
    text = "\u56fe3.8Al-Ferron\u6bd4\u8272\u6807\u51c6\u66f2\u7ebf\u4e0e\u6807\u51c6\u65b9\u7a0b \u94dd\u6eb6\u80f6\u6d4b\u5b9a\u6570\u636e\u89c1\u88683.3\u3002"
    caption, refs = split_caption_and_references(text)
    assert caption == "\u56fe3.8Al-Ferron\u6bd4\u8272\u6807\u51c6\u66f2\u7ebf\u4e0e\u6807\u51c6\u65b9\u7a0b \u94dd\u6eb6\u80f6\u6d4b\u5b9a"
    assert refs and "\u6570\u636e\u89c1\u88683.3" in refs[0]


def test_caption_split_when_figure_id_repeats() -> None:
    text = "\u56fe2.19 \u94dd\u6eb6\u80f6\u7684XRD\u56fe \u56fe2.19\u4e3a\u94dd\u6eb6\u80f6\u7684XRD\u56fe\uff0c\u5982\u56fe\u6240\u793a\u3002"
    caption, refs = split_caption_and_references(text)
    assert caption == "\u56fe2.19 \u94dd\u6eb6\u80f6\u7684XRD\u56fe"
    assert refs and "\u56fe2.19\u4e3a" in refs[0]


def test_space_body_start_split() -> None:
    text = "\u56fe3.6 ^27AlNMR \u7684\u5316\u5b66\u4f4d\u79fb\u8303\u56f4 \u94dd\u6eb6\u80f6\u4e2d\u542b\u6709\u591a\u79cd\u6c34\u5408\u94dd\u56e2\u7c07\u5f62\u6001\uff0c\u6839\u636e\u6838\u78c1\u5171\u632f\u7684\u539f\u7406\u53ef\u77e5\u3002"
    caption, refs = split_caption_and_following_text(text, "\u56fe3.6")
    assert caption == "\u56fe3.6 ^27AlNMR \u7684\u5316\u5b66\u4f4d\u79fb\u8303\u56f4"
    assert refs and "\u94dd\u6eb6\u80f6\u4e2d\u542b\u6709\u591a\u79cd\u6c34\u5408\u94dd\u56e2\u7c07\u5f62\u6001" in refs[0]


def test_normal_caption_not_split() -> None:
    text = "\u56fe2.6 \u4e0d\u540c\u6405\u62cc\u901f\u5ea6\u5408\u6210\u7684\u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe(a)\u548c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u56fe(b)"
    caption, refs = split_caption_and_following_text(text, "\u56fe2.6")
    assert caption == text
    assert refs == []


def test_temperature_caption_split_at_explanation() -> None:
    text = "\u56fe2.5\u4e0d\u540c\u8d77\u59cb\u53cd\u5e94\u6e29\u5ea6\u7684\u70e7\u74f6\u5185\u6eb6\u6db2\u6e29\u5ea6\u53d8\u5316\u56fe\uff1a(a) 50\u00b0C \uff0c(b) 55\u00b0C \u7ed3\u5408\u4e4b\u524d\u5173\u4e8e\u53cd\u5e94\u6e29\u5ea6\u7684\u63a2\u7a76\uff0c\u8d77\u59cb\u53cd\u5e94\u6e29\u5ea6\u4e3a50\u00b0C\u65f6\u66f4\u6709\u5229\u3002"
    caption, refs = split_caption_and_following_text(text, "\u56fe2.5")
    assert caption == "\u56fe2.5\u4e0d\u540c\u8d77\u59cb\u53cd\u5e94\u6e29\u5ea6\u7684\u70e7\u74f6\u5185\u6eb6\u6db2\u6e29\u5ea6\u53d8\u5316\u56fe\uff1a(a) 50\u00b0C \uff0c(b) 55\u00b0C"
    assert refs and "\u7ed3\u5408\u4e4b\u524d\u5173\u4e8e\u53cd\u5e94\u6e29\u5ea6\u7684\u63a2\u7a76" in refs[0]


def test_english_caption_split() -> None:
    text = "Fig. 3 XRD patterns of alumina fibers after calcination. The results show that phase conversion occurred."
    caption, refs = split_caption_and_following_text(text, "Fig.3")
    assert caption == "Fig. 3 XRD patterns of alumina fibers after calcination."
    assert refs and "The results show that" in refs[0]


if __name__ == "__main__":
    test_caption_body_split()
    test_caption_body_split_with_subfigure_label()
    test_caption_does_not_absorb_table_reference()
    test_caption_split_when_figure_id_repeats()
    test_space_body_start_split()
    test_normal_caption_not_split()
    test_temperature_caption_split_at_explanation()
    test_english_caption_split()
    print("caption truncation test passed")
