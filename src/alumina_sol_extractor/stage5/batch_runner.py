from __future__ import annotations

import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from alumina_sol_extractor.stage5.dataset_fusion.exporters import export_fusion_outputs, write_json, write_markdown
from alumina_sol_extractor.stage5.dataset_fusion.fusion import run_stage5_dataset_fusion
from alumina_sol_extractor.stage5.dataset_fusion.link_aware_export import generate_link_aware_exports
from alumina_sol_extractor.stage5.dataset_fusion.loaders import load_paper_inputs, read_jsonl
from alumina_sol_extractor.stage5.linking.candidate_builder import (
    build_deterministic_links,
    build_link_candidates,
    load_final_dataset_inputs,
)
from alumina_sol_extractor.stage5.linking.exporters import export_linking_outputs
from alumina_sol_extractor.stage5.linking.report import render_linking_report
from alumina_sol_extractor.stage5.linking.validators import build_linking_summary


DEFAULT_CATEGORIES = ["mechanism", "fiber_process", "applications", "rheology"]
STAGE3_DIR_CANDIDATES = ["stage3_twopass", "stage3", "stage3_dspy_smoke"]
STAGE4_DIR_CANDIDATES = ["stage4_vision_spectra_universal", "stage4_vision_spectra"]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _safe_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            normalized = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, (list, dict)):
                    normalized[key] = json.dumps(value, ensure_ascii=False)
                else:
                    normalized[key] = value
            writer.writerow(normalized)
    return path


def discover_papers(
    outputs_dir: Path,
    *,
    categories: list[str],
    paper_filter: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str]] = set()
    for category in categories:
        category_dir = outputs_dir / category
        if not category_dir.exists():
            continue
        for paper_dir in sorted((item for item in category_dir.iterdir() if item.is_dir()), key=lambda path: path.name):
            paper_id = paper_dir.name
            if paper_filter and paper_filter not in paper_id:
                continue
            key = (category, paper_id, str(paper_dir.resolve()))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "paper_dir": paper_dir,
                }
            )
    for paper_dir in sorted((item for item in outputs_dir.iterdir() if item.is_dir()), key=lambda path: path.name):
        if paper_dir.name.startswith("_") or paper_dir.name in categories:
            continue
        if not any((paper_dir / candidate).exists() for candidate in STAGE3_DIR_CANDIDATES + STAGE4_DIR_CANDIDATES + ["final_dataset"]):
            continue
        paper_id = paper_dir.name
        if paper_filter and paper_filter not in paper_id:
            continue
        key = (None, paper_id, str(paper_dir.resolve()))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "category": "",
                "paper_id": paper_id,
                "paper_dir": paper_dir,
            }
        )
    rows.sort(key=lambda item: (item["category"], item["paper_id"]))
    return rows


def discover_stage_dirs(paper_dir: Path) -> tuple[Path | None, Path | None]:
    stage3_dir = next((paper_dir / name for name in STAGE3_DIR_CANDIDATES if (paper_dir / name).exists()), None)
    stage4_dir = next((paper_dir / name for name in STAGE4_DIR_CANDIDATES if (paper_dir / name).exists()), None)
    return stage3_dir, stage4_dir


def _count_jsonl_rows(path: Path) -> int:
    return len(read_jsonl(path))


def has_complete_stage5_outputs(paper_dir: Path, *, with_linking: bool) -> bool:
    dataset_dir = paper_dir / "final_dataset"
    if not dataset_dir.exists():
        return False
    required = [
        dataset_dir / "stage5_summary.json",
        dataset_dir / "paper.json",
        dataset_dir / "parameters.jsonl",
        dataset_dir / "process_steps.jsonl",
        dataset_dir / "evidence.jsonl",
        dataset_dir / "spectra.jsonl",
        dataset_dir / "quality_summary.json",
        dataset_dir / "fusion_report.md",
    ]
    if with_linking:
        required.extend(
            [
                dataset_dir / "linking" / "links.jsonl",
                dataset_dir / "linking" / "linking_summary.json",
                dataset_dir / "link_aware_exports" / "final_parameters_linked.csv",
                dataset_dir / "link_aware_exports" / "sample_parameter_matrix.csv",
                dataset_dir / "link_aware_exports" / "process_steps_table.csv",
                dataset_dir / "link_aware_exports" / "evidence_parameter_links.csv",
                dataset_dir / "link_aware_exports" / "spectra_parameter_links.csv",
                dataset_dir / "link_aware_exports" / "link_aware_export_summary.json",
            ]
        )
    return all(path.exists() for path in required)


