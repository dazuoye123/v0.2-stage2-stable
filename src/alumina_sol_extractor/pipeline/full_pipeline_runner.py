"""Controlled full-pipeline runner and resume helpers.

The public ``run_full_pipeline.py`` entrypoint still routes through this module
for backward compatibility. Stage 4 execution itself should flow through the
official :mod:`alumina_sol_extractor.stage4` runner/extractor path.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.config.settings_loader import build_runtime_settings as build_runtime_settings_loader
from alumina_sol_extractor.config.settings_loader import resolve_project_path
from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs
from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion
from alumina_sol_extractor.dspy_modules import run_stage3_dspy_smoke_test
from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv, resolve_dspy_runtime_config
from alumina_sol_extractor.linking.candidate_builder import (
    DEFAULT_LINK_FAMILIES,
    build_deterministic_links,
    build_link_candidates,
    load_final_dataset_inputs,
)
from alumina_sol_extractor.linking.exporters import export_linking_outputs
from alumina_sol_extractor.linking.llm_linker import EvidenceSpectraParameterLinker
from alumina_sol_extractor.linking.report import render_linking_report
from alumina_sol_extractor.linking.validators import (
    build_linking_summary,
    merge_live_unmatched_candidates,
    sanitize_link_decision_payloads,
    validate_llm_link_decisions,
)
from alumina_sol_extractor.pipeline.stage2_figure_pipeline import run_stage2_figure_pipeline
from alumina_sol_extractor.stage4.batch_runner import (
    DEFAULT_CANDIDATE_SOURCE as DEFAULT_STAGE4_CANDIDATE_SOURCE,
    DEFAULT_ROUTING_MODE as DEFAULT_STAGE4_ROUTING_MODE,
    DEFAULT_STAGE3_SUBDIR as DEFAULT_STAGE4_STAGE3_SUBDIR,
    DEFAULT_STAGE4_SUBDIR as DEFAULT_STAGE4_SUBDIR,
    run_stage4_for_paper,
)
from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor
from alumina_sol_extractor.stage4.io import read_json, read_jsonl
from alumina_sol_extractor.stage4.quality_review import (
    load_stage4_outputs,
    review_stage4_extractions,
    write_stage4_quality_review,
)
from alumina_sol_extractor.stage4.vlm_client import VisionLanguageModelClient
from alumina_sol_extractor.utils.jsonl import write_jsonl

from .resume_status import detect_stage_status, discover_resume_candidates


STAGE_ORDER = ("stage2", "stage3", "stage4a", "stage5", "stage55")
OFFICIAL_STAGE_ORDER = ("stage2", "stage3", "stage4", "stage5", "linking")
LEGACY_STAGE_NAME_MAP = {"stage4a": "stage4", "stage55": "linking", "stage6c": "full_pipeline"}
STAGE4_PRIORITY_TYPES = (
    "ftir_spectrum",
    "ir_spectrum",
    "xrd_pattern",
    "nmr_spectrum",
    "raman_spectrum",
    "tg_dsc_curve",
    "tg_curve",
    "dsc_curve",
    "sem_image",
    "tem_image",
    "microscopy",
)
DEFAULT_STAGE3_SECTION_KEYWORDS = ["Al13", "NMR", "Ferron", "FTIR", "XRD", "pH", "可纺性"]


def _normalize_stage4a_figure_types(
    figure_types: list[str] | tuple[str, ...] | set[str] | None,
) -> tuple[str, ...]:
    if not figure_types:
        return STAGE4_PRIORITY_TYPES
    normalized = tuple(str(item).strip() for item in figure_types if str(item).strip())
    return normalized or STAGE4_PRIORITY_TYPES


def build_full_resume_plan(
    status: dict[str, Any],
    *,
    auto_complete: bool = False,
    allow_stage2_refresh: bool,
    live_stage3: bool,
    live_stage4a: bool,
    live_linking: bool,
    force_stage3: bool,
    force_stage4a: bool,
    force_stage5: bool,
    force_linking: bool,
    stage3_budget_available: bool = True,
    stage4a_budget_available: bool = True,
    model_call_budget_available: bool = True,
) -> dict[str, str]:
    actions: dict[str, str] = {}

    if status["stage2"]["completed"]:
        actions["stage2"] = "skip_stage2"
    elif status.get("markdown_exists") and status.get("mineru_raw_exists") and allow_stage2_refresh:
        actions["stage2"] = "run_stage2_refresh"
    else:
        actions["stage2"] = "pending_stage2_missing_inputs"

    stage3_allowed = live_stage3 or (auto_complete and stage3_budget_available and model_call_budget_available)
    stage4a_allowed = live_stage4a or (auto_complete and stage4a_budget_available and model_call_budget_available)

    if status["stage3"]["completed"] and not force_stage3:
        actions["stage3"] = "skip_stage3"
    elif stage3_allowed:
        actions["stage3"] = "run_stage3"
    else:
        actions["stage3"] = "pending_stage3_requires_llm"

    stage3_ready_or_running = status["stage3"]["completed"] or actions["stage3"] == "run_stage3"
    if status["stage4a"]["completed"] and not force_stage4a:
        actions["stage4a"] = "skip_stage4a"
    elif not stage3_ready_or_running:
        actions["stage4a"] = "pending_stage4a_depends_on_stage3"
    elif stage4a_allowed:
        actions["stage4a"] = "run_stage4a"
    else:
        actions["stage4a"] = "pending_stage4a_requires_vlm"

    stage5_requires_rerun = (
        force_stage5
        or not status["stage5"]["completed"]
        or actions["stage3"] == "run_stage3"
        or actions["stage4a"] == "run_stage4a"
    )
    if not stage3_ready_or_running:
        actions["stage5"] = "pending_stage5_requires_stage3"
    elif stage5_requires_rerun:
        actions["stage5"] = "run_stage5"
    else:
        actions["stage5"] = "skip_stage5"

    stage55_requires_rerun = (
        force_linking
        or not status["stage55"]["completed"]
        or actions["stage5"] == "run_stage5"
    )
    if actions["stage5"] == "pending_stage5_requires_stage3":
        actions["stage55"] = "pending_stage55_requires_stage5"
    elif stage55_requires_rerun:
        actions["stage55"] = "run_stage55_live" if live_linking else "run_stage55_dry_run"
    else:
        actions["stage55"] = "skip_stage55"

    return actions


def build_full_pipeline_plan(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Preferred public name for the full-pipeline planner."""
    return build_full_resume_plan(*args, **kwargs)


