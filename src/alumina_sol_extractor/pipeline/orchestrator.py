from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import export_batch_link_aware_dataset
from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs, write_json, write_markdown
from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion
from alumina_sol_extractor.dataset_fusion.link_aware_export import generate_link_aware_exports
from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates, load_final_dataset_inputs
from alumina_sol_extractor.linking.exporters import export_linking_outputs
from alumina_sol_extractor.linking.report import render_linking_report
from alumina_sol_extractor.linking.validators import build_linking_summary
from alumina_sol_extractor.pipeline.full_pipeline_runner import run_full_pipeline_orchestrated
from alumina_sol_extractor.pipeline.resume_status import discover_resume_candidates
from alumina_sol_extractor.pipeline.stage1_pdf_to_markdown import run_stage1_pdf_to_markdown

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_paper_output_dir(outputs_dir: Path, paper_id: str) -> Path:
    direct = outputs_dir / paper_id
    if direct.exists():
        return direct
    matches = [
        category_dir / paper_id
        for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir())
        if (category_dir / paper_id).exists()
    ]
    if matches:
        return matches[0]
    return direct


def _discover_target_papers(
    *,
    markdown_dir: Path | None,
    outputs_dir: Path,
    paper_ids: list[str] | None,
    max_papers: int,
    pdf_dir: Path | None,
) -> list[str]:
    if paper_ids:
        return list(dict.fromkeys(paper_ids))
    discovered: list[str] = []
    if markdown_dir and markdown_dir.exists():
        discovered = [item["paper_id"] for item in discover_resume_candidates(markdown_dir, outputs_dir, max_papers=max_papers)]
    if not discovered and pdf_dir and pdf_dir.exists():
        discovered = [path.stem for path in sorted(pdf_dir.glob("*.pdf"), key=lambda item: item.name)[:max_papers]]
    return discovered[:max_papers]


def _run_stage1_for_missing_markdown(
    *,
    paper_ids: list[str],
    markdown_dir: Path | None,
    pdf_dir: Path | None,
    stage1_runner: Callable[[Path, dict[str, Any]], Any] = run_stage1_pdf_to_markdown,
) -> list[dict[str, Any]]:
    if not paper_ids or not markdown_dir or not pdf_dir:
        return []
    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    stage1_runs: list[dict[str, Any]] = []
    for paper_id in paper_ids:
        markdown_path = markdown_dir / f"{paper_id}.md"
        if markdown_path.exists():
            continue
        pdf_path = pdf_dir / f"{paper_id}.pdf"
        if not pdf_path.exists():
            stage1_runs.append({"paper_id": paper_id, "status": "pending", "reason": "missing_pdf_for_stage1"})
            continue
        stage1_settings = copy.deepcopy(settings)
        stage1_settings.setdefault("paths", {})
        stage1_settings["paths"]["input_pdf"] = str(pdf_path)
        result = stage1_runner(PROJECT_ROOT, stage1_settings)
        stage1_runs.append(
            {
                "paper_id": paper_id,
                "status": "completed",
                "cleaned_markdown_path": str(result.cleaned_markdown_path),
                "output_dir": str(result.output_dir),
            }
        )
    return stage1_runs


def _build_run_summary(
    *,
    stage1_runs: list[dict[str, Any]],
    full_resume_result: dict[str, Any],
    exports: list[dict[str, Any]],
    batch_export: dict[str, Any] | None,
) -> dict[str, Any]:
    export_summary = {
        row["paper_id"]: row["summary"]
        for row in exports
    }
    return {
        "stage1_runs": stage1_runs,
        "full_resume_summary": full_resume_result.get("full_resume_summary", {}),
        "exported_papers": len(exports),
        "papers_with_link_aware_exports": sorted(export_summary.keys()),
        "per_paper_link_aware_summary": export_summary,
        "batch_export_summary": batch_export.get("summary") if batch_export else None,
    }


