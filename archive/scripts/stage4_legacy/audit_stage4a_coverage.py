from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor  # noqa: E402
from alumina_sol_extractor.stage4.io import read_json, read_jsonl, write_json  # noqa: E402
from alumina_sol_extractor.stage4.processed_index import (  # noqa: E402
    classify_failed_record,
    is_dry_run_extraction_record,
    is_dry_run_raw_output_record,
    is_fallback_success_extraction_record,
    is_live_success_extraction_record,
    is_real_raw_output_record,
)
from alumina_sol_extractor.utils.batch_categories import normalize_batch_category  # noqa: E402


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_STAGE3_SUBDIR = "stage3_twopass"
DEFAULT_STAGE4_SUBDIR = "stage4_vision_spectra_universal"
DEFAULT_AUDIT_DIR = PROJECT_ROOT / "data" / "analysis_outputs_stage4a_audit"

REAL_SUCCESS_STATUSES = {"success_live", "success_reused_previous"}
MANIFEST_STATUSES = {"dry_run_only", "failed_retryable", "raw_without_extraction", "missing_all", "schema_validation_failed"}
PRIORITY_BY_STATUS = {
    "missing_all": "P0",
    "dry_run_only": "P1",
    "failed_retryable": "P2",
    "raw_without_extraction": "P3",
    "schema_validation_failed": "P4",
}
RETRYABLE_STATUSES = {"missing_all", "dry_run_only", "failed_retryable", "raw_without_extraction"}


def main() -> None:
    result = run_audit()
    print(json.dumps(result["consistency"], ensure_ascii=False, indent=2))


