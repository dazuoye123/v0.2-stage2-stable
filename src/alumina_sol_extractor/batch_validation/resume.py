"""Legacy compatibility layer for runtime resume helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alumina_sol_extractor.pipeline import resume_status as _impl


build_runtime_settings = _impl.build_runtime_settings
resolve_project_path = _impl.resolve_project_path
export_fusion_outputs = _impl.export_fusion_outputs
run_stage5_dataset_fusion = _impl.run_stage5_dataset_fusion
read_json = _impl.read_json
build_deterministic_links = _impl.build_deterministic_links
build_link_candidates = _impl.build_link_candidates
load_final_dataset_inputs = _impl.load_final_dataset_inputs
export_linking_outputs = _impl.export_linking_outputs
render_linking_report = _impl.render_linking_report
build_linking_summary = _impl.build_linking_summary
run_stage2_figure_pipeline = _impl.run_stage2_figure_pipeline
write_jsonl = _impl.write_jsonl

STAGE2_REQUIRED_FILES = _impl.STAGE2_REQUIRED_FILES
RELEVANCE_KEYWORDS = _impl.RELEVANCE_KEYWORDS
LOW_PRIORITY_KEYWORDS = _impl.LOW_PRIORITY_KEYWORDS
STAGE_ORDER = _impl.STAGE_ORDER

_ORIG_EXECUTE_PLAN = _impl._execute_plan
_ORIG_RUN_STAGE2_REFRESH = _impl._run_stage2_refresh
_ORIG_RUN_STAGE55_DRY_RUN = _impl._run_stage55_dry_run


def _sync_impl() -> None:
    _impl.build_runtime_settings = build_runtime_settings
    _impl.resolve_project_path = resolve_project_path
    _impl.export_fusion_outputs = export_fusion_outputs
    _impl.run_stage5_dataset_fusion = run_stage5_dataset_fusion
    _impl.read_json = read_json
    _impl.build_deterministic_links = build_deterministic_links
    _impl.build_link_candidates = build_link_candidates
    _impl.load_final_dataset_inputs = load_final_dataset_inputs
    _impl.export_linking_outputs = export_linking_outputs
    _impl.render_linking_report = render_linking_report
    _impl.build_linking_summary = build_linking_summary
    _impl.run_stage2_figure_pipeline = run_stage2_figure_pipeline
    _impl.write_jsonl = write_jsonl
    _impl.STAGE2_REQUIRED_FILES = STAGE2_REQUIRED_FILES
    _impl.RELEVANCE_KEYWORDS = RELEVANCE_KEYWORDS
    _impl.LOW_PRIORITY_KEYWORDS = LOW_PRIORITY_KEYWORDS
    _impl.STAGE_ORDER = STAGE_ORDER
    _impl._execute_plan = _execute_plan
    _impl._run_stage2_refresh = _run_stage2_refresh
    _impl._run_stage55_dry_run = _run_stage55_dry_run


def discover_resume_candidates(
    markdown_dir: Path | str,
    outputs_dir: Path | str,
    *,
    max_papers: int = 5,
) -> list[dict[str, Any]]:
    _sync_impl()
    return _impl.discover_resume_candidates(markdown_dir, outputs_dir, max_papers=max_papers)


def detect_stage_status(
    *,
    project_root: Path | str,
    paper_id: str,
    markdown_path: Path | str | None,
    output_dir: Path | str,
) -> dict[str, Any]:
    _sync_impl()
    return _impl.detect_stage_status(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
    )


build_stage_plan = _impl.build_stage_plan
build_resume_summary = _impl.build_resume_summary
render_resume_report = _impl.render_resume_report


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
    _sync_impl()
    return _impl.run_stage6b_batch_resume(
        project_root=project_root,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=max_papers,
        paper_ids=paper_ids,
        safe=safe,
        live_stage3=live_stage3,
        live_stage4a=live_stage4a,
        live_linking=live_linking,
        allow_stage2_refresh=allow_stage2_refresh,
        force_stage5=force_stage5,
        force_linking=force_linking,
        dry_run_plan_only=dry_run_plan_only,
        output_dir=output_dir,
    )


def _execute_plan(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
    plan: dict[str, str],
    safe: bool,
) -> list[dict[str, Any]]:
    _sync_impl()
    return _ORIG_EXECUTE_PLAN(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
        plan=plan,
        safe=safe,
    )


def _run_stage2_refresh(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE2_REFRESH(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
    )


def _run_stage55_dry_run(*, output_dir: Path) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE55_DRY_RUN(output_dir=output_dir)


_paper_status = _impl._paper_status
_remaining_blockers = _impl._remaining_blockers
_compact_stage_status = _impl._compact_stage_status
_resume_recommendation = _impl._resume_recommendation
_write_json = _impl._write_json
_is_relevant_paper = _impl._is_relevant_paper
_candidate_sort_key = _impl._candidate_sort_key


__all__ = [
    "STAGE2_REQUIRED_FILES",
    "RELEVANCE_KEYWORDS",
    "LOW_PRIORITY_KEYWORDS",
    "STAGE_ORDER",
    "build_resume_summary",
    "build_stage_plan",
    "detect_stage_status",
    "discover_resume_candidates",
    "render_resume_report",
    "run_stage6b_batch_resume",
]
