from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.io import read_json, read_jsonl, write_json  # noqa: E402
from scripts.dev.run_stage4a_batch import (  # noqa: E402
    _is_dry_run_only_stage4_summary,
    _is_live_successful_stage4_summary,
    run_stage4a_batch,
)


SELECTED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_selected_papers.csv"
REMAINING_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_remaining_papers.csv"
COMPLETED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_completed_papers.csv"
FAILED_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_failed_papers.csv"
REMAINING_TXT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_remaining_papers.txt"
STATUS_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_FULL_ELIGIBLE_RUN_STATUS.md"
CHUNK_ROOT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_full_eligible_self_run_chunks_live_only"
DEFER_PAPER_ID = "032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究"
CHUNK_SIZE = 10
RANGE_PATTERN = re.compile(r"(?P<a>\d+(?:\.\d+)?)\s*(?:-|–|—|~|～|to)\s*(?P<b>\d+(?:\.\d+)?)|^[~～]\s*\d+(?:\.\d+)?$", re.IGNORECASE)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field) for field in fieldnames} for row in rows])


def _summary_path(category: str, paper_id: str) -> Path:
    return PROJECT_ROOT / "data" / "outputs" / category / paper_id / "stage4_vision_spectra_universal" / "stage4a_summary.json"


def _stage4_dir(category: str, paper_id: str) -> Path:
    return PROJECT_ROOT / "data" / "outputs" / category / paper_id / "stage4_vision_spectra_universal"


def _load_summary(category: str, paper_id: str) -> dict[str, Any]:
    return read_json(_summary_path(category, paper_id), default={}) or {}


def _is_range_like(text: str | None) -> bool:
    if not text:
        return False
    return bool(RANGE_PATTERN.search(str(text)))


def _range_peak_midpoint_error_count(extractions: list[dict[str, Any]]) -> int:
    count = 0
    for record in extractions:
        for field in ("peaks", "endothermic_peaks", "exothermic_peaks"):
            for peak in record.get(field) or []:
                if not isinstance(peak, dict):
                    continue
                if _is_range_like(peak.get("source_text")) and peak.get("position") is not None:
                    count += 1
    return count


def _sem_tem_unscaled_diameter_error_count(extractions: list[dict[str, Any]]) -> int:
    count = 0
    for record in extractions:
        figure_type = str(record.get("figure_type") or "")
        if figure_type not in {"sem_image", "tem_image", "microscopy"}:
            continue
        if record.get("scale_bar"):
            continue
        if any(record.get(field) is not None for field in ("diameter_estimate", "diameter_range", "particle_size_estimate", "particle_size_range")):
            basis = str(record.get("diameter_basis") or record.get("particle_size_basis") or "")
            if basis != "not_measurable":
                count += 1
    return count


def _schema_validation_failed_count(failed_records: list[dict[str, Any]]) -> int:
    return sum(1 for item in failed_records if item.get("error_type") == "schema_validation_failed")


def _classify_remaining_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    completed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in rows:
        category = row["category"]
        paper_id = row["paper_id"]
        run_action = row["run_action"]
        stage4_dir = _stage4_dir(category, paper_id)
        summary = _load_summary(category, paper_id)
        live_success = _is_live_successful_stage4_summary(summary)
        dry_run_only = _is_dry_run_only_stage4_summary(summary)
        stage4_exists = stage4_dir.exists()
        live_count = int(summary.get("live_count") or 0)
        if "successful_extractions_count" in summary:
            successful_extractions_count = int(summary.get("successful_extractions_count") or 0)
        else:
            successful_extractions_count = live_count
        entry = {
            **row,
            "has_stage4_dir": stage4_exists,
            "live_success": live_success,
            "dry_run_only": dry_run_only,
            "live_count": live_count,
            "dry_run_count": int(summary.get("dry_run_count") or 0),
            "successful_extractions_count": successful_extractions_count,
            "failed_record_count": int(summary.get("failed_record_count") or 0),
        }
        if live_success:
            completed.append(entry)
        elif run_action == "run_live":
            remaining.append(entry)
        else:
            failed.append(entry)
    return completed, remaining, failed


