"""Mechanical property plot taxonomy test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_mechanical_property_plot() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图3-18",
        caption="图3-18 所制纤维典型试样的强度及模量离散",
        reference_sentences=["随后，对所制纤维进行了耐温性测试。"],
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class in {"mechanical_property_plot", "mechanical_curve"}
    assert figure.figure_class != "microscopy_image"
    assert figure.send_to_vision_model is True

    xrd = FigureInfo(
        paper_id="demo",
        figure_id="图3-8",
        caption="图3-8 凝胶纤维在不同陶瓷化阶段的XRD",
        reference_sentences=["强度和模量用于后续性能分析。"],
    )
    FigureFilter().apply_one(xrd)
    assert xrd.figure_class == "xrd_pattern"
    assert xrd.figure_class != "mechanical_property_plot"


if __name__ == "__main__":
    test_mechanical_property_plot()
    print("mechanical property plot test passed")
