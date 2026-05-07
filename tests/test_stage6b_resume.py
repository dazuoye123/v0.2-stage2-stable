from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.batch_validation.resume import (
    build_resume_summary,
    build_stage_plan,
    run_stage6b_batch_resume,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _status(*, stage2: bool, stage3: bool, stage4a: bool, stage5: bool, stage55: bool, markdown_exists: bool = True, mineru_raw_exists: bool = True) -> dict:
    return {
        "paper_id": "paper",
        "markdown_exists": markdown_exists,
        "mineru_raw_exists": mineru_raw_exists,
        "stage2": {"completed": stage2},
        "stage3": {"completed": stage3},
        "stage4a": {"completed": stage4a},
        "stage5": {"completed": stage5},
        "stage55": {"completed": stage55},
    }


def test_completed_stages_skip() -> None:
    plan = build_stage_plan(
        _status(stage2=True, stage3=True, stage4a=True, stage5=True, stage55=True),
        safe=True,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        allow_stage2_refresh=True,
        force_stage5=False,
        force_linking=False,
    )
    assert plan == {
        "stage2": "skip_stage2",
        "stage3": "skip_stage3",
        "stage4a": "skip_stage4a",
        "stage5": "skip_stage5",
        "stage55": "skip_stage55",
    }


def test_missing_stage3_and_stage4a_pending_in_safe_mode() -> None:
    plan = build_stage_plan(
        _status(stage2=True, stage3=False, stage4a=False, stage5=False, stage55=False),
        safe=True,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        allow_stage2_refresh=False,
        force_stage5=False,
        force_linking=False,
    )
    assert plan["stage3"] == "pending_stage3_requires_llm"
    assert plan["stage4a"] == "pending_stage4a_requires_stage3"
    assert plan["stage5"] == "pending_stage5_requires_stage3"
    assert plan["stage55"] == "pending_stage55_requires_stage5"


def test_missing_stage5_and_stage55_can_run_without_models() -> None:
    plan = build_stage_plan(
        _status(stage2=True, stage3=True, stage4a=False, stage5=False, stage55=False),
        safe=True,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        allow_stage2_refresh=False,
        force_stage5=False,
        force_linking=False,
    )
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_force_flags_trigger_reruns() -> None:
    plan = build_stage_plan(
        _status(stage2=True, stage3=True, stage4a=False, stage5=True, stage55=True),
        safe=True,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        allow_stage2_refresh=False,
        force_stage5=True,
        force_linking=True,
    )
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_run_stage6b_resume_handles_chinese_paper_and_summary(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "repo"
    markdown_dir = project_root / "data" / "markdown"
    outputs_dir = project_root / "data" / "outputs"
    paper_id = "纤维用铝溶胶前驱体的制备及表征_牛延强 (1)"
    markdown_path = markdown_dir / f"{paper_id}.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("正文", encoding="utf-8")
    output_dir = outputs_dir / paper_id
    _touch(output_dir / "figures.jsonl", "{}\n")
    _touch(output_dir / "vision_inputs.jsonl", "{}\n")
    _write_json(output_dir / "stage3_dspy_smoke" / "stage3_smoke_summary.json", {"schema_valid": True})
    _write_json(output_dir / "stage3_dspy_smoke" / "paper_extraction.schema_v2.json", {})
    _touch(output_dir / "stage3_dspy_smoke" / "evidence_objects.jsonl", "{}\n")

    def fake_run_stage5_dataset_fusion(*, paper_id: str, output_dir: Path, **_: object) -> dict:
        return {
            "paper": {"paper_id": paper_id},
            "samples": [],
            "parameters": [],
            "evidence": [],
            "figures": [],
            "spectra": [],
            "quality_summary": {"invalid_canonical_key_count": 0},
            "final_dataset_rows": [],
            "fusion_report": "ok",
            "inputs": {"dirs": {"dataset_dir": str(Path(output_dir) / "final_dataset")}},
        }

    def fake_export_fusion_outputs(bundle: dict, dataset_dir: Path) -> dict:
        _write_json(dataset_dir / "quality_summary.json", bundle["quality_summary"])
        _touch(dataset_dir / "parameters.jsonl", "")
        _touch(dataset_dir / "evidence.jsonl", "")
        _touch(dataset_dir / "samples.jsonl", "")
        _touch(dataset_dir / "fusion_report.md", "ok")
        return {}

    def fake_run_stage55_dry_run(*, output_dir: Path) -> None:
        linking_dir = Path(output_dir) / "final_dataset" / "linking"
        _write_json(
            linking_dir / "linking_summary.json",
            {"invalid_source_id_count": 0, "invalid_target_id_count": 0},
        )
        _touch(linking_dir / "links.jsonl", "")

    monkeypatch.setattr("alumina_sol_extractor.batch_validation.resume.run_stage5_dataset_fusion", fake_run_stage5_dataset_fusion)
    monkeypatch.setattr("alumina_sol_extractor.batch_validation.resume.export_fusion_outputs", fake_export_fusion_outputs)
    monkeypatch.setattr("alumina_sol_extractor.batch_validation.resume._run_stage55_dry_run", fake_run_stage55_dry_run)

    result = run_stage6b_batch_resume(
        project_root=project_root,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=5,
        safe=True,
        allow_stage2_refresh=False,
        force_stage5=True,
        force_linking=True,
        output_dir=project_root / "data" / "batch_validation" / "resume",
    )

    assert result["resume_summary"]["total_papers"] == 1
    assert result["resume_summary"]["run_stages_count"] >= 2
    per_paper = result["per_paper_results"][0]
    assert per_paper["planned_actions"]["stage5"] == "run_stage5"
    assert per_paper["planned_actions"]["stage55"] == "run_stage55_dry_run"
    assert per_paper["paper_status_after"] == "partial"
    executed = {item["stage"]: item["status"] for item in per_paper["executed_actions"]}
    assert executed["stage5"] == "completed"
    assert executed["stage55"] == "completed"
    assert (project_root / "data" / "batch_validation" / "resume" / "resume_summary.json").exists()


def test_resume_summary_counts() -> None:
    summary = build_resume_summary(
        [
            {
                "planned_actions": {"stage2": "skip_stage2", "stage3": "pending_stage3_requires_llm"},
                "executed_actions": [],
                "paper_status_after": "partial",
            },
            {
                "planned_actions": {"stage2": "run_stage2_refresh", "stage5": "run_stage5"},
                "executed_actions": [{"status": "completed"}, {"status": "failed"}],
                "paper_status_after": "complete",
            },
        ]
    )
    assert summary["total_papers"] == 2
    assert summary["skipped_stages_count"] == 1
    assert summary["run_stages_count"] == 2
    assert summary["pending_stages_count"] == 1
    assert summary["completed_papers_after_resume"] == 1
    assert summary["partial_papers_after_resume"] == 1
    assert summary["requires_llm_count"] == 1
    assert summary["failed_actions_count"] == 1
