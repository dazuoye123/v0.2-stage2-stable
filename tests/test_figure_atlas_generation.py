from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.figure_atlas.runner import run_figure_atlas


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_full_figure_atlas_generation_writes_figures_and_sources(tmp_path: Path) -> None:
    project_root = tmp_path
    outputs_dir = project_root / "data" / "outputs"
    batch_dir = outputs_dir / "_batch_final_exports"
    batch_output_dir = project_root / "data" / "batch_validation"

    _write_json(project_root / "data" / "analysis_outputs_stage3_v2" / "analysis_outputs_stage3_summary.json", {"total_papers": 1})
    _write_csv(project_root / "data" / "analysis_outputs_stage3" / "parameter_distribution.csv", "canonical_key,paper_count\npH,1\n")
    _write_csv(project_root / "data" / "analysis_outputs_stage3" / "sample_parameter_long.csv", "paper_id,sample_id,canonical_key,value\np1,s1,pH,4\n")
    _write_csv(project_root / "data" / "analysis_outputs_stage3" / "paper_stage3_summary.csv", "paper_id,sample_count\np1,1\n")
    _write_csv(project_root / "data" / "analysis_outputs_stage3_publication" / "fig3_coverage_matrix_plotting_data.csv", "sample,pH\ns1,1\n")

    _write_csv(batch_dir / "all_papers_final_parameters_linked.csv", "paper_id,category,parameter_id,canonical_key,zh_name,en_name,resolved_sample_id,sample_id_original,value_raw,value_num,value_text,unit,link_types,linked_evidence_ids,linked_spectra_ids,normalization_note\np1,applications,param-1,pH,,,s1,s1,4,4,,unitless,sample;spectra,,spectra-1,\n")
    _write_csv(batch_dir / "all_papers_process_steps_table.csv", "paper_id,category,step_id,action,action_zh,section,product_or_outcome,reagent_name,condition_key,evidence_text\np1,applications,step-1,calcination,煅烧,,,,,\n")
    _write_csv(batch_dir / "all_papers_spectra_parameter_links.csv", "paper_id,category,source_id,figure_id,figure_type,parameter_id,canonical_key,created_by\np1,applications,spectra-1,f1,xrd_pattern,param-1,pH,manual\n")
    _write_csv(batch_dir / "all_papers_evidence_parameter_links.csv", "paper_id,category,source_id,parameter_id,canonical_key,created_by\np1,applications,e1,param-1,pH,manual\n")
    _write_csv(batch_dir / "all_papers_process_step_parameter_links.csv", "paper_id,category,source_id,parameter_id,canonical_key,created_by\np1,applications,step-1,param-1,pH,manual\n")
    _write_csv(batch_dir / "all_papers_sample_parameter_matrix.csv", "paper_id,category,sample_id,sample_name,parameter_count,linked_parameter_count,spectra_count\np1,applications,s1,Sample 1,1,1,1\n")
    _write_csv(batch_dir / "all_papers_final_showcase_table.csv", "paper_id,category\np1,applications\n")
    _write_json(batch_dir / "all_papers_link_aware_summary.json", {"ok": True})

    stage4_dir = outputs_dir / "applications" / "p1" / "stage4_vision_spectra_universal"
    _write_json(stage4_dir / "stage4a_summary.json", {"total_candidates": 1, "successful_extractions_count": 1})
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [{"figure_id": "f1", "figure_type": "xrd_pattern", "technique": "XRD", "peaks": [{"position": 25.5, "unit": "2theta_deg"}]}])

    result = run_figure_atlas(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_dir,
        batch_output_dir=batch_output_dir,
        generate_figures=True,
        continue_on_error=False,
    )

    out_dir = Path(result["output_dir"])
    assert (out_dir / "audit" / "result_inventory.json").exists()
    assert (out_dir / "figure_atlas_manifest.json").exists()
    assert (out_dir / "figure_index.csv").exists()
    assert any((out_dir / "figures").rglob("*.png"))
    assert any((out_dir / "tables").glob("*_source.csv"))
    assert any((out_dir / "figure_data").glob("*.json"))