def _build_run_report(
    *,
    paper_ids: list[str],
    stage1_runs: list[dict[str, Any]],
    full_resume_result: dict[str, Any],
    exports: list[dict[str, Any]],
    batch_export: dict[str, Any] | None,
    include_showcase: bool,
) -> str:
    resume_summary = full_resume_result.get("full_resume_summary", {})
    lines = [
        "# Full Pipeline Run Report",
        "",
        "## Overall",
        f"- papers_requested: {len(paper_ids)}",
        f"- stage1_runs: {len([row for row in stage1_runs if row.get('status') == 'completed'])}",
        f"- completed_after_resume: {resume_summary.get('completed_after', 0)}",
        f"- partial_after_resume: {resume_summary.get('partial_after', 0)}",
        f"- failed_papers: {resume_summary.get('failed_papers', 0)}",
        f"- link_aware_exports_generated: {len(exports)}",
        f"- showcase_enabled: {include_showcase}",
        "",
        "## Per Paper",
    ]
    per_paper = {row["paper_id"]: row for row in full_resume_result.get("per_paper_summary", [])}
    export_map = {row["paper_id"]: row for row in exports}
    for paper_id in paper_ids:
        resume_row = per_paper.get(paper_id, {})
        export_row = export_map.get(paper_id, {})
        lines.extend(
            [
                "",
                f"### {paper_id}",
                f"- status_before: {resume_row.get('status_before')}",
                f"- status_after: {resume_row.get('status_after')}",
                f"- completed_stages: {', '.join(resume_row.get('completed_stages_after', [])) or 'none'}",
                f"- failed_reason: {resume_row.get('failed_reason') or 'none'}",
                f"- link_aware_exported: {'yes' if export_row else 'no'}",
            ]
        )
        if export_row:
            summary = export_row.get("summary", {})
            lines.extend(
                [
                    f"- parameters_with_any_link: {summary.get('parameters_with_any_link', 0)}",
                    f"- parameters_with_evidence_link: {summary.get('parameters_with_evidence_link', 0)}",
                    f"- parameters_with_spectra_link: {summary.get('parameters_with_spectra_link', 0)}",
                ]
            )
    if batch_export:
        lines.extend(
            [
                "",
                "## Batch Export",
                f"- output_dir: {batch_export.get('output_dir')}",
                f"- showcase_rows: {batch_export.get('summary', {}).get('showcase_rows', 0)}",
            ]
        )
    return "\n".join(lines)


