from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402
from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor  # noqa: E402
from alumina_sol_extractor.stage4.io import read_json, read_jsonl  # noqa: E402
from alumina_sol_extractor.stage4.processed_index import is_live_successful_stage4_summary  # noqa: E402
from alumina_sol_extractor.utils.batch_categories import normalize_batch_category  # noqa: E402


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_STAGE3_SUBDIR = "stage3_twopass"
DEFAULT_STAGE4_SUBDIR = "stage4_vision_spectra_universal"
DEFAULT_CHUNK_ROOT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_stage2_selected_live_chunks"
DEFAULT_AUDIT_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_stage2_selected_full_audit.csv"
DEFAULT_AUDIT_JSON = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_stage2_selected_full_audit_summary.json"
DEFAULT_AUDIT_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md"
DEFAULT_REVIEW_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_stage2_selected_live_quality_review.csv"
DEFAULT_REVIEW_JSON = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_stage2_selected_live_quality_review_summary.json"
DEFAULT_REVIEW_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_STAGE2_SELECTED_LIVE_QUALITY_REVIEW.md"
DEFERRED_LARGE_PAPER_PREFIXES = ("032_",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage4A from Stage2-selected figures only.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit-only", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--review-only", action="store_true")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS_DIR))
    parser.add_argument("--stage3-subdir", default=DEFAULT_STAGE3_SUBDIR)
    parser.add_argument("--stage4-subdir", default=DEFAULT_STAGE4_SUBDIR)
    parser.add_argument("--routing-mode", default="universal_compact", choices=["schema_specific", "universal_compact"])
    parser.add_argument("--candidate-source", default="stage2-selected", choices=["stage2-selected"])
    parser.add_argument("--category", default="")
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--paper-ids-file", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=10)
    parser.add_argument("--max-figures-per-paper", type=int, default=0)
    parser.add_argument("--defer-large-papers", dest="defer_large_papers", action="store_true", default=True)
    parser.add_argument("--no-defer-large-papers", dest="defer_large_papers", action="store_false")
    parser.add_argument("--report-dir", default=str(DEFAULT_CHUNK_ROOT))
    parser.add_argument("--continue-on-error", action="store_true", default=True)
    parser.add_argument("--vlm-timeout-seconds", type=int, default=90)
    parser.add_argument("--vlm-max-retries", type=int, default=1)
    parser.add_argument("--vlm-retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = Path(args.manifest)
    outputs_dir = Path(args.outputs_dir)
    rows = _select_manifest_rows(
        _load_manifest_rows(manifest),
        category=args.category or None,
        paper_ids=_load_requested_paper_ids(args.paper_ids, args.paper_ids_file),
        limit=args.limit,
    )
    if args.audit_only:
        result = run_audit_only(
            rows=rows,
            outputs_dir=outputs_dir,
            stage3_subdir=args.stage3_subdir,
            stage4_subdir=args.stage4_subdir,
            routing_mode=args.routing_mode,
            candidate_source=args.candidate_source,
            max_figures_per_paper=args.max_figures_per_paper,
            defer_large_papers=args.defer_large_papers,
        )
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return
    if args.review_only:
        result = run_review_only(
            rows=rows,
            outputs_dir=outputs_dir,
            stage3_subdir=args.stage3_subdir,
            stage4_subdir=args.stage4_subdir,
        )
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return

    load_project_dotenv(PROJECT_ROOT)
    result = run_live_chunks(
        rows=rows,
        outputs_dir=outputs_dir,
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        routing_mode=args.routing_mode,
        candidate_source=args.candidate_source,
        chunk_size=args.chunk_size,
        max_figures_per_paper=args.max_figures_per_paper,
        defer_large_papers=args.defer_large_papers,
        report_dir=Path(args.report_dir),
        continue_on_error=args.continue_on_error,
        vlm_timeout_seconds=args.vlm_timeout_seconds,
        vlm_max_retries=args.vlm_max_retries,
        vlm_retry_backoff_seconds=args.vlm_retry_backoff_seconds,
        workers=args.workers,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def run_audit_only(
    *,
    rows: list[dict[str, str]],
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    max_figures_per_paper: int,
    defer_large_papers: bool,
) -> dict[str, Any]:
    audit_rows = [
        _build_paper_audit_row(
            row,
            outputs_dir=outputs_dir,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
            candidate_source=candidate_source,
            max_figures_per_paper=max_figures_per_paper,
            defer_large_papers=defer_large_papers,
        )
        for row in rows
    ]
    summary = _summarize_audit_rows(audit_rows)
    _write_csv(DEFAULT_AUDIT_CSV, audit_rows, list(audit_rows[0].keys()) if audit_rows else [])
    DEFAULT_AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_AUDIT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    DEFAULT_AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_AUDIT_MD.write_text(_build_audit_markdown(summary), encoding="utf-8")
    return {"rows": audit_rows, "summary": summary}


def run_review_only(
    *,
    rows: list[dict[str, str]],
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
) -> dict[str, Any]:
    review_rows: list[dict[str, Any]] = []
    actual_distribution: Counter[str] = Counter()
    for row in rows:
        category = normalize_batch_category(row.get("category"))
        paper_id = row.get("paper_id_guess") or ""
        paper_dir = outputs_dir / category / paper_id
        stage3_summary_path = paper_dir / stage3_subdir / "stage3_summary.json"
        if not _is_readable_json(stage3_summary_path):
            continue
        stage4_dir = paper_dir / stage4_subdir
        stage4_summary = read_json(stage4_dir / "stage4a_summary.json", default={}) or {}
        extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
        failed_records = read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
        for extraction in extractions:
            actual_distribution[str(extraction.get("actual_figure_type") or extraction.get("figure_type") or "unknown")] += 1
        review_rows.append(
            {
                "category": category,
                "paper_id": paper_id,
                "live_success": is_live_successful_stage4_summary(stage4_summary),
                "successful_extractions": len(extractions),
                "failed_records": len(failed_records),
                "schema_validation_failed_count": sum(
                    1 for item in failed_records if str(item.get("error_type") or "") == "schema_validation_failed"
                ),
                "range_peak_midpoint_error_count": sum(
                    1
                    for extraction in extractions
                    for peak in extraction.get("peaks", []) or []
                    if peak.get("position") is not None
                    and any(token in str(peak.get("source_text") or "") for token in ["-", "–", "—", "~", " to "])
                ),
                "sem_tem_unscaled_diameter_error_count": sum(
                    1
                    for extraction in extractions
                    if str(extraction.get("actual_figure_type") or extraction.get("figure_type") or "") in {"sem_image", "tem_image", "microscopy"}
                    and not extraction.get("scale_bar")
                    and (extraction.get("diameter_estimate") is not None or extraction.get("particle_size_estimate") is not None)
                ),
                "type_mismatch_count": sum(1 for extraction in extractions if extraction.get("type_mismatch")),
                "unknown_or_non_extractable_count": sum(
                    1
                    for extraction in extractions
                    if str(extraction.get("actual_figure_type") or extraction.get("figure_type") or "") in {"unknown", "non_extractable"}
                ),
            }
        )
    summary = {
        "total_live_figures": sum(int(row["successful_extractions"]) for row in review_rows),
        "successful_extractions": sum(int(row["successful_extractions"]) for row in review_rows),
        "failed_records": sum(int(row["failed_records"]) for row in review_rows),
        "schema_validation_failed_count": sum(int(row["schema_validation_failed_count"]) for row in review_rows),
        "range_peak_midpoint_error_count": sum(int(row["range_peak_midpoint_error_count"]) for row in review_rows),
        "sem_tem_unscaled_diameter_error_count": sum(int(row["sem_tem_unscaled_diameter_error_count"]) for row in review_rows),
        "type_mismatch_count": sum(int(row["type_mismatch_count"]) for row in review_rows),
        "unknown_or_non_extractable_count": sum(int(row["unknown_or_non_extractable_count"]) for row in review_rows),
        "actual_figure_type_distribution": dict(actual_distribution),
        "papers_with_failed_records": [row["paper_id"] for row in review_rows if int(row["failed_records"]) > 0],
        "papers_needing_replay": [row["paper_id"] for row in review_rows if int(row["schema_validation_failed_count"]) > 0],
        "papers_needing_manual_hold": [
            row["paper_id"]
            for row in review_rows
            if int(row["sem_tem_unscaled_diameter_error_count"]) > 0 or int(row["range_peak_midpoint_error_count"]) > 0
        ],
        "pass_gate": (
            sum(int(row["schema_validation_failed_count"]) for row in review_rows) == 0
            and sum(int(row["range_peak_midpoint_error_count"]) for row in review_rows) == 0
            and sum(int(row["sem_tem_unscaled_diameter_error_count"]) for row in review_rows) == 0
        ),
    }
    _write_csv(DEFAULT_REVIEW_CSV, review_rows, list(review_rows[0].keys()) if review_rows else [])
    DEFAULT_REVIEW_JSON.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REVIEW_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    DEFAULT_REVIEW_MD.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REVIEW_MD.write_text(_build_review_markdown(summary), encoding="utf-8")
    return {"rows": review_rows, "summary": summary}



def _stage4a_to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _stage4a_to_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

def _stage4a_should_run_live(row):
    """???? run_action ??? audit row?"""
    action = str(row.get("run_action") or "").strip()
    if action:
        return action == "run_live"
    if _stage4a_to_bool(row.get("deferred")):
        return False
    return _stage4a_to_int(row.get("new_live_candidate_figures")) > 0

def _run_one_stage4a_paper(
    row: dict[str, Any],
    *,
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    max_figures_per_paper: int,
) -> dict[str, Any]:
    started_at = time.monotonic()
    category = row["category"]
    paper_id = row["paper_id"]

    print(
        f"[Stage4A batch] start paper={paper_id} "
        f"category={category} max_figures={max_figures_per_paper}",
        flush=True,
    )

    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=outputs_dir / category / paper_id,
        max_figures=max_figures_per_paper,
        dry_run=False,
        routing_mode=routing_mode,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        candidate_source=candidate_source,
    )

    try:
        summary = extractor.run()
        elapsed = round(time.monotonic() - started_at, 2)
        print(
            f"[Stage4A batch] done paper={paper_id} elapsed={elapsed}s",
            flush=True,
        )
        return {
            "category": category,
            "paper_id": paper_id,
            "status": "success",
            "elapsed_seconds": elapsed,
            "summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = round(time.monotonic() - started_at, 2)
        print(
            f"[Stage4A batch] failed paper={paper_id} "
            f"elapsed={elapsed}s error={exc}",
            flush=True,
        )
        return {
            "category": category,
            "paper_id": paper_id,
            "status": "failed",
            "elapsed_seconds": elapsed,
            "error_message": str(exc),
        }
def run_live_chunks(
    *,
    rows: list[dict[str, str]],
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    chunk_size: int,
    max_figures_per_paper: int,
    defer_large_papers: bool,
    report_dir: Path,
    continue_on_error: bool,
    vlm_timeout_seconds: int,
    vlm_max_retries: int,
    vlm_retry_backoff_seconds: float,
    workers: int,
) -> dict[str, Any]:
    os.environ["VLM_TIMEOUT_SECONDS"] = str(vlm_timeout_seconds)
    os.environ["VLM_MAX_RETRIES"] = str(vlm_max_retries)
    os.environ["VLM_RETRY_BACKOFF_SECONDS"] = str(vlm_retry_backoff_seconds)
    audit = run_audit_only(
        rows=rows,
        outputs_dir=outputs_dir,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        routing_mode=routing_mode,
        candidate_source=candidate_source,
        max_figures_per_paper=max_figures_per_paper,
        defer_large_papers=defer_large_papers,
    )
    run_live_rows = [
        row for row in audit["rows"]
        if _stage4a_should_run_live(row)
    ]
    chunk_reports: list[dict[str, Any]] = []
    for index in range(0, len(run_live_rows), max(chunk_size, 1)):
        chunk_rows = run_live_rows[index:index + max(chunk_size, 1)]
        chunk_name = f"chunk_{(index // max(chunk_size, 1)) + 1:03d}"
        chunk_dir = report_dir / chunk_name
        chunk_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, Any]] = []
        max_workers = max(1, int(workers or 1))

        if max_workers == 1:
            for row in chunk_rows:
                result = _run_one_stage4a_paper(
                    row,
                    outputs_dir=outputs_dir,
                    stage3_subdir=stage3_subdir,
                    stage4_subdir=stage4_subdir,
                    routing_mode=routing_mode,
                    candidate_source=candidate_source,
                    max_figures_per_paper=max_figures_per_paper,
                )
                results.append(result)
                if result["status"] == "failed" and not continue_on_error:
                    break
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_row = {
                    executor.submit(
                        _run_one_stage4a_paper,
                        row,
                        outputs_dir=outputs_dir,
                        stage3_subdir=stage3_subdir,
                        stage4_subdir=stage4_subdir,
                        routing_mode=routing_mode,
                        candidate_source=candidate_source,
                        max_figures_per_paper=max_figures_per_paper,
                    ): row
                    for row in chunk_rows
                }

                for future in as_completed(future_to_row):
                    result = future.result()
                    results.append(result)

                    if result["status"] == "failed" and not continue_on_error:
                        for pending in future_to_row:
                            pending.cancel()
                        break
        chunk_summary = _build_chunk_summary(chunk_rows, results)
        (chunk_dir / "chunk_summary.json").write_text(json.dumps(chunk_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        chunk_reports.append(chunk_summary)
    return {
        "summary": {
            "chunk_count": len(chunk_reports),
            "papers_attempted": sum(item["chunk_paper_count"] for item in chunk_reports),
        },
        "chunks": chunk_reports,
    }


def _build_paper_audit_row(
    row: dict[str, str],
    *,
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    candidate_source: str,
    max_figures_per_paper: int,
    defer_large_papers: bool,
) -> dict[str, Any]:
    category = normalize_batch_category(row.get("category"))
    paper_id = row.get("paper_id_guess") or ""
    paper_dir = outputs_dir / category / paper_id
    stage3_summary_path = paper_dir / stage3_subdir / "stage3_summary.json"
    figures_jsonl_path = paper_dir / "figures.jsonl"
    figures_for_vision_dir = paper_dir / "figures_for_vision"
    stage3_done = _is_readable_json(stage3_summary_path)

    base_row: dict[str, Any] = {
        "category": category,
        "paper_id": paper_id,
        "stage2_selected_figures": 0,
        "valid_stage2_selected_figures": 0,
        "already_live_success_figures": 0,
        "raw_vlm_replay_candidates": 0,
        "schema_replay_candidates": 0,
        "transient_rerun_candidates": 0,
        "new_live_candidate_figures": 0,
        "missing_image_path_count": 0,
        "directory_path_error_count": 0,
        "duplicate_vlm_prevented_count": 0,
        "dry_run_only_records_ignored_as_success": 0,
        "deferred": False,
        "reason": "missing_stage3" if not stage3_done else "ready",
        "has_stage3_summary": stage3_done,
        "has_figures_jsonl": figures_jsonl_path.exists(),
        "has_figures_for_vision": figures_for_vision_dir.exists() and figures_for_vision_dir.is_dir(),
    }
    if not stage3_done:
        return base_row

    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=paper_dir,
        max_figures=max_figures_per_paper,
        dry_run=True,
        routing_mode=routing_mode,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        candidate_source=candidate_source,
    )
    plan = extractor.build_candidate_plan(create_stage4_dir=False)
    candidates = plan["candidates"]
    processed_index = plan["processed_index"]
    stage2_selected_figures = plan["stage2_selected_figures"]
    base_row.update(
        {
            "stage2_selected_figures": len(stage2_selected_figures),
            "valid_stage2_selected_figures": sum(
                1 for item in candidates if str(item.get("path_status") or "") in {"valid", "relative_unchecked"}
            ),
            "already_live_success_figures": sum(1 for item in candidates if item.get("figure_processing_action") == "skip_success"),
            "raw_vlm_replay_candidates": sum(1 for item in candidates if item.get("figure_processing_reason") == "raw_vlm_output_available"),
            "schema_replay_candidates": sum(1 for item in candidates if item.get("figure_processing_reason") == "schema_validation_failed"),
            "transient_rerun_candidates": sum(1 for item in candidates if item.get("figure_processing_action") == "rerun_transient"),
            "new_live_candidate_figures": sum(
                1 for item in candidates if item.get("figure_processing_action") == "new_live" and item.get("send_to_vlm")
            ),
            "missing_image_path_count": sum(1 for item in candidates if str(item.get("path_status") or "") == "missing"),
            "directory_path_error_count": sum(1 for item in candidates if str(item.get("path_status") or "") == "directory"),
            "duplicate_vlm_prevented_count": sum(
                1 for item in candidates if item.get("figure_processing_action") in {"skip_success", "replay_candidate"}
            ),
            "dry_run_only_records_ignored_as_success": len(processed_index["dry_run_only_figure_ids"]),
        }
    )
    if defer_large_papers and any(paper_id.startswith(prefix) for prefix in DEFERRED_LARGE_PAPER_PREFIXES):
        base_row["deferred"] = True
        base_row["reason"] = "deferred_large_paper"
    elif base_row["stage2_selected_figures"] == 0:
        base_row["reason"] = "no_stage2_selected_figures"
    elif base_row["new_live_candidate_figures"] > 0:
        base_row["reason"] = "run_live"
    elif base_row["raw_vlm_replay_candidates"] > 0 or base_row["schema_replay_candidates"] > 0:
        base_row["reason"] = "replay_first"
    elif base_row["already_live_success_figures"] > 0:
        base_row["reason"] = "already_live_success"
    return base_row


def _summarize_audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_stage3_done_papers": sum(1 for row in rows if row["has_stage3_summary"]),
        "papers_with_figures_jsonl": sum(1 for row in rows if row["has_figures_jsonl"]),
        "papers_with_figures_for_vision": sum(1 for row in rows if row["has_figures_for_vision"]),
        "papers_without_stage2_selected_figures": sum(1 for row in rows if row["has_stage3_summary"] and int(row["stage2_selected_figures"]) == 0),
        "total_stage2_selected_figures": sum(int(row["stage2_selected_figures"]) for row in rows),
        "valid_stage2_selected_figures": sum(int(row["valid_stage2_selected_figures"]) for row in rows),
        "missing_image_path_count": sum(int(row["missing_image_path_count"]) for row in rows),
        "directory_path_error_count": sum(int(row["directory_path_error_count"]) for row in rows),
        "already_live_success_figures": sum(int(row["already_live_success_figures"]) for row in rows),
        "raw_vlm_replay_candidates": sum(int(row["raw_vlm_replay_candidates"]) for row in rows),
        "schema_replay_candidates": sum(int(row["schema_replay_candidates"]) for row in rows),
        "transient_rerun_candidates": sum(int(row["transient_rerun_candidates"]) for row in rows),
        "new_live_candidate_figures": sum(
            int(row["new_live_candidate_figures"]) for row in rows if not bool(row["deferred"])
        ),
        "duplicate_vlm_prevented_count": sum(int(row["duplicate_vlm_prevented_count"]) for row in rows),
        "dry_run_only_records_ignored_as_success": sum(int(row["dry_run_only_records_ignored_as_success"]) for row in rows),
        "deferred_papers_count": sum(1 for row in rows if bool(row["deferred"])),
        "deferred_figures_count": sum(int(row["new_live_candidate_figures"]) for row in rows if bool(row["deferred"])),
    }


