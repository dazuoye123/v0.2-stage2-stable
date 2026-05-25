from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _build_compact_stage3_prompt_inputs


def test_compact_stage3_prompt_inputs_truncate_large_payload_and_keep_procedure_context() -> None:
    paper_text = "# Experimental\n" + ("mix solution and stir for 2 h.\n" * 5000)
    procedure_sections = [
        {
            "title": "Experimental",
            "score": 10,
            "selected_for_process_steps": True,
            "text_preview": "mix solution and stir for 2 h. calcine at 1200 C for 2 h." * 200,
        }
    ]
    figures = [
        {
            "figure_id": f"Fig.{idx}",
            "figure_class": "xrd_pattern",
            "caption": "XRD pattern " * 50,
            "reference_sentences": ["This figure supports the phase analysis. " * 20],
        }
        for idx in range(150)
    ]
    tables = [{"table_id": f"table_{idx}", "rows": [["a", "b", "c"] * 10]} for idx in range(80)]
    captions = [{"figure_id": f"Fig.{idx}", "caption": "SEM images " * 30, "reference_sentences": ["microstructure " * 30]} for idx in range(120)]
    ontology_keys = [f"key_{idx}" for idx in range(1000)]

    result = _build_compact_stage3_prompt_inputs(
        paper_text=paper_text,
        procedure_sections=procedure_sections,
        figures=figures,
        figure_summaries=figures,
        tables_summary=tables,
        captions_and_references=captions,
        ontology_keys=ontology_keys,
        stage3_core_payload=None,
        pass_name="pass1",
    )

    assert result["input_truncated"] is True
    assert result["total_chars"] <= 180000
    assert "Experimental" in result["paper_text"]
    assert "calcine at 1200 C" in result["procedure_text"]
