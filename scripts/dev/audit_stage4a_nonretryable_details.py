from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.io import read_jsonl, write_json  # noqa: E402

try:  # pragma: no cover - environment-dependent import
    from PIL import Image, UnidentifiedImageError  # type: ignore
except Exception:  # noqa: BLE001
    Image = None
    UnidentifiedImageError = Exception


AUDIT_DIR = PROJECT_ROOT / "data" / "analysis_outputs_stage4a_audit"
DEFAULT_COVERAGE_CSV = AUDIT_DIR / "stage4a_coverage_audit.csv"
DEFAULT_ERROR_SUMMARY_CSV = AUDIT_DIR / "stage4a_error_type_summary.csv"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"

SCHEMA_PARSE_HINTS = (
    "schema_validation_failed",
    "validation error",
    "validationerror",
    "pydantic",
    "json",
    "parse",
    "malformed",
    "empty response",
    "response_parse_error",
    "raw_without_valid_extraction",
    "invalid string",
    "input should be a valid",
    "valueerror",
)
PATH_HINTS = (
    "missing_image",
    "missing image",
    "invalid image path",
    "path does not appear to be valid",
    "filenotfounderror",
    "permissionerror",
)
AUTH_HINTS = (
    "auth",
    "unauthorized",
    "forbidden",
    "arrearage",
    "api key",
    "access denied",
)
UNSUPPORTED_HINTS = (
    "unsupported format",
    "unsupported media",
    "not an image",
)


