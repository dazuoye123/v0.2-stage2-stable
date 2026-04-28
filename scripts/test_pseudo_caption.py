"""Pseudo-caption tests."""

from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PIL import Image  # noqa: E402

from alumina_sol_extractor.linking import match_figure_contexts  # noqa: E402
from alumina_sol_extractor.utils.figure_utils import find_figures_in_markdown_any  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def test_pseudo_caption_nmr() -> None:
    paper_id = "_pseudo_caption_test"
    work_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
    markdown_dir = work_dir / "markdown"
    images_dir = markdown_dir / "images"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 60), (255, 255, 255)).save(images_dir / "nmr.png")

    markdown_path = markdown_dir / "paper.md"
    markdown = """# \u7b2c\u4e09\u7ae0 3.3 \u7ed3\u679c
\u6838\u78c1\u7ed3\u679c\u89c1\u56fe3.20\u3002
![](images/nmr.png)
\u5982\u56fe3.20\u6240\u793a\uff0c^27Al NMR \u548c ppm \u4fe1\u53f7\u53d1\u751f\u53d8\u5316\u3002"""
    markdown_path.write_text(markdown, encoding="utf-8")
    figures = find_figures_in_markdown_any(markdown, markdown_path, PROJECT_ROOT, paper_id)
    figures = match_figure_contexts(markdown, figures)
    figures = FigureFilter().apply(figures)

    assert len(figures) == 1
    assert figures[0].caption_source == "pseudo_caption"
    assert figures[0].figure_class == "nmr_spectrum"
    assert figures[0].send_to_vision_model
    shutil.rmtree(work_dir)


if __name__ == "__main__":
    test_pseudo_caption_nmr()
    print("pseudo caption test passed")