def missing_stage5_outputs(paper_dir: Path, *, with_linking: bool) -> list[str]:
    dataset_dir = paper_dir / "final_dataset"
    required = [
        "final_dataset/stage5_summary.json",
        "final_dataset/paper.json",
        "final_dataset/parameters.jsonl",
        "final_dataset/process_steps.jsonl",
        "final_dataset/evidence.jsonl",
        "final_dataset/spectra.jsonl",
        "final_dataset/quality_summary.json",
        "final_dataset/fusion_report.md",
    ]
    if with_linking:
        required.extend(
            [
                "final_dataset/linking/links.jsonl",
                "final_dataset/linking/linking_summary.json",
                "final_dataset/link_aware_exports/final_parameters_linked.csv",
                "final_dataset/link_aware_exports/sample_parameter_matrix.csv",
                "final_dataset/link_aware_exports/process_steps_table.csv",
                "final_dataset/link_aware_exports/evidence_parameter_links.csv",
                "final_dataset/link_aware_exports/spectra_parameter_links.csv",
                "final_dataset/link_aware_exports/link_aware_export_summary.json",
            ]
        )
    return [rel for rel in required if not (paper_dir / rel).exists()]


def filter_incomplete_papers(
    rows: list[dict[str, Any]],
    *,
    with_linking: bool,
) -> list[dict[str, Any]]:
    return [row for row in rows if missing_stage5_outputs(row["paper_dir"], with_linking=with_linking)]


