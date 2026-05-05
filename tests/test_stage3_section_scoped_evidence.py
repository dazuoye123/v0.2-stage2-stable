from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _scope_stage2_evidence_inputs


def test_section_scoped_evidence_keeps_selected_chapter_figures_only() -> None:
    scoped = _scope_stage2_evidence_inputs(
        figures=[
            {"figure_id": "图2.12", "caption": "图2.12 27Al NMR 光谱", "reference_sentences": ["见图2.12"]},
            {"figure_id": "图3.7", "caption": "图3.7 第三章 NMR 标准曲线", "reference_sentences": ["见图3.7"]},
        ],
        vision_inputs=[
            {"figure_id": "图2.12", "figure_class": "nmr_spectrum"},
            {"figure_id": "图3.7", "figure_class": "nmr_quantification_plot"},
        ],
        tables_summary=[
            {"table_id": "table_015", "rows": [{"title": "第三章表格"}]},
            {"table_id": "table_017", "rows": [{"title": "第三章分离结果"}]},
        ],
        selected_sections_text="第二章 结果与讨论 图2.12 给出 27Al NMR 结果以及 Al13 比例。",
        selected_section_titles=["第二章 高 Al13 团簇含量铝溶胶的可控制备与表征", "2.3 结果与讨论"],
        selected_chapter_numbers={"2"},
        section_keywords=["Al13", "NMR"],
    )

    assert [item["figure_id"] for item in scoped["figures"]] == ["图2.12"]
    assert [item["figure_id"] for item in scoped["vision_inputs"]] == ["图2.12"]
    assert scoped["tables_summary"] == []
    assert "图3.7" in scoped["scope"]["reviewed_figure_ids"]
    assert "table_015" in scoped["scope"]["reviewed_table_ids"]


def test_full_text_mode_keeps_original_evidence_pool() -> None:
    scoped = _scope_stage2_evidence_inputs(
        figures=[{"figure_id": "图2.12"}, {"figure_id": "图3.7"}],
        vision_inputs=[{"figure_id": "图2.12"}, {"figure_id": "图3.7"}],
        tables_summary=[{"table_id": "table_015", "rows": []}],
        selected_sections_text=None,
        selected_section_titles=[],
        selected_chapter_numbers=set(),
        section_keywords=[],
    )

    assert len(scoped["figures"]) == 2
    assert len(scoped["vision_inputs"]) == 2
    assert len(scoped["tables_summary"]) == 1
    assert scoped["scope"]["mode"] == "full_text"
