from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.batch_validation.full_resume import (
    build_full_resume_plan,
    build_full_resume_summary,
    run_stage6c_full_resume,
)


def _status(
    *,
    stage2: bool,
    stage3: bool,
    stage4a: bool,
    stage5: bool,
    stage55: bool,
    markdown_exists: bool = True,
    mineru_raw_exists: bool = True,
) -> dict:
    return {
        "markdown_exists": markdown_exists,
        "mineru_raw_exists": mineru_raw_exists,
        "stage2": {"completed": stage2},
        "stage3": {"completed": stage3, "schema_valid": stage3},
        "stage4a": {"completed": stage4a, "total_records": 1 if stage4a else None},
        "stage5": {"completed": stage5, "invalid_canonical_key_count": 0 if stage5 else None},
        "stage55": {
            "completed": stage55,
            "invalid_source_id_count": 0 if stage55 else None,
            "invalid_target_id_count": 0 if stage55 else None,
        },
    }


def test_completed_stage_actions_skip() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=True, stage4a=True, stage5=True, stage55=True),
        auto_complete=False,
        allow_stage2_refresh=True,
        live_stage3=True,
        live_stage4a=True,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
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


def test_missing_stage3_and_stage4a_live_plan_runs() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=False, stage4a=False, stage5=False, stage55=False),
        auto_complete=False,
        allow_stage2_refresh=False,
        live_stage3=True,
        live_stage4a=True,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=False,
        force_linking=False,
    )
    assert plan["stage3"] == "run_stage3"
    assert plan["stage4a"] == "run_stage4a"
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_missing_stage3_without_live_is_pending() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=False, stage4a=False, stage5=False, stage55=False),
        auto_complete=False,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=True,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=False,
        force_linking=False,
    )
    assert plan["stage3"] == "pending_stage3_requires_llm"
    assert plan["stage4a"] == "pending_stage4a_depends_on_stage3"
    assert plan["stage5"] == "pending_stage5_requires_stage3"


def test_stage5_and_stage55_rerun_when_forced() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=True, stage4a=True, stage5=True, stage55=True),
        auto_complete=False,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=True,
        force_linking=True,
    )
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_stage5_and_stage55_rerun_when_forced_in_auto_complete_mode() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=True, stage4a=True, stage5=True, stage55=True),
        auto_complete=True,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=True,
        force_linking=True,
        stage3_budget_available=True,
        stage4a_budget_available=True,
        model_call_budget_available=True,
    )
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_auto_complete_runs_missing_stage4a_and_reruns_downstream() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=True, stage4a=False, stage5=True, stage55=True),
        auto_complete=True,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=True,
        force_linking=True,
        stage3_budget_available=False,
        stage4a_budget_available=True,
        model_call_budget_available=True,
    )
    assert plan["stage4a"] == "run_stage4a"
    assert plan["stage5"] == "run_stage5"
    assert plan["stage55"] == "run_stage55_dry_run"


def test_auto_complete_respects_stage4a_budget_limit() -> None:
    plan = build_full_resume_plan(
        _status(stage2=True, stage3=True, stage4a=False, stage5=True, stage55=True),
        auto_complete=True,
        allow_stage2_refresh=False,
        live_stage3=False,
        live_stage4a=False,
        live_linking=False,
        force_stage3=False,
        force_stage4a=False,
        force_stage5=False,
        force_linking=False,
        stage3_budget_available=False,
        stage4a_budget_available=False,
        model_call_budget_available=True,
    )
    assert plan["stage4a"] == "pending_stage4a_requires_vlm"


def test_run_stage6c_full_resume_continues_after_paper_failure(monkeypatch, tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    markdown_dir.mkdir()
    outputs_dir.mkdir()
    for paper_id in ["paper_a", "paper_b"]:
        (markdown_dir / f"{paper_id}.md").write_text("content", encoding="utf-8")
        (outputs_dir / paper_id).mkdir()

    candidates = [
        {"paper_id": "paper_a", "markdown_path": str(markdown_dir / "paper_a.md"), "output_dir": str(outputs_dir / "paper_a")},
        {"paper_id": "paper_b", "markdown_path": str(markdown_dir / "paper_b.md"), "output_dir": str(outputs_dir / "paper_b")},
    ]
    statuses = {
        "paper_a": _status(stage2=True, stage3=True, stage4a=True, stage5=False, stage55=False),
        "paper_b": _status(stage2=True, stage3=False, stage4a=False, stage5=False, stage55=False),
    }

    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume.discover_resume_candidates", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(
        "alumina_sol_extractor.batch_validation.full_resume.detect_stage_status",
        lambda **kwargs: statuses[kwargs["paper_id"]],
    )

    def fake_execute(**kwargs):
        if kwargs["paper_id"] == "paper_a":
            raise RuntimeError("boom")
        return [{"paper_id": "paper_b", "stage": "stage3", "action": "run_stage3", "status": "completed"}]

    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume._execute_full_resume_plan", fake_execute)

    result = run_stage6c_full_resume(
        project_root=tmp_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=2,
        live_stage3=True,
        output_dir=tmp_path / "batch" / "stage6c_full_resume",
    )
    summary = result["full_resume_summary"]
    assert summary["total_papers"] == 2
    assert summary["failed_actions_count"] == 1
    assert any(item["paper_id"] == "paper_b" for item in result["per_paper_summary"])


