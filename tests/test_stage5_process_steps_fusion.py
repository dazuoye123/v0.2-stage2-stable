from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs
from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""), encoding="utf-8")


def _build_fixture(output_dir: Path) -> None:
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage4_dir = output_dir / "stage4_vision_spectra"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "paper_basic_info.json").write_text(
        json.dumps({"title": "Process steps paper", "authors": ["A"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage3_dir / "global_constants.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    _write_jsonl(stage3_dir / "experiment_series.jsonl", [])
    _write_jsonl(stage3_dir / "data_points.jsonl", [])
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [
            {
                "step_id": "step-01",
                "step_order": 1,
                "action": "dissolve",
                "action_zh": "溶解",
                "reagent_name": "AlCl3·6H2O",
                "reagent_amount": 0.005,
                "reagent_unit": "mol",
                "evidence_text": "0.005 mol AlCl3·6H2O 溶于一定量去离子水中。",
                "linked_parameter_keys": ["aluminum_source"],
                "needs_manual_review": False,
            },
            {
                "step_id": "step-02",
                "step_order": 2,
                "action": "add_polymer",
                "action_zh": "加入聚合物",
                "reagent_name": "PVP",
                "reagent_amount": "一定量",
                "evidence_text": "然后加入一定量的 PVP。",
                "linked_parameter_keys": [],
                "needs_manual_review": True,
            },
        ],
    )
    _write_jsonl(stage3_dir / "evidence_objects.jsonl", [])
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")
    (stage3_dir / "stage3_smoke_summary.json").write_text(
        json.dumps({"schema_valid": True, "canonical_key_errors_count": 0, "core_parameter_without_evidence_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage3_dir / "stage3_validation_report.md").write_text("ok", encoding="utf-8")
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [])
    (stage4_dir / "stage4_summary.json").write_text(
        json.dumps({"total_candidates": 0, "failed_record_count": 0, "validation_error_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage4_dir / "stage4_quality_review.json").write_text(
        json.dumps({"summary": {"overall_status": "pass"}, "figures": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage4_dir / "stage4_quality_review.md").write_text("ok", encoding="utf-8")


def test_stage5_fusion_carries_process_steps_and_exports_jsonl(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    _build_fixture(output_dir)

    bundle = run_stage5_dataset_fusion(paper_id="paper-1", output_dir=output_dir)
    assert len(bundle["process_steps"]) == 2
    assert bundle["quality_summary"]["total_process_steps"] == 2
    assert bundle["quality_summary"]["process_steps_with_reagent_amount_count"] == 2
    assert bundle["quality_summary"]["process_steps_needs_manual_review_count"] == 1

    export_fusion_outputs(bundle, output_dir / "final_dataset")
    exported = output_dir / "final_dataset" / "process_steps.jsonl"
    assert exported.exists()
    lines = [json.loads(line) for line in exported.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["reagent_name"] == "AlCl3·6H2O"
