from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.research_figures.batch_runner import run_research_figures


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_batch_level_output_layout_is_written(tmp_path: Path) -> None:
    project_root = tmp_path
    outputs_dir = project_root / "data" / "outputs"
    batch_output_dir = project_root / "data" / "batch_validation"
    analysis_dir = project_root / "data" / "analysis_outputs_stage3_v2"
    publication_dir = project_root / "data" / "analysis_outputs_stage3_publication"

    _write_json(analysis_dir / "analysis_outputs_stage3_summary.json", {"total_papers": 1})
    _write_csv(
        analysis_dir / "parameter_distribution.csv",
        "canonical_key,raw_name_examples,count,paper_count,category_count,value_numeric_count,value_text_count,unit_examples,source_text_coverage,evidence_ref_coverage\n"
        "calcination_temperature_C,temp,2,1,1,2,0,C,1.0,1.0\n",
    )
    _write_csv(
        analysis_dir / "sample_parameter_long.csv",
        "category,paper_id,sample_id,sample_name,canonical_key,raw_name,value,value_text,unit,source_text,evidence_refs,needs_manual_review\n"
        "fiber,p1,s1,S1,calcination_temperature_C,temp,900,,C,text,[],False\n",
    )
    _write_csv(
        analysis_dir / "paper_stage3_summary.csv",
        "category,paper_id,stage3_status,data_point_count,process_steps_count,evidence_object_count,sample_count,canonical_key_errors_count,rejected_parameter_records_count,process_steps_warning_count,process_steps_other_action_ratio,process_steps_missing_evidence_ratio,cleaned_body_chars,input_truncated,truncation_reason,quality_flag\n"
        "fiber,p1,success,1,1,1,1,0,0,0,0,0,100,False,,ok\n",
    )
    _write_csv(analysis_dir / "canonical_key_category_summary.csv", "category,canonical_key,count,paper_count,normalized_frequency\nfiber,calcination_temperature_C,2,1,1.0\n")
    _write_csv(publication_dir / "label_mapping.csv", "canonical_key,short_label,unit,parameter_type\ncalcination_temperature_C,Calcination T,C,process\n")

    paper_dir = outputs_dir / "fiber" / "p1"
    _write_json(paper_dir / "stage4_vision_spectra_universal" / "stage4a_summary.json", {"total_candidates": 1, "successful_extractions_count": 1, "failed_record_count": 0, "by_stage2_figure_class": {"generic_chart_or_plot": 1}})
    _write_jsonl(paper_dir / "stage4_vision_spectra_universal" / "spectra_extractions.jsonl", [{"figure_id": "Fig.1", "figure_type": "ftir_spectrum", "technique": "FTIR", "peaks": [{"position": 467, "unit": "cm^-1"}]}])
    _write_json(outputs_dir / "fiber" / "p2" / "stage4_vision_spectra_universal" / "stage4a_summary.json", {"total_candidates": 1, "successful_extractions_count": 0, "failed_record_count": 1, "by_stage2_figure_class": {"generic_chart_or_plot": 1}})
    manifest_path = project_root / "data" / "batch_manifest" / "source_manifest.csv"
    _write_csv(
        manifest_path,
        "source_id,category,paper_id_guess\n"
        "fiber__p1,fiber,p1\n",
    )

    result = run_research_figures(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_output_dir=batch_output_dir,
        stage3_analysis_dir=analysis_dir,
        stage3_publication_dir=publication_dir,
        manifest_path=manifest_path,
        generate_figures=True,
    )

    out_dir = Path(result["output_dir"])
    assert (out_dir / "figures" / "stage4_extraction_overview.svg").exists()
    assert (out_dir / "tables" / "stage4_statistics.csv").exists()
    assert (out_dir / "stage3_stage4_figure_data.csv").exists()
    assert (out_dir / "batch_research_figures.md").exists()
    assert (out_dir / "figure_data" / "stage4_extraction_overview.json").exists()

    statistics_rows = (out_dir / "tables" / "stage4_statistics.csv").read_text(encoding="utf-8-sig")
    assert "p1" in statistics_rows
    assert "p2" not in statistics_rows

    figure_json = json.loads((out_dir / "figure_data" / "stage4_extraction_overview.json").read_text(encoding="utf-8"))
    assert figure_json["figure_name"] == "stage4_extraction_overview"
    assert figure_json["row_count"] >= 1
    assert figure_json["rows"]
