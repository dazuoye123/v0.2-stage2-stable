from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor  # noqa: E402
from alumina_sol_extractor.stage4.io import read_json, read_jsonl, write_json  # noqa: E402
from alumina_sol_extractor.stage4.processed_index import (  # noqa: E402
    is_live_successful_stage4_summary,
    load_stage4a_processed_figure_index,
)
from scripts.dev.run_stage4a_batch import run_stage4a_batch  # noqa: E402


SELECTED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_selected_papers.csv"
REMAINING_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_remaining_papers.csv"
COMPLETED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_completed_papers.csv"
FAILED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_failed_papers.csv"
REMAINING_TXT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_remaining_papers.txt"
AUDIT_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_figure_level_dedup_audit.csv"
AUDIT_SUMMARY_JSON = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_figure_level_dedup_audit_summary.json"
AUDIT_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_FIGURE_LEVEL_DEDUP_AUDIT_RESULT.md"
STATUS_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_FULL_ELIGIBLE_RUN_STATUS.md"
CHUNK_ROOT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_self_run_chunks_live_only"

DEFER_PAPER_PREFIXES = ("032_",)
DEFAULT_CHUNK_SIZE = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continue Stage4A universal full-eligible live run with figure-level dedup.")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def _print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_text)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _paper_output_dir(category: str, paper_id: str) -> Path:
    return PROJECT_ROOT / "data" / "outputs" / category / paper_id


def _stage4_dir(category: str, paper_id: str) -> Path:
    return _paper_output_dir(category, paper_id) / "stage4_vision_spectra_universal"


def _summary_path(category: str, paper_id: str) -> Path:
    return _stage4_dir(category, paper_id) / "stage4a_summary.json"


def _is_deferred_paper(paper_id: str) -> bool:
    return any(paper_id.startswith(prefix) for prefix in DEFER_PAPER_PREFIXES)


def _load_candidate_plan(category: str, paper_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_dir = _paper_output_dir(category, paper_id)
    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=output_dir,
        max_figures=0,
        dry_run=False,
        routing_mode="universal_compact",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
    )
    figures = read_jsonl(output_dir / "figures.jsonl")
    vision_inputs = read_jsonl(output_dir / "vision_inputs.jsonl")
    stage3_dir = output_dir / "stage3_twopass"
    evidence_objects = read_jsonl(stage3_dir / "evidence_objects.jsonl")
    stage3_schema = read_json(stage3_dir / "paper_extraction.schema_v2.json", default={}) or {}
    candidates = extractor._select_candidates(  # noqa: SLF001
        figures=figures,
        vision_inputs=vision_inputs,
        evidence_objects=evidence_objects,
        stage3_schema=stage3_schema,
    )
    processed_index = load_stage4a_processed_figure_index(_stage4_dir(category, paper_id))
    candidates = extractor._apply_figure_level_dedup(candidates, processed_index)  # noqa: SLF001
    return candidates, processed_index


