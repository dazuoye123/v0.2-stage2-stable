"""Review candidate rules test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter, is_review_candidate  # noqa: E402


def test_other_class_goes_to_review() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图9-9",
        caption="图9-9 未能识别的图片",
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class == "other"
    assert figure.review_reason == "figure_class_other"
    assert is_review_candidate(figure)


if __name__ == "__main__":
    test_other_class_goes_to_review()
    print("review candidates test passed")
