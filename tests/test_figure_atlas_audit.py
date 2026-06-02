from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.figure_atlas.audit import run_audit


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_audit_outputs_are_generated(tmp_path: Path) -> None:
    project_root = tmp_path
    outputs_dir = project_root / "data" / "outputs"
    batch_dir = outputs_dir / "_batch_final_exports"
    audit_dir = project_root / "data" / "batch_validation" / "audit"

    _write_json(project_root / "data" / "analysis_outputs_stage3_v2" / "analysis_outputs_stage3_summary.json", {"total_papers": 1})
    _write_csv(batch_dir / "all_papers_final_parameters_linked.csv", "paper_id,category,parameter_id,canonical_key\np1,applications,param-1,pH\n")
    _write_csv(batch_dir / "all_papers_process_steps_table.csv", "paper_id,category,step_id,action\np1,applications,step-1,calcination\n")
    _write_csv(batch_dir / "all_papers_spectra_parameter_links.csv", "paper_id,category,figure_id,parameter_id,canonical_key\np1,applications,f1,param-1,pH\n")
    _write_json(batch_dir / "all_papers_link_aware_summary.json", {"ok": True})
    _write_json(outputs_dir / "applications" / "p1" / "stage4_vision_spectra_universal" / "stage4a_summary.json", {"total_candidates": 1})
    _write_csv(outputs_dir / "applications" / "p1" / "final_dataset" / "link_aware_exports" / "final_parameters_linked.csv", "paper_id\np1\n")

    result = run_audit(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_dir,
        audit_dir=audit_dir,
    )

    assert result["core_inputs_ready"] is True
    assert (audit_dir / "result_inventory.json").exists()
    assert (audit_dir / "figure_feasibility_matrix.csv").exists()
