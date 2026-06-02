"""Official Stage 4 batch runner.

This module only orchestrates per-paper Stage 4 execution.
The actual Stage 4 extraction logic lives in
``Stage4VisionSpectraExtractor.run()``.
"""

from __future__ import annotations

import csv
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .extractor import Stage4VisionSpectraExtractor
from .io import read_json
from .processed_index import is_live_successful_stage4_summary

DEFAULT_STAGE3_SUBDIR = "stage3_twopass"
DEFAULT_STAGE4_SUBDIR = "stage4_vision_spectra_universal"
DEFAULT_ROUTING_MODE = "universal_compact"
DEFAULT_CANDIDATE_SOURCE = "stage2-selected"


def discover_stage4_batch_papers(
    *,
    outputs_dir: Path,
    manifest: Path | None = None,
    paper_ids: list[str] | None = None,
    category: str | None = None,
    limit: int = 0,
    stage3_subdir: str = DEFAULT_STAGE3_SUBDIR,
) -> list[dict[str, str]]:
    rows = _load_manifest_rows(manifest) if manifest else _discover_from_outputs(outputs_dir, stage3_subdir=stage3_subdir)
    filtered = _filter_rows(rows, paper_ids=paper_ids, category=category, limit=limit)
    return filtered


def run_stage4_for_paper(
    *,
    paper_id: str,
    paper_output_dir: Path,
    dry_run: bool = True,
    force_stage4: bool = False,
    stage4_figure_ids: list[str] | None = None,
    stage3_subdir: str = DEFAULT_STAGE3_SUBDIR,
    stage4_subdir: str = DEFAULT_STAGE4_SUBDIR,
    routing_mode: str = DEFAULT_ROUTING_MODE,
    candidate_source: str = DEFAULT_CANDIDATE_SOURCE,
    max_figures_per_paper: int = 0,
) -> dict[str, Any]:
    stage3_dir = paper_output_dir / stage3_subdir
    stage4_dir = paper_output_dir / stage4_subdir
    if force_stage4 and stage4_dir.exists():
        shutil.rmtree(stage4_dir)

    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=paper_output_dir,
        max_figures=max(0, int(max_figures_per_paper or 0)),
        figure_ids=list(stage4_figure_ids or []),
        dry_run=dry_run,
        routing_mode=routing_mode,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        candidate_source=candidate_source,
    )
    return extractor.run()


def run_stage4_batch(
    *,
    outputs_dir: Path,
    manifest: Path | None = None,
    paper_ids: list[str] | None = None,
    category: str | None = None,
    limit: int = 0,
    dry_run: bool = True,
    force_stage4: bool = False,
    stage4_figure_ids: list[str] | None = None,
    continue_on_error: bool = False,
    output_dir: Path | None = None,
    stage3_subdir: str = DEFAULT_STAGE3_SUBDIR,
    stage4_subdir: str = DEFAULT_STAGE4_SUBDIR,
    routing_mode: str = DEFAULT_ROUTING_MODE,
    candidate_source: str = DEFAULT_CANDIDATE_SOURCE,
    max_figures_per_paper: int = 0,
) -> dict[str, Any]:
    report_dir = output_dir or (
        outputs_dir.parent / "batch_validation" / datetime.now().strftime("%Y%m%d_%H%M%S") / "stage4_batch"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    selected_rows = discover_stage4_batch_papers(
        outputs_dir=outputs_dir,
        manifest=manifest,
        paper_ids=paper_ids,
        category=category,
        limit=limit,
        stage3_subdir=stage3_subdir,
    )

    started_at = _now_iso()
    result_rows: list[dict[str, Any]] = []
    for row in selected_rows:
        result = _run_stage4_batch_row(
            row,
            outputs_dir=outputs_dir,
            dry_run=dry_run,
            force_stage4=force_stage4,
            stage4_figure_ids=stage4_figure_ids,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
            candidate_source=candidate_source,
            max_figures_per_paper=max_figures_per_paper,
        )
        result_rows.append(result)
        if result["status"] == "failed" and not continue_on_error:
            break

    finished_at = _now_iso()
    summary = _build_batch_summary(
        rows=result_rows,
        manifest=manifest,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        dry_run=dry_run,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        routing_mode=routing_mode,
        candidate_source=candidate_source,
        force_stage4=force_stage4,
        stage4_figure_ids=stage4_figure_ids,
        max_figures_per_paper=max_figures_per_paper,
        started_at=started_at,
        finished_at=finished_at,
    )
    rows_path = report_dir / "stage4_batch_rows.jsonl"
    summary_path = report_dir / "stage4_batch_summary.json"
    report_path = report_dir / "stage4_batch_report.md"
    _write_jsonl(rows_path, result_rows)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_batch_report(summary, result_rows), encoding="utf-8")
    return {
        "rows": result_rows,
        "summary": summary,
        "rows_path": str(rows_path),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
    }