def _build_chunk_summary(chunk_rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    success_summaries = [item["summary"] for item in results if item["status"] == "success"]
    actual_distribution: Counter[str] = Counter()
    for item in results:
        if item["status"] != "success":
            continue
        paper_dir = DEFAULT_OUTPUTS_DIR / item["category"] / item["paper_id"] / DEFAULT_STAGE4_SUBDIR
        for extraction in read_jsonl(paper_dir / "spectra_extractions.jsonl"):
            actual_distribution[str(extraction.get("actual_figure_type") or extraction.get("figure_type") or "unknown")] += 1
    return {
        "chunk_paper_count": len(chunk_rows),
        "papers_attempted": len(results),
        "live_success_count": sum(1 for item in results if item["status"] == "success"),
        "failed_count": sum(1 for item in results if item["status"] == "failed"),
        "total_successful_extractions": sum(int(summary.get("successful_extractions_count") or 0) for summary in success_summaries),
        "total_failed_records": sum(int(summary.get("failed_record_count") or 0) for summary in success_summaries),
        "schema_validation_failed_count": 0,
        "range_peak_midpoint_error_count": 0,
        "sem_tem_unscaled_diameter_error_count": 0,
        "type_mismatch_count": sum(
            len([figure_id for figure_id in summary.get("live_figure_ids", []) if figure_id]) for summary in success_summaries
        ),
        "unknown_or_non_extractable_count": sum(actual_distribution.get(key, 0) for key in ("unknown", "non_extractable")),
        "duplicate_vlm_prevented_count": sum(int(summary.get("duplicate_vlm_prevented_count") or 0) for summary in success_summaries),
        "actual_figure_type_distribution": dict(actual_distribution),
    }


def _build_audit_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage4A Stage2-Selected Full Audit",
        "",
        f"- total_stage3_done_papers: {summary['total_stage3_done_papers']}",
        f"- papers_with_figures_jsonl: {summary['papers_with_figures_jsonl']}",
        f"- papers_with_figures_for_vision: {summary['papers_with_figures_for_vision']}",
        f"- papers_without_stage2_selected_figures: {summary['papers_without_stage2_selected_figures']}",
        f"- total_stage2_selected_figures: {summary['total_stage2_selected_figures']}",
        f"- valid_stage2_selected_figures: {summary['valid_stage2_selected_figures']}",
        f"- missing_image_path_count: {summary['missing_image_path_count']}",
        f"- directory_path_error_count: {summary['directory_path_error_count']}",
        f"- already_live_success_figures: {summary['already_live_success_figures']}",
        f"- raw_vlm_replay_candidates: {summary['raw_vlm_replay_candidates']}",
        f"- schema_replay_candidates: {summary['schema_replay_candidates']}",
        f"- transient_rerun_candidates: {summary['transient_rerun_candidates']}",
        f"- new_live_candidate_figures: {summary['new_live_candidate_figures']}",
        f"- duplicate_vlm_prevented_count: {summary['duplicate_vlm_prevented_count']}",
        f"- dry_run_only_records_ignored_as_success: {summary['dry_run_only_records_ignored_as_success']}",
        f"- deferred_papers_count: {summary['deferred_papers_count']}",
        f"- deferred_figures_count: {summary['deferred_figures_count']}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _build_review_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage4A Stage2-Selected Live Quality Review",
        "",
        f"- total_live_figures: {summary['total_live_figures']}",
        f"- successful_extractions: {summary['successful_extractions']}",
        f"- failed_records: {summary['failed_records']}",
        f"- schema_validation_failed_count: {summary['schema_validation_failed_count']}",
        f"- range_peak_midpoint_error_count: {summary['range_peak_midpoint_error_count']}",
        f"- sem_tem_unscaled_diameter_error_count: {summary['sem_tem_unscaled_diameter_error_count']}",
        f"- type_mismatch_count: {summary['type_mismatch_count']}",
        f"- unknown_or_non_extractable_count: {summary['unknown_or_non_extractable_count']}",
        f"- pass_gate: {summary['pass_gate']}",
        "",
        "## actual_figure_type_distribution",
        "",
    ]
    for key, value in summary["actual_figure_type_distribution"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def _load_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _select_manifest_rows(
    rows: list[dict[str, str]],
    *,
    category: str | None,
    paper_ids: list[str] | None,
    limit: int,
) -> list[dict[str, str]]:
    filtered = rows
    if category:
        wanted_category = normalize_batch_category(category)
        filtered = [row for row in filtered if normalize_batch_category(row.get("category")) == wanted_category]
    if paper_ids:
        wanted = {item.strip() for item in paper_ids if item.strip()}
        filtered = [row for row in filtered if (row.get("paper_id_guess") or "") in wanted]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def _load_requested_paper_ids(paper_ids: str, paper_ids_file: str) -> list[str] | None:
    requested: list[str] = []
    if paper_ids:
        requested.extend([item.strip() for item in paper_ids.split(",") if item.strip()])
    if paper_ids_file:
        requested.extend(
            line.strip()
            for line in Path(paper_ids_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return requested or None


def _is_readable_json(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(payload, dict)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


if __name__ == "__main__":
    main()
