from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.dspy_modules.runner import _postprocess_paper_basic_info


def test_author_and_year_fallbacks_and_alumina_sol_inference(tmp_path: Path) -> None:
    markdown_text = """# 纤维用铝溶胶前驱体的制备及表征
第二章 高 Al13 团簇含量铝溶胶的可控制备与表征
27Al NMR、Ferron、FTIR、XRD 与可纺性分析。
"""
    payload = _postprocess_paper_basic_info(
        payload={
            "title_en": "Preparation and characterization of aluminum sol for preparing alumina fibers",
            "author": "牛延强",
            "date": "2020-05-30",
            "material_system": "alumina-based ceramic fiber",
            "process_route": "sol-gel dry spinning",
        },
        paper_text=markdown_text,
        source_file=tmp_path / "纤维用铝溶胶前驱体的制备及表征_牛延强 (1).md",
    )

    assert payload["authors"] == ["牛延强"]
    assert payload["year"] == 2020
    assert payload["material_system"] in {"alumina_sol", "alumina_fiber_precursor"}
    assert payload["process_route"] == "alumina sol synthesis and characterization"
