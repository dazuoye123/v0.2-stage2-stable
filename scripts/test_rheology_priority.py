"""Rheology priority test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_rheology_priority() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图2-10",
        caption="图2-10 粘度为400Pa·s的可纺性溶胶的流变性特征",
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class == "rheology_curve"
    assert figure.figure_class != "photo_image"


if __name__ == "__main__":
    test_rheology_priority()
    print("rheology priority test passed")