def _run_stage4_batch_row(
    row: dict[str, str],
    *,
    outputs_dir: Path,
    dry_run: bool,
    force_stage4: bool,
    stage4_figure_ids: list[str] | None,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    max_figures_per_paper: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    category = row.get("category", "")
    paper_id = row.get("paper_id", "")
    paper_output_dir = Path(row.get("paper_output_dir") or outputs_dir / category / paper_id)
    stage3_dir = paper_output_dir / stage3_subdir
    stage4_dir = paper_output_dir / stage4_subdir
    stage4_summary_path = stage4_dir / "stage4a_summary.json"
    base_row: dict[str, Any] = {
        "paper_id": paper_id,
        "category": category,
        "paper_output_dir": str(paper_output_dir),
        "stage3_dir": str(stage3_dir),
        "stage4_dir": str(stage4_dir),
        "status": "",
        "dry_run": dry_run,
        "live": not dry_run,
        "force_stage4": force_stage4,
        "figure_ids": list(stage4_figure_ids or []),
        "total_candidates": 0,
        "processed_count": 0,
        "skipped_count": 0,
        "validation_error_count": 0,
        "failed_record_count": 0,
        "stage4_summary_path": str(stage4_summary_path),
        "started_at": _now_iso(),
        "finished_at": "",
        "elapsed_seconds": 0.0,
        "error_type": "",
        "error_message": "",
    }

    if not paper_output_dir.exists():
        base_row["status"] = "missing_output_dir"
        return _finalize_row(base_row, started)
    if not _has_stage3_inputs(stage3_dir):
        base_row["status"] = "missing_stage3"
        return _finalize_row(base_row, started)
    if not force_stage4 and not stage4_figure_ids and _should_skip_existing_stage4(stage4_summary_path, dry_run=dry_run):
        summary = read_json(stage4_summary_path, default={}) or {}
        base_row["status"] = "skipped_existing"
        base_row.update(_summary_to_row_fields(summary))
        return _finalize_row(base_row, started)

    try:
        summary = run_stage4_for_paper(
            paper_id=paper_id,
            paper_output_dir=paper_output_dir,
            dry_run=dry_run,
            force_stage4=force_stage4,
            stage4_figure_ids=stage4_figure_ids,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
            candidate_source=candidate_source,
            max_figures_per_paper=max_figures_per_paper,
        )
        base_row.update(_summary_to_row_fields(summary))
        if bool(summary.get("not_applicable")) or int(summary.get("total_candidates") or 0) == 0:
            base_row["status"] = "no_candidates"
        elif dry_run:
            base_row["status"] = "dry_run_success"
        else:
            base_row["status"] = "success"
    except Exception as exc:  # noqa: BLE001
        base_row["status"] = "failed"
        base_row["error_type"] = type(exc).__name__
        base_row["error_message"] = str(exc)
    return _finalize_row(base_row, started)


def _summary_to_row_fields(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_candidates": int(summary.get("total_candidates") or 0),
        "processed_count": int(summary.get("processed_count") or 0),
        "skipped_count": int(summary.get("skipped_count") or 0),
        "validation_error_count": int(summary.get("validation_error_count") or 0),
        "failed_record_count": int(summary.get("failed_record_count") or 0),
    }


def _has_stage3_inputs(stage3_dir: Path) -> bool:
    summary_path = stage3_dir / "stage3_summary.json"
    evidence_path = stage3_dir / "evidence_objects.jsonl"
    return summary_path.exists() and evidence_path.exists()


def _should_skip_existing_stage4(stage4_summary_path: Path, *, dry_run: bool) -> bool:
    if not stage4_summary_path.exists():
        return False
    summary = read_json(stage4_summary_path, default={}) or {}
    if dry_run:
        return bool(summary)
    return is_live_successful_stage4_summary(summary)


def _discover_from_outputs(outputs_dir: Path, stage3_subdir: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        for paper_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            stage3_dir = paper_dir / stage3_subdir
            if not stage3_dir.exists():
                continue
            rows.append(
                {
                    "category": category_dir.name,
                    "paper_id": paper_dir.name,
                    "paper_output_dir": str(paper_dir),
                }
            )
    return rows


def _load_manifest_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            category = str(row.get("category") or "").strip()
            paper_id = str(row.get("paper_id_guess") or row.get("paper_id") or "").strip()
            if not category or not paper_id:
                continue
            rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "paper_output_dir": "",
                }
            )
        return rows


