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

from alumina_sol_extractor.stage4.io import read_json, read_jsonl  # noqa: E402
from scripts.dev.replay_stage4a_batch_from_raw import replay_batch  # noqa: E402


DIAGNOSIS_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_live_only_C3_diagnosis.csv"
LIVE_ONLY_V2_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_live_only_abcd_quality_review_v2.csv"
LIVE_ONLY_V2_SUMMARY_TXT = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_live_only_abcd_quality_review_v2_summary.txt"
SELECTED_FOR_REPLAY_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_live_only_C3_selected_for_replay.csv"
FAILURE_AUDIT_CSV = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_live_only_C3_failure_field_audit.csv"
BEFORE_STATUS_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_LIMIT5_FORMAL_OUTPUT_STATUS_BEFORE_REPLAY.md"
FAILURE_AUDIT_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_LIVE_ONLY_C3_FAILURE_FIELD_AUDIT.md"
AFTER_REVIEW_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_LIVE_ONLY_ABCD_QUALITY_REVIEW_V2_AFTER_C3_FIX.md"
FINAL_REPORT_MD = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_C3_FIX_AND_SAFE_RESUME_REPORT.md"

RANGE_PATTERN = re.compile(
    r"(?P<a>\d+(?:\.\d+)?)\s*(?:-|–|—|~|～|to)\s*(?P<b>\d+(?:\.\d+)?)|^[~～]\s*\d+(?:\.\d+)?$",
    re.IGNORECASE,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_stage4_dir(path: Path) -> dict[str, Any]:
    extractions = read_jsonl(path / "spectra_extractions.jsonl")
    failed = read_jsonl(path / "spectra_failed_records.jsonl")
    raw = read_jsonl(path / "raw_vlm_outputs.jsonl")
    summary = read_json(path / "stage4a_summary.json", default={}) or {}
    return {
        "extractions": extractions,
        "failed": failed,
        "raw": raw,
        "summary": summary,
    }


def _is_range_like(text: str | None) -> bool:
    if not text:
        return False
    return bool(RANGE_PATTERN.search(str(text)))


def _count_range_peak_midpoint_errors(extractions: list[dict[str, Any]]) -> int:
    count = 0
    for record in extractions:
        peak_lists = [
            record.get("peaks") or [],
            record.get("endothermic_peaks") or [],
            record.get("exothermic_peaks") or [],
        ]
        for peak_list in peak_lists:
            if not isinstance(peak_list, list):
                continue
            for peak in peak_list:
                if not isinstance(peak, dict):
                    continue
                if _is_range_like(peak.get("source_text")) and peak.get("position") is not None:
                    count += 1
    return count


def _count_sem_tem_unscaled_diameter_errors(extractions: list[dict[str, Any]]) -> int:
    count = 0
    for record in extractions:
        figure_type = str(record.get("figure_type") or "")
        if figure_type not in {"sem_image", "tem_image", "microscopy"}:
            continue
        scale_bar = record.get("scale_bar")
        if scale_bar:
            continue
        if any(
            record.get(field) is not None
            for field in ("diameter_estimate", "diameter_range", "particle_size_estimate", "particle_size_range")
        ):
            basis = str(record.get("diameter_basis") or record.get("particle_size_basis") or "")
            if basis != "not_measurable":
                count += 1
    return count


def _status_row(row: dict[str, str]) -> dict[str, Any]:
    stage4_dir = Path(row["stage4_dir"])
    payload = _load_stage4_dir(stage4_dir)
    extractions = payload["extractions"]
    failed = payload["failed"]
    summary = payload["summary"]
    return {
        "category": row["category"],
        "paper_id": row["paper_id"],
        "stage4_dir": str(stage4_dir),
        "raw_vlm_outputs_exists": (stage4_dir / "raw_vlm_outputs.jsonl").exists(),
        "successful_extractions_count": len(extractions),
        "failed_records_count": len(failed),
        "schema_validation_failed_count": sum(1 for item in failed if item.get("error_type") == "schema_validation_failed"),
        "live_count": int(summary.get("live_count") or 0),
        "dry_run_count": int(summary.get("dry_run_count") or 0),
    }


def _build_before_status(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [_status_row(row) for row in rows]


def _write_before_status_md(rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Stage4A Limit5 Formal Output Status Before Replay",
        "",
    ]
    total_success = sum(int(row["successful_extractions_count"]) for row in rows)
    total_failed = sum(int(row["failed_records_count"]) for row in rows)
    lines.extend(
        [
            f"- paper_count: {len(rows)}",
            f"- total_successful_extractions: {total_success}",
            f"- total_failed_records: {total_failed}",
            "",
            "| paper_id | successful_extractions_count | failed_records_count | schema_validation_failed_count | live_count | dry_run_count | raw_vlm_outputs_exists |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['paper_id']} | {row['successful_extractions_count']} | {row['failed_records_count']} | "
            f"{row['schema_validation_failed_count']} | {row['live_count']} | {row['dry_run_count']} | "
            f"{row['raw_vlm_outputs_exists']} |"
        )
    BEFORE_STATUS_MD.parent.mkdir(parents=True, exist_ok=True)
    BEFORE_STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _audit_failure_fields(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        stage4_dir = Path(row["stage4_dir"])
        payload = _load_stage4_dir(stage4_dir)
        for failed in payload["failed"]:
            error_message = str(failed.get("error_message") or failed.get("error") or "")
            failed_field = ""
            expected_type = ""
            actual_shape = ""
            raw_preview = ""
            if failed.get("error_type") == "schema_validation_failed":
                match = re.search(r"extraction\.([A-Za-z0-9_]+)", error_message)
                failed_field = match.group(1) if match else ""
                if "valid string" in error_message:
                    expected_type = "string"
                elif "valid list" in error_message:
                    expected_type = "list"
                raw_preview = error_message[:220]
                actual_shape = "list" if "input_value=[" in error_message else "unknown"
            else:
                raw_preview = error_message[:220]
            audit_rows.append(
                {
                    "category": row["category"],
                    "paper_id": row["paper_id"],
                    "figure_id": failed.get("figure_id"),
                    "actual_figure_type": failed.get("actual_figure_type") or failed.get("figure_type"),
                    "schema_name": failed.get("schema_name") or "",
                    "failed_field": failed_field,
                    "expected_type": expected_type,
                    "actual_value_shape": actual_shape,
                    "raw_value_preview": raw_preview,
                    "whether_can_normalize": failed.get("error_type") == "schema_validation_failed",
                    "error_type": failed.get("error_type"),
                }
            )
        for record in payload["extractions"]:
            figure_id = record.get("figure_id")
            for peak_list_name in ("peaks", "endothermic_peaks", "exothermic_peaks"):
                peak_list = record.get(peak_list_name) or []
                if not isinstance(peak_list, list):
                    continue
                for peak in peak_list:
                    if not isinstance(peak, dict):
                        continue
                    source_text = peak.get("source_text")
                    if _is_range_like(source_text) and peak.get("position") is not None:
                        audit_rows.append(
                            {
                                "category": row["category"],
                                "paper_id": row["paper_id"],
                                "figure_id": figure_id,
                                "actual_figure_type": record.get("figure_type"),
                                "schema_name": record.get("schema_name") or "",
                                "failed_field": "peaks.position",
                                "expected_type": "null",
                                "actual_value_shape": type(peak.get("position")).__name__,
                                "raw_value_preview": str(source_text)[:220],
                                "whether_can_normalize": True,
                                "error_type": "range_peak_midpoint_error",
                            }
                        )
    return audit_rows


def _write_failure_audit(audit_rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "category",
        "paper_id",
        "figure_id",
        "actual_figure_type",
        "schema_name",
        "failed_field",
        "expected_type",
        "actual_value_shape",
        "raw_value_preview",
        "whether_can_normalize",
        "error_type",
    ]
    _write_csv(FAILURE_AUDIT_CSV, audit_rows, fieldnames)
    by_error = Counter(str(row["error_type"] or "unknown") for row in audit_rows)
    lines = [
        "# Stage4A Live-Only C3 Failure Field Audit",
        "",
        f"- audited_records: {len(audit_rows)}",
        "",
        "## Error Distribution",
        "",
    ]
    for key, value in sorted(by_error.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Detailed Rows", ""])
    for row in audit_rows:
        lines.append(
            f"- {row['paper_id']} / {row['figure_id']} / {row['error_type']}: "
            f"{row['failed_field'] or row['raw_value_preview']}"
        )
    FAILURE_AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    FAILURE_AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_selected_for_replay(rows: list[dict[str, str]]) -> None:
    selected_rows = [{"category": row["category"], "paper_id": row["paper_id"]} for row in rows]
    _write_csv(SELECTED_FOR_REPLAY_CSV, selected_rows, ["category", "paper_id"])


def _regenerate_live_only_v2(rows_to_update: list[dict[str, str]]) -> dict[str, Any]:
    current_rows = _read_csv(LIVE_ONLY_V2_CSV)
    updates: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows_to_update:
        stage4_dir = Path(row["stage4_dir"])
        payload = _load_stage4_dir(stage4_dir)
        extractions = payload["extractions"]
        failed = payload["failed"]
        summary = payload["summary"]
        unknown_count = sum(1 for item in extractions if str(item.get("figure_type") or "") == "unknown")
        needs_manual_review_count = sum(1 for item in extractions if item.get("needs_manual_review"))
        type_mismatch_count = sum(1 for item in extractions if item.get("type_mismatch"))
        range_errors = _count_range_peak_midpoint_errors(extractions)
        schema_failures = sum(1 for item in failed if item.get("error_type") == "schema_validation_failed")
        failed_records = len(failed)
        manual_ratio = round(needs_manual_review_count / len(extractions), 4) if extractions else 0.0
        unknown_ratio = round(unknown_count / len(extractions), 4) if extractions else 0.0
        hard_reasons: list[str] = []
        review_flag = "ok"
        grade_v2 = ""
        if schema_failures > 0:
            hard_reasons.append("schema_validation_failed")
        if range_errors > 0:
            hard_reasons.append("range_peak_midpoint_error")
        if hard_reasons:
            review_flag = "repair_or_replay"
            grade_v2 = "C"
        elif failed_records > 0:
            review_flag = "minor_failed_records"
            grade_v2 = "B"
        else:
            grade_v2 = row.get("grade") if row.get("grade") in {"A", "B"} else "B"
        updates[(row["category"], row["paper_id"])] = {
            "live_count": int(summary.get("live_count") or 0),
            "dry_run_count": int(summary.get("dry_run_count") or 0),
            "successful_extractions": len(extractions),
            "failed_records": failed_records,
            "schema_validation_failed_count": schema_failures,
            "type_mismatch_count": type_mismatch_count,
            "needs_manual_review_count": needs_manual_review_count,
            "manual_review_ratio": manual_ratio,
            "unknown_count": unknown_count,
            "unknown_ratio": unknown_ratio,
            "range_peak_midpoint_errors": range_errors,
            "sem_tem_unscaled_diameter_errors": _count_sem_tem_unscaled_diameter_errors(extractions),
            "grade_v2": grade_v2,
            "review_flag_v2": review_flag,
            "hard_reasons_v2": "|".join(hard_reasons),
        }

    updated_rows: list[dict[str, str]] = []
    for row in current_rows:
        key = (row["category"], row["paper_id"])
        if key in updates:
            for field, value in updates[key].items():
                row[field] = str(value)
        updated_rows.append(row)

    _write_csv(LIVE_ONLY_V2_CSV, updated_rows, list(updated_rows[0].keys()) if updated_rows else [])
    by_grade = Counter(str(row.get("grade_v2") or "unknown") for row in updated_rows)
    lines = [
        "Stage4A universal live-only ABCD v2 summary",
        f"A = {by_grade.get('A', 0)}",
        f"B = {by_grade.get('B', 0)}",
        f"C = {by_grade.get('C', 0)}",
        f"D = {by_grade.get('D', 0)}",
    ]
    LIVE_ONLY_V2_SUMMARY_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    AFTER_REVIEW_MD.write_text(
        "\n".join(
            [
                "# Stage4A Universal Live-Only ABCD Quality Review V2 After C3 Fix",
                "",
                "- replay_materialized: true",
                f"- A: {by_grade.get('A', 0)}",
                f"- B: {by_grade.get('B', 0)}",
                f"- C: {by_grade.get('C', 0)}",
                f"- D: {by_grade.get('D', 0)}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"rows": updated_rows, "counts": dict(by_grade)}


def _write_final_report(
    *,
    before_rows: list[dict[str, Any]],
    replay_summary: dict[str, Any],
    review_counts: dict[str, int],
) -> None:
    lines = [
        "# Stage4A C3 Fix And Safe Resume Report",
        "",
        "- vlm_used_for_c3_fix: false",
        "- stage5_run: false",
        "- replay_materialized: true",
        f"- replay_before_successful_extractions: {sum(int(row['successful_extractions_count']) for row in before_rows)}",
        f"- replay_before_failed_records: {sum(int(row['failed_records_count']) for row in before_rows)}",
        f"- replay_after_successful_extractions: {replay_summary['new_successful_extractions']}",
        f"- replay_after_failed_records: {replay_summary['new_failed_records']}",
        f"- live_only_v2_A: {review_counts.get('A', 0)}",
        f"- live_only_v2_B: {review_counts.get('B', 0)}",
        f"- live_only_v2_C: {review_counts.get('C', 0)}",
        f"- live_only_v2_D: {review_counts.get('D', 0)}",
        "",
        "## Notes",
        "",
        "- schema_validation_failed was repaired offline where raw_vlm_outputs were available.",
        "- range peaks are now replayed with position=null and range_peak_position_not_numeric warnings.",
        "- minor failed records remain warning-level unless they still indicate a hard schema/range problem.",
        "",
    ]
    FINAL_REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    FINAL_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = _read_csv(DIAGNOSIS_CSV)
    before_rows = _build_before_status(rows)
    _write_before_status_md(before_rows)
    failure_audit_rows = _audit_failure_fields(rows)
    _write_failure_audit(failure_audit_rows)
    _write_selected_for_replay(rows)
    backup_name = f"_backup_before_C3_replay_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    replay_summary = replay_batch(
        batch_report=None,
        selected_papers_csv=SELECTED_FOR_REPLAY_CSV,
        outputs_dir=PROJECT_ROOT / "data" / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        report_csv=PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_live_only_C3_replay_materialized.csv",
        summary_json=PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_live_only_C3_replay_materialized_summary.json",
        report_md=PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_LIVE_ONLY_C3_REPLAY_MATERIALIZED.md",
        materialize=True,
        backup_dir_name=backup_name,
    )
    regenerated = _regenerate_live_only_v2(rows)
    _write_final_report(before_rows=before_rows, replay_summary=replay_summary, review_counts=regenerated["counts"])
    print(json.dumps({"replay_summary": replay_summary, "review_counts": regenerated["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
