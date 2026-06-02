from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.research_figures.stage3_inputs import (
    build_stage3_numeric_parameter_distribution,
    build_stage3_parameter_coverage,
    build_stage3_sample_parameter_heatmap,
    filter_stage3_analysis,
    load_stage3_analysis,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_stage3_existing_outputs_are_loaded_and_reused(tmp_path: Path) -> None:
    project_root = tmp_path
    analysis_dir = project_root / "data" / "analysis_outputs_stage3_v2"
    _write_json(analysis_dir / "analysis_outputs_stage3_summary.json", {"total_papers": 4})
    _write_csv(
        analysis_dir / "parameter_distribution.csv",
        "canonical_key,raw_name_examples,count,paper_count,category_count,value_numeric_count,value_text_count,unit_examples,source_text_coverage,evidence_ref_coverage\n"
        "calcination_temperature_C,temp,10,4,1,10,0,C,1.0,1.0\n"
        "pH,pH,8,3,1,8,0,,1.0,1.0\n",
    )
    _write_csv(
        analysis_dir / "sample_parameter_long.csv",
        "category,paper_id,sample_id,sample_name,canonical_key,raw_name,value,value_text,unit,source_text,evidence_refs,needs_manual_review\n"
        "fiber,p1,s1,S1,calcination_temperature_C,temp,900,,C,text,[],False\n"
        "fiber,p1,s1,S1,pH,pH,4,,,text,[],False\n"
        "fiber,p2,s2,S2,calcination_temperature_C,temp,1000,,C,text,[],False\n",
    )
    _write_csv(
        analysis_dir / "paper_stage3_summary.csv",
        "category,paper_id,stage3_status,data_point_count,process_steps_count,evidence_object_count,sample_count,canonical_key_errors_count,rejected_parameter_records_count,process_steps_warning_count,process_steps_other_action_ratio,process_steps_missing_evidence_ratio,cleaned_body_chars,input_truncated,truncation_reason,quality_flag\n"
        "fiber,p1,success,2,1,1,1,0,0,0,0,0,100,False,,ok\n"
        "fiber,p2,success,1,1,1,1,0,0,0,0,0,100,False,,ok\n",
    )
    _write_csv(
        analysis_dir / "canonical_key_category_summary.csv",
        "category,canonical_key,count,paper_count,normalized_frequency\n"
        "fiber,calcination_temperature_C,10,4,1.0\n",
    )
    _write_csv(
        project_root / "data" / "analysis_outputs_stage3_publication" / "label_mapping.csv",
        "canonical_key,short_label,unit,parameter_type\n"
        "calcination_temperature_C,Calcination T,C,process\n"
        "pH,pH,,synthesis\n",
    )

    payload = load_stage3_analysis(project_root=project_root)
    coverage = build_stage3_parameter_coverage(payload)
    heatmap = build_stage3_sample_parameter_heatmap(payload)
    numeric = build_stage3_numeric_parameter_distribution(payload)

    assert payload["analysis_dir"].endswith("analysis_outputs_stage3_v2")
    assert not coverage.empty
    assert "Calcination T" in coverage["short_label"].tolist()
    assert not heatmap.empty
    assert not numeric.empty

    filtered = filter_stage3_analysis(payload, selected_pairs={("fiber", "p1")}, selected_paper_ids={"p1"})
    filtered_coverage = build_stage3_parameter_coverage(filtered)
    assert filtered["paper_stage3_summary"]["paper_id"].tolist() == ["p1"]
    assert filtered["stage3_analysis_summary"]["total_papers"] == 1
    assert filtered_coverage["paper_count"].max() == 1