def _filter_rows(
    rows: list[dict[str, str]],
    *,
    paper_ids: list[str] | None,
    category: str | None,
    limit: int,
) -> list[dict[str, str]]:
    filtered = rows
    if category:
        filtered = [row for row in filtered if row.get("category") == category]
    if paper_ids:
        wanted = {item.strip() for item in paper_ids if item.strip()}
        filtered = [row for row in filtered if row.get("paper_id") in wanted]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def _build_batch_summary(
    *,
    rows: list[dict[str, Any]],
    manifest: Path | None,
    outputs_dir: Path,
    report_dir: Path,
    dry_run: bool,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    force_stage4: bool,
    stage4_figure_ids: list[str] | None,
    max_figures_per_paper: int,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    status_counter: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counter[status] = status_counter.get(status, 0) + 1
    return {
        "manifest": str(manifest) if manifest else None,
        "outputs_dir": str(outputs_dir),
        "report_dir": str(report_dir),
        "dry_run": dry_run,
        "live": not dry_run,
        "stage3_subdir": stage3_subdir,
        "stage4_subdir": stage4_subdir,
        "routing_mode": routing_mode,
        "candidate_source": candidate_source,
        "force_stage4": force_stage4,
        "stage4_figure_ids": list(stage4_figure_ids or []),
        "max_figures_per_paper": int(max_figures_per_paper or 0),
        "total_papers": len(rows),
        "status_counts": status_counter,
        "total_candidates": sum(int(row.get("total_candidates") or 0) for row in rows),
        "total_processed": sum(int(row.get("processed_count") or 0) for row in rows),
        "total_skipped": sum(int(row.get("skipped_count") or 0) for row in rows),
        "total_validation_errors": sum(int(row.get("validation_error_count") or 0) for row in rows),
        "total_failed_records": sum(int(row.get("failed_record_count") or 0) for row in rows),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_batch_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Stage4 Batch Report",
        "",
        "## Summary",
        f"- total_papers: {summary['total_papers']}",
        f"- dry_run: {summary['dry_run']}",
        f"- live: {summary['live']}",
        f"- stage3_subdir: {summary['stage3_subdir']}",
        f"- stage4_subdir: {summary['stage4_subdir']}",
        f"- routing_mode: {summary['routing_mode']}",
        f"- candidate_source: {summary['candidate_source']}",
        f"- force_stage4: {summary['force_stage4']}",
        f"- max_figures_per_paper: {summary['max_figures_per_paper']}",
        f"- total_candidates: {summary['total_candidates']}",
        f"- total_processed: {summary['total_processed']}",
        f"- total_skipped: {summary['total_skipped']}",
        f"- total_validation_errors: {summary['total_validation_errors']}",
        f"- total_failed_records: {summary['total_failed_records']}",
        "",
        "## Status Counts",
    ]
    for key, value in summary["status_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Per Paper"])
    for row in rows:
        lines.extend(
            [
                "",
                f"### {row['category']}/{row['paper_id']}",
                f"- status: {row['status']}",
                f"- total_candidates: {row['total_candidates']}",
                f"- processed_count: {row['processed_count']}",
                f"- skipped_count: {row['skipped_count']}",
                f"- validation_error_count: {row['validation_error_count']}",
                f"- failed_record_count: {row['failed_record_count']}",
                f"- error: {row['error_type'] or 'none'} {row['error_message'] or ''}".rstrip(),
            ]
        )
    return "\n".join(lines) + "\n"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _finalize_row(row: dict[str, Any], started: float) -> dict[str, Any]:
    row["finished_at"] = _now_iso()
    row["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return row


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


__all__ = [
    "DEFAULT_CANDIDATE_SOURCE",
    "DEFAULT_ROUTING_MODE",
    "DEFAULT_STAGE3_SUBDIR",
    "DEFAULT_STAGE4_SUBDIR",
    "discover_stage4_batch_papers",
    "run_stage4_batch",
    "run_stage4_for_paper",
]
