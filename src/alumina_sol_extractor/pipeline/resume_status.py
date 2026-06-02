"""Runtime resume planning helpers for the full pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config.settings_loader import build_runtime_settings, resolve_project_path
from alumina_sol_extractor.stage4.processed_index import is_live_successful_stage4_summary
from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs
from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion
from alumina_sol_extractor.dataset_fusion.loaders import read_json
from alumina_sol_extractor.linking.candidate_builder import (
    build_deterministic_links,
    build_link_candidates,
    load_final_dataset_inputs,
)
from alumina_sol_extractor.linking.exporters import export_linking_outputs
from alumina_sol_extractor.linking.report import render_linking_report
from alumina_sol_extractor.linking.validators import build_linking_summary
from alumina_sol_extractor.pipeline.stage2_figure_pipeline import run_stage2_figure_pipeline
from alumina_sol_extractor.utils.jsonl import write_jsonl


STAGE2_REQUIRED_FILES = ("figures.jsonl", "vision_inputs.jsonl")
RELEVANCE_KEYWORDS = (
    "铝溶胶",
    "氧化铝",
    "Al_2O_3",
    "Al2O3",
    "前驱体",
    "纤维",
    "sol",
    "alumina",
)
LOW_PRIORITY_KEYWORDS = ("example", "excerpt", ".gitkeep")


STAGE_ORDER = ("stage2", "stage3", "stage4a", "stage5", "stage55")
PREFERRED_STAGE3_SUBDIRS = ("stage3_twopass", "stage3_dspy_smoke", "stage3")
PREFERRED_STAGE4_SUBDIRS = ("stage4_vision_spectra_universal", "stage4_vision_spectra")


def _iter_markdown_files(markdown_dir: Path) -> list[Path]:
    return sorted(path for path in markdown_dir.rglob("*.md") if path.is_file())


def _resolve_output_dir(outputs_dir: Path, paper_id: str) -> Path:
    direct = outputs_dir / paper_id
    if direct.exists():
        return direct
    matches = [
        child / paper_id
        for child in sorted(path for path in outputs_dir.iterdir() if path.is_dir())
        if (child / paper_id).exists()
    ]
    if matches:
        return matches[0]
    return direct


def _first_existing_subdir(output_dir: Path, candidates: tuple[str, ...]) -> Path:
    for name in candidates:
        candidate = output_dir / name
        if candidate.exists():
            return candidate
    return output_dir / candidates[0]


def _stage3_summary_path(stage3_dir: Path) -> Path:
    for filename in ("stage3_summary.json", "stage3_smoke_summary.json"):
        path = stage3_dir / filename
        if path.exists():
            return path
    return stage3_dir / "stage3_summary.json"


def _stage4_summary_path(stage4_dir: Path) -> Path:
    for filename in ("stage4a_summary.json", "stage4_summary.json"):
        path = stage4_dir / filename
        if path.exists():
            return path
    return stage4_dir / "stage4a_summary.json"


def discover_resume_candidates(
    markdown_dir: Path | str,
    outputs_dir: Path | str,
    *,
    max_papers: int = 5,
) -> list[dict[str, Any]]:
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    candidates: list[dict[str, Any]] = []
    for markdown_path in _iter_markdown_files(markdown_dir):
        paper_id = markdown_path.stem
        output_dir = _resolve_output_dir(outputs_dir, paper_id)
        stage3_dir = _first_existing_subdir(output_dir, PREFERRED_STAGE3_SUBDIRS)
        stage4_dir = _first_existing_subdir(output_dir, PREFERRED_STAGE4_SUBDIRS)
        has_stage2 = output_dir.exists() and all((output_dir / name).exists() for name in STAGE2_REQUIRED_FILES)
        has_stage3 = _stage3_summary_path(stage3_dir).exists()
        has_stage4a = _stage4_summary_path(stage4_dir).exists()
        has_stage5 = (output_dir / "final_dataset" / "quality_summary.json").exists()
        has_stage55 = (output_dir / "final_dataset" / "linking" / "linking_summary.json").exists()
        missing_inputs: list[str] = []
        if not output_dir.exists():
            missing_inputs.append("output_dir")
        if output_dir.exists() and not has_stage2:
            for name in STAGE2_REQUIRED_FILES:
                if not (output_dir / name).exists():
                    missing_inputs.append(name)
        candidates.append(
            {
                "paper_id": paper_id,
                "markdown_path": str(markdown_path),
                "output_dir": str(output_dir),
                "has_stage2": has_stage2,
                "has_stage3": has_stage3,
                "has_stage4a": has_stage4a,
                "has_stage5": has_stage5,
                "has_stage55": has_stage55,
                "missing_inputs": missing_inputs,
            }
        )
    candidates.sort(key=_candidate_sort_key)
    research_candidates = [item for item in candidates if _is_relevant_paper(item["paper_id"])]
    selected = research_candidates[:max_papers] if research_candidates else candidates[:max_papers]
    return selected


def detect_stage_status(
    *,
    project_root: Path | str,
    paper_id: str,
    markdown_path: Path | str | None,
    output_dir: Path | str,
) -> dict[str, Any]:
    project_root = Path(project_root)
    output_dir = Path(output_dir)
    settings = build_runtime_settings(project_root)
    paths = settings.get("paths", {})
    mineru_raw_root = resolve_project_path(project_root, paths.get("mineru_raw_dir", "data/mineru_raw"))
    markdown = Path(markdown_path) if markdown_path else None
    markdown_exists = bool(markdown and markdown.exists())
    mineru_raw_dir = mineru_raw_root / paper_id
    mineru_raw_exists = mineru_raw_dir.exists()

    stage3_dir = _first_existing_subdir(output_dir, PREFERRED_STAGE3_SUBDIRS)
    stage4_dir = _first_existing_subdir(output_dir, PREFERRED_STAGE4_SUBDIRS)
    stage5_dir = output_dir / "final_dataset"
    stage55_dir = stage5_dir / "linking"

    stage3_summary = read_json(_stage3_summary_path(stage3_dir), default={}) or {}
    stage4_summary = read_json(_stage4_summary_path(stage4_dir), default={}) or {}
    stage5_summary = read_json(stage5_dir / "quality_summary.json", default={}) or {}
    stage55_summary = read_json(stage55_dir / "linking_summary.json", default={}) or {}

    stage2_completed = (output_dir / "figures.jsonl").exists() and (output_dir / "vision_inputs.jsonl").exists()
    stage3_completed = (
        _stage3_summary_path(stage3_dir).exists()
        and any((stage3_dir / name).exists() for name in ("paper_extraction.schema_v2.json", "schema_v2.json"))
        and (stage3_dir / "evidence_objects.jsonl").exists()
        and bool(stage3_summary.get("schema_valid", True))
    )
    stage4_completed = (
        _stage4_summary_path(stage4_dir).exists()
        and (stage4_dir / "spectra_extractions.jsonl").exists()
        and (
            (stage4_dir / "stage4_quality_review.json").exists()
            or (stage4_dir / "stage4_quality_review.md").exists()
            or (stage4_dir / "stage4a_validation_report.md").exists()
        )
        and is_live_successful_stage4_summary(stage4_summary)
    )
    stage5_completed = (
        (stage5_dir / "quality_summary.json").exists()
        and (stage5_dir / "parameters.jsonl").exists()
        and (stage5_dir / "evidence.jsonl").exists()
        and (stage5_dir / "samples.jsonl").exists()
        and (stage5_dir / "fusion_report.md").exists()
        and int(stage5_summary.get("invalid_canonical_key_count") or 0) == 0
    )
    stage55_completed = (
        (stage55_dir / "linking_summary.json").exists()
        and (stage55_dir / "links.jsonl").exists()
        and int(stage55_summary.get("invalid_source_id_count") or 0) == 0
        and int(stage55_summary.get("invalid_target_id_count") or 0) == 0
    )
    return {
        "paper_id": paper_id,
        "markdown_path": str(markdown) if markdown else None,
        "markdown_exists": markdown_exists,
        "output_dir": str(output_dir),
        "output_dir_exists": output_dir.exists(),
        "mineru_raw_dir": str(mineru_raw_dir),
        "mineru_raw_exists": mineru_raw_exists,
        "stage2": {"completed": stage2_completed},
        "stage3": {"completed": stage3_completed, "schema_valid": stage3_summary.get("schema_valid")},
        "stage4a": {"completed": stage4_completed, "total_records": stage4_summary.get("total_records") or stage4_summary.get("processed_count")},
        "stage5": {"completed": stage5_completed, "invalid_canonical_key_count": stage5_summary.get("invalid_canonical_key_count")},
        "stage55": {
            "completed": stage55_completed,
            "invalid_source_id_count": stage55_summary.get("invalid_source_id_count"),
            "invalid_target_id_count": stage55_summary.get("invalid_target_id_count"),
        },
    }


def build_stage_plan(
    status: dict[str, Any],
    *,
    safe: bool,
    live_stage3: bool,
    live_stage4a: bool,
    live_linking: bool,
    allow_stage2_refresh: bool,
    force_stage5: bool,
    force_linking: bool,
) -> dict[str, str]:
    actions: dict[str, str] = {}
    if status["stage2"]["completed"]:
        actions["stage2"] = "skip_stage2"
    elif allow_stage2_refresh and status.get("markdown_exists") and status.get("mineru_raw_exists"):
        actions["stage2"] = "run_stage2_refresh"
    else:
        actions["stage2"] = "pending_stage2_missing_inputs"

    if status["stage3"]["completed"]:
        actions["stage3"] = "skip_stage3"
    elif live_stage3 and not safe:
        actions["stage3"] = "run_stage3"
    else:
        actions["stage3"] = "pending_stage3_requires_llm"

    if status["stage4a"]["completed"]:
        actions["stage4a"] = "skip_stage4a"
    elif actions["stage3"] in {"run_stage3", "pending_stage3_requires_llm"} and not status["stage3"]["completed"]:
        actions["stage4a"] = "pending_stage4a_requires_stage3"
    elif live_stage4a and not safe:
        actions["stage4a"] = "run_stage4a"
    else:
        actions["stage4a"] = "pending_stage4a_requires_vlm"

    if (status["stage5"]["completed"] and not force_stage5 and actions["stage3"] == "skip_stage3" and actions["stage4a"] == "skip_stage4a"):
        actions["stage5"] = "skip_stage5"
    elif status["stage3"]["completed"]:
        actions["stage5"] = "run_stage5"
    else:
        actions["stage5"] = "pending_stage5_requires_stage3"

    if status["stage55"]["completed"] and not force_linking and actions["stage5"] == "skip_stage5":
        actions["stage55"] = "skip_stage55"
    elif actions["stage5"] in {"run_stage5", "skip_stage5"} and (status["stage5"]["completed"] or actions["stage5"] == "run_stage5"):
        actions["stage55"] = "run_stage55_live" if (live_linking and not safe) else "run_stage55_dry_run"
    else:
        actions["stage55"] = "pending_stage55_requires_stage5"
    return actions


def run_stage6b_batch_resume(
    *,
    project_root: Path | str,
    markdown_dir: Path | str,
    outputs_dir: Path | str,
    max_papers: int = 5,
    paper_ids: list[str] | None = None,
    safe: bool = True,
    live_stage3: bool = False,
    live_stage4a: bool = False,
    live_linking: bool = False,
    allow_stage2_refresh: bool = False,
    force_stage5: bool = False,
    force_linking: bool = False,
    dry_run_plan_only: bool = False,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    discovered = discover_resume_candidates(markdown_dir, outputs_dir, max_papers=max_papers)
    if paper_ids:
        allowed = set(paper_ids)
        discovered = [item for item in discovered if item["paper_id"] in allowed]

    batch_dir = Path(output_dir) if output_dir else project_root / "data" / "batch_validation" / datetime.now().strftime("%Y%m%d_%H%M%S") / "stage6b_resume"
    batch_dir.mkdir(parents=True, exist_ok=True)

    resume_candidates: list[dict[str, Any]] = []
    resume_plan: list[dict[str, Any]] = []
    execution_log: list[dict[str, Any]] = []
    per_paper_results: list[dict[str, Any]] = []

    for candidate in discovered:
        paper_id = candidate["paper_id"]
        markdown_path = Path(candidate["markdown_path"]) if candidate.get("markdown_path") else markdown_dir / f"{paper_id}.md"
        output_dir_path = Path(candidate["output_dir"]) if candidate.get("output_dir") else outputs_dir / paper_id
        before = detect_stage_status(
            project_root=project_root,
            paper_id=paper_id,
            markdown_path=markdown_path,
            output_dir=output_dir_path,
        )
        plan = build_stage_plan(
            before,
            safe=safe,
            live_stage3=live_stage3,
            live_stage4a=live_stage4a,
            live_linking=live_linking,
            allow_stage2_refresh=allow_stage2_refresh,
            force_stage5=force_stage5,
            force_linking=force_linking,
        )
        resume_candidates.append(before)
        resume_plan.append({"paper_id": paper_id, "actions": plan})
        executed_actions: list[dict[str, Any]] = []
        if not dry_run_plan_only:
            executed_actions = _execute_plan(
                project_root=project_root,
                paper_id=paper_id,
                markdown_path=markdown_path,
                output_dir=output_dir_path,
                plan=plan,
                safe=safe,
            )
            execution_log.extend(executed_actions)
        after = detect_stage_status(
            project_root=project_root,
            paper_id=paper_id,
            markdown_path=markdown_path,
            output_dir=output_dir_path,
        )
        per_paper_results.append(
            {
                "paper_id": paper_id,
                "stage_status_before": before,
                "planned_actions": plan,
                "executed_actions": executed_actions,
                "stage_status_after": after,
                "remaining_blockers": _remaining_blockers(after, plan),
                "paper_status_after": _paper_status(after),
            }
        )

    _write_json(batch_dir / "resume_candidates.json", resume_candidates)
    _write_json(batch_dir / "resume_plan.json", resume_plan)
    write_jsonl(execution_log, batch_dir / "resume_execution_log.jsonl")
    summary = build_resume_summary(per_paper_results)
    _write_json(batch_dir / "resume_summary.json", summary)
    report = render_resume_report(
        summary=summary,
        per_paper_results=per_paper_results,
        model_calls_enabled=not safe and any([live_stage3, live_stage4a, live_linking]),
    )
    (batch_dir / "resume_report.md").write_text(report, encoding="utf-8")
    return {
        "batch_output_dir": str(batch_dir),
        "resume_candidates": resume_candidates,
        "resume_plan": resume_plan,
        "execution_log": execution_log,
        "resume_summary": summary,
        "resume_report": report,
        "per_paper_results": per_paper_results,
    }


def build_resume_summary(per_paper_results: list[dict[str, Any]]) -> dict[str, Any]:
    skipped = 0
    run = 0
    pending = 0
    failed = 0
    completed_after = 0
    partial_after = 0
    requires_llm = 0
    requires_vlm = 0
    for item in per_paper_results:
        actions = item.get("planned_actions", {})
        for action in actions.values():
            if action.startswith("skip_"):
                skipped += 1
            elif action.startswith("run_"):
                run += 1
            elif action.startswith("pending_"):
                pending += 1
                if "llm" in action:
                    requires_llm += 1
                if "vlm" in action:
                    requires_vlm += 1
        for execution in item.get("executed_actions", []):
            if execution.get("status") == "failed":
                failed += 1
        paper_status = item.get("paper_status_after")
        if paper_status == "complete":
            completed_after += 1
        elif paper_status == "partial":
            partial_after += 1
    return {
        "total_papers": len(per_paper_results),
        "skipped_stages_count": skipped,
        "run_stages_count": run,
        "pending_stages_count": pending,
        "completed_papers_after_resume": completed_after,
        "partial_papers_after_resume": partial_after,
        "requires_llm_count": requires_llm,
        "requires_vlm_count": requires_vlm,
        "failed_actions_count": failed,
    }


def render_resume_report(
    *,
    summary: dict[str, Any],
    per_paper_results: list[dict[str, Any]],
    model_calls_enabled: bool,
) -> str:
    lines = [
        "# Stage 6B Batch Resume Report",
        "",
        "## Overall",
        f"- total_papers: {summary['total_papers']}",
        f"- skipped_stages_count: {summary['skipped_stages_count']}",
        f"- run_stages_count: {summary['run_stages_count']}",
        f"- pending_stages_count: {summary['pending_stages_count']}",
        f"- completed_papers_after_resume: {summary['completed_papers_after_resume']}",
        f"- partial_papers_after_resume: {summary['partial_papers_after_resume']}",
        f"- requires_llm_count: {summary['requires_llm_count']}",
        f"- requires_vlm_count: {summary['requires_vlm_count']}",
        f"- failed_actions_count: {summary['failed_actions_count']}",
        f"- model_calls_enabled: {str(model_calls_enabled).lower()}",
        "",
        "## Per Paper",
    ]
    for item in per_paper_results:
        lines.extend(
            [
                "",
                f"### {item['paper_id']}",
                f"- stage status before: {json.dumps(_compact_stage_status(item['stage_status_before']), ensure_ascii=False)}",
                f"- planned actions: {json.dumps(item['planned_actions'], ensure_ascii=False)}",
                f"- executed actions: {json.dumps(item['executed_actions'], ensure_ascii=False)}",
                f"- stage status after: {json.dumps(_compact_stage_status(item['stage_status_after']), ensure_ascii=False)}",
                f"- remaining blockers: {json.dumps(item['remaining_blockers'], ensure_ascii=False)}",
            ]
        )
    lines.extend(
        [
            "",
            "## Next Recommendation",
            f"- recommendation: {_resume_recommendation(summary)}",
            f"- papers_needing_live_stage3: {json.dumps([item['paper_id'] for item in per_paper_results if 'pending_stage3_requires_llm' in item.get('planned_actions', {}).values()], ensure_ascii=False)}",
            f"- papers_needing_live_stage4a: {json.dumps([item['paper_id'] for item in per_paper_results if 'pending_stage4a_requires_vlm' in item.get('planned_actions', {}).values()], ensure_ascii=False)}",
            f"- papers_needing_stage2_refresh: {json.dumps([item['paper_id'] for item in per_paper_results if item.get('planned_actions', {}).get('stage2') == 'run_stage2_refresh'], ensure_ascii=False)}",
        ]
    )
    return "\n".join(lines)


def _execute_plan(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
    plan: dict[str, str],
    safe: bool,
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        action = plan.get(stage)
        if not action or not action.startswith("run_"):
            continue
        log_item = {"paper_id": paper_id, "stage": stage, "action": action, "status": "skipped"}
        try:
            if action == "run_stage2_refresh":
                _run_stage2_refresh(project_root=project_root, paper_id=paper_id, markdown_path=markdown_path, output_dir=output_dir)
            elif action == "run_stage5":
                bundle = run_stage5_dataset_fusion(paper_id=paper_id, output_dir=output_dir)
                export_fusion_outputs(bundle, output_dir / "final_dataset")
            elif action == "run_stage55_dry_run":
                _run_stage55_dry_run(output_dir=output_dir)
            elif action in {"run_stage3", "run_stage4a", "run_stage55_live"}:
                if safe:
                    raise RuntimeError(f"{action} is blocked in safe mode.")
                raise RuntimeError(f"{action} is not implemented in Stage 6B safe pipeline.")
            log_item["status"] = "completed"
        except Exception as exc:  # pragma: no cover - integration guard
            log_item["status"] = "failed"
            log_item["error"] = f"{type(exc).__name__}: {exc}"
        logs.append(log_item)
    return logs


def _run_stage2_refresh(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
) -> None:
    settings = build_runtime_settings(project_root)
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


def _run_stage55_dry_run(*, output_dir: Path) -> None:
    final_dataset_dir = output_dir / "final_dataset"
    inputs = load_final_dataset_inputs(final_dataset_dir)
    candidates = build_link_candidates(
        inputs["paper"],
        inputs["parameters"],
        inputs["evidence"],
        inputs["spectra"],
        inputs["samples"],
        process_steps=inputs.get("process_steps"),
        max_candidates_per_type=100,
    )
    accepted_links, unmatched_candidates = build_deterministic_links(candidates)
    summary = build_linking_summary(
        candidates=candidates,
        accepted_links=accepted_links,
        rejected_links=[],
        unmatched_candidates=unmatched_candidates,
        raw_llm_outputs=[],
        invalid_source_id_count=0,
        invalid_target_id_count=0,
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
        rejected_links=[],
        summary=summary,
    )
    export_linking_outputs(
        final_dataset_dir / "linking",
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=[],
        raw_llm_outputs=[],
        summary=summary,
        report=report,
    )


def _paper_status(status: dict[str, Any]) -> str:
    stage2 = bool(status["stage2"]["completed"])
    stage3 = bool(status["stage3"]["completed"])
    stage4a = bool(status["stage4a"]["completed"])
    stage5 = bool(status["stage5"]["completed"])
    stage55 = bool(status["stage55"]["completed"])
    if stage2 and stage3 and stage4a and stage5 and stage55:
        return "complete"
    if any([stage2, stage3, stage4a, stage5, stage55]):
        return "partial"
    return "skipped"


def _remaining_blockers(status: dict[str, Any], plan: dict[str, str]) -> list[str]:
    blockers: list[str] = []
    for stage in STAGE_ORDER:
        if not status[stage]["completed"]:
            blockers.append(plan.get(stage, f"missing_{stage}"))
    return blockers


def _compact_stage_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage2": status["stage2"]["completed"],
        "stage3": status["stage3"]["completed"],
        "stage4a": status["stage4a"]["completed"],
        "stage5": status["stage5"]["completed"],
        "stage55": status["stage55"]["completed"],
    }


def _resume_recommendation(summary: dict[str, Any]) -> str:
    if summary.get("requires_llm_count") or summary.get("requires_vlm_count"):
        return "not_ready_for_10_20_papers"
    if summary.get("failed_actions_count"):
        return "stabilize_non_model_reruns_first"
    return "safe_to_expand_non_live_validation"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_relevant_paper(name: str) -> bool:
    casefolded = name.casefold()
    return any(keyword.casefold() in casefolded for keyword in RELEVANCE_KEYWORDS)


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    priority = 0 if _is_relevant_paper(candidate["paper_id"]) else 1
    low_priority = 1 if any(token in candidate["paper_id"].casefold() for token in LOW_PRIORITY_KEYWORDS) else 0
    completion_rank = (
        int(bool(candidate.get("has_stage55"))),
        int(bool(candidate.get("has_stage5"))),
        int(bool(candidate.get("has_stage4a"))),
        int(bool(candidate.get("has_stage3"))),
        int(bool(candidate.get("has_stage2"))),
    )
    return (priority, low_priority, tuple(-item for item in completion_rank), candidate["paper_id"].casefold())
