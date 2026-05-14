"""Tests for bbox-based image stitching."""

from pathlib import Path
import sys
import tempfile

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.bbox_fragment_stitcher import stitch_fragments_by_bbox


def _colored_fragment(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (20, 20), color).save(path)
    return path


def _pixel_close(pixel: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
    return all(abs(pixel[index] - expected[index]) <= 6 for index in range(3))


def test_grid_bbox_stitch_with_shuffled_markdown_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
            (120, 120, 120),
            (0, 0, 0),
        ]
        boxes = []
        expected_positions = []
        for row in range(4):
            for col in range(2):
                x0 = col * 40
                y0 = row * 30
                boxes.append([x0, y0, x0 + 20, y0 + 20])
                expected_positions.append((x0 + 10 + 5, y0 + 10 + 5))
        order = [4, 0, 7, 1, 5, 2, 6, 3]
        figures = []
        for idx in order:
            path = _colored_fragment(root / f"frag_{idx}.jpg", colors[idx])
            figures.append(
                FigureInfo(
                    paper_id="p",
                    figure_id="\u56fe1",
                    image_path=str(path),
                    page_idx=0,
                    bbox=boxes[idx],
                    bbox_format="pixel",
                )
            )

        output = stitch_fragments_by_bbox(figures, root / "stitched.jpg", margin=5)

        with Image.open(output) as image:
            assert image.size == (70, 120)
            for idx, position in enumerate(expected_positions):
                assert _pixel_close(image.getpixel(position), colors[idx])


def test_single_column_bbox_stitch_uses_bbox_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        bboxes = [[0, 40, 20, 60], [0, 0, 20, 20], [0, 80, 20, 100]]
        figures = []
        for idx, bbox in enumerate(bboxes):
            path = _colored_fragment(root / f"frag_{idx}.jpg", colors[idx])
            figures.append(
                FigureInfo(
                    paper_id="p",
                    figure_id="\u56fe2",
                    image_path=str(path),
                    page_idx=0,
                    bbox=bbox,
                    bbox_format="pixel",
                )
            )

        output = stitch_fragments_by_bbox(figures, root / "single_col.jpg", margin=5)

        with Image.open(output) as image:
            assert _pixel_close(image.getpixel((15, 15)), colors[1])
            assert _pixel_close(image.getpixel((15, 55)), colors[0])
            assert _pixel_close(image.getpixel((15, 95)), colors[2])


if __name__ == "__main__":
    test_grid_bbox_stitch_with_shuffled_markdown_order()
    test_single_column_bbox_stitch_uses_bbox_order()
    print("bbox fragment stitcher test passed")