def summarize_existing_outputs(
    *,
    category: str,
    paper_id: str,
    paper_dir: Path,
    stage3_inputs: dict[str, Any] | None,
    with_linking: bool,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    dataset_dir = paper_dir / "final_dataset"
    export_dir = dataset_dir / "link_aware_exports"
    stage5_summary = json.loads((dataset_dir / "stage5_summary.json").read_text(encoding="utf-8")) if (dataset_dir / "stage5_summary.json").exists() else {}
    link_summary = json.loads((export_dir / "link_aware_export_summary.json").read_text(encoding="utf-8")) if (export_dir / "link_aware_export_summary.json").exists() else {}
    stage4_usage = ((stage3_inputs or {}).get("stage4") or {}).get("usage_summary", {})
    parameters_count = _count_jsonl_rows(dataset_dir / "parameters.jsonl")
    samples_count = _count_jsonl_rows(dataset_dir / "samples.jsonl")
    process_steps_count = _count_jsonl_rows(dataset_dir / "process_steps.jsonl")
    evidence_objects_count = _count_jsonl_rows(dataset_dir / "evidence.jsonl")
    spectra_count_used = _count_jsonl_rows(dataset_dir / "spectra.jsonl")
    evidence_parameter_links_count = _safe_int(link_summary.get("total_evidence_parameter_links"))
    spectra_parameter_links_count = _safe_int(link_summary.get("total_spectra_parameter_links"))
    process_step_parameter_links_count = _safe_int(link_summary.get("process_step_parameter_links"))
    sample_matrix_rows = _count_jsonl_rows(dataset_dir / "samples.jsonl")
    if (export_dir / "sample_parameter_matrix.csv").exists():
        with (export_dir / "sample_parameter_matrix.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            sample_matrix_rows = max(sum(1 for _ in csv.DictReader(handle)), 0)
    row_warnings = list(warnings or [])
    row_warnings.extend(stage5_summary.get("warnings", []))
    return {
        "category": category,
        "paper_id": paper_id,
        "paper_dir": str(paper_dir),
        "stage3_found": bool(stage3_inputs),
        "stage4a_found": bool(stage4_usage.get("stage4_found")),
        "stage4a_live_spectra_count": _safe_int(stage4_usage.get("spectra_live_count")),
        "stage4a_fallback_spectra_count": _safe_int(stage4_usage.get("spectra_fallback_count")),
        "stage4a_dry_run_excluded_count": _safe_int(stage4_usage.get("spectra_dry_run_excluded_count")),
        "parameters_count": parameters_count,
        "samples_count": samples_count,
        "process_steps_count": process_steps_count,
        "evidence_objects_count": evidence_objects_count,
        "spectra_count_used": spectra_count_used,
        "evidence_parameter_links_count": evidence_parameter_links_count,
        "spectra_parameter_links_count": spectra_parameter_links_count,
        "process_step_parameter_links_count": process_step_parameter_links_count,
        "sample_matrix_rows": sample_matrix_rows,
        "status": stage5_summary.get("status") or ("success" if has_complete_stage5_outputs(paper_dir, with_linking=with_linking) else "partial_success"),
        "warnings": "|".join(item for item in row_warnings if item),
        "error_message": stage5_summary.get("error_message"),
        "elapsed_seconds": float(stage5_summary.get("elapsed_seconds") or 0.0),
        "attempted_stage5": False,
        "planned_action": "skip_existing",
    }


def _build_linking_outputs(final_dataset_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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
    outputs = export_linking_outputs(
        final_dataset_dir / "linking",
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=rejected_links,
        raw_llm_outputs=raw_llm_outputs,
        summary=summary,
        report=report,
    )
    return summary, outputs


def _derive_status_and_warnings(
    *,
    stage4a_found: bool,
    spectra_count_used: int,
    stage4a_dry_run_excluded_count: int,
    parameters_count: int,
    process_steps_count: int,
    evidence_objects_count: int,
    evidence_parameter_links_count: int,
    spectra_parameter_links_count: int,
    process_step_parameter_links_count: int,
    sample_matrix_rows: int,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not stage4a_found:
        warnings.append("missing_stage4a_but_stage5_partial_ok")
    if spectra_count_used == 0:
        if stage4a_dry_run_excluded_count > 0:
            warnings.append("dry_run_only_spectra")
        else:
            warnings.append("no_stage4a_live_spectra")
    if parameters_count == 0:
        warnings.append("empty_parameters")
    if process_steps_count == 0:
        warnings.append("zero_process_steps")
    if evidence_objects_count > 0 and evidence_parameter_links_count == 0:
        warnings.append("zero_evidence_links")
    if spectra_count_used > 0 and spectra_parameter_links_count == 0:
        warnings.append("zero_spectra_links")
    if process_steps_count > 0 and process_step_parameter_links_count == 0:
        warnings.append("zero_process_step_links")
    if sample_matrix_rows == 0:
        warnings.append("zero_sample_matrix")
    status = "partial_success" if any(
        item in warnings
        for item in (
            "missing_stage4a_but_stage5_partial_ok",
            "dry_run_only_spectra",
            "no_stage4a_live_spectra",
            "empty_parameters",
        )
    ) else "success"
    return status, warnings


def run_single_paper(
    paper_row: dict[str, Any],
    *,
    with_linking: bool,
    dry_run: bool,
    force: bool,
    skip_existing: bool,
) -> dict[str, Any]:
    category = paper_row["category"]
    paper_id = paper_row["paper_id"]
    paper_dir = paper_row["paper_dir"]
    started = time.perf_counter()
    stage3_dir, stage4_dir = discover_stage_dirs(paper_dir)

    if stage3_dir is None:
        return {
            "category": category,
            "paper_id": paper_id,
            "paper_dir": str(paper_dir),
            "stage3_found": False,
            "stage4a_found": bool(stage4_dir),
            "stage4a_live_spectra_count": 0,
            "stage4a_fallback_spectra_count": 0,
            "stage4a_dry_run_excluded_count": 0,
            "parameters_count": 0,
            "samples_count": 0,
            "process_steps_count": 0,
            "evidence_objects_count": 0,
            "spectra_count_used": 0,
            "evidence_parameter_links_count": 0,
            "spectra_parameter_links_count": 0,
            "process_step_parameter_links_count": 0,
            "sample_matrix_rows": 0,
            "status": "failed_missing_stage3",
            "warnings": "",
            "error_message": "missing_stage3",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "attempted_stage5": False,
            "planned_action": "missing_stage3",
        }

    inputs = load_paper_inputs(paper_dir, stage3_dir=stage3_dir, stage4_dir=stage4_dir, output_dataset_dir=paper_dir / "final_dataset")
    stage4_usage = inputs["stage4"]["usage_summary"]

    if skip_existing and not force and has_complete_stage5_outputs(paper_dir, with_linking=with_linking):
        return summarize_existing_outputs(
            category=category,
            paper_id=paper_id,
            paper_dir=paper_dir,
            stage3_inputs=inputs,
            with_linking=with_linking,
            warnings=["skipped_existing"],
        )

    if dry_run:
        status, warnings = _derive_status_and_warnings(
            stage4a_found=bool(stage4_usage["stage4_found"]),
            spectra_count_used=_safe_int(stage4_usage["spectra_count_used"]),
            stage4a_dry_run_excluded_count=_safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
            parameters_count=_safe_int(len(inputs["stage3"]["data_points"])),
            process_steps_count=_safe_int(len(inputs["stage3"]["process_steps"])),
            evidence_objects_count=_safe_int(len(inputs["stage3"]["evidence_objects"])),
            evidence_parameter_links_count=0,
            spectra_parameter_links_count=0,
            process_step_parameter_links_count=0,
            sample_matrix_rows=0,
        )
        return {
            "category": category,
            "paper_id": paper_id,
            "paper_dir": str(paper_dir),
            "stage3_found": True,
            "stage4a_found": bool(stage4_usage["stage4_found"]),
            "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
            "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
            "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
            "parameters_count": 0,
            "samples_count": 0,
            "process_steps_count": len(inputs["stage3"]["process_steps"]),
            "evidence_objects_count": len(inputs["stage3"]["evidence_objects"]),
            "spectra_count_used": _safe_int(stage4_usage["spectra_count_used"]),
            "evidence_parameter_links_count": 0,
            "spectra_parameter_links_count": 0,
            "process_step_parameter_links_count": 0,
            "sample_matrix_rows": 0,
            "status": f"planned_{status}",
            "warnings": "|".join(warnings),
            "error_message": None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "attempted_stage5": False,
            "planned_action": "run_stage5",
        }

    dataset_dir = paper_dir / "final_dataset"
    try:
        bundle = run_stage5_dataset_fusion(
            paper_id=paper_id,
            output_dir=paper_dir,
            stage3_dir=stage3_dir,
            stage4_dir=stage4_dir,
            output_dataset_dir=dataset_dir,
        )
        export_fusion_outputs(bundle, dataset_dir)
    except Exception as exc:  # pragma: no cover - exercised in batch tests via monkeypatch
        return {
            "category": category,
            "paper_id": paper_id,
            "paper_dir": str(paper_dir),
            "stage3_found": True,
            "stage4a_found": bool(stage4_usage["stage4_found"]),
            "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
            "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
            "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
            "parameters_count": 0,
            "samples_count": 0,
            "process_steps_count": len(inputs["stage3"]["process_steps"]),
            "evidence_objects_count": len(inputs["stage3"]["evidence_objects"]),
            "spectra_count_used": _safe_int(stage4_usage["spectra_count_used"]),
            "evidence_parameter_links_count": 0,
            "spectra_parameter_links_count": 0,
            "process_step_parameter_links_count": 0,
            "sample_matrix_rows": 0,
            "status": "failed_stage5_exception",
            "warnings": "",
            "error_message": str(exc),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "attempted_stage5": True,
            "planned_action": "run_stage5",
        }

    linking_summary: dict[str, Any] = {}
    export_result: dict[str, Any] = {}
    if with_linking:
        try:
            linking_summary, _ = _build_linking_outputs(dataset_dir)
        except Exception as exc:  # pragma: no cover - exercised in batch tests via monkeypatch
            return {
                "category": category,
                "paper_id": paper_id,
                "paper_dir": str(paper_dir),
                "stage3_found": True,
                "stage4a_found": bool(stage4_usage["stage4_found"]),
                "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
                "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
                "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
                "parameters_count": len(bundle["parameters"]),
                "samples_count": len(bundle["samples"]),
                "process_steps_count": len(bundle["process_steps"]),
                "evidence_objects_count": len(bundle["evidence"]),
                "spectra_count_used": len(bundle["spectra"]),
                "evidence_parameter_links_count": 0,
                "spectra_parameter_links_count": 0,
                "process_step_parameter_links_count": 0,
                "sample_matrix_rows": 0,
                "status": "failed_linking_exception",
                "warnings": "",
                "error_message": str(exc),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "attempted_stage5": True,
                "planned_action": "run_stage5",
            }
        try:
            export_result = generate_link_aware_exports(
                dataset_dir,
                paper_id=paper_id,
                project_root=PROJECT_ROOT,
                include_showcase=True,
            )
        except Exception as exc:  # pragma: no cover - exercised in batch tests via monkeypatch
            return {
                "category": category,
                "paper_id": paper_id,
                "paper_dir": str(paper_dir),
                "stage3_found": True,
                "stage4a_found": bool(stage4_usage["stage4_found"]),
                "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
                "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
                "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
                "parameters_count": len(bundle["parameters"]),
                "samples_count": len(bundle["samples"]),
                "process_steps_count": len(bundle["process_steps"]),
                "evidence_objects_count": len(bundle["evidence"]),
                "spectra_count_used": len(bundle["spectra"]),
                "evidence_parameter_links_count": 0,
                "spectra_parameter_links_count": 0,
                "process_step_parameter_links_count": 0,
                "sample_matrix_rows": 0,
                "status": "failed_export_exception",
                "warnings": "",
                "error_message": str(exc),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "attempted_stage5": True,
                "planned_action": "run_stage5",
            }

    evidence_parameter_links_count = _safe_int(export_result.get("summary", {}).get("total_evidence_parameter_links"))
    spectra_parameter_links_count = _safe_int(export_result.get("summary", {}).get("total_spectra_parameter_links"))
    process_step_parameter_links_count = _safe_int(export_result.get("summary", {}).get("process_step_parameter_links"))
    sample_matrix_rows = len(export_result.get("sample_parameter_matrix", [])) if export_result else 0
    status, warnings = _derive_status_and_warnings(
        stage4a_found=bool(stage4_usage["stage4_found"]),
        spectra_count_used=len(bundle["spectra"]),
        stage4a_dry_run_excluded_count=_safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
        parameters_count=len(bundle["parameters"]),
        process_steps_count=len(bundle["process_steps"]),
        evidence_objects_count=len(bundle["evidence"]),
        evidence_parameter_links_count=evidence_parameter_links_count,
        spectra_parameter_links_count=spectra_parameter_links_count,
        process_step_parameter_links_count=process_step_parameter_links_count,
        sample_matrix_rows=sample_matrix_rows if with_linking else 0,
    )

    stage5_summary = {
        "paper_id": paper_id,
        "category": category,
        "stage3_dir": str(stage3_dir),
        "stage4_dir": str(stage4_dir) if stage4_dir else None,
        "stage4a_found": bool(stage4_usage["stage4_found"]),
        "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
        "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
        "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
        "parameters_count": len(bundle["parameters"]),
        "samples_count": len(bundle["samples"]),
        "process_steps_count": len(bundle["process_steps"]),
        "evidence_objects_count": len(bundle["evidence"]),
        "spectra_count_used": len(bundle["spectra"]),
        "evidence_parameter_links_count": evidence_parameter_links_count,
        "spectra_parameter_links_count": spectra_parameter_links_count,
        "process_step_parameter_links_count": process_step_parameter_links_count,
        "sample_matrix_rows": sample_matrix_rows,
        "status": status,
        "warnings": warnings,
        "linking_summary": linking_summary,
        "link_aware_summary": export_result.get("summary", {}),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "error_message": None,
    }
    write_json(dataset_dir / "stage5_summary.json", stage5_summary)

    return {
        "category": category,
        "paper_id": paper_id,
        "paper_dir": str(paper_dir),
        "stage3_found": True,
        "stage4a_found": bool(stage4_usage["stage4_found"]),
        "stage4a_live_spectra_count": _safe_int(stage4_usage["spectra_live_count"]),
        "stage4a_fallback_spectra_count": _safe_int(stage4_usage["spectra_fallback_count"]),
        "stage4a_dry_run_excluded_count": _safe_int(stage4_usage["spectra_dry_run_excluded_count"]),
        "parameters_count": len(bundle["parameters"]),
        "samples_count": len(bundle["samples"]),
        "process_steps_count": len(bundle["process_steps"]),
        "evidence_objects_count": len(bundle["evidence"]),
        "spectra_count_used": len(bundle["spectra"]),
        "evidence_parameter_links_count": evidence_parameter_links_count,
        "spectra_parameter_links_count": spectra_parameter_links_count,
        "process_step_parameter_links_count": process_step_parameter_links_count,
        "sample_matrix_rows": sample_matrix_rows,
        "status": status,
        "warnings": "|".join(warnings),
        "error_message": None,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "attempted_stage5": True,
        "planned_action": "run_stage5",
    }


def build_failure_manifest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failure_rows: list[dict[str, Any]] = []
    warning_action_map = {
        "missing_stage4a_but_stage5_partial_ok": ("missing_stage4a_but_stage5_partial_ok", False),
        "dry_run_only_spectra": ("dry_run_only_spectra", False),
        "no_stage4a_live_spectra": ("missing_stage4a_but_stage5_partial_ok", False),
        "empty_parameters": ("empty_parameters", False),
        "zero_process_steps": ("zero_process_steps", False),
        "zero_evidence_links": ("zero_evidence_links", False),
        "zero_spectra_links": ("zero_spectra_links", False),
        "zero_process_step_links": ("zero_process_step_links", False),
        "zero_sample_matrix": ("zero_sample_matrix", False),
    }
    for row in rows:
        warnings = [item for item in str(row.get("warnings") or "").split("|") if item]
        status = row.get("status")
        if status in {"failed_missing_stage3", "failed_stage5_exception", "failed_linking_exception", "failed_export_exception"}:
            failure_rows.append(
                {
                    "category": row["category"],
                    "paper_id": row["paper_id"],
                    "paper_dir": row["paper_dir"],
                    "failure_type": status.replace("failed_", ""),
                    "error_message": row.get("error_message"),
                    "suggested_action": "inspect_and_retry",
                    "retryable": status != "failed_missing_stage3",
                }
            )
        for warning in warnings:
            if warning not in warning_action_map:
                continue
            failure_type, retryable = warning_action_map[warning]
            failure_rows.append(
                {
                    "category": row["category"],
                    "paper_id": row["paper_id"],
                    "paper_dir": row["paper_dir"],
                    "failure_type": failure_type,
                    "error_message": row.get("error_message"),
                    "suggested_action": "review_stage5_outputs",
                    "retryable": retryable,
                }
            )
    return failure_rows


def build_quality_issue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: dict[str, list[str]] = {}
    for row in rows:
        issue_names: list[str] = []
        if _safe_int(row.get("stage4a_live_spectra_count")) == 0:
            issue_names.append("no_stage4a_live_spectra")
        if _safe_int(row.get("stage4a_dry_run_excluded_count")) > 0:
            issue_names.append("dry_run_spectra_excluded")
        if _safe_int(row.get("process_steps_count")) == 0:
            issue_names.append("zero_process_steps")
        if _safe_int(row.get("evidence_parameter_links_count")) == 0 and _safe_int(row.get("evidence_objects_count")) > 0:
            issue_names.append("zero_evidence_links")
        if _safe_int(row.get("spectra_parameter_links_count")) == 0 and _safe_int(row.get("spectra_count_used")) > 0:
            issue_names.append("zero_spectra_links")
        if _safe_int(row.get("process_step_parameter_links_count")) == 0 and _safe_int(row.get("process_steps_count")) > 0:
            issue_names.append("zero_process_step_links")
        if _safe_int(row.get("sample_matrix_rows")) == 0:
            issue_names.append("zero_sample_matrix")
        if _safe_int(row.get("parameters_count")) == 0:
            issue_names.append("empty_parameters")
        for issue in issue_names:
            issues.setdefault(issue, []).append(row["paper_id"])
    return [
        {
            "quality_issue": issue,
            "count": len(papers),
            "example_papers": "|".join(papers[:10]),
        }
        for issue, papers in sorted(issues.items())
    ]


def build_overall_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attempted_rows = [row for row in rows if row.get("attempted_stage5")]
    success_rows = [row for row in rows if row.get("status") == "success"]
    partial_rows = [row for row in rows if row.get("status") == "partial_success"]
    failed_rows = [row for row in rows if str(row.get("status")).startswith("failed_")]
    return {
        "total_papers_scanned": len(rows),
        "total_papers_attempted": len(attempted_rows),
        "total_success": len(success_rows),
        "total_partial_success": len(partial_rows),
        "total_failed": len(failed_rows),
        "total_parameters": sum(_safe_int(row.get("parameters_count")) for row in rows),
        "total_samples": sum(_safe_int(row.get("samples_count")) for row in rows),
        "total_process_steps": sum(_safe_int(row.get("process_steps_count")) for row in rows),
        "total_evidence_objects": sum(_safe_int(row.get("evidence_objects_count")) for row in rows),
        "total_spectra_used": sum(_safe_int(row.get("spectra_count_used")) for row in rows),
        "total_stage4a_live_spectra": sum(_safe_int(row.get("stage4a_live_spectra_count")) for row in rows),
        "total_stage4a_fallback_spectra": sum(_safe_int(row.get("stage4a_fallback_spectra_count")) for row in rows),
        "total_stage4a_dry_run_excluded": sum(_safe_int(row.get("stage4a_dry_run_excluded_count")) for row in rows),
        "total_evidence_parameter_links": sum(_safe_int(row.get("evidence_parameter_links_count")) for row in rows),
        "total_spectra_parameter_links": sum(_safe_int(row.get("spectra_parameter_links_count")) for row in rows),
        "total_process_step_parameter_links": sum(_safe_int(row.get("process_step_parameter_links_count")) for row in rows),
        "total_sample_matrix_rows": sum(_safe_int(row.get("sample_matrix_rows")) for row in rows),
        "papers_with_stage4a_missing": sum(1 for row in rows if not row.get("stage4a_found")),
        "papers_with_zero_process_steps": sum(1 for row in rows if _safe_int(row.get("process_steps_count")) == 0),
        "papers_with_zero_evidence_links": sum(
            1 for row in rows if _safe_int(row.get("evidence_parameter_links_count")) == 0 and _safe_int(row.get("evidence_objects_count")) > 0
        ),
        "papers_with_zero_spectra_links": sum(
            1 for row in rows if _safe_int(row.get("spectra_parameter_links_count")) == 0 and _safe_int(row.get("spectra_count_used")) > 0
        ),
        "papers_with_zero_process_step_links": sum(
            1 for row in rows if _safe_int(row.get("process_step_parameter_links_count")) == 0 and _safe_int(row.get("process_steps_count")) > 0
        ),
        "papers_with_zero_sample_matrix": sum(1 for row in rows if _safe_int(row.get("sample_matrix_rows")) == 0),
        "elapsed_seconds": round(sum(float(row.get("elapsed_seconds") or 0.0) for row in rows), 3),
    }


def build_run_report(rows: list[dict[str, Any]], overall_summary: dict[str, Any], quality_rows: list[dict[str, Any]]) -> str:
    partial_papers = [row["paper_id"] for row in rows if row.get("status") == "partial_success"][:20]
    failed_papers = [row["paper_id"] for row in rows if str(row.get("status")).startswith("failed_")][:20]
    lines = [
        "# Stage 5 Batch Run Report",
        "",
        "## 总览",
        f"- 扫描论文数: {overall_summary['total_papers_scanned']}",
        f"- 实际执行论文数: {overall_summary['total_papers_attempted']}",
        f"- success: {overall_summary['total_success']}",
        f"- partial_success: {overall_summary['total_partial_success']}",
        f"- failed: {overall_summary['total_failed']}",
        f"- total_parameters: {overall_summary['total_parameters']}",
        f"- total_samples: {overall_summary['total_samples']}",
        f"- total_process_steps: {overall_summary['total_process_steps']}",
        f"- total_evidence_objects: {overall_summary['total_evidence_objects']}",
        f"- total_spectra_used: {overall_summary['total_spectra_used']}",
        f"- total_stage4a_live_spectra: {overall_summary['total_stage4a_live_spectra']}",
        f"- total_stage4a_fallback_spectra: {overall_summary['total_stage4a_fallback_spectra']}",
        f"- total_stage4a_dry_run_excluded: {overall_summary['total_stage4a_dry_run_excluded']}",
        "",
        "## 说明",
        "- Stage 5 只使用 Stage4A 的 live / fallback spectra，dry-run spectra 已全部排除。",
        "- 如果 Stage 4A 缺失或只有 dry-run 图谱，Stage 5 仍会融合 Stage 3 的文本参数、process_steps、evidence_objects，并标记 partial_success。",
        "- process_steps 已进入 Stage 5，不会只融合 parameters。",
        "- evidence / spectra / process_step links 不会因为其中某一类为空就让整篇失败。",
        "",
        "## 重点论文",
        f"- partial_success 示例: {'; '.join(partial_papers) if partial_papers else '无'}",
        f"- failed 示例: {'; '.join(failed_papers) if failed_papers else '无'}",
        "",
        "## 质量问题统计",
    ]
    if quality_rows:
        for row in quality_rows:
            lines.append(f"- {row['quality_issue']}: {row['count']} ({row['example_papers']})")
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 下一步建议",
            "- 优先检查 partial_success 中 `dry_run_only_spectra`、`no_stage4a_live_spectra` 和 `zero_process_step_links` 的论文。",
            "- 在 Stage 5 汇总稳定后，再决定是否进入更上游的 analysis/export 阶段。",
        ]
    )
    return "\n".join(lines)


def run_stage5_batch(
    *,
    outputs_dir: Path,
    report_dir: Path,
    categories: list[str],
    limit: int | None,
    paper_filter: str | None,
    force: bool,
    skip_existing: bool,
    with_linking: bool,
    dry_run: bool,
    continue_on_error: bool,
    workers: int,
    only_incomplete: bool = False,
) -> dict[str, Any]:
    discovered = discover_papers(outputs_dir, categories=categories, paper_filter=paper_filter)
    if only_incomplete:
        discovered = filter_incomplete_papers(discovered, with_linking=with_linking)
    if limit:
        discovered = discovered[:limit]
    report_dir.mkdir(parents=True, exist_ok=True)

    def _job(row: dict[str, Any]) -> dict[str, Any]:
        return run_single_paper(
            row,
            with_linking=with_linking,
            dry_run=dry_run,
            force=force,
            skip_existing=skip_existing,
        )

    rows: list[dict[str, Any]] = []
    if workers > 1 and not dry_run:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_job, row): row for row in discovered}
            for future in as_completed(futures):
                try:
                    rows.append(future.result())
                except Exception as exc:  # pragma: no cover
                    if not continue_on_error:
                        raise
                    source = futures[future]
                    rows.append(
                        {
                            "category": source["category"],
                            "paper_id": source["paper_id"],
                            "paper_dir": str(source["paper_dir"]),
                            "stage3_found": False,
                            "stage4a_found": False,
                            "stage4a_live_spectra_count": 0,
                            "stage4a_fallback_spectra_count": 0,
                            "stage4a_dry_run_excluded_count": 0,
                            "parameters_count": 0,
                            "samples_count": 0,
                            "process_steps_count": 0,
                            "evidence_objects_count": 0,
                            "spectra_count_used": 0,
                            "evidence_parameter_links_count": 0,
                            "spectra_parameter_links_count": 0,
                            "process_step_parameter_links_count": 0,
                            "sample_matrix_rows": 0,
                            "status": "failed_stage5_exception",
                            "warnings": "",
                            "error_message": str(exc),
                            "elapsed_seconds": 0.0,
                            "attempted_stage5": True,
                            "planned_action": "run_stage5",
                        }
                    )
    else:
        for row in discovered:
            try:
                rows.append(_job(row))
            except Exception as exc:  # pragma: no cover
                if not continue_on_error:
                    raise
                rows.append(
                    {
                        "category": row["category"],
                        "paper_id": row["paper_id"],
                        "paper_dir": str(row["paper_dir"]),
                        "stage3_found": False,
                        "stage4a_found": False,
                        "stage4a_live_spectra_count": 0,
                        "stage4a_fallback_spectra_count": 0,
                        "stage4a_dry_run_excluded_count": 0,
                        "parameters_count": 0,
                        "samples_count": 0,
                        "process_steps_count": 0,
                        "evidence_objects_count": 0,
                        "spectra_count_used": 0,
                        "evidence_parameter_links_count": 0,
                        "spectra_parameter_links_count": 0,
                        "process_step_parameter_links_count": 0,
                        "sample_matrix_rows": 0,
                        "status": "failed_stage5_exception",
                        "warnings": "",
                        "error_message": str(exc),
                        "elapsed_seconds": 0.0,
                        "attempted_stage5": True,
                        "planned_action": "run_stage5",
                    }
                )

    rows.sort(key=lambda item: (item["category"], item["paper_id"]))
    failure_rows = build_failure_manifest(rows)
    quality_rows = build_quality_issue_rows(rows)
    overall_summary = build_overall_summary(rows)
    report_text = build_run_report(rows, overall_summary, quality_rows)

    _write_csv(report_dir / "stage5_batch_paper_summary.csv", rows)
    _write_csv(report_dir / "stage5_batch_failure_manifest.csv", failure_rows)
    _write_csv(report_dir / "stage5_batch_quality_summary.csv", quality_rows)
    write_json(report_dir / "stage5_batch_overall_summary.json", overall_summary)
    write_markdown(report_dir / "stage5_batch_run_report.md", report_text)

    return {
        "paper_summary_path": str(report_dir / "stage5_batch_paper_summary.csv"),
        "failure_manifest_path": str(report_dir / "stage5_batch_failure_manifest.csv"),
        "quality_summary_path": str(report_dir / "stage5_batch_quality_summary.csv"),
        "overall_summary_path": str(report_dir / "stage5_batch_overall_summary.json"),
        "report_path": str(report_dir / "stage5_batch_run_report.md"),
        "summary": overall_summary,
    }


__all__ = [
    "DEFAULT_CATEGORIES",
    "STAGE3_DIR_CANDIDATES",
    "STAGE4_DIR_CANDIDATES",
    "build_failure_manifest",
    "build_overall_summary",
    "build_quality_issue_rows",
    "build_run_report",
    "discover_papers",
    "discover_stage_dirs",
    "filter_incomplete_papers",
    "has_complete_stage5_outputs",
    "missing_stage5_outputs",
    "run_single_paper",
    "run_stage5_batch",
    "summarize_existing_outputs",
]
