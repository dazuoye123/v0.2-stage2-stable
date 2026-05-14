"""Smoke tests for grouped MinerU figure caption extraction."""

from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PIL import Image  # noqa: E402

from alumina_sol_extractor.utils.figure_utils import find_figures_in_markdown_any  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_grouped_caption_extraction() -> None:
    paper_id = "_figure_caption_test"
    work_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
    markdown_dir = work_dir / "markdown"
    images_dir = markdown_dir / "images"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for name, color in {"a.png": (255, 0, 0), "b.png": (0, 255, 0), "c.png": (0, 0, 255)}.items():
        Image.new("RGB", (16, 16), color).save(images_dir / name)

    markdown_path = markdown_dir / "paper.md"
    markdown = """![](images/a.png)
![](images/b.png)
![](images/c.png)
Fig.6 SEM images of gamma-Al2O3 fibers at low magnification(A), alpha-Al2O3 fibers at high magnification(B) and alpha-Al2O3 fibers after heat treatment(C).

\u7531\u56fe6(A)\u53ef\u89c1\uff0c\u5e72\u51dd\u80f6\u7ea4\u7ef4\u5f62\u6210\u8fde\u7eed\u7ed3\u6784\u3002"""
    markdown_path.write_text(markdown, encoding="utf-8")

    figures = find_figures_in_markdown_any(markdown, markdown_path, PROJECT_ROOT, paper_id)
    figures = FigureFilter().apply(figures)

    assert len(figures) == 3
    assert [figure.figure_id for figure in figures] == ["Fig.6", "Fig.6", "Fig.6"]
    assert [figure.subfigure_index for figure in figures] == [1, 2, 3]
    assert [figure.subfigure_label for figure in figures] == ["A", "B", "C"]
    assert all(figure.caption and "Fig.6 SEM images" in figure.caption for figure in figures)
    assert all(figure.caption_source == "standard_caption" for figure in figures)
    assert all(figure.figure_class == "microscopy_image" for figure in figures)

    shutil.rmtree(work_dir)


def test_decimal_figure_id_and_group_labels() -> None:
    paper_id = "_figure_decimal_test"
    work_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
    markdown_dir = work_dir / "markdown"
    images_dir = markdown_dir / "images"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for name, color in {
        "fill.png": (255, 255, 255),
        "spin.png": (220, 220, 220),
        "recover.png": (180, 180, 180),
        "collect.png": (120, 120, 120),
    }.items():
        Image.new("RGB", (20, 20), color).save(images_dir / name)

    markdown_path = markdown_dir / "paper.md"
    markdown = """# \u7b2c\u4e00\u7ae0 \u7eea\u8bba
![Fill](images/fill.png)
![Spin](images/spin.png)
![Recover](images/recover.png)
![Collect](images/collect.png)
\u56fe1.3 \u8d85\u6ee4\u79bb\u5fc3\u7ba1\u6784\u9020\u53ca\u4f7f\u7528\u6b65\u9aa4\u793a\u610f\u56fe
\u5982\u56fe1.3\u6240\u793a\uff0c\u88c5\u7f6e\u5305\u62ec\u56db\u4e2a\u6b65\u9aa4\u3002\u56fe1.30\u5c55\u793a\u7684\u662f\u53e6\u4e00\u4e2a\u7f16\u53f7\u3002"""
    markdown_path.write_text(markdown, encoding="utf-8")

    figures = find_figures_in_markdown_any(markdown, markdown_path, PROJECT_ROOT, paper_id)
    figures = FigureFilter().apply(figures)

    assert len(figures) == 4
    assert [figure.figure_id for figure in figures] == ["\u56fe1.3"] * 4
    assert [figure.subfigure_label for figure in figures] == ["Fill", "Spin", "Recover", "Collect"]
    assert all(figure.section_title == "\u7b2c\u4e00\u7ae0 \u7eea\u8bba" for figure in figures)
    assert all(figure.figure_class == "schematic_or_flow" for figure in figures)
    assert not any(figure.send_to_vision_model for figure in figures)

    shutil.rmtree(work_dir)


def test_multi_caption_assignment_to_consecutive_images() -> None:
    paper_id = "_figure_multi_caption_test"
    work_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
    markdown_dir = work_dir / "markdown"
    images_dir = markdown_dir / "images"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for name, color in {
        "a.png": (255, 240, 240),
        "b.png": (240, 255, 240),
        "c.png": (240, 240, 255),
    }.items():
        Image.new("RGB", (24, 24), color).save(images_dir / name)

    markdown_path = markdown_dir / "paper.md"
    markdown = """![](images/a.png)
![](images/b.png)
![](images/c.png)
图2-4新制莫来石晶种分散液(a)及其放置3个月后(b)的光学照片 图2-5 新制莫来石晶种分散液的TEM

如图2-4所示，晶种分散液放置后仍保持分散。
图2-5显示晶种呈现典型TEM形貌。"""
    markdown_path.write_text(markdown, encoding="utf-8")

    figures = find_figures_in_markdown_any(markdown, markdown_path, PROJECT_ROOT, paper_id)
    figures = FigureFilter().apply(figures)

    assert len(figures) == 3
    assert [figure.figure_id for figure in figures] == ["图2-4", "图2-4", "图2-5"]
    assert [figure.subfigure_label for figure in figures] == ["a", "b", None]
    assert figures[0].caption == "图2-4新制莫来石晶种分散液(a)及其放置3个月后(b)的光学照片"
    assert figures[1].caption == figures[0].caption
    assert figures[2].caption == "图2-5 新制莫来石晶种分散液的TEM"
    assert not any("图2-5 新制莫来石晶种分散液的TEM" in " ".join(figure.reference_sentences) for figure in figures[:2])
    assert figures[2].figure_class == "microscopy_image"
    assert "图2-5 新制莫来石晶种分散液的TEM" not in (figures[0].description_text or "")

    shutil.rmtree(work_dir)


if __name__ == "__main__":
    test_grouped_caption_extraction()
    test_decimal_figure_id_and_group_labels()
    test_multi_caption_assignment_to_consecutive_images()
    print("figure caption extraction test passed")