def test_stage4a_not_applicable_is_logged(monkeypatch, tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    markdown_dir.mkdir()
    outputs_dir.mkdir()
    paper_id = "paper_a"
    (markdown_dir / f"{paper_id}.md").write_text("content", encoding="utf-8")
    (outputs_dir / paper_id).mkdir()

    candidates = [{"paper_id": paper_id, "markdown_path": str(markdown_dir / f"{paper_id}.md"), "output_dir": str(outputs_dir / paper_id)}]
    status_before = _status(stage2=True, stage3=True, stage4a=False, stage5=True, stage55=True)
    status_after = _status(stage2=True, stage3=True, stage4a=False, stage5=True, stage55=True)
    calls = {"count": 0}

    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume.discover_resume_candidates", lambda *args, **kwargs: candidates)

    def fake_detect(**kwargs):
        calls["count"] += 1
        return status_before if calls["count"] == 1 else status_after

    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume.detect_stage_status", fake_detect)
    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume._stage4a_live_ready", lambda: (True, None))
    monkeypatch.setattr("alumina_sol_extractor.batch_validation.full_resume._select_stage4_figure_ids", lambda **kwargs: [])

    result = run_stage6c_full_resume(
        project_root=tmp_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=1,
        auto_complete=True,
        output_dir=tmp_path / "batch" / "stage6c_full_resume",
    )
    executed = result["per_paper_summary"][0]["executed_actions"]
    assert any(item["stage"] == "stage4a" and item["status"] == "not_applicable" for item in executed)


def test_build_full_resume_summary_counts() -> None:
    summary = build_full_resume_summary(
        [
            {
                "status_before": "partial",
                "status_after": "complete",
                "stage_status_after": {"stage2": True, "stage3": True, "stage4a": True, "stage5": True, "stage55": True},
                "planned_actions": {
                    "stage2": "skip_stage2",
                    "stage3": "skip_stage3",
                    "stage4a": "skip_stage4a",
                    "stage5": "run_stage5",
                    "stage55": "run_stage55_dry_run",
                },
                "executed_actions": [
                    {"stage": "stage5", "status": "completed"},
                    {"stage": "stage55", "status": "completed"},
                ],
            },
            {
                "status_before": "partial",
                "status_after": "partial",
                "stage_status_after": {"stage2": True, "stage3": False, "stage4a": False, "stage5": False, "stage55": False},
                "planned_actions": {
                    "stage2": "skip_stage2",
                    "stage3": "pending_stage3_requires_llm",
                    "stage4a": "pending_stage4a_depends_on_stage3",
                    "stage5": "pending_stage5_requires_stage3",
                    "stage55": "pending_stage55_requires_stage5",
                },
                "executed_actions": [],
            },
        ]
    )
    assert summary["total_papers"] == 2
    assert summary["completed_after"] == 1
    assert summary["partial_after"] == 1
    assert summary["stage5_run_count"] == 1
    assert summary["stage55_run_count"] == 1
    assert summary["remaining_pending_stage3_count"] == 1


def test_build_full_resume_summary_complete_increases_after_stage4a_recovery() -> None:
    summary = build_full_resume_summary(
        [
            {
                "status_before": "complete",
                "status_after": "complete",
                "stage_status_after": {"stage2": True, "stage3": True, "stage4a": True, "stage5": True, "stage55": True},
                "planned_actions": {"stage2": "skip_stage2", "stage3": "skip_stage3", "stage4a": "skip_stage4a", "stage5": "skip_stage5", "stage55": "skip_stage55"},
                "executed_actions": [],
            },
            {
                "status_before": "complete",
                "status_after": "complete",
                "stage_status_after": {"stage2": True, "stage3": True, "stage4a": True, "stage5": True, "stage55": True},
                "planned_actions": {"stage2": "skip_stage2", "stage3": "skip_stage3", "stage4a": "skip_stage4a", "stage5": "skip_stage5", "stage55": "skip_stage55"},
                "executed_actions": [],
            },
            {
                "status_before": "complete",
                "status_after": "complete",
                "stage_status_after": {"stage2": True, "stage3": True, "stage4a": True, "stage5": True, "stage55": True},
                "planned_actions": {"stage2": "skip_stage2", "stage3": "skip_stage3", "stage4a": "skip_stage4a", "stage5": "skip_stage5", "stage55": "skip_stage55"},
                "executed_actions": [],
            },
            {
                "status_before": "partial",
                "status_after": "complete",
                "stage_status_after": {"stage2": True, "stage3": True, "stage4a": True, "stage5": True, "stage55": True},
                "planned_actions": {
                    "stage2": "skip_stage2",
                    "stage3": "skip_stage3",
                    "stage4a": "run_stage4a",
                    "stage5": "run_stage5",
                    "stage55": "run_stage55_dry_run",
                },
                "executed_actions": [
                    {"stage": "stage4a", "status": "completed", "action": "run_stage4a"},
                    {"stage": "stage5", "status": "completed", "action": "run_stage5"},
                    {"stage": "stage55", "status": "completed", "action": "run_stage55_dry_run"},
                ],
            },
        ]
    )
    assert summary["completed_before"] == 3
    assert summary["completed_after"] == 4
    assert summary["partial_after"] == 0