def main() -> None:
    result = run_nonretryable_reaudit()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def run_nonretryable_reaudit(
    *,
    coverage_csv: Path = DEFAULT_COVERAGE_CSV,
    error_summary_csv: Path = DEFAULT_ERROR_SUMMARY_CSV,
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR,
    audit_dir: Path = AUDIT_DIR,
) -> dict[str, Any]:
    rows = _load_csv_rows(coverage_csv)
    nonretryable_rows = [row for row in rows if str(row.get("status") or "") == "failed_nonretryable"]
    reaudit_rows: list[dict[str, Any]] = []
    force_retry_rows: list[dict[str, Any]] = []
    true_nonretryable_rows: list[dict[str, Any]] = []
    by_original_error_type: Counter[str] = Counter()
    by_new_retry_reason: Counter[str] = Counter()

    for row in nonretryable_rows:
        category = str(row.get("category") or "")
        paper_id = str(row.get("paper_id") or "")
        figure_id = str(row.get("figure_id") or "")
        paper_dir = outputs_dir / category / paper_id
        stage4_dir = paper_dir / "stage4_vision_spectra_universal"
        failed_records = _group_by_figure_id(_load_failed_records(stage4_dir))
        raw_outputs = _group_by_figure_id(read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl"))
        extractions = _group_by_figure_id(read_jsonl(stage4_dir / "spectra_extractions.jsonl"))

        figure_failed_records = failed_records.get(figure_id, [])
        figure_raw_outputs = raw_outputs.get(figure_id, [])
        figure_extractions = extractions.get(figure_id, [])
        original_error_type, original_error_message = _resolve_primary_error(
            row=row,
            failed_records=figure_failed_records,
            raw_outputs=figure_raw_outputs,
        )
        image_check = inspect_image_reference(
            image_path=row.get("image_path"),
            paper_dir=paper_dir,
            outputs_dir=outputs_dir,
            project_root=PROJECT_ROOT,
        )
        classification = classify_nonretryable_candidate(
            original_error_type=original_error_type,
            original_error_message=original_error_message,
            image_check=image_check,
            has_raw_real=_to_bool(row.get("has_raw_real")),
            has_extraction_live=_to_bool(row.get("has_extraction_live")),
            has_failed=_to_bool(row.get("has_failed")),
            duplicate_or_inconsistent=_to_bool(row.get("duplicate_or_inconsistent")),
        )

        reaudit_row = {
            "category": category,
            "paper_id": paper_id,
            "figure_id": figure_id,
            "image_path": str(row.get("image_path") or ""),
            "resolved_image_path": image_check["resolved_image_path"],
            "image_exists": image_check["image_exists"],
            "image_size_bytes": image_check["image_size_bytes"],
            "image_readable": image_check["image_readable"],
            "image_error": image_check["image_error"],
            "original_error_type": original_error_type,
            "original_error_message": original_error_message,
            "has_raw_real": _to_bool(row.get("has_raw_real")),
            "has_extraction_live": _to_bool(row.get("has_extraction_live")),
            "has_failed": _to_bool(row.get("has_failed")),
            "duplicate_or_inconsistent": _to_bool(row.get("duplicate_or_inconsistent")),
            "force_retry_candidate": classification["force_retry_candidate"],
            "true_nonretryable": classification["true_nonretryable"],
            "needs_manual_review": classification["needs_manual_review"],
            "new_retry_reason": classification["new_retry_reason"],
            "suggested_action": classification["suggested_action"],
        }
        reaudit_rows.append(reaudit_row)
        by_original_error_type[original_error_type or "unknown"] += 1
        by_new_retry_reason[classification["new_retry_reason"] or "unknown"] += 1

        if classification["force_retry_candidate"]:
            force_retry_rows.append(
                {
                    "category": category,
                    "paper_id": paper_id,
                    "figure_id": figure_id,
                    "image_path": str(row.get("image_path") or ""),
                    "resolved_image_path": image_check["resolved_image_path"],
                    "reason": classification["new_retry_reason"],
                    "suggested_action": classification["suggested_action"],
                    "priority": _priority_for_force_retry_reason(classification["new_retry_reason"]),
                    "status": "failed_nonretryable",
                    "retryable": True,
                }
            )
        if classification["true_nonretryable"]:
            true_nonretryable_rows.append(reaudit_row)

    summary = {
        "failed_nonretryable_total": len(nonretryable_rows),
        "image_exists_count": sum(1 for row in reaudit_rows if row["image_exists"]),
        "image_readable_count": sum(1 for row in reaudit_rows if row["image_readable"]),
        "force_retry_candidate_count": sum(1 for row in reaudit_rows if row["force_retry_candidate"]),
        "true_nonretryable_count": sum(1 for row in reaudit_rows if row["true_nonretryable"]),
        "needs_manual_review_count": sum(1 for row in reaudit_rows if row["needs_manual_review"]),
        "by_original_error_type": dict(by_original_error_type),
        "by_new_retry_reason": dict(by_new_retry_reason),
        "source_error_summary_csv": str(error_summary_csv),
    }

    audit_dir.mkdir(parents=True, exist_ok=True)
    reaudit_csv = audit_dir / "stage4a_nonretryable_reaudit.csv"
    force_retry_csv = audit_dir / "stage4a_force_retry_nonretryable_manifest.csv"
    true_nonretryable_csv = audit_dir / "stage4a_true_nonretryable_manifest.csv"
    summary_json = audit_dir / "stage4a_nonretryable_reaudit_summary.json"
    report_md = audit_dir / "stage4a_nonretryable_reaudit_report.md"

    _write_csv(reaudit_csv, reaudit_rows)
    _write_csv(force_retry_csv, force_retry_rows)
    _write_csv(true_nonretryable_csv, true_nonretryable_rows)
    write_json(summary_json, summary)
    report_md.write_text(_build_markdown_report(summary), encoding="utf-8")
    return {
        "reaudit_csv": reaudit_csv,
        "force_retry_csv": force_retry_csv,
        "true_nonretryable_csv": true_nonretryable_csv,
        "summary_json": summary_json,
        "report_md": report_md,
        "summary": summary,
    }


def inspect_image_reference(
    *,
    image_path: Any,
    paper_dir: Path,
    outputs_dir: Path,
    project_root: Path,
) -> dict[str, Any]:
    raw_path = str(image_path or "").strip()
    candidates: list[Path] = []
    if raw_path:
        raw = Path(raw_path)
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend([paper_dir / raw, outputs_dir / raw, project_root / raw])
    resolved: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            resolved = candidate
            break
    image_exists = bool(resolved and resolved.exists())
    size_bytes = resolved.stat().st_size if image_exists else 0
    readable = False
    image_error = ""
    if image_exists and resolved is not None and resolved.is_file() and size_bytes > 0:
        readable, image_error = _verify_image_readable(resolved)
    elif image_exists and resolved is not None and resolved.is_dir():
        image_error = "path_is_directory"
    elif image_exists and size_bytes <= 0:
        image_error = "empty_file"
    else:
        image_error = "image_not_found"
    return {
        "resolved_image_path": str(resolved) if resolved else "",
        "image_exists": image_exists,
        "image_size_bytes": int(size_bytes),
        "image_readable": readable,
        "image_error": image_error,
    }


def classify_nonretryable_candidate(
    *,
    original_error_type: str,
    original_error_message: str,
    image_check: dict[str, Any],
    has_raw_real: bool,
    has_extraction_live: bool,
    has_failed: bool,
    duplicate_or_inconsistent: bool,
) -> dict[str, Any]:
    error_text = f"{original_error_type} {original_error_message}".lower()
    image_exists = bool(image_check["image_exists"])
    image_readable = bool(image_check["image_readable"])
    path_now_resolvable = image_exists and image_readable and any(hint in error_text for hint in PATH_HINTS)
    schema_or_parse = any(hint in error_text for hint in SCHEMA_PARSE_HINTS)
    auth_error = any(hint in error_text for hint in AUTH_HINTS)
    unsupported = any(hint in error_text for hint in UNSUPPORTED_HINTS)

    if duplicate_or_inconsistent or has_extraction_live:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": False,
            "needs_manual_review": True,
            "new_retry_reason": "history_inconsistent_or_already_successful",
            "suggested_action": "manual_review_history",
        }
    if not image_exists:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": True,
            "needs_manual_review": False,
            "new_retry_reason": "image_missing_now",
            "suggested_action": "do_not_rerun_missing_image",
        }
    if int(image_check["image_size_bytes"]) <= 0:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": True,
            "needs_manual_review": False,
            "new_retry_reason": "image_empty_file",
            "suggested_action": "do_not_rerun_empty_image",
        }
    if not image_readable:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": True,
            "needs_manual_review": False,
            "new_retry_reason": "image_unreadable_now",
            "suggested_action": "do_not_rerun_unreadable_image",
        }
    if auth_error:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": True,
            "needs_manual_review": False,
            "new_retry_reason": "auth_or_account_error",
            "suggested_action": "fix_auth_before_rerun",
        }
    if unsupported:
        return {
            "force_retry_candidate": False,
            "true_nonretryable": True,
            "needs_manual_review": False,
            "new_retry_reason": "unsupported_format_confirmed",
            "suggested_action": "manual_hold_unsupported_media",
        }
    if path_now_resolvable:
        return {
            "force_retry_candidate": True,
            "true_nonretryable": False,
            "needs_manual_review": False,
            "new_retry_reason": "path_now_resolvable",
            "suggested_action": "force_rerun_with_resolved_path",
        }
    if schema_or_parse:
        return {
            "force_retry_candidate": True,
            "true_nonretryable": False,
            "needs_manual_review": False,
            "new_retry_reason": "schema_or_parse_error_with_readable_image",
            "suggested_action": "force_rerun_or_replay_parse",
        }
    if has_raw_real and has_failed:
        return {
            "force_retry_candidate": True,
            "true_nonretryable": False,
            "needs_manual_review": False,
            "new_retry_reason": "raw_present_but_no_valid_extraction",
            "suggested_action": "force_rerun_or_manual_reparse",
        }
    return {
        "force_retry_candidate": False,
        "true_nonretryable": False,
        "needs_manual_review": True,
        "new_retry_reason": "unknown_nonretryable_needs_manual_review",
        "suggested_action": "manual_review_before_rerun",
    }