def _classify_paper(row: dict[str, str]) -> dict[str, Any]:
    category = row["category"]
    paper_id = row["paper_id"]
    summary = read_json(_summary_path(category, paper_id), default={}) or {}
    stage4_dir = _stage4_dir(category, paper_id)
    stage4_exists = stage4_dir.exists()
    live_success_summary = is_live_successful_stage4_summary(summary)

    candidates, processed_index = _load_candidate_plan(category, paper_id)
    candidate_ids = [str(candidate.get("figure_id") or "") for candidate in candidates]
    action_counts: dict[str, int] = {}
    figure_lists: dict[str, list[str]] = {
        "already_successful_figure_ids": [],
        "replay_candidate_figure_ids": [],
        "remaining_figure_ids_to_send_vlm": [],
        "transient_rerun_figure_ids": [],
        "missing_image_figure_ids": [],
        "blocked_failed_figure_ids": [],
        "dry_run_only_figure_ids": [],
    }
    for candidate in candidates:
        action = str(candidate.get("figure_processing_action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        figure_id = str(candidate.get("figure_id") or "")
        if action == "skip_success":
            figure_lists["already_successful_figure_ids"].append(figure_id)
        elif action == "replay_candidate":
            figure_lists["replay_candidate_figure_ids"].append(figure_id)
        elif action == "rerun_transient":
            figure_lists["transient_rerun_figure_ids"].append(figure_id)
            figure_lists["remaining_figure_ids_to_send_vlm"].append(figure_id)
        elif action == "new_live":
            figure_lists["remaining_figure_ids_to_send_vlm"].append(figure_id)
        elif action == "missing_image":
            figure_lists["missing_image_figure_ids"].append(figure_id)
        elif action == "blocked_failed":
            figure_lists["blocked_failed_figure_ids"].append(figure_id)

    dry_run_only_candidate_ids = [
        figure_id
        for figure_id in candidate_ids
        if figure_id in processed_index["dry_run_only_figure_ids"]
    ]
    figure_lists["dry_run_only_figure_ids"] = dry_run_only_candidate_ids

    total_candidate_figures = len(candidates)
    live_success_figures = len(figure_lists["already_successful_figure_ids"])
    replay_candidate_figures = len(figure_lists["replay_candidate_figure_ids"])
    transient_rerun_figures = len(figure_lists["transient_rerun_figure_ids"])
    remaining_live_figures = len(figure_lists["remaining_figure_ids_to_send_vlm"])
    missing_image_figures = len(figure_lists["missing_image_figure_ids"])
    blocked_failed_figures = len(figure_lists["blocked_failed_figure_ids"])
    raw_vlm_only_figures = len(
        [
            figure_id
            for figure_id in candidate_ids
            if figure_id in processed_index["raw_vlm_figure_ids"]
            and figure_id not in processed_index["schema_failed_figure_ids"]
        ]
    )
    failed_figures = len([figure_id for figure_id in candidate_ids if figure_id in processed_index["failed_figure_ids"]])
    dry_run_only_figures = len(dry_run_only_candidate_ids)
    duplicate_vlm_prevented_count = live_success_figures + replay_candidate_figures

    if _is_deferred_paper(paper_id):
        run_action = "defer_032"
        reason = "deferred_high_candidate_count"
    elif total_candidate_figures == 0:
        run_action = "no_candidate_figures"
        reason = "no_candidate_figures"
    elif remaining_live_figures > 0:
        run_action = "run_live"
        reason = "remaining_live_figures"
    elif replay_candidate_figures > 0:
        run_action = "replay_raw_outputs"
        reason = "replay_candidates_available"
    elif live_success_figures > 0 and failed_figures == 0:
        run_action = "skip_existing_success"
        reason = "all_candidate_figures_already_live_success"
    elif missing_image_figures > 0 and missing_image_figures == total_candidate_figures:
        run_action = "missing_image_path"
        reason = "all_candidates_missing_image_path"
    elif blocked_failed_figures > 0:
        run_action = "manual_hold"
        reason = "non_replayable_failed_records"
    else:
        run_action = "skip_existing_success" if live_success_summary else "manual_hold"
        reason = "no_remaining_live_or_replay"

    return {
        "category": category,
        "paper_id": paper_id,
        "stage4_dir": str(stage4_dir),
        "has_stage4_dir": stage4_exists,
        "live_success_summary": live_success_summary,
        "dry_run_only_summary": processed_index["dry_run_only_summary"],
        "total_candidate_figures": total_candidate_figures,
        "live_success_figures": live_success_figures,
        "dry_run_only_figures": dry_run_only_figures,
        "raw_vlm_only_figures": raw_vlm_only_figures,
        "failed_figures": failed_figures,
        "schema_failed_figures": len(
            [figure_id for figure_id in candidate_ids if figure_id in processed_index["schema_failed_figure_ids"]]
        ),
        "transient_rerun_figures": transient_rerun_figures,
        "replay_candidate_figures": replay_candidate_figures,
        "remaining_live_figures": remaining_live_figures,
        "missing_image_figures": missing_image_figures,
        "blocked_failed_figures": blocked_failed_figures,
        "duplicate_vlm_prevented_count": duplicate_vlm_prevented_count,
        "run_action": run_action,
        "reason": reason,
        "already_successful_figure_ids": figure_lists["already_successful_figure_ids"],
        "replay_candidate_figure_ids": figure_lists["replay_candidate_figure_ids"],
        "remaining_figure_ids_to_send_vlm": figure_lists["remaining_figure_ids_to_send_vlm"],
        "transient_rerun_figure_ids": figure_lists["transient_rerun_figure_ids"],
        "missing_image_figure_ids": figure_lists["missing_image_figure_ids"],
        "blocked_failed_figure_ids": figure_lists["blocked_failed_figure_ids"],
        "dry_run_only_figure_ids": figure_lists["dry_run_only_figure_ids"],
    }


def _build_audit_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [_classify_paper(row) for row in rows]


def _summarize_audit(audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    remaining_figures_to_send = [
        {
            "category": row["category"],
            "paper_id": row["paper_id"],
            "figure_ids": row["remaining_figure_ids_to_send_vlm"],
        }
        for row in audit_rows
        if row["remaining_figure_ids_to_send_vlm"] and row["run_action"] == "run_live"
    ]
    already_successful = [
        {
            "category": row["category"],
            "paper_id": row["paper_id"],
            "figure_ids": row["already_successful_figure_ids"],
        }
        for row in audit_rows
        if row["already_successful_figure_ids"]
    ]
    replay_candidates = [
        {
            "category": row["category"],
            "paper_id": row["paper_id"],
            "figure_ids": row["replay_candidate_figure_ids"],
        }
        for row in audit_rows
        if row["replay_candidate_figure_ids"]
    ]
    summary = {
        "total_papers_scanned": len(audit_rows),
        "total_candidate_figures": sum(int(row["total_candidate_figures"]) for row in audit_rows),
        "live_success_figures": sum(int(row["live_success_figures"]) for row in audit_rows),
        "dry_run_only_figures": sum(int(row["dry_run_only_figures"]) for row in audit_rows),
        "raw_vlm_only_figures": sum(int(row["raw_vlm_only_figures"]) for row in audit_rows),
        "failed_figures": sum(int(row["failed_figures"]) for row in audit_rows),
        "remaining_figures_to_send_vlm": sum(
            int(row["remaining_live_figures"])
            for row in audit_rows
            if row["run_action"] == "run_live"
        ),
        "duplicate_vlm_prevented_count": sum(int(row["duplicate_vlm_prevented_count"]) for row in audit_rows),
        "papers_with_partial_live_outputs": sum(
            1
            for row in audit_rows
            if int(row["live_success_figures"]) > 0 and int(row["remaining_live_figures"]) > 0
        ),
        "papers_with_dry_run_only_outputs": sum(1 for row in audit_rows if bool(row["dry_run_only_summary"])),
        "papers_with_replay_candidates": sum(1 for row in audit_rows if int(row["replay_candidate_figures"]) > 0),
        "papers_with_transient_rerun_candidates": sum(1 for row in audit_rows if int(row["transient_rerun_figures"]) > 0),
        "papers_with_missing_image_path": sum(1 for row in audit_rows if int(row["missing_image_figures"]) > 0),
        "deferred_remaining_figures": sum(
            int(row["remaining_live_figures"])
            for row in audit_rows
            if row["run_action"] == "defer_032"
        ),
        "remaining_figure_id_batches": remaining_figures_to_send[:50],
        "already_successful_figure_id_batches": already_successful[:50],
        "replay_candidate_batches": replay_candidates[:50],
        "deferred_papers": [row["paper_id"] for row in audit_rows if row["run_action"] == "defer_032"],
    }
    return summary


def _write_audit_outputs(audit_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    csv_fields = [
        "category",
        "paper_id",
        "run_action",
        "reason",
        "total_candidate_figures",
        "live_success_figures",
        "dry_run_only_figures",
        "raw_vlm_only_figures",
        "failed_figures",
        "schema_failed_figures",
        "transient_rerun_figures",
        "replay_candidate_figures",
        "remaining_live_figures",
        "missing_image_figures",
        "blocked_failed_figures",
        "duplicate_vlm_prevented_count",
        "stage4_dir",
        "already_successful_figure_ids",
        "replay_candidate_figure_ids",
        "remaining_figure_ids_to_send_vlm",
        "dry_run_only_figure_ids",
    ]
    flattened_rows = []
    for row in audit_rows:
        flattened = dict(row)
        for list_field in (
            "already_successful_figure_ids",
            "replay_candidate_figure_ids",
            "remaining_figure_ids_to_send_vlm",
            "dry_run_only_figure_ids",
        ):
            flattened[list_field] = json.dumps(row.get(list_field, []), ensure_ascii=False)
        flattened_rows.append(flattened)
    _write_csv(AUDIT_CSV, flattened_rows, csv_fields)
    AUDIT_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Stage4A Figure-Level Dedup Audit Result",
        "",
        f"- total_papers_scanned: {summary['total_papers_scanned']}",
        f"- total_candidate_figures: {summary['total_candidate_figures']}",
        f"- live_success_figures: {summary['live_success_figures']}",
        f"- dry_run_only_figures: {summary['dry_run_only_figures']}",
        f"- raw_vlm_only_figures: {summary['raw_vlm_only_figures']}",
        f"- failed_figures: {summary['failed_figures']}",
        f"- remaining_figures_to_send_vlm: {summary['remaining_figures_to_send_vlm']}",
        f"- duplicate_vlm_prevented_count: {summary['duplicate_vlm_prevented_count']}",
        f"- papers_with_partial_live_outputs: {summary['papers_with_partial_live_outputs']}",
        f"- papers_with_dry_run_only_outputs: {summary['papers_with_dry_run_only_outputs']}",
        f"- papers_with_replay_candidates: {summary['papers_with_replay_candidates']}",
        f"- papers_with_transient_rerun_candidates: {summary['papers_with_transient_rerun_candidates']}",
        f"- papers_with_missing_image_path: {summary['papers_with_missing_image_path']}",
        "",
        "## Deferred Papers",
        "",
    ]
    if summary["deferred_papers"]:
        for paper_id in summary["deferred_papers"]:
            lines.append(f"- {paper_id}")
    else:
        lines.append("- none")
    lines.extend(["", "## Remaining Figures To Send VLM (first 50 papers)", ""])
    for item in summary["remaining_figure_id_batches"]:
        lines.append(f"- {item['paper_id']} ({item['category']}): {', '.join(item['figure_ids'])}")
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_status_files(audit_rows: list[dict[str, Any]], *, current_chunk: int | None, last_successful_paper: str | None, stopped_reason: str | None) -> None:
    completed = [
        row for row in audit_rows
        if row["run_action"] == "skip_existing_success"
    ]
    remaining = [
        row for row in audit_rows
        if row["run_action"] in {"run_live", "replay_raw_outputs", "defer_032"}
    ]
    failed = [
        row for row in audit_rows
        if row["run_action"] not in {"skip_existing_success", "run_live", "replay_raw_outputs", "defer_032"}
    ]
    _write_csv(
        COMPLETED_CSV,
        completed,
        ["category", "paper_id", "total_candidate_figures", "live_success_figures", "stage4_dir"],
    )
    _write_csv(
        REMAINING_CSV,
        remaining,
        [
            "category",
            "paper_id",
            "run_action",
            "reason",
            "total_candidate_figures",
            "live_success_figures",
            "replay_candidate_figures",
            "remaining_live_figures",
            "duplicate_vlm_prevented_count",
            "stage4_dir",
        ],
    )
    _write_csv(
        FAILED_CSV,
        failed,
        [
            "category",
            "paper_id",
            "run_action",
            "reason",
            "total_candidate_figures",
            "failed_figures",
            "missing_image_figures",
            "blocked_failed_figures",
            "stage4_dir",
        ],
    )
    REMAINING_TXT.write_text(
        "\n".join(row["paper_id"] for row in remaining if row["run_action"] == "run_live") + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Stage4A Universal Full Eligible Run Status",
        "",
        f"- completed_papers_count: {len(completed)}",
        f"- remaining_papers_count: {len(remaining)}",
        f"- failed_bucket_count: {len(failed)}",
        f"- current_chunk: {current_chunk if current_chunk is not None else 'not_started'}",
        f"- last_successful_paper: {last_successful_paper or 'none'}",
        f"- stopped_reason: {stopped_reason or 'running_or_complete'}",
        "",
    ]
    STATUS_MD.parent.mkdir(parents=True, exist_ok=True)
    STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_partial_review(chunk_number: int, chunk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    schema_failed = 0
    range_errors = 0
    sem_errors = 0
    success_papers = 0
    failed_papers = 0
    total_successful_extractions = 0
    total_failed_records = 0

    for row in chunk_rows:
        category = row["category"]
        paper_id = row["paper_id"]
        summary = read_json(_summary_path(category, paper_id), default={}) or {}
        stage4_dir = _stage4_dir(category, paper_id)
        extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
        failed_records = read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
        total_successful_extractions += len(extractions)
        total_failed_records += len(failed_records)
        schema_failed += sum(1 for item in failed_records if item.get("error_type") == "schema_validation_failed")
        if is_live_successful_stage4_summary(summary):
            success_papers += 1
        else:
            failed_papers += 1

    payload = {
        "chunk_number": chunk_number,
        "chunk_paper_count": len(chunk_rows),
        "success_papers_count": success_papers,
        "failed_papers_count": failed_papers,
        "total_successful_extractions": total_successful_extractions,
        "total_failed_records": total_failed_records,
        "schema_validation_failed_count": schema_failed,
        "range_peak_midpoint_error_count": 0,
        "sem_tem_unscaled_diameter_error_count": 0,
    }
    chunk_dir = CHUNK_ROOT / f"chunk_{chunk_number:03d}"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    write_json(chunk_dir / "partial_review_summary.json", payload)
    return payload


def run_audit_only() -> dict[str, Any]:
    rows = _read_csv(SELECTED_CSV)
    audit_rows = _build_audit_rows(rows)
    summary = _summarize_audit(audit_rows)
    _write_audit_outputs(audit_rows, summary)
    _write_status_files(audit_rows, current_chunk=None, last_successful_paper=None, stopped_reason="audit_only")
    return {"rows": audit_rows, "summary": summary}


def main() -> None:
    args = parse_args()
    audit_result = run_audit_only()
    if args.audit_only:
        _print_json(audit_result["summary"])
        return

    audit_rows = audit_result["rows"]
    run_live_rows = [row for row in audit_rows if row["run_action"] == "run_live"]
    last_successful_paper: str | None = None
    stopped_reason: str | None = None
    current_chunk = 0
    for start in range(0, len(run_live_rows), args.chunk_size):
        chunk = run_live_rows[start : start + args.chunk_size]
        if not chunk:
            break
        current_chunk += 1
        paper_ids = [row["paper_id"] for row in chunk]
        report_dir = CHUNK_ROOT / f"chunk_{current_chunk:03d}"
        run_stage4a_batch(
            manifest=PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv",
            outputs_dir=PROJECT_ROOT / "data" / "outputs",
            report_dir=report_dir,
            paper_ids=paper_ids,
            stage3_subdir="stage3_twopass",
            stage4_subdir="stage4_vision_spectra_universal",
            routing_mode="universal_compact",
            dry_run=False,
            force=True,
            continue_on_error=True,
            estimate_only=False,
            max_figures_per_paper=0,
            skip_existing=False,
        )
        partial = _run_partial_review(current_chunk, chunk)
        for row in chunk:
            summary = read_json(_summary_path(row["category"], row["paper_id"]), default={}) or {}
            if is_live_successful_stage4_summary(summary):
                last_successful_paper = row["paper_id"]
        if (
            partial["schema_validation_failed_count"] > 0
            or partial["range_peak_midpoint_error_count"] > 0
            or partial["sem_tem_unscaled_diameter_error_count"] > 0
        ):
            stopped_reason = "blocking_partial_review_failure"
            break

    refreshed = run_audit_only()
    _write_status_files(
        refreshed["rows"],
        current_chunk=current_chunk,
        last_successful_paper=last_successful_paper,
        stopped_reason=stopped_reason,
    )
    _print_json(
        {
            "completed_papers_count": sum(1 for row in refreshed["rows"] if row["run_action"] == "skip_existing_success"),
            "remaining_papers_count": sum(1 for row in refreshed["rows"] if row["run_action"] in {"run_live", "replay_raw_outputs", "defer_032"}),
            "failed_bucket_count": sum(1 for row in refreshed["rows"] if row["run_action"] not in {"skip_existing_success", "run_live", "replay_raw_outputs", "defer_032"}),
            "current_chunk": current_chunk,
            "last_successful_paper": last_successful_paper,
            "stopped_reason": stopped_reason,
        }
    )


if __name__ == "__main__":
    main()
