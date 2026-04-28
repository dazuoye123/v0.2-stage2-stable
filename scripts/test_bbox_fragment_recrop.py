"""Tests for bbox-driven fragment layout decisions."""

from pathlib import Path
import sys
import tempfile

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.figure_fragment_merger import detect_and_merge_fragmented_figures
from alumina_sol_extractor.vision.pdf_figure_recropper import infer_fragment_layout_from_bboxes


def _figure(index: int, bbox: list[float], caption: str = "图3-17 损伤形貌图") -> FigureInfo:
    return FigureInfo(
        paper_id="p",
        figure_id="图3-17",
        caption=caption,
        image_path=f"image_{index}.jpg",
        page_idx=0,
        bbox=bbox,
        bbox_format="pixel",
        position=index * 100,
    )


def test_grid_layout() -> None:
    fragments = []
    for row in range(4):
        for col in range(2):
            x0 = 100 + col * 260
            y0 = 100 + row * 120
            fragments.append(_figure(len(fragments), [x0, y0, x0 + 220, y0 + 90]))

    assert infer_fragment_layout_from_bboxes(fragments) == "grid"


def test_vertical_layout() -> None:
    fragments = [_figure(i, [100, 100 + i * 110, 520, 180 + i * 110]) for i in range(4)]

    assert infer_fragment_layout_from_bboxes(fragments) == "vertical"


def test_grid_without_pdf_is_not_vertical_merged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        caption = "图3-17 损伤形貌图"
        paths = []
        markdown_parts = []
        figures = []
        for row in range(4):
            for col in range(2):
                index = row * 2 + col
                path = root / f"grid_{index}.jpg"
                Image.new("RGB", (420, 90), "black").save(path)
                paths.append(path)
                markdown_parts.append(f"![]({path.as_posix()})")
        markdown = "\n".join(markdown_parts) + "\n" + caption

        offset = 0
        for row in range(4):
            for col in range(2):
                index = row * 2 + col
                path = paths[index]
                token = f"![]({path.as_posix()})"
                position = markdown.index(token, offset)
                offset = position + len(token)
                x0 = 100 + col * 260
                y0 = 100 + row * 120
                figures.append(
                    FigureInfo(
                        paper_id="p",
                        figure_id="图3-17",
                        caption=caption,
                        image_path=str(path),
                        page_idx=0,
                        bbox=[x0, y0, x0 + 220, y0 + 90],
                        bbox_format="pixel",
                        position=position,
                    )
                )

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "p", pdf_path=None)

        assert not any(figure.is_merged_figure for figure in result)
        assert not any(figure.is_fragment for figure in result)
        assert all(figure.review_reason == "bbox_recrop_pdf_missing" for figure in result)


if __name__ == "__main__":
    test_grid_layout()
    test_vertical_layout()
    test_grid_without_pdf_is_not_vertical_merged()
    print("bbox fragment recrop test passed")
