"""Legacy compatibility layer for the full pipeline runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alumina_sol_extractor.pipeline import full_pipeline_runner as _impl


build_runtime_settings = _impl.build_runtime_settings
build_runtime_settings_loader = _impl.build_runtime_settings_loader
resolve_project_path = _impl.resolve_project_path
export_fusion_outputs = _impl.export_fusion_outputs
run_stage5_dataset_fusion = _impl.run_stage5_dataset_fusion
run_stage3_dspy_smoke_test = _impl.run_stage3_dspy_smoke_test
load_project_dotenv = _impl.load_project_dotenv
resolve_dspy_runtime_config = _impl.resolve_dspy_runtime_config
DEFAULT_LINK_FAMILIES = _impl.DEFAULT_LINK_FAMILIES
build_deterministic_links = _impl.build_deterministic_links
build_link_candidates = _impl.build_link_candidates
load_final_dataset_inputs = _impl.load_final_dataset_inputs
export_linking_outputs = _impl.export_linking_outputs
EvidenceSpectraParameterLinker = _impl.EvidenceSpectraParameterLinker
render_linking_report = _impl.render_linking_report
build_linking_summary = _impl.build_linking_summary
merge_live_unmatched_candidates = _impl.merge_live_unmatched_candidates
sanitize_link_decision_payloads = _impl.sanitize_link_decision_payloads
validate_llm_link_decisions = _impl.validate_llm_link_decisions
run_stage2_figure_pipeline = _impl.run_stage2_figure_pipeline
write_jsonl = _impl.write_jsonl
Stage4VisionSpectraExtractor = _impl.Stage4VisionSpectraExtractor
read_json = _impl.read_json
read_jsonl = _impl.read_jsonl
load_stage4_outputs = _impl.load_stage4_outputs
review_stage4_extractions = _impl.review_stage4_extractions
write_stage4_quality_review = _impl.write_stage4_quality_review
VisionLanguageModelClient = _impl.VisionLanguageModelClient
detect_stage_status = _impl.detect_stage_status
discover_resume_candidates = _impl.discover_resume_candidates

STAGE_ORDER = _impl.STAGE_ORDER
STAGE4_PRIORITY_TYPES = _impl.STAGE4_PRIORITY_TYPES
DEFAULT_STAGE3_SECTION_KEYWORDS = _impl.DEFAULT_STAGE3_SECTION_KEYWORDS

_ORIG_EXECUTE_FULL_RESUME_PLAN = _impl._execute_full_resume_plan
_ORIG_RUN_STAGE2_REFRESH = _impl._run_stage2_refresh
_ORIG_STAGE3_LIVE_READY = _impl._stage3_live_ready
_ORIG_RUN_STAGE3_LIVE = _impl._run_stage3_live
_ORIG_STAGE4A_LIVE_READY = _impl._stage4a_live_ready
_ORIG_SELECT_STAGE4_FIGURE_IDS = _impl._select_stage4_figure_ids
_ORIG_RUN_STAGE4A_LIVE = _impl._run_stage4a_live
_ORIG_WRITE_STAGE4A_NOT_APPLICABLE = _impl._write_stage4a_not_applicable
_ORIG_LINKING_LIVE_READY = _impl._linking_live_ready
_ORIG_RUN_STAGE55 = _impl._run_stage55


def _sync_impl() -> None:
    _impl.build_runtime_settings = build_runtime_settings
    _impl.build_runtime_settings_loader = build_runtime_settings_loader
    _impl.resolve_project_path = resolve_project_path
    _impl.export_fusion_outputs = export_fusion_outputs
    _impl.run_stage5_dataset_fusion = run_stage5_dataset_fusion
    _impl.run_stage3_dspy_smoke_test = run_stage3_dspy_smoke_test
    _impl.load_project_dotenv = load_project_dotenv
    _impl.resolve_dspy_runtime_config = resolve_dspy_runtime_config
    _impl.DEFAULT_LINK_FAMILIES = DEFAULT_LINK_FAMILIES
    _impl.build_deterministic_links = build_deterministic_links
    _impl.build_link_candidates = build_link_candidates
    _impl.load_final_dataset_inputs = load_final_dataset_inputs
    _impl.export_linking_outputs = export_linking_outputs
    _impl.EvidenceSpectraParameterLinker = EvidenceSpectraParameterLinker
    _impl.render_linking_report = render_linking_report
    _impl.build_linking_summary = build_linking_summary
    _impl.merge_live_unmatched_candidates = merge_live_unmatched_candidates
    _impl.sanitize_link_decision_payloads = sanitize_link_decision_payloads
    _impl.validate_llm_link_decisions = validate_llm_link_decisions
    _impl.run_stage2_figure_pipeline = run_stage2_figure_pipeline
    _impl.write_jsonl = write_jsonl
    _impl.Stage4VisionSpectraExtractor = Stage4VisionSpectraExtractor
    _impl.read_json = read_json
    _impl.read_jsonl = read_jsonl
    _impl.load_stage4_outputs = load_stage4_outputs
    _impl.review_stage4_extractions = review_stage4_extractions
    _impl.write_stage4_quality_review = write_stage4_quality_review
    _impl.VisionLanguageModelClient = VisionLanguageModelClient
    _impl.detect_stage_status = detect_stage_status
    _impl.discover_resume_candidates = discover_resume_candidates
    _impl.STAGE_ORDER = STAGE_ORDER
    _impl.STAGE4_PRIORITY_TYPES = STAGE4_PRIORITY_TYPES
    _impl.DEFAULT_STAGE3_SECTION_KEYWORDS = DEFAULT_STAGE3_SECTION_KEYWORDS
    _impl._execute_full_resume_plan = _execute_full_resume_plan
    _impl._run_stage2_refresh = _run_stage2_refresh
    _impl._stage3_live_ready = _stage3_live_ready
    _impl._run_stage3_live = _run_stage3_live
    _impl._stage4a_live_ready = _stage4a_live_ready
    _impl._select_stage4_figure_ids = _select_stage4_figure_ids
    _impl._run_stage4a_live = _run_stage4a_live
    _impl._write_stage4a_not_applicable = _write_stage4a_not_applicable
    _impl._linking_live_ready = _linking_live_ready
    _impl._run_stage55 = _run_stage55


_normalize_stage4a_figure_types = _impl._normalize_stage4a_figure_types
build_full_resume_plan = _impl.build_full_resume_plan
build_full_resume_summary = _impl.build_full_resume_summary
render_full_resume_report = _impl.render_full_resume_report


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
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    _sync_impl()
    return _impl.run_stage6c_full_resume(
        project_root=project_root,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=max_papers,
        paper_ids=paper_ids,
        auto_complete=auto_complete,
        allow_stage2_refresh=allow_stage2_refresh,
        live_stage3=live_stage3,
        live_stage4a=live_stage4a,
        live_linking=live_linking,
        force_stage3=force_stage3,
        force_stage4a=force_stage4a,
        force_stage5=force_stage5,
        force_linking=force_linking,
        stop_on_error=stop_on_error,
        dry_run_plan_only=dry_run_plan_only,
        max_stage4a_figures_per_paper=max_stage4a_figures_per_paper,
        max_stage3_papers=max_stage3_papers,
        max_stage4a_papers=max_stage4a_papers,
        max_total_model_calls=max_total_model_calls,
        stage4a_figure_types=stage4a_figure_types,
        output_dir=output_dir,
    )


def _execute_full_resume_plan(
    *,
    project_root: Path,
    paper_id: str,
    markdown_path: Path,
    output_dir: Path,
    plan: dict[str, str],
    max_stage4a_figures_per_paper: int,
    stage4a_figure_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    _sync_impl()
    return _ORIG_EXECUTE_FULL_RESUME_PLAN(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
        plan=plan,
        max_stage4a_figures_per_paper=max_stage4a_figures_per_paper,
        stage4a_figure_types=stage4a_figure_types,
    )


def _run_stage2_refresh(*, project_root: Path, paper_id: str, markdown_path: Path, output_dir: Path) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE2_REFRESH(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
    )


def _stage3_live_ready(project_root: Path) -> tuple[bool, str | None]:
    _sync_impl()
    return _ORIG_STAGE3_LIVE_READY(project_root)


def _run_stage3_live(*, project_root: Path, paper_id: str, markdown_path: Path, output_dir: Path) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE3_LIVE(
        project_root=project_root,
        paper_id=paper_id,
        markdown_path=markdown_path,
        output_dir=output_dir,
    )


def _stage4a_live_ready() -> tuple[bool, str | None]:
    _sync_impl()
    return _ORIG_STAGE4A_LIVE_READY()


def _select_stage4_figure_ids(
    *,
    paper_id: str,
    output_dir: Path,
    max_figures: int = 4,
    allowed_figure_types: tuple[str, ...] | None = None,
) -> list[str]:
    _sync_impl()
    return _ORIG_SELECT_STAGE4_FIGURE_IDS(
        paper_id=paper_id,
        output_dir=output_dir,
        max_figures=max_figures,
        allowed_figure_types=allowed_figure_types,
    )


def _run_stage4a_live(
    *,
    paper_id: str,
    output_dir: Path,
    figure_ids: list[str],
    allowed_figure_types: tuple[str, ...] | None = None,
) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE4A_LIVE(
        paper_id=paper_id,
        output_dir=output_dir,
        figure_ids=figure_ids,
        allowed_figure_types=allowed_figure_types,
    )


def _write_stage4a_not_applicable(*, paper_id: str, output_dir: Path) -> None:
    _sync_impl()
    _ORIG_WRITE_STAGE4A_NOT_APPLICABLE(paper_id=paper_id, output_dir=output_dir)


def _linking_live_ready() -> tuple[bool, str | None]:
    _sync_impl()
    return _ORIG_LINKING_LIVE_READY()


def _run_stage55(*, output_dir: Path, live: bool) -> None:
    _sync_impl()
    _ORIG_RUN_STAGE55(output_dir=output_dir, live=live)


_paper_status = _impl._paper_status
_compact_stage_status = _impl._compact_stage_status
_remaining_blockers = _impl._remaining_blockers
_build_output_summary = _impl._build_output_summary
_paper_recommendation = _impl._paper_recommendation
_count_action = _impl._count_action
_count_model_stage_calls = _impl._count_model_stage_calls
_full_resume_recommendation = _impl._full_resume_recommendation
_write_json = _impl._write_json


__all__ = [
    "STAGE_ORDER",
    "STAGE4_PRIORITY_TYPES",
    "DEFAULT_STAGE3_SECTION_KEYWORDS",
    "build_full_resume_plan",
    "build_full_resume_summary",
    "render_full_resume_report",
    "run_stage6c_full_resume",
]
