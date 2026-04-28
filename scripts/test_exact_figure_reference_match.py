"""Exact figure-reference matching tests."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.linking import match_figure_contexts  # noqa: E402
from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402


def test_exact_decimal_reference() -> None:
    markdown = """# \u7b2c\u4e8c\u7ae0 2.3 \u7ed3\u679c
![](images/a.png)
\u56fe2.3 XRD pattern of alumina sol powder.

\u5982\u56fe2.3\u6240\u793a\uff0c\u6837\u54c1\u51fa\u73b0\u660e\u663e\u7684\u6c27\u5316\u94dd\u884d\u5c04\u5cf0\u3002
\u56fe2.30\u5c55\u793a\u7684\u662f\u53e6\u4e00\u4e2a\u6837\u54c1\u3002
\u56fe2.1\u4e5f\u662f\u53e6\u4e00\u4e2a\u6837\u54c1\u3002
Figure 2.3 shows the same diffraction pattern in English.
"""
    figure = FigureInfo(
        paper_id="demo",
        figure_id="\u56fe2.3",
        position=markdown.index("![]"),
        caption="\u56fe2.3 XRD pattern of alumina sol powder.",
    )
    [figure] = match_figure_contexts(markdown, [figure])
    joined = " ".join(figure.reference_sentences)
    assert "\u5982\u56fe2.3\u6240\u793a" in joined
    assert "Figure 2.3 shows" in joined
    assert "\u56fe2.30\u5c55\u793a" not in joined
    assert "\u56fe2.1\u4e5f" not in joined


if __name__ == "__main__":
    test_exact_decimal_reference()
    print("exact figure reference match test passed")
