"""Tests for MinerU fragmented figure detection and merging."""

from pathlib import Path
import sys
import tempfile

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.figure_fragment_merger import detect_and_merge_fragmented_figures


def _make_image(path: Path, size: tuple[int, int], color: str = "black") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def _figures_from_markdown(
    markdown: str,
    image_paths: list[Path],
    caption: str,
    size_group_id: str = "图3-17",
    bboxes: list[list[float]] | None = None,
) -> list[FigureInfo]:
    figures = []
    offset = 0
    for index, image_path in enumerate(image_paths, start=1):
        token = f"![]({image_path.as_posix()})"
        position = markdown.index(token, offset)
        offset = position + len(token)
        figures.append(
            FigureInfo(
                paper_id="test",
                figure_id=size_group_id,
                caption=caption,
                caption_source="standard_caption",
                image_path=str(image_path),
                position=position,
                subfigure_index=index,
                keep_for_archive=True,
                page_idx=0 if bboxes else None,
                page_number=1 if bboxes else None,
                bbox=bboxes[index - 1] if bboxes else None,
                bbox_format="pixel" if bboxes else None,
                bbox_source="test" if bboxes else None,
            )
        )
    return figures


def test_merge_long_strip_fragments() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"frag{i}.jpg", (600, 80)) for i in range(1, 6)]
        caption = "图3-17 所制纤维摩擦10000次后的损伤形貌(a)1#；(b)2#；(c)3#"
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        bboxes = [[100, 50 + i * 90, 700, 120 + i * 90] for i in range(5)]
        figures = _figures_from_markdown(markdown, paths, caption, bboxes=bboxes)

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")
        fragments = [figure for figure in result if figure.is_fragment]
        merged = [figure for figure in result if figure.is_merged_figure]

        assert len(fragments) == 5
        assert len({figure.fragment_group_id for figure in fragments}) == 1
        assert all(not figure.send_to_vision_model for figure in fragments)
        assert len(merged) == 1
        assert merged[0].caption == caption
        assert merged[0].image_origin == "merged_from_fragments"
        assert Path(merged[0].merged_image_path).exists()


def test_keep_normal_subfigures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"panel{i}.jpg", (400, 300), "white") for i in range(1, 4)]
        caption = "图6 SEM images of fibers at low magnification(a), high magnification(b), after treatment(c)."
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        figures = _figures_from_markdown(markdown, paths, caption, "图6")

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert not any(figure.is_fragment for figure in result)
        assert not any(figure.is_merged_figure for figure in result)
        assert [figure.subfigure_index for figure in result] == [1, 2, 3]


def test_single_long_strip_goes_to_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = _make_image(root / "single_frag.jpg", (700, 90))
        caption = "图9 损伤形貌图"
        markdown = f"![]({path.as_posix()})\n{caption}"
        figures = _figures_from_markdown(markdown, [path], caption, "图9")

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert len(result) == 1
        assert not result[0].is_fragment
        assert not result[0].is_merged_figure
        assert result[0].review_reason == "possible_fragment_single_image"


def test_group_without_bbox_is_not_blindly_merged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"frag{i}.jpg", (600, 80)) for i in range(1, 4)]
        caption = "图8 损伤形貌图"
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        figures = _figures_from_markdown(markdown, paths, caption, "图8")

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert not any(figure.is_fragment for figure in result)
        assert not any(figure.is_merged_figure for figure in result)
        assert all(figure.review_reason == "bbox_missing_for_fragment_group" for figure in result)


if __name__ == "__main__":
    test_merge_long_strip_fragments()
    test_keep_normal_subfigures()
    test_single_long_strip_goes_to_review()
    test_group_without_bbox_is_not_blindly_merged()
    print("figure fragment merger test passed")