def _resolve_primary_error(
    *,
    row: dict[str, Any],
    failed_records: list[dict[str, Any]],
    raw_outputs: list[dict[str, Any]],
) -> tuple[str, str]:
    if failed_records:
        record = failed_records[-1]
        return str(record.get("error_type") or ""), str(record.get("error_message") or record.get("error") or "")
    for record in reversed(raw_outputs):
        if record.get("error_type") or record.get("error"):
            return str(record.get("error_type") or ""), str(record.get("error_message") or record.get("error") or "")
    return str(row.get("error_type") or ""), str(row.get("error_message") or "")


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


def _verify_image_readable(path: Path) -> tuple[bool, str]:
    if Image is None:
        return True, "pil_not_available_skipped_verify"
    try:
        with Image.open(path) as image:
            image.verify()
        return True, ""
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return False, str(exc)


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _priority_for_force_retry_reason(reason: str) -> str:
    if reason == "schema_or_parse_error_with_readable_image":
        return "P1"
    if reason == "path_now_resolvable":
        return "P2"
    if reason == "raw_present_but_no_valid_extraction":
        return "P3"
    return "P4"


def _to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


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


def _build_markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage4A failed_nonretryable 二次复核",
        "",
        f"- failed_nonretryable_total: {summary['failed_nonretryable_total']}",
        f"- image_exists_count: {summary['image_exists_count']}",
        f"- image_readable_count: {summary['image_readable_count']}",
        f"- force_retry_candidate_count: {summary['force_retry_candidate_count']}",
        f"- true_nonretryable_count: {summary['true_nonretryable_count']}",
        f"- needs_manual_review_count: {summary['needs_manual_review_count']}",
        "",
        "## 说明",
        "",
        "- force_retry_candidate 表示图片现在本地存在且可读，历史错误更像 schema/parse/path 残留，适合强制补跑。",
        "- true_nonretryable 表示图片现在仍不可用，或确实属于认证/格式/空文件等问题，不建议盲目重跑。",
        "- needs_manual_review 表示历史状态冲突或错误信息异常，需要先人工看记录。",
        "",
        "## 统计",
        "",
        "### by_original_error_type",
    ]
    for key, value in sorted((summary.get("by_original_error_type") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("### by_new_retry_reason")
    for key, value in sorted((summary.get("by_new_retry_reason") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## 建议")
    lines.append("")
    lines.append("- 先从 P1 / P2 的 force_retry_nonretryable manifest 小批补跑。")
    lines.append("- 对 auth/account/unsupported/image_unreadable 这类 true_nonretryable，不建议直接重打 VLM。")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
