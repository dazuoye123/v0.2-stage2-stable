"""EDS mapping taxonomy test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_eds_mapping_taxonomy() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图3-22",
        caption="图3-22 所制纤维试样EDS-mapping",
    )
    FigureFilter().apply_one(figure)
    assert figure.figure_class == "elemental_mapping"
    assert figure.send_to_vision_model is True


if __name__ == "__main__":
    test_eds_mapping_taxonomy()
    print("EDS mapping taxonomy test passed")
