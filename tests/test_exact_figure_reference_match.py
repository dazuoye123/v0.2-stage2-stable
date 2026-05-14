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


def test_exact_hyphen_reference_and_junk_filter() -> None:
    markdown = """![](images/a.png)
\u56fe3-17 \u6240\u5236\u7ea4\u7ef4\u6469\u64e610000\u6b21\u540e\u7684\u635f\u4f24\u5f62\u8c8c\u3002

json) \u5982\u56fe3-17\u6240\u793a\uff0c1#\u7ea4\u7ef4\u8868\u9762\u51fa\u73b0\u6761\u5e26\u72b6\u635f\u4f24\u5f62\u8c8c\u3002
\u56fe3-16\u5c55\u793a\u4e86\u78e8\u64e6\u524d\u7684\u5f62\u8c8c\u3002
[TableID: table_001] table_001.json)
\u56fe3-19\u8868\u660e\u4e0d\u540c\u6837\u54c1\u7684\u65ad\u88c2\u884c\u4e3a\u3002
"""
    figure = FigureInfo(
        paper_id="demo",
        figure_id="\u56fe3-17",
        position=markdown.index("![]"),
        caption="\u56fe3-17 \u6240\u5236\u7ea4\u7ef4\u6469\u64e610000\u6b21\u540e\u7684\u635f\u4f24\u5f62\u8c8c\u3002",
        is_merged_figure=True,
    )
    [figure] = match_figure_contexts(markdown, [figure])
    assert figure.reference_sentences
    assert len(figure.reference_sentences) == 1
    assert "\u5982\u56fe3-17\u6240\u793a" in figure.reference_sentences[0]
    assert "json" not in figure.reference_sentences[0].lower()
    assert "\u56fe3-16" not in " ".join(figure.reference_sentences)
    assert "\u56fe3-19" not in " ".join(figure.reference_sentences)


if __name__ == "__main__":
    test_exact_decimal_reference()
    test_exact_hyphen_reference_and_junk_filter()
    print("exact figure reference match test passed")