def run_stage6c_full_resume(
    *,
    project_root: Path | str,
    markdown_dir: Path | str,
    outputs_dir: Path | str,
    max_papers: int = 4,
    paper_ids: list[str] | None = None,
    auto_complete: bool = False,
    allow_stage2_refresh: bool = False,
    live_stage3: bool = False,
    live_stage4a: bool = False,
    live_linking: bool = False,
    force_stage3: bool = False,
    force_stage4a: bool = False,
    force_stage5: bool = False,
    force_linking: bool = False,
    stop_on_error: bool = False,
    dry_run_plan_only: bool = False,
    max_stage4a_figures_per_paper: int = 4,
    max_stage3_papers: int = 2,
    max_stage4a_papers: int = 2,
    max_total_model_calls: int = 10,
    stage4a_figure_types: list[str] | tuple[str, ...] | set[str] | None = None,
    stage3_subdir: str = DEFAULT_STAGE4_STAGE3_SUBDIR,
    stage4_subdir: str = DEFAULT_STAGE4_SUBDIR,
    stage4_routing_mode: str = DEFAULT_STAGE4_ROUTING_MODE,
    stage4_candidate_source: str = DEFAULT_STAGE4_CANDIDATE_SOURCE,
    stage4_figure_ids: list[str] | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Legacy compatibility wrapper.

    Prefer :func:`run_full_pipeline_orchestrated` for new code.
    """
    project_root = Path(project_root)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    load_project_dotenv(project_root)
    allowed_stage4a_types = _normalize_stage4a_figure_types(stage4a_figure_types)

    discovered = discover_resume_candidates(markdown_dir, outputs_dir, max_papers=max_papers)
    if paper_ids:
        allowed = set(paper_ids)
        discovered = [item for item in discovered if item["paper_id"] in allowed]

    batch_dir = Path(output_dir) if output_dir else project_root / "data" / "batch_validation" / datetime.now().strftime("%Y%m%d_%H%M%S") / "stage6c_full_resume"
    batch_dir.mkdir(parents=True, exist_ok=True)

    plan_rows: list[dict[str, Any]] = []
    execution_log: list[dict[str, Any]] = []
    per_paper_summary: list[dict[str, Any]] = []
    stage3_planned = 0
    stage4a_planned = 0
    model_stage_planned = 0

    for candidate in discovered:
        paper_id = candidate["paper_id"]
        markdown_path = Path(candidate["markdown_path"]) if candidate.get("markdown_path") else markdown_dir / f"{paper_id}.md"
        output_dir_path = Path(candidate["output_dir"])
        before = detect_stage_status(
            project_root=project_root,
            paper_id=paper_id,
            markdown_path=markdown_path,
            output_dir=output_dir_path,
        )
        stage3_budget_available = max_stage3_papers <= 0 or stage3_planned < max_stage3_papers
        stage4a_budget_available = max_stage4a_papers <= 0 or stage4a_planned < max_stage4a_papers
        model_budget_available = max_total_model_calls <= 0 or model_stage_planned < max_total_model_calls
        plan = build_full_resume_plan(
            before,
            auto_complete=auto_complete,
            allow_stage2_refresh=allow_stage2_refresh,
            live_stage3=live_stage3,
            live_stage4a=live_stage4a,
            live_linking=live_linking,
            force_stage3=force_stage3,
            force_stage4a=force_stage4a,
            force_stage5=force_stage5,
            force_linking=force_linking,
            stage3_budget_available=stage3_budget_available,
            stage4a_budget_available=stage4a_budget_available,
            model_call_budget_available=model_budget_available,
        )
        if plan.get("stage3") == "run_stage3":
            stage3_planned += 1
            model_stage_planned += 1
        if plan.get("stage4a") == "run_stage4a":
            stage4a_planned += 1
            model_stage_planned += 1
        plan_rows.append({"paper_id": paper_id, "stage_status_before": before, "planned_actions": plan})

        executed_actions: list[dict[str, Any]] = []
        paper_failed_reason: str | None = None
        if not dry_run_plan_only:
            try:
                executed_actions = _execute_full_resume_plan(
                    project_root=project_root,
                    paper_id=paper_id,
                    markdown_path=markdown_path,
                    output_dir=output_dir_path,
                    plan=plan,
                    max_stage4a_figures_per_paper=max_stage4a_figures_per_paper,
                    stage4a_figure_types=allowed_stage4a_types,
                    stage3_subdir=stage3_subdir,
                    stage4_subdir=stage4_subdir,
                    stage4_routing_mode=stage4_routing_mode,
                    stage4_candidate_source=stage4_candidate_source,
                    stage4_figure_ids=stage4_figure_ids,
                )
            except Exception as exc:  # pragma: no cover - top-level batch guard
                paper_failed_reason = f"{type(exc).__name__}: {exc}"
                executed_actions.append(
                    {
                        "paper_id": paper_id,
                        "stage": "batch",
                        "action": "paper_level_failure",
                        "status": "failed",
                        "error": paper_failed_reason,
                    }
                )
                if stop_on_error:
                    execution_log.extend(executed_actions)
                    raise
        execution_log.extend(executed_actions)
        after = detect_stage_status(
            project_root=project_root,
            paper_id=paper_id,
            markdown_path=markdown_path,
            output_dir=output_dir_path,
        )
        per_paper_summary.append(
            {
                "paper_id": paper_id,
                "status_before": _paper_status(before),
                "status_after": _paper_status(after),
                "stage_status_before": _compact_stage_status(before),
                "stage_status_after": _compact_stage_status(after),
                "planned_actions": plan,
                "executed_actions": executed_actions,
                "failed_reason": paper_failed_reason,
                "remaining_blockers": _remaining_blockers(after, plan),
                "recommendation": _paper_recommendation(after),
                "output_summary": _build_output_summary(after),
            }
        )

    summary = build_full_resume_summary(per_paper_summary)
    report = render_full_resume_report(summary=summary, per_paper_summary=per_paper_summary)

    _write_json(batch_dir / "full_resume_plan.json", plan_rows)
    write_jsonl(execution_log, batch_dir / "full_resume_execution_log.jsonl")
    write_jsonl(per_paper_summary, batch_dir / "full_resume_per_paper_summary.jsonl")
    _write_json(batch_dir / "full_resume_summary.json", summary)
    (batch_dir / "full_resume_report.md").write_text(report, encoding="utf-8")

    return {
        "batch_output_dir": str(batch_dir),
        "full_resume_summary": summary,
        "per_paper_summary": per_paper_summary,
    }


def run_full_pipeline_orchestrated(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Preferred public orchestrator entrypoint.

    Internally delegates to the legacy-named implementation so historical
    callers remain compatible.
    """
    return run_stage6c_full_resume(*args, **kwargs)


def build_full_resume_summary(per_paper_summary: list[dict[str, Any]]) -> dict[str, Any]:
    completed_before = sum(1 for item in per_paper_summary if item.get("status_before") == "complete")
    completed_after = sum(1 for item in per_paper_summary if item.get("status_after") == "complete")
    partial_before = sum(1 for item in per_paper_summary if item.get("status_before") == "partial")
    partial_after = sum(1 for item in per_paper_summary if item.get("status_after") == "partial")
    failed_papers = sum(1 for item in per_paper_summary if item.get("status_after") == "failed")

    executed = [entry for item in per_paper_summary for entry in item.get("executed_actions", [])]
    planned_actions = [
        action
        for item in per_paper_summary
        for action in item.get("planned_actions", {}).values()
    ]

    summary = {
        "total_papers": len(per_paper_summary),
        "completed_before": completed_before,
        "completed_after": completed_after,
        "partial_before": partial_before,
        "partial_after": partial_after,
        "failed_papers": failed_papers,
        "stage2_run_count": _count_action(executed, "stage2", "completed"),
        "stage3_run_count": _count_action(executed, "stage3", "completed"),
        "stage4a_run_count": _count_action(executed, "stage4a", "completed"),
        "stage5_run_count": _count_action(executed, "stage5", "completed"),
        "stage55_run_count": _count_action(executed, "stage55", "completed"),
        "stage2_skip_count": planned_actions.count("skip_stage2"),
        "stage3_skip_count": planned_actions.count("skip_stage3"),
        "stage4a_skip_count": planned_actions.count("skip_stage4a"),
        "stage5_skip_count": planned_actions.count("skip_stage5"),
        "stage55_skip_count": planned_actions.count("skip_stage55"),
        "llm_call_stages_count": _count_model_stage_calls(executed, {"run_stage3", "run_stage55_live"}),
        "vlm_call_stages_count": _count_model_stage_calls(executed, {"run_stage4a"}),
        "failed_actions_count": sum(1 for entry in executed if entry.get("status") == "failed"),
        "remaining_pending_stage3_count": sum(1 for item in per_paper_summary if not item["stage_status_after"].get("stage3")),
        "remaining_pending_stage4a_count": sum(1 for item in per_paper_summary if not item["stage_status_after"].get("stage4a")),
    }
    summary["recommendation"] = _full_resume_recommendation(summary)
    return summary


def render_full_resume_report(*, summary: dict[str, Any], per_paper_summary: list[dict[str, Any]]) -> str:
    lines = [
        "# Full Pipeline Resume Report",
        "",
        "## Overall",
        f"- total_papers: {summary['total_papers']}",
        f"- completed_before: {summary['completed_before']}",
        f"- completed_after: {summary['completed_after']}",
        f"- partial_before: {summary['partial_before']}",
        f"- partial_after: {summary['partial_after']}",
        f"- failed_papers: {summary['failed_papers']}",
        f"- stage2_run_count: {summary['stage2_run_count']}",
        f"- stage3_run_count: {summary['stage3_run_count']}",
        f"- stage4a_run_count: {summary['stage4a_run_count']}",
        f"- stage5_run_count: {summary['stage5_run_count']}",
        f"- stage55_run_count: {summary['stage55_run_count']}",
        f"- llm_call_stages_count: {summary['llm_call_stages_count']}",
        f"- vlm_call_stages_count: {summary['vlm_call_stages_count']}",
        f"- recommendation: {summary['recommendation']}",
        "",
        "## Per Paper",
    ]
    for item in per_paper_summary:
        lines.extend(
            [
                "",
                f"### {item['paper_id']}",
                f"- status before: {item['status_before']}",
                f"- actions: {json.dumps(item['planned_actions'], ensure_ascii=False)}",
                f"- status after: {item['status_after']}",
                f"- failed reason: {item.get('failed_reason') or 'none'}",
                f"- output summary: {json.dumps(item.get('output_summary', {}), ensure_ascii=False)}",
                f"- recommendation: {item.get('recommendation')}",
                f"- remaining blockers: {json.dumps(item.get('remaining_blockers', []), ensure_ascii=False)}",
            ]
        )
    blockers_stage3 = [item["paper_id"] for item in per_paper_summary if not item["stage_status_after"].get("stage3")]
    blockers_stage4a = [item["paper_id"] for item in per_paper_summary if not item["stage_status_after"].get("stage4a")]
    lines.extend(
        [
            "",
            "## Remaining Blockers",
            f"- papers_missing_stage3: {json.dumps(blockers_stage3, ensure_ascii=False)}",
            f"- papers_missing_stage4a: {json.dumps(blockers_stage4a, ensure_ascii=False)}",
            "",
            "## Readiness",
            f"- recommendation: {summary['recommendation']}",
        ]
    )
    return "\n".join(lines)


def _execute_full_resume_plan(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
    plan: dict[str, str],
    max_stage4a_figures_per_paper: int,
    stage4a_figure_types: tuple[str, ...],
    stage3_subdir: str,
    stage4_subdir: str,
    stage4_routing_mode: str,
    stage4_candidate_source: str,
    stage4_figure_ids: list[str] | None,
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
    for stage in STAGE_ORDER:
        action = plan.get(stage)
        if not action:
            continue
        if action.startswith("skip_") or action.startswith("pending_"):
            logs.append({"paper_id": paper_id, "stage": stage, "action": action, "status": "skipped" if action.startswith("skip_") else "pending"})
            continue
        log_item = {"paper_id": paper_id, "stage": stage, "action": action, "status": "pending"}
        try:
            if stage == "stage2":
                _run_stage2_refresh(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
            elif stage == "stage3":
                live_ready, reason = _stage3_live_ready(project_root)
                if not live_ready:
                    log_item["status"] = "pending"
                    log_item["reason"] = reason
                    logs.append(log_item)
                    current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
                    continue
                _run_stage3_live(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
            elif stage == "stage4a":
                current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
                if not current_status["stage3"]["completed"]:
                    log_item["status"] = "pending"
                    log_item["reason"] = "stage3_not_complete"
                    logs.append(log_item)
                    continue
                live_ready, reason = _stage4a_live_ready()
                if not live_ready:
                    log_item["status"] = "pending"
                    log_item["reason"] = reason
                    logs.append(log_item)
                    continue
                stage4_summary = _run_stage4a_live(
                    paper_id=paper_id,
                    output_dir=output_dir,
                    stage3_subdir=stage3_subdir,
                    stage4_subdir=stage4_subdir,
                    routing_mode=stage4_routing_mode,
                    candidate_source=stage4_candidate_source,
                    figure_ids=stage4_figure_ids,
                    max_figures=max_stage4a_figures_per_paper,
                )
                log_item["figure_ids"] = list(stage4_figure_ids or [])
                if bool(stage4_summary.get("not_applicable")) or int(stage4_summary.get("total_candidates") or 0) == 0:
                    log_item["status"] = "not_applicable"
                    log_item["reason"] = "no_stage2_selected_candidates"
                    logs.append(log_item)
                    continue
            elif stage == "stage5":
                current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
                if not current_status["stage3"]["completed"]:
                    log_item["status"] = "pending"
                    log_item["reason"] = "stage3_not_complete"
                    logs.append(log_item)
                    continue
                bundle = run_stage5_dataset_fusion(paper_id=paper_id, output_dir=output_dir)
                export_fusion_outputs(bundle, output_dir / "final_dataset")
            elif stage == "stage55":
                current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
                if not current_status["stage5"]["completed"]:
                    log_item["status"] = "pending"
                    log_item["reason"] = "stage5_not_complete"
                    logs.append(log_item)
                    continue
                if action == "run_stage55_live":
                    live_ready, reason = _linking_live_ready()
                    if not live_ready:
                        log_item["status"] = "pending"
                        log_item["reason"] = reason
                        logs.append(log_item)
                        continue
                    _run_stage55(output_dir=output_dir, live=True)
                else:
                    _run_stage55(output_dir=output_dir, live=False)
            current_status = detect_stage_status(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
            log_item["status"] = "completed" if current_status[stage]["completed"] else "failed"
        except Exception as exc:  # pragma: no cover - integration guard
            log_item["status"] = "failed"
            log_item["error"] = f"{type(exc).__name__}: {exc}"
        logs.append(log_item)
    return logs


def _run_stage2_refresh(*, project_root: Path, paper_id: str, markdown_path: Path, output_dir: Path) -> None:
    settings = build_runtime_settings_loader(project_root)
    pdf_dir = resolve_project_path(project_root, settings.get("paths", {}).get("pdf_dir", "data/pdfs"))
    input_pdf = pdf_dir / f"{paper_id}.pdf"
    run_stage2_figure_pipeline(
        project_root=project_root,
        settings=settings,
        input_pdf=input_pdf,
        paper_id=paper_id,
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
    )


def _stage3_live_ready(project_root: Path) -> tuple[bool, str | None]:
    try:
        settings = build_runtime_settings(project_root, project_root / "settings.yaml")
        dspy_settings = dict(settings.get("dspy", {}))
        resolve_dspy_runtime_config(dspy_settings)
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"missing_stage3_runtime: {exc}"


def _run_stage3_live(*, project_root: Path, paper_id: str, markdown_path: Path, output_dir: Path) -> None:
    settings = build_runtime_settings(project_root, project_root / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = True
    settings.setdefault("stage3", {})
    settings["stage3"]["dry_run_validator"] = False
    run_stage3_dspy_smoke_test(
        project_root=project_root,
        settings=settings,
        paper_id=paper_id,
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
        paper_text_limit_chars=None,
        max_experiment_series=1,
        section_aware=False,
        section_method="rule",
        max_sections=6,
        section_keywords=DEFAULT_STAGE3_SECTION_KEYWORDS,
    )


def _stage4a_live_ready() -> tuple[bool, str | None]:
    client = VisionLanguageModelClient(dry_run=False)
    if not client.api_key:
        return False, "missing_stage4a_api_key"
    if not client.base_url:
        return False, "missing_stage4a_base_url"
    return True, None


def _select_stage4_figure_ids(
    *,
    paper_id: str,
    output_dir: Path,
    max_figures: int = 4,
    allowed_figure_types: tuple[str, ...] | None = None,
) -> list[str]:
    """Legacy compatibility helper for the old Stage4A pre-selection flow."""
    from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor

    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=output_dir,
        max_figures=max_figures,
        allowed_figure_types=set(allowed_figure_types or STAGE4_PRIORITY_TYPES),
        dry_run=True,
    )
    figures = read_jsonl(output_dir / "figures.jsonl")
    vision_inputs = read_jsonl(output_dir / "vision_inputs.jsonl")
    evidence_objects = read_jsonl(output_dir / "stage3_dspy_smoke" / "evidence_objects.jsonl")
    stage3_schema = read_json(output_dir / "stage3_dspy_smoke" / "paper_extraction.schema_v2.json", default={}) or {}
    candidates = extractor._select_candidates(  # pyright: ignore[reportPrivateUsage]
        figures=figures,
        vision_inputs=vision_inputs,
        evidence_objects=evidence_objects,
        stage3_schema=stage3_schema,
    )
    sendable = [item for item in candidates if item.get("send_to_vlm")]
    priority_order = allowed_figure_types or STAGE4_PRIORITY_TYPES
    priority_map = {name: index for index, name in enumerate(priority_order)}
    sendable.sort(key=lambda item: (priority_map.get(str(item.get("figure_type") or "unknown"), 999), str(item.get("figure_id") or "")))
    return [str(item.get("figure_id")) for item in sendable[:max_figures] if item.get("figure_id")]


def _run_stage4a_live(
    *,
    paper_id: str,
    output_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    figure_ids: list[str] | None = None,
    max_figures: int = 0,
) -> dict[str, Any]:
    summary = run_stage4_for_paper(
        paper_id=paper_id,
        paper_output_dir=output_dir,
        dry_run=False,
        force_stage4=False,
        stage4_figure_ids=figure_ids,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        routing_mode=routing_mode,
        candidate_source=candidate_source,
        max_figures_per_paper=max_figures,
    )
    stage4_dir = output_dir / stage4_subdir
    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))
    write_stage4_quality_review(
        review_payload,
        output_md=stage4_dir / "stage4_quality_review.md",
        output_json=stage4_dir / "stage4_quality_review.json",
    )
    return summary


def _write_stage4a_not_applicable(*, paper_id: str, output_dir: Path) -> None:
    """Legacy compatibility writer for historical Stage4A paths."""
    stage4_dir = output_dir / "stage4_vision_spectra"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "paper_id": paper_id,
        "total_candidates": 0,
        "processed_count": 0,
        "skipped_count": 0,
        "dry_run_count": 0,
        "live_count": 0,
        "validation_error_count": 0,
        "failed_record_count": 0,
        "by_figure_type": {},
        "not_applicable": True,
        "reason": "no_high_value_spectra_candidates",
    }
    review_payload = {
        "summary": {
            "total_records": 0,
            "failed_record_count": 0,
            "validation_error_count": 0,
            "source_distribution": {},
            "overall_status": "not_applicable",
        },
        "figures": [],
        "global_warnings": [{"figure_id": None, "warning": "stage4a_not_applicable"}],
    }
    write_jsonl([], stage4_dir / "stage4_candidates.jsonl")
    write_jsonl([], stage4_dir / "stage4_prompts.jsonl")
    write_jsonl([], stage4_dir / "spectra_extractions.jsonl")
    write_jsonl([], stage4_dir / "raw_vlm_outputs.jsonl")
    write_jsonl([], stage4_dir / "failed_records.jsonl")
    _write_json(stage4_dir / "stage4_summary.json", summary)
    write_stage4_quality_review(
        review_payload,
        output_md=stage4_dir / "stage4_quality_review.md",
        output_json=stage4_dir / "stage4_quality_review.json",
    )


def _linking_live_ready() -> tuple[bool, str | None]:
    linker = EvidenceSpectraParameterLinker(dry_run=False)
    if not linker.api_key:
        return False, "missing_linking_api_key"
    if not linker.base_url:
        return False, "missing_linking_base_url"
    return True, None


def _run_stage55(*, output_dir: Path, live: bool) -> None:
    final_dataset_dir = output_dir / "final_dataset"
    linking_dir = final_dataset_dir / "linking"
    inputs = load_final_dataset_inputs(final_dataset_dir)
    candidates = build_link_candidates(
        inputs["paper"],
        inputs["parameters"],
        inputs["evidence"],
        inputs["spectra"],
        inputs["samples"],
        process_steps=inputs.get("process_steps"),
        link_types=DEFAULT_LINK_FAMILIES,
        max_candidates_per_type=100,
    )
    deterministic_links, unmatched_candidates = build_deterministic_links(candidates)
    accepted_links = list(deterministic_links)
    rejected_links: list[dict[str, Any]] = []
    raw_llm_outputs: list[dict[str, Any]] = []
    invalid_source_id_count = 0
    invalid_target_id_count = 0

    if live:
        llm_candidate_pool = [item for item in candidates if item.get("needs_llm")]
        linker = EvidenceSpectraParameterLinker(dry_run=False)
        decisions, raw_llm_outputs, parse_failures = linker.run(
            llm_candidate_pool,
            paper_context=inputs["paper"],
            max_candidates_per_call=min(20, max(1, len(llm_candidate_pool))),
        )
        decisions = sanitize_link_decision_payloads(decisions)
        reviewed, rejected, unmatched, stats = validate_llm_link_decisions(
            llm_candidate_pool,
            decisions,
            starting_index=len(accepted_links) + 1,
        )
        accepted_links.extend(reviewed)
        rejected_links.extend(rejected)
        unmatched_candidates = merge_live_unmatched_candidates(unmatched_candidates, llm_candidate_pool, unmatched)
        rejected_links.extend(parse_failures)
        invalid_source_id_count = stats["invalid_source_id_count"]
        invalid_target_id_count = stats["invalid_target_id_count"]

    summary = build_linking_summary(
        candidates=candidates,
        accepted_links=accepted_links,
        rejected_links=rejected_links,
        unmatched_candidates=unmatched_candidates,
        raw_llm_outputs=raw_llm_outputs,
        invalid_source_id_count=invalid_source_id_count,
        invalid_target_id_count=invalid_target_id_count,
    )
    report = render_linking_report(
        file_presence={
            "paper": (final_dataset_dir / "paper.json").exists(),
            "samples": (final_dataset_dir / "samples.jsonl").exists(),
            "parameters": (final_dataset_dir / "parameters.jsonl").exists(),
            "evidence": (final_dataset_dir / "evidence.jsonl").exists(),
            "spectra": (final_dataset_dir / "spectra.jsonl").exists(),
            "quality_summary": (final_dataset_dir / "quality_summary.json").exists(),
            "fusion_report": (final_dataset_dir / "fusion_report.md").exists(),
            "figures": (final_dataset_dir / "figures.jsonl").exists(),
        },
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=rejected_links,
        summary=summary,
    )
    export_linking_outputs(
        linking_dir,
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=rejected_links,
        raw_llm_outputs=raw_llm_outputs,
        summary=summary,
        report=report,
    )


def _paper_status(status: dict[str, Any]) -> str:
    completed = [_compact_stage_status(status).get(stage) for stage in STAGE_ORDER]
    if all(completed):
        return "complete"
    if any(completed):
        return "partial"
    return "skipped"


def _compact_stage_status(status: dict[str, Any]) -> dict[str, bool]:
    return {
        "stage2": bool(status["stage2"]["completed"]),
        "stage3": bool(status["stage3"]["completed"]),
        "stage4a": bool(status["stage4a"]["completed"]),
        "stage5": bool(status["stage5"]["completed"]),
        "stage55": bool(status["stage55"]["completed"]),
    }


def _remaining_blockers(status: dict[str, Any], plan: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    for stage in STAGE_ORDER:
        if not status[stage]["completed"]:
            blockers.append(plan.get(stage, f"missing_{stage}"))
    return blockers


def _build_output_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage3_schema_valid": status["stage3"].get("schema_valid"),
        "stage4_total_records": status["stage4a"].get("total_records"),
        "stage5_invalid_canonical_key_count": status["stage5"].get("invalid_canonical_key_count"),
        "stage55_invalid_source_id_count": status["stage55"].get("invalid_source_id_count"),
        "stage55_invalid_target_id_count": status["stage55"].get("invalid_target_id_count"),
    }


def _paper_recommendation(status: dict[str, Any]) -> str:
    compact = _compact_stage_status(status)
    if all(compact.values()):
        return "usable"
    if not compact["stage3"]:
        return "pending_stage3_live"
    if not compact["stage4a"]:
        return "pending_stage4a_live"
    return "hold_for_manual_review"


def _count_action(entries: list[dict[str, Any]], stage: str, status: str) -> int:
    return sum(1 for entry in entries if entry.get("stage") == stage and entry.get("status") == status)


def _count_model_stage_calls(entries: list[dict[str, Any]], live_actions: set[str]) -> int:
    return sum(
        1
        for entry in entries
        if entry.get("status") == "completed" and entry.get("action") in live_actions
    )


def _full_resume_recommendation(summary: dict[str, Any]) -> str:
    if summary["remaining_pending_stage3_count"] or summary["remaining_pending_stage4a_count"]:
        return "not_ready_for_10_20_papers"
    if summary["failed_actions_count"]:
        return "stabilize_failed_actions_first"
    if summary["completed_after"] <= summary["completed_before"]:
        return "expand_only_after_more_live_coverage"
    return "ready_for_careful_scale_out"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