def run_audit(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR,
    stage3_subdir: str = DEFAULT_STAGE3_SUBDIR,
    stage4_subdir: str = DEFAULT_STAGE4_SUBDIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
) -> dict[str, Any]:
    manifest_rows = _load_manifest_rows(manifest_path)
    per_figure_rows: list[dict[str, Any]] = []
    per_paper_rows: list[dict[str, Any]] = []
    error_summary: Counter[tuple[str, str, str]] = Counter()
    dry_run_only_rows: list[dict[str, Any]] = []
    manifest_rows_out: list[dict[str, Any]] = []
    latest_raw_info = {"path": "", "mtime": None}

    expected_candidates_total = 0
    raw_real_total = 0
    raw_dry_total = 0
    extraction_live_total = 0
    extraction_dry_total = 0
    extraction_fallback_total = 0
    failed_records_total = 0
    status_counter: Counter[str] = Counter()
    duplicate_count = 0
    total_stage3_done_papers = 0

    for row in manifest_rows:
        category = normalize_batch_category(row.get("category"))
        paper_id = row.get("paper_id_guess") or ""
        paper_dir = outputs_dir / category / paper_id
        stage3_summary_path = paper_dir / stage3_subdir / "stage3_summary.json"
        if not _is_readable_json(stage3_summary_path):
            continue
        total_stage3_done_papers += 1

        extractor = Stage4VisionSpectraExtractor(
            paper_id=paper_id,
            output_dir=paper_dir,
            dry_run=True,
            routing_mode="universal_compact",
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            candidate_source="stage2-selected",
        )
        plan = extractor.build_candidate_plan(create_stage4_dir=False)
        candidates = plan["candidates"]
        stage4_dir = plan["stage4_dir"]
        files = _load_stage4a_files(stage4_dir)
        latest_raw_info = _update_latest_raw_info(latest_raw_info, files["raw_file_mtime"], stage4_dir / "raw_vlm_outputs.jsonl")

        raw_by_figure = _group_by_figure_id(files["raw_outputs"])
        extractions_by_figure = _group_by_figure_id(files["extractions"])
        failed_by_figure = _group_by_figure_id(files["failed_records"])

        paper_counter: Counter[str] = Counter()
        paper_retryable_count = 0
        paper_manual_review_count = 0
        for candidate in candidates:
            expected_candidates_total += 1
            figure_id = str(candidate.get("figure_id") or "").strip()
            raw_records = raw_by_figure.get(figure_id, [])
            extraction_records = extractions_by_figure.get(figure_id, [])
            failed_records = failed_by_figure.get(figure_id, [])
            audit_state = _classify_figure_state(
                category=category,
                paper_id=paper_id,
                candidate=candidate,
                paper_dir=paper_dir,
                stage4_dir=stage4_dir,
                raw_records=raw_records,
                extraction_records=extraction_records,
                failed_records=failed_records,
                stage4_summary=files["summary"],
            )
            per_figure_rows.append(dict(audit_state))
            paper_counter[str(audit_state["status"])] += 1
            if audit_state["duplicate_or_inconsistent"]:
                paper_counter["duplicate_or_inconsistent"] += 1
                duplicate_count += 1
            if audit_state["retryable"]:
                paper_retryable_count += 1
            if audit_state["needs_manual_review"]:
                paper_manual_review_count += 1
            if audit_state["status"] == "dry_run_only":
                dry_run_only_rows.append(dict(audit_state))
            if audit_state["status"] in MANIFEST_STATUSES:
                manifest_rows_out.append(
                    {
                        "category": audit_state["category"],
                        "paper_id": audit_state["paper_id"],
                        "figure_id": audit_state["figure_id"],
                        "image_path": audit_state["image_path"],
                        "status": audit_state["status"],
                        "reason": audit_state["error_type"] or audit_state["status"],
                        "suggested_action": audit_state["suggested_action"],
                        "retryable": audit_state["retryable"],
                        "priority": PRIORITY_BY_STATUS[audit_state["status"]],
                    }
                )
            raw_real_total += int(audit_state["raw_real_count"])
            raw_dry_total += int(audit_state["raw_dry_run_count"])
            extraction_live_total += int(audit_state["extraction_live_count"])
            extraction_dry_total += int(audit_state["extraction_dry_run_count"])
            extraction_fallback_total += int(audit_state["fallback_count"])
            failed_records_total += int(audit_state["failed_count"])
            status_counter[str(audit_state["status"])] += 1
            if audit_state["error_type"] or audit_state["error_message"]:
                error_summary[(str(audit_state["status"]), str(audit_state["error_type"]), str(audit_state["error_message"]))] += 1

        per_paper_rows.append(
            {
                "category": category,
                "paper_id": paper_id,
                "expected_figures": len(candidates),
                "success_live": paper_counter["success_live"],
                "success_reused_previous": paper_counter["success_reused_previous"],
                "dry_run_only": paper_counter["dry_run_only"],
                "failed_retryable": paper_counter["failed_retryable"],
                "failed_nonretryable": paper_counter["failed_nonretryable"],
                "schema_validation_failed": paper_counter["schema_validation_failed"],
                "raw_without_extraction": paper_counter["raw_without_extraction"],
                "missing_all": paper_counter["missing_all"],
                "duplicate_or_inconsistent": paper_counter["duplicate_or_inconsistent"],
                "coverage_rate_live_only": _safe_ratio(paper_counter["success_live"], len(candidates)),
                "coverage_rate_including_fallback": _safe_ratio(
                    paper_counter["success_live"] + paper_counter["success_reused_previous"], len(candidates)
                ),
                "retryable_count": paper_retryable_count,
                "needs_manual_review_count": paper_manual_review_count,
            }
        )

    consistency = {
        "expected_candidates_total": expected_candidates_total,
        "total_stage3_done_papers": total_stage3_done_papers,
        "raw_vlm_outputs_total": raw_real_total + raw_dry_total,
        "raw_vlm_outputs_real": raw_real_total,
        "raw_vlm_outputs_dry_run": raw_dry_total,
        "spectra_extractions_total": extraction_live_total + extraction_dry_total + extraction_fallback_total,
        "spectra_extractions_live": extraction_live_total,
        "spectra_extractions_dry_run": extraction_dry_total,
        "spectra_extractions_fallback": extraction_fallback_total,
        "failed_records_total": failed_records_total,
        "success_live_total": status_counter["success_live"],
        "success_reused_previous_total": status_counter["success_reused_previous"],
        "dry_run_only_total": status_counter["dry_run_only"],
        "failed_retryable_total": status_counter["failed_retryable"],
        "failed_nonretryable_total": status_counter["failed_nonretryable"],
        "schema_validation_failed_total": status_counter["schema_validation_failed"],
        "raw_without_extraction_total": status_counter["raw_without_extraction"],
        "missing_all_total": status_counter["missing_all"],
        "duplicate_or_inconsistent_total": duplicate_count,
        "raw_minus_success_minus_failed": raw_real_total
        - status_counter["success_live"]
        - status_counter["success_reused_previous"]
        - status_counter["failed_retryable"]
        - status_counter["failed_nonretryable"]
        - status_counter["schema_validation_failed"],
        "recommended_retry_total": sum(1 for row in manifest_rows_out if row["priority"] in {"P0", "P1", "P2", "P3"}),
        "latest_raw_time": latest_raw_info["mtime"].isoformat() if latest_raw_info["mtime"] else None,
        "latest_raw_file": latest_raw_info["path"],
    }

    audit_dir.mkdir(parents=True, exist_ok=True)
    coverage_csv = audit_dir / "stage4a_coverage_audit.csv"
    paper_summary_csv = audit_dir / "stage4a_paper_coverage_summary.csv"
    retry_manifest_csv = audit_dir / "stage4a_missing_or_retry_manifest.csv"
    error_summary_csv = audit_dir / "stage4a_error_type_summary.csv"
    dry_run_report_csv = audit_dir / "stage4a_dry_run_only_report.csv"
    consistency_json = audit_dir / "stage4a_raw_extraction_consistency.json"
    report_md = audit_dir / "stage4a_audit_report.md"

    _write_csv(coverage_csv, per_figure_rows)
    _write_csv(paper_summary_csv, per_paper_rows)
    _write_csv(retry_manifest_csv, manifest_rows_out)
    _write_csv(
        error_summary_csv,
        [
            {
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "count": count,
            }
            for (status, error_type, error_message), count in sorted(error_summary.items(), key=lambda item: (-item[1], *item[0]))
        ],
    )
    _write_csv(dry_run_report_csv, dry_run_only_rows)
    write_json(consistency_json, consistency)
    report_md.write_text(_build_markdown_report(consistency), encoding="utf-8")

    return {
        "coverage_csv": coverage_csv,
        "paper_summary_csv": paper_summary_csv,
        "retry_manifest_csv": retry_manifest_csv,
        "error_summary_csv": error_summary_csv,
        "dry_run_report_csv": dry_run_report_csv,
        "consistency_json": consistency_json,
        "report_md": report_md,
        "consistency": consistency,
    }


