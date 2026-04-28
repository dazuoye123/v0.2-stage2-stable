"""Schematic taxonomy test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_schematic_taxonomy() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图2-1",
        caption="图2-1 氧化铝凝胶连续纤维的形成过程",
    )
    FigureFilter(include_schematics_for_vision=False).apply_one(figure)
    assert figure.figure_class == "schematic_or_flow"
    assert figure.maybe_useful is True
    assert figure.send_to_vision_model is False

    mechanism = FigureInfo(
        paper_id="demo",
        figure_id="图1-2",
        caption="图1-2 不同结构物相的 SiO2 的作用机理",
    )
    FigureFilter(include_schematics_for_vision=False).apply_one(mechanism)
    assert mechanism.figure_class == "schematic_or_flow"
    assert mechanism.maybe_useful is True


if __name__ == "__main__":
    test_schematic_taxonomy()
    print("schematic taxonomy test passed")
