from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.extractor import validate_universal_extraction_payload  # noqa: E402


FIELD_RE = re.compile(
    r"(?P<field>[A-Za-z0-9_.]+)\n\s+Input should be (?P<expected>[^\[]+)\[type=[^,]+, input_value=(?P<raw>.*?), input_type=(?P<input_type>[^\]]+)\]",
    re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Stage4A universal raw outputs without calling VLM.")
    parser.add_argument(
        "--batch-report",
        default=str(PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_limit5_live" / "stage4a_batch_report.csv"),
    )
    parser.add_argument(
        "--audit-csv",
        default=str(PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_limit5_schema_failure_audit.csv"),
    )
    parser.add_argument(
        "--audit-md",
        default=str(PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_LIMIT5_SCHEMA_FAILURE_AUDIT.md"),
    )
    parser.add_argument(
        "--replay-csv",
        default=str(PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_limit5_replay_after_schema_fix.csv"),
    )
    parser.add_argument(
        "--replay-summary-json",
        default=str(PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_limit5_replay_after_schema_fix_summary.json"),
    )
    parser.add_argument(
        "--replay-md",
        default=str(PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_LIMIT5_SCHEMA_FIX_REPLAY.md"),
    )
    return parser.parse_args()


def _load_batch_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_candidate(universal_payload: dict[str, Any]) -> dict[str, Any]:
    extraction = universal_payload.get("extraction") or {}
    return {
        "paper_id": universal_payload.get("paper_id"),
        "figure_id": universal_payload.get("figure_id"),
        "caption": universal_payload.get("caption"),
        "source_image_path": universal_payload.get("source_image_path"),
        "stage2_figure_class": universal_payload.get("stage2_figure_class"),
        "stage3_figure_type": universal_payload.get("stage3_figure_type"),
        "initial_figure_type": universal_payload.get("initial_figure_type") or universal_payload.get("figure_type"),
        "technique": extraction.get("technique"),
        "context_source": {},
    }


def _parse_validation_error(message: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for match in FIELD_RE.finditer(message):
        matches.append(
            {
                "failed_field": match.group("field"),
                "expected_type": match.group("expected").strip(),
                "actual_value_shape": match.group("input_type").strip(),
                "raw_value_preview": match.group("raw").strip()[:300],
            }
        )
    return matches


def _shape_for_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return f"list[{type(value[0]).__name__}]" if value else "list[empty]"
    return type(value).__name__


def _value_for_field(payload: dict[str, Any], field_path: str) -> Any:
    current: Any = payload.get("extraction") or {}
    for part in field_path.split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            idx = int(part)
            if idx >= len(current):
                return None
            current = current[idx]
            continue
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def run_replay(
    *,
    batch_report: Path,
    audit_csv: Path,
    audit_md: Path,
    replay_csv: Path,
    replay_summary_json: Path,
    replay_md: Path,
) -> dict[str, Any]:
    rows = _load_batch_rows(batch_report)
    audit_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []

    old_successful_extractions = 0
    old_failed_records = 0
    replay_success = 0
    replay_failed = 0
    failure_reason_counter: Counter[str] = Counter()

    for row in rows:
        stage4_dir = PROJECT_ROOT / row["stage4_dir"]
        extraction_lines = (stage4_dir / "spectra_extractions.jsonl").read_text(encoding="utf-8").splitlines() if (stage4_dir / "spectra_extractions.jsonl").exists() else []
        old_successful_extractions += sum(1 for line in extraction_lines if line.strip())
        failed_lines = (stage4_dir / "spectra_failed_records.jsonl").read_text(encoding="utf-8").splitlines() if (stage4_dir / "spectra_failed_records.jsonl").exists() else []
        old_failed_records += sum(1 for line in failed_lines if line.strip())
        raw_lines = (stage4_dir / "raw_vlm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if (stage4_dir / "raw_vlm_outputs.jsonl").exists() else []

        for line in raw_lines:
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("error_type") != "schema_validation_failed":
                continue
            universal_payload = raw.get("raw_universal_payload") or {}
            candidate = _build_candidate(universal_payload)
            replay_result = validate_universal_extraction_payload(universal_payload, candidate)
            error_message = ""
            error_entries = _parse_validation_error(raw.get("raw_response") or "")
            failed_field = ""
            expected_type = ""
            actual_value_shape = ""
            raw_value_preview = ""
            if not error_entries:
                error_entries = _parse_validation_error(raw.get("warnings", [""])[0] if raw.get("warnings") else "")
            original_failure_message = next(
                (
                    json.loads(item).get("error_message")
                    for item in failed_lines
                    if item.strip() and json.loads(item).get("figure_id") == universal_payload.get("figure_id")
                ),
                "",
            )
            parsed_original_errors = _parse_validation_error(original_failure_message)
            if parsed_original_errors:
                failed_field = " | ".join(item["failed_field"] for item in parsed_original_errors)
                expected_type = " | ".join(item["expected_type"] for item in parsed_original_errors)
                actual_value_shape = " | ".join(item["actual_value_shape"] for item in parsed_original_errors)
                raw_value_preview = " | ".join(item["raw_value_preview"] for item in parsed_original_errors)
            else:
                failed_field = "unparsed"
                expected_type = "unknown"
                raw_value = _value_for_field(universal_payload, "band_assignments")
                actual_value_shape = _shape_for_value(raw_value)
                raw_value_preview = str(raw_value)[:300]

            if replay_result["ok"]:
                replay_success += 1
                can_normalize = True
                result_status = "recovered"
            else:
                replay_failed += 1
                can_normalize = False
                result_status = "still_failed"
                error_message = str(replay_result.get("error_message") or "")
                failure_reason_counter[replay_result.get("schema_name") or "unknown"] += 1

            audit_rows.append(
                {
                    "paper_id": universal_payload.get("paper_id"),
                    "figure_id": universal_payload.get("figure_id"),
                    "actual_figure_type": universal_payload.get("actual_figure_type"),
                    "schema_name": replay_result.get("schema_name"),
                    "failed_field": failed_field,
                    "expected_type": expected_type,
                    "actual_value_shape": actual_value_shape,
                    "raw_value_preview": raw_value_preview,
                    "whether_can_normalize": can_normalize,
                }
            )
            replay_rows.append(
                {
                    "category": row["category"],
                    "paper_id": row["paper_id_guess"],
                    "figure_id": universal_payload.get("figure_id"),
                    "actual_figure_type": universal_payload.get("actual_figure_type"),
                    "schema_name": replay_result.get("schema_name"),
                    "replay_status": result_status,
                    "normalization_warning_count": len((replay_result.get("record") or {}).get("warnings", []) or replay_result.get("warnings", [])),
                    "error_message": error_message,
                }
            )

    summary = {
        "old_successful_extractions": old_successful_extractions,
        "old_failed_records": old_failed_records,
        "new_successful_extractions": old_successful_extractions + replay_success,
        "new_failed_records": replay_failed,
        "schema_validation_failed_count_before": old_failed_records,
        "schema_validation_failed_count_after": replay_failed,
        "failure_reason_distribution_after": dict(failure_reason_counter),
    }

    _write_csv(
        audit_csv,
        audit_rows,
        [
            "paper_id",
            "figure_id",
            "actual_figure_type",
            "schema_name",
            "failed_field",
            "expected_type",
            "actual_value_shape",
            "raw_value_preview",
            "whether_can_normalize",
        ],
    )
    _write_csv(
        replay_csv,
        replay_rows,
        [
            "category",
            "paper_id",
            "figure_id",
            "actual_figure_type",
            "schema_name",
            "replay_status",
            "normalization_warning_count",
            "error_message",
        ],
    )
    replay_summary_json.parent.mkdir(parents=True, exist_ok=True)
    replay_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_md.parent.mkdir(parents=True, exist_ok=True)
    audit_md.write_text(_build_audit_markdown(audit_rows), encoding="utf-8")
    replay_md.parent.mkdir(parents=True, exist_ok=True)
    replay_md.write_text(_build_replay_markdown(summary, replay_rows), encoding="utf-8")
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_audit_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Stage4A Universal Limit5 Schema Failure Audit",
        "",
        f"- total_failed_records: {len(rows)}",
        "",
    ]
    for row in rows:
        lines.append(
            f"- {row['paper_id']} / {row['figure_id']} / {row['schema_name']}: "
            f"{row['failed_field']} -> {row['expected_type']} ({row['actual_value_shape']}) "
            f"normalize={row['whether_can_normalize']}"
        )
    return "\n".join(lines) + "\n"


def _build_replay_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Stage4A Universal Limit5 Schema Fix Replay",
        "",
        f"- old_successful_extractions: {summary['old_successful_extractions']}",
        f"- old_failed_records: {summary['old_failed_records']}",
        f"- new_successful_extractions: {summary['new_successful_extractions']}",
        f"- new_failed_records: {summary['new_failed_records']}",
        f"- schema_validation_failed_count before/after: {summary['schema_validation_failed_count_before']} -> {summary['schema_validation_failed_count_after']}",
        "",
    ]
    remaining = [row for row in rows if row["replay_status"] != "recovered"]
    if remaining:
        lines.append("## Remaining failures")
        lines.append("")
        for row in remaining:
            lines.append(f"- {row['paper_id']} / {row['figure_id']} / {row['schema_name']}: {row['error_message']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    summary = run_replay(
        batch_report=Path(args.batch_report),
        audit_csv=Path(args.audit_csv),
        audit_md=Path(args.audit_md),
        replay_csv=Path(args.replay_csv),
        replay_summary_json=Path(args.replay_summary_json),
        replay_md=Path(args.replay_md),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