def _run_stage5_and_stage55_dry_run(
    *,
    outputs_dir: Path,
    paper_ids: list[str],
    include_showcase: bool,
    export_link_aware: bool,
    link_exporter: Callable[..., dict[str, Any]] = generate_link_aware_exports,
    batch_exporter: Callable[..., dict[str, Any]] = export_batch_link_aware_dataset,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    per_paper_summary: list[dict[str, Any]] = []
    exports: list[dict[str, Any]] = []

    for paper_id in paper_ids:
        paper_output_dir = _resolve_paper_output_dir(outputs_dir, paper_id)
        final_dataset_dir = paper_output_dir / "final_dataset"
        if not paper_output_dir.exists():
            per_paper_summary.append(
                {
                    "paper_id": paper_id,
                    "status_before": "missing_output_dir",
                    "status_after": "failed",
                    "completed_stages_after": [],
                    "failed_reason": "missing_output_dir",
                }
            )
            continue

        bundle = run_stage5_dataset_fusion(paper_id=paper_id, output_dir=paper_output_dir)
        export_fusion_outputs(bundle, final_dataset_dir)

        linking_dir = final_dataset_dir / "linking"
        inputs = load_final_dataset_inputs(final_dataset_dir)
        candidates = build_link_candidates(
            inputs["paper"],
            inputs["parameters"],
            inputs["evidence"],
            inputs["spectra"],
            inputs["samples"],
            process_steps=inputs.get("process_steps"),
        )
        accepted_links, unmatched_candidates = build_deterministic_links(candidates)
        rejected_links: list[dict[str, Any]] = []
        raw_llm_outputs: list[dict[str, Any]] = []
        summary = build_linking_summary(
            candidates=candidates,
            accepted_links=accepted_links,
            rejected_links=rejected_links,
            unmatched_candidates=unmatched_candidates,
            raw_llm_outputs=raw_llm_outputs,
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

        if export_link_aware:
            exports.append(
                link_exporter(
                    final_dataset_dir,
                    paper_id=paper_id,
                    project_root=PROJECT_ROOT,
                    include_showcase=include_showcase,
                )
            )
        per_paper_summary.append(
            {
                "paper_id": paper_id,
                "status_before": "existing_final_dataset",
                "status_after": "complete",
                "completed_stages_after": ["stage5", "stage55"],
                "failed_reason": None,
            }
        )

    batch_export = None
    if export_link_aware and exports:
        batch_export = batch_exporter(
            outputs_dir,
            output_dir=outputs_dir / "_batch_final_exports",
            paper_ids=paper_ids,
        )

    full_resume_result = {
        "full_resume_summary": {
            "completed_after": sum(1 for row in per_paper_summary if row.get("status_after") == "complete"),
            "partial_after": sum(1 for row in per_paper_summary if row.get("status_after") == "partial"),
            "failed_papers": sum(1 for row in per_paper_summary if row.get("status_after") == "failed"),
        },
        "per_paper_summary": per_paper_summary,
    }
    return full_resume_result, exports, batch_export


def run_full_pipeline(
    *,
    pdf_dir: Path | None,
    markdown_dir: Path | None,
    outputs_dir: Path,
    paper_ids: list[str] | None,
    max_papers: int,
    auto_complete: bool,
    allow_stage1: bool,
    allow_stage2_refresh: bool,
    live_stage3: bool,
    live_linking: bool,
    force_stage3: bool,
    force_stage5: bool,
    force_linking: bool,
    export_link_aware: bool,
    dry_run: bool,
    safe: bool,
    max_stage3_papers: int,
    max_total_model_calls: int,
    include_showcase: bool,
    output_dir: Path | None,
    live_stage4: bool | None = None,
    live_stage4a: bool | None = None,
    force_stage4: bool | None = None,
    force_stage4a: bool | None = None,
    max_stage4_papers: int | None = None,
    max_stage4a_papers: int | None = None,
    max_stage4_figures_per_paper: int | None = None,
    max_stage4a_figures_per_paper: int | None = None,
    stage4_figure_types: list[str] | None = None,
    stage4a_figure_types: list[str] | None = None,
    stage4_figure_ids: list[str] | None = None,
    stage3_subdir: str = "stage3_twopass",
    stage4_subdir: str = "stage4_vision_spectra_universal",
    stage4_routing_mode: str = "universal_compact",
    stage4_candidate_source: str = "stage2-selected",
    stage1_runner: Callable[[Path, dict[str, Any]], Any] = run_stage1_pdf_to_markdown,
    full_pipeline_resume_runner: Callable[..., dict[str, Any]] = run_full_pipeline_orchestrated,
    link_exporter: Callable[..., dict[str, Any]] = generate_link_aware_exports,
    batch_exporter: Callable[..., dict[str, Any]] = export_batch_link_aware_dataset,
    stage5_only_runner: Callable[..., tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]] = _run_stage5_and_stage55_dry_run,
) -> dict[str, Any]:
    effective_live_stage4 = live_stage4 if live_stage4 is not None else bool(live_stage4a)
    effective_force_stage4 = force_stage4 if force_stage4 is not None else bool(force_stage4a)
    effective_max_stage4_papers = (
        max_stage4_papers
        if max_stage4_papers is not None
        else (max_stage4a_papers if max_stage4a_papers is not None else 0)
    )
    effective_max_stage4_figures = (
        max_stage4_figures_per_paper
        if max_stage4_figures_per_paper is not None
        else (max_stage4a_figures_per_paper if max_stage4a_figures_per_paper is not None else 0)
    )
    effective_stage4_types = stage4_figure_types if stage4_figure_types is not None else (stage4a_figure_types or [])
    outputs_dir.mkdir(parents=True, exist_ok=True)
    selected_paper_ids = _discover_target_papers(
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        paper_ids=paper_ids,
        max_papers=max_papers,
        pdf_dir=pdf_dir,
    )
    stage1_runs: list[dict[str, Any]] = []
    if allow_stage1 and not dry_run:
        stage1_runs = _run_stage1_for_missing_markdown(
            paper_ids=selected_paper_ids,
            markdown_dir=markdown_dir,
            pdf_dir=pdf_dir,
            stage1_runner=stage1_runner,
        )

    batch_dir = output_dir or PROJECT_ROOT / "data" / "batch_validation" / datetime.now().strftime("%Y%m%d_%H%M%S") / "full_pipeline_run"
    batch_dir.mkdir(parents=True, exist_ok=True)

    if markdown_dir is None:
        if not selected_paper_ids:
            raise ValueError("--paper-ids or --markdown-dir is required to select papers for a Stage 5-only rerun.")
        full_resume_result, exports, batch_export = stage5_only_runner(
            outputs_dir=outputs_dir,
            paper_ids=selected_paper_ids,
            include_showcase=include_showcase,
            export_link_aware=export_link_aware and not dry_run,
            link_exporter=link_exporter,
            batch_exporter=batch_exporter,
        )
    else:
        full_resume_result = full_pipeline_resume_runner(
            project_root=PROJECT_ROOT,
            markdown_dir=markdown_dir,
            outputs_dir=outputs_dir,
            max_papers=max_papers,
            paper_ids=selected_paper_ids or None,
            auto_complete=auto_complete and not safe,
            allow_stage2_refresh=allow_stage2_refresh,
            live_stage3=live_stage3 and not safe,
            live_stage4a=effective_live_stage4 and not safe,
            live_linking=live_linking and not safe,
            force_stage3=force_stage3,
            force_stage4a=effective_force_stage4,
            force_stage5=force_stage5,
            force_linking=force_linking,
            dry_run_plan_only=dry_run,
            max_stage3_papers=max_stage3_papers,
            max_stage4a_papers=effective_max_stage4_papers,
            max_stage4a_figures_per_paper=effective_max_stage4_figures,
            max_total_model_calls=max_total_model_calls,
            stage4a_figure_types=effective_stage4_types,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            stage4_routing_mode=stage4_routing_mode,
            stage4_candidate_source=stage4_candidate_source,
            stage4_figure_ids=stage4_figure_ids,
            output_dir=batch_dir / "stage6c_full_resume",
        )

        exports = []
        if export_link_aware and not dry_run:
            for paper_id in selected_paper_ids:
                final_dataset_dir = _resolve_paper_output_dir(outputs_dir, paper_id) / "final_dataset"
                if not final_dataset_dir.exists():
                    continue
                exports.append(
                    link_exporter(
                        final_dataset_dir,
                        paper_id=paper_id,
                        project_root=PROJECT_ROOT,
                        include_showcase=include_showcase,
                    )
                )

        batch_export = None
        if export_link_aware and not dry_run and exports:
            batch_export = batch_exporter(
                outputs_dir,
                output_dir=outputs_dir / "_batch_final_exports",
                paper_ids=selected_paper_ids or None,
            )

    summary = _build_run_summary(
        stage1_runs=stage1_runs,
        full_resume_result=full_resume_result,
        exports=exports,
        batch_export=batch_export,
    )
    report = _build_run_report(
        paper_ids=selected_paper_ids,
        stage1_runs=stage1_runs,
        full_resume_result=full_resume_result,
        exports=exports,
        batch_export=batch_export,
        include_showcase=include_showcase,
    )
    write_json(batch_dir / "run_summary.json", summary)
    write_markdown(batch_dir / "run_report.md", report)

    return {
        "paper_ids": selected_paper_ids,
        "stage1_runs": stage1_runs,
        "full_resume_result": full_resume_result,
        "exports": exports,
        "batch_export": batch_export,
        "run_summary": summary,
        "run_report_path": str(batch_dir / "run_report.md"),
    }


def run_full_pipeline_orchestrated(**kwargs: Any) -> dict[str, Any]:
    """Preferred orchestrator entrypoint for the full pipeline."""
    return run_full_pipeline(**kwargs)


__all__ = [
    "run_full_pipeline",
    "run_full_pipeline_orchestrated",
]