def _classify_figure_state(
    *,
    category: str,
    paper_id: str,
    candidate: dict[str, Any],
    paper_dir: Path,
    stage4_dir: Path,
    raw_records: list[dict[str, Any]],
    extraction_records: list[dict[str, Any]],
    failed_records: list[dict[str, Any]],
    stage4_summary: dict[str, Any],
) -> dict[str, Any]:
    real_raw_records = [record for record in raw_records if is_real_raw_output_record(record)]
    dry_raw_records = [record for record in raw_records if is_dry_run_raw_output_record(record)]
    live_extractions = [record for record in extraction_records if is_live_success_extraction_record(record, summary=stage4_summary)]
    dry_extractions = [record for record in extraction_records if is_dry_run_extraction_record(record, summary=stage4_summary)]
    fallback_extractions = [record for record in extraction_records if is_fallback_success_extraction_record(record)]

    schema_failed_records = [record for record in failed_records if classify_failed_record(record) == "schema_validation_failed"]
    retryable_failed_records = [record for record in failed_records if classify_failed_record(record) == "failed_retryable"]
    nonretryable_failed_records = [record for record in failed_records if classify_failed_record(record) == "failed_nonretryable"]
    unknown_failed_records = [record for record in failed_records if classify_failed_record(record) == "failed_unknown"]

    has_live_success = bool(live_extractions)
    has_fallback_success = bool(fallback_extractions)
    has_failed = bool(failed_records)
    duplicate_or_inconsistent = False
    if has_live_success and (schema_failed_records or retryable_failed_records or nonretryable_failed_records or unknown_failed_records):
        duplicate_or_inconsistent = True
    if len({str(item.get("actual_figure_type") or item.get("figure_type") or "") for item in live_extractions if item}) > 1:
        duplicate_or_inconsistent = True

    path_status = str(candidate.get("path_status") or "")
    if has_live_success:
        status = "success_live"
        retryable = False
        needs_manual_review = False
        suggested_action = "keep_live_success"
    elif has_fallback_success:
        status = "success_reused_previous"
        retryable = False
        needs_manual_review = False
        suggested_action = "keep_reused_previous_success"
    elif (dry_raw_records or dry_extractions) and not real_raw_records:
        status = "dry_run_only"
        retryable = True
        needs_manual_review = False
        suggested_action = "rerun_live"
    elif schema_failed_records:
        status = "schema_validation_failed"
        retryable = False
        needs_manual_review = True
        suggested_action = "replay_or_manual_review"
    elif retryable_failed_records:
        status = "failed_retryable"
        retryable = True
        needs_manual_review = False
        suggested_action = "rerun_live"
    elif nonretryable_failed_records or path_status in {"missing", "directory"}:
        status = "failed_nonretryable"
        retryable = False
        needs_manual_review = True
        suggested_action = "manual_hold"
    elif unknown_failed_records:
        status = "failed_nonretryable"
        retryable = False
        needs_manual_review = True
        suggested_action = "needs_manual_review"
    elif real_raw_records:
        status = "raw_without_extraction"
        retryable = True
        needs_manual_review = True
        suggested_action = "replay_raw_then_review"
    elif not candidate.get("send_to_vlm"):
        status = "routed_out_or_not_candidate"
        retryable = False
        needs_manual_review = False
        suggested_action = "skip"
    else:
        status = "missing_all"
        retryable = True
        needs_manual_review = False
        suggested_action = "rerun_live"

    primary_error = (
        schema_failed_records[:1]
        or retryable_failed_records[:1]
        or nonretryable_failed_records[:1]
        or unknown_failed_records[:1]
    )
    error_type = str(primary_error[0].get("error_type") or "") if primary_error else ""
    error_message = str(primary_error[0].get("error_message") or primary_error[0].get("error") or "") if primary_error else ""

    return {
        "category": category,
        "paper_id": paper_id,
        "paper_dir": str(paper_dir),
        "figure_id": str(candidate.get("figure_id") or ""),
        "image_path": str(candidate.get("source_image_path") or candidate.get("vision_image_path") or candidate.get("image_path") or ""),
        "figure_caption": str(candidate.get("caption") or ""),
        "routing_label": str(
            candidate.get("stage2_predicted_figure_type")
            or candidate.get("initial_figure_type")
            or candidate.get("stage2_figure_class")
            or ""
        ),
        "source_file": str(candidate.get("source_file") or candidate.get("source_pdf") or candidate.get("selection_source") or ""),
        "expected_stage4a_subdir": str(stage4_dir.name),
        "status": status,
        "has_raw_real": bool(real_raw_records),
        "has_raw_dry_run": bool(dry_raw_records),
        "has_extraction_live": bool(live_extractions),
        "has_extraction_dry_run": bool(dry_extractions),
        "has_fallback_success": bool(fallback_extractions),
        "has_failed": has_failed,
        "raw_real_count": len(real_raw_records),
        "raw_dry_run_count": len(dry_raw_records),
        "extraction_live_count": len(live_extractions),
        "extraction_dry_run_count": len(dry_extractions),
        "fallback_count": len(fallback_extractions),
        "failed_count": len(failed_records),
        "error_type": error_type,
        "error_message": error_message,
        "retryable": retryable,
        "needs_manual_review": needs_manual_review,
        "suggested_action": suggested_action,
        "duplicate_or_inconsistent": duplicate_or_inconsistent,
        "stage4_dir": str(stage4_dir),
    }


