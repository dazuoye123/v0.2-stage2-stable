"""Smoke test for HTML table extraction from Markdown."""

from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.utils.table_utils import extract_tables_from_markdown  # noqa: E402


def test_table_extraction() -> None:
    paper_id = "_table_test"
    test_output_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)

    markdown = """
前文介绍氧化铝溶胶组成。

表1 铝溶胶样品组成
<table>
<tr><th>样品</th><th>Al(NO3)3 / mol</th><th>温度 / ℃</th></tr>
<tr><td>S1</td><td>0.10</td><td>80</td></tr>
<tr><td>S2</td><td>0.20</td><td>90</td></tr>
</table>

后文讨论凝胶化过程。
"""
    new_markdown, infos = extract_tables_from_markdown(
        markdown=markdown,
        project_root=PROJECT_ROOT,
        paper_id=paper_id,
    )
    assert len(infos) == 1
    assert "[TableID: table_001]" in new_markdown
    assert "<table>" not in new_markdown
    assert "样品" in new_markdown

    info = infos[0]
    csv_path = Path(info.csv_path)
    json_path = Path(info.json_path)
    index_path = PROJECT_ROOT / "data" / "outputs" / paper_id / "tables" / "tables_index.jsonl"
    assert csv_path.exists()
    assert json_path.exists()
    assert index_path.exists()
    assert "样品" in csv_path.read_text(encoding="utf-8-sig")
    records = json.loads(json_path.read_text(encoding="utf-8"))
    assert records[0]["样品"] == "S1"
    shutil.rmtree(test_output_dir)


if __name__ == "__main__":
    test_table_extraction()
    print("table extraction test passed")
