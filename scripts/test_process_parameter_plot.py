"""Process parameter plot routing test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_process_parameter_plot() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图2-18",
        caption="图2-18 纺丝环境参数的影响",
        reference_sentences=["如图2-18所示，在上述环境参数下，凝胶纤维的收丝重量最大。"],
        caption_source="standard_caption",
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class == "process_parameter_plot"
    assert figure.send_to_vision_model


def test_generic_chart_fallback() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图9-9",
        caption="图9-9 试样数据对比图",
        caption_source="standard_caption",
        resnet_raw_class="Graph plots",
        clip_decision="positive",
        clip_label="a scientific graph or plot",
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class == "generic_chart_or_plot"
    assert figure.send_to_vision_model


if __name__ == "__main__":
    test_process_parameter_plot()
    test_generic_chart_fallback()
    print("process parameter plot test passed")
