"""False candidate fragment skip test."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import is_false_candidate  # noqa: E402


def test_false_candidate_skips_fragments() -> None:
    figure = FigureInfo(
        paper_id="demo",
        figure_id="图3-17",
        caption="图3-17 SEM 损伤形貌",
        is_fragment=True,
        exclude_reason="replaced_by_bbox_stitched_figure",
        send_to_vision_model=False,
    )
    assert is_false_candidate(figure) is False


if __name__ == "__main__":
    test_false_candidate_skips_fragments()
    print("false candidate skips fragments test passed")