def _load_stage4a_files(stage4_dir: Path) -> dict[str, Any]:
    extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
    raw_outputs = read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl")
    failed_records = _load_failed_records(stage4_dir)
    summary = read_json(stage4_dir / "stage4a_summary.json", default={}) or {}
    raw_path = stage4_dir / "raw_vlm_outputs.jsonl"
    return {
        "extractions": extractions,
        "raw_outputs": raw_outputs,
        "failed_records": failed_records,
        "summary": summary,
        "raw_file_mtime": datetime.fromtimestamp(raw_path.stat().st_mtime) if raw_path.exists() else None,
    }


def _load_failed_records(stage4_dir: Path) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for path in (stage4_dir / "spectra_failed_records.jsonl", stage4_dir / "failed_records.jsonl"):
        for record in read_jsonl(path):
            key = (
                str(record.get("figure_id") or ""),
                str(record.get("error_type") or ""),
                str(record.get("error_message") or record.get("error") or ""),
                str(record.get("final_status") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(record)
    return merged


def _group_by_figure_id(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        figure_id = str(record.get("figure_id") or "").strip()
        if figure_id:
            grouped[figure_id].append(record)
    return grouped


def _load_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _is_readable_json(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(payload, dict)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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
            writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fieldnames})


def _serialize_csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _build_markdown_report(consistency: dict[str, Any]) -> str:
    lines = [
        "# Stage4A Coverage Audit",
        "",
        "## 总体统计",
        "",
        f"- expected_candidates_total: {consistency['expected_candidates_total']}",
        f"- success_live_total: {consistency['success_live_total']}",
        f"- success_reused_previous_total: {consistency['success_reused_previous_total']}",
        f"- dry_run_only_total: {consistency['dry_run_only_total']}",
        f"- failed_retryable_total: {consistency['failed_retryable_total']}",
        f"- failed_nonretryable_total: {consistency['failed_nonretryable_total']}",
        f"- schema_validation_failed_total: {consistency['schema_validation_failed_total']}",
        f"- raw_without_extraction_total: {consistency['raw_without_extraction_total']}",
        f"- missing_all_total: {consistency['missing_all_total']}",
        f"- duplicate_or_inconsistent_total: {consistency['duplicate_or_inconsistent_total']}",
        f"- recommended_retry_total: {consistency['recommended_retry_total']}",
        "",
        "## 口径说明",
        "",
        "- dry_run_only：只有 dry-run raw 或 dry-run extraction，没有真实 live success，也没有 fallback success。",
        "- success_reused_previous：通过 replay / reused_previous_success / fallback 得到成功结果，不算 live success。",
        "- raw_without_extraction：已经有真实 raw，但没有成功 extraction，也没有完整 failed 记录。",
        "- raw_vlm_outputs 与 spectra_extractions + failed_records 不完全对齐，常见原因是同一 figure 多次 raw、dry-run 历史、raw 已存在但后处理未 materialize。",
        "",
        f"- latest_raw_time: {consistency.get('latest_raw_time')}",
        f"- latest_raw_file: {consistency.get('latest_raw_file')}",
        "",
        "## 建议",
        "",
        "- 优先补跑 dry_run_only / missing_all / failed_retryable。",
        "- raw_without_extraction 先做 replay，再决定是否 live rerun。",
        "- schema_validation_failed 默认进入人工复核或 normalization/replay，不要直接重打 VLM。",
        "- failed_nonretryable 通常不建议盲目补跑。",
        "",
    ]
    return "\n".join(lines) + "\n"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _update_latest_raw_info(current: dict[str, Any], mtime: datetime | None, raw_path: Path) -> dict[str, Any]:
    if mtime is None:
        return current
    if current["mtime"] is None or mtime > current["mtime"]:
        return {"mtime": mtime, "path": str(raw_path)}
    return current


if __name__ == "__main__":
    main()
