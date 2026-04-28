"""Tests for MinerU fragmented figure detection and bbox stitching."""

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
    figure_id: str = "\u56fe3-17",
    bboxes: list[list[float]] | None = None,
    page_indices: list[int] | None = None,
) -> list[FigureInfo]:
    figures = []
    offset = 0
    for index, image_path in enumerate(image_paths, start=1):
        token = f"![]({image_path.as_posix()})"
        position = markdown.index(token, offset)
        offset = position + len(token)
        page_idx = page_indices[index - 1] if page_indices else 0 if bboxes else None
        figures.append(
            FigureInfo(
                paper_id="test",
                figure_id=figure_id,
                caption=caption,
                caption_source="standard_caption",
                image_path=str(image_path),
                position=position,
                subfigure_index=index,
                keep_for_archive=True,
                page_idx=page_idx,
                page_number=page_idx + 1 if page_idx is not None else None,
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
        caption = "\u56fe3-17 \u6240\u5236\u7ea4\u7ef4\u6469\u64e610000\u6b21\u540e\u7684\u635f\u4f24\u5f62\u8c8c(a)1#;(b)2#;(c)3#"
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        bboxes = [[100, 50 + i * 90, 700, 120 + i * 90] for i in range(5)]
        figures = _figures_from_markdown(markdown, paths, caption, bboxes=bboxes)

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")
        fragments = [figure for figure in result if figure.is_fragment]
        merged = [figure for figure in result if figure.is_merged_figure]

        assert len(fragments) == 5
        assert len({figure.fragment_group_id for figure in fragments}) == 1
        assert all(not figure.send_to_vision_model for figure in fragments)
        assert all(figure.exclude_reason == "replaced_by_bbox_stitched_figure" for figure in fragments)
        assert len(merged) == 1
        assert merged[0].caption == caption
        assert merged[0].image_origin == "stitched_from_bbox_fragments"
        assert merged[0].merge_mode == "bbox_grid_stitch"
        assert Path(merged[0].merged_image_path).exists()


def test_keep_normal_subfigures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"panel{i}.jpg", (400, 300), "white") for i in range(1, 4)]
        caption = "\u56fe6 SEM images of fibers at low magnification(a), high magnification(b), after treatment(c)."
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        figures = _figures_from_markdown(markdown, paths, caption, "\u56fe6")

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert not any(figure.is_fragment for figure in result)
        assert not any(figure.is_merged_figure for figure in result)
        assert [figure.subfigure_index for figure in result] == [1, 2, 3]


def test_group_without_bbox_is_not_merged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"frag{i}.jpg", (600, 80)) for i in range(1, 4)]
        caption = "\u56fe8 \u635f\u4f24\u5f62\u8c8c\u56fe"
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        figures = _figures_from_markdown(markdown, paths, caption, "\u56fe8")

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert not any(figure.is_fragment for figure in result)
        assert not any(figure.is_merged_figure for figure in result)
        assert all(figure.review_reason == "bbox_missing_for_fragment_group" for figure in result)


def test_cross_page_group_is_not_merged() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = [_make_image(root / f"frag{i}.jpg", (600, 80)) for i in range(1, 4)]
        caption = "\u56fe9 \u635f\u4f24\u5f62\u8c8c\u56fe"
        markdown = "\n".join(f"![]({path.as_posix()})" for path in paths) + "\n" + caption
        bboxes = [[100, 50 + i * 90, 700, 120 + i * 90] for i in range(3)]
        figures = _figures_from_markdown(markdown, paths, caption, "\u56fe9", bboxes=bboxes, page_indices=[0, 0, 1])

        result = detect_and_merge_fragmented_figures(figures, markdown, root / "outputs", "test")

        assert not any(figure.is_fragment for figure in result)
        assert not any(figure.is_merged_figure for figure in result)
        assert all(figure.review_reason == "fragments_not_on_same_page" for figure in result)


if __name__ == "__main__":
    test_merge_long_strip_fragments()
    test_keep_normal_subfigures()
    test_group_without_bbox_is_not_merged()
    test_cross_page_group_is_not_merged()
    print("figure fragment merger test passed")
