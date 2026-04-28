"""Caption split test for multiple figure IDs."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.utils.figure_utils import _split_caption_details  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_multiple_figure_ids_caption_split() -> None:
    text = "图2-18纺丝环境参数的影响 图2-19采用400孔喷丝板进行纺丝的过程"
    caption, following, reason = _split_caption_details(text, "图2-18")
    assert caption == "图2-18纺丝环境参数的影响"
    assert following and "图2-19采用400孔喷丝板" in following[0]
    assert reason == "multiple_figure_ids_in_caption"

    figure = FigureInfo(
        paper_id="demo",
        figure_id="图2-18",
        caption=caption,
        caption_cleaned=True,
        caption_truncation_reason=reason,
    )
    FigureFilter().apply_one(figure)
    assert figure.review_reason == "multiple_figure_ids_in_caption"

    panel_text = "图3-17所制纤维摩擦10000次后的损伤形貌(a)1#；(b)2#；(c)3#"
    caption, following, reason = _split_caption_details(panel_text, "图3-17")
    assert caption == panel_text
    assert following == []
    assert reason is None


if __name__ == "__main__":
    test_multiple_figure_ids_caption_split()
    print("multiple figure ids caption split test passed")