def _write_status_files(completed: list[dict[str, Any]], remaining: list[dict[str, Any]], failed: list[dict[str, Any]], *, current_chunk: int | None, last_successful_paper: str | None, stopped_reason: str | None) -> None:
    completed_fields = ["category", "paper_id", "live_count", "successful_extractions_count", "failed_record_count", "dry_run_only"]
    remaining_fields = ["category", "paper_id", "run_action", "candidate_count", "estimated_vlm_call_count", "reason", "live_success", "dry_run_only", "live_count", "dry_run_count", "successful_extractions_count", "failed_record_count"]
    failed_fields = ["category", "paper_id", "run_action", "candidate_count", "estimated_vlm_call_count", "reason", "live_success", "dry_run_only", "live_count", "dry_run_count", "successful_extractions_count", "failed_record_count"]
    _write_csv(COMPLETED_CSV, completed, completed_fields)
    _write_csv(REMAINING_CSV, remaining, remaining_fields)
    _write_csv(FAILED_CSV, failed, failed_fields)
    REMAINING_TXT.write_text("\n".join(row["paper_id"] for row in remaining if row["run_action"] == "run_live") + "\n", encoding="utf-8")
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
        summary = _load_summary(category, paper_id)
        stage4_dir = _stage4_dir(category, paper_id)
        extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
        failed_records = read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
        total_successful_extractions += len(extractions)
        total_failed_records += len(failed_records)
        schema_failed += _schema_validation_failed_count(failed_records)
        range_errors += _range_peak_midpoint_error_count(extractions)
        sem_errors += _sem_tem_unscaled_diameter_error_count(extractions)
        if _is_live_successful_stage4_summary(summary):
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
        "range_peak_midpoint_error_count": range_errors,
        "sem_tem_unscaled_diameter_error_count": sem_errors,
    }
    chunk_dir = CHUNK_ROOT / f"chunk_{chunk_number:03d}"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    write_json(chunk_dir / "partial_review_summary.json", payload)
    return payload


def main() -> None:
    rows = _read_csv(SELECTED_CSV)
    completed, remaining, failed = _classify_remaining_rows(rows)
    remaining = [
        row for row in remaining
        if row["run_action"] == "run_live"
        and row["paper_id"] != DEFER_PAPER_ID
        and not row["live_success"]
    ]
    last_successful_paper: str | None = None
    stopped_reason: str | None = None
    current_chunk = 0

    for start in range(0, len(remaining), CHUNK_SIZE):
        chunk = remaining[start : start + CHUNK_SIZE]
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
            summary = _load_summary(row["category"], row["paper_id"])
            if _is_live_successful_stage4_summary(summary):
                last_successful_paper = row["paper_id"]
        if (
            partial["schema_validation_failed_count"] > 0
            or partial["range_peak_midpoint_error_count"] > 0
            or partial["sem_tem_unscaled_diameter_error_count"] > 0
        ):
            stopped_reason = "blocking_partial_review_failure"
            break

    refreshed_rows = _read_csv(SELECTED_CSV)
    completed_now, remaining_now, failed_now = _classify_remaining_rows(refreshed_rows)
    remaining_now = [row for row in remaining_now if row["paper_id"] != DEFER_PAPER_ID]
    _write_status_files(
        completed_now,
        remaining_now,
        failed_now,
        current_chunk=current_chunk,
        last_successful_paper=last_successful_paper,
        stopped_reason=stopped_reason,
    )
    print(
        json.dumps(
            {
                "completed_papers_count": len(completed_now),
                "remaining_papers_count": len(remaining_now),
                "failed_bucket_count": len(failed_now),
                "current_chunk": current_chunk,
                "last_successful_paper": last_successful_paper,
                "stopped_reason": stopped_reason,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
