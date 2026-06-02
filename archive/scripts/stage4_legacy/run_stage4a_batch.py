from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor  # noqa: E402
from alumina_sol_extractor.stage4.io import read_json, read_jsonl  # noqa: E402
from alumina_sol_extractor.stage4.processed_index import (  # noqa: E402
    is_dry_run_only_stage4_summary,
    is_live_successful_stage4_summary,
)
from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402
from alumina_sol_extractor.utils.batch_categories import (  # noqa: E402
    CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED,
    normalize_batch_category,
)


KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_dry_run"
REPORT_FIELDS = [
    "run_id",
    "source_id",
    "category",
    "paper_id_guess",
    "paper_output_dir",
    "stage3_dir",
    "stage4_dir",
    "status",
    "routing_mode",
    "dry_run",
    "stage4_summary_path",
    "total_candidates",
    "processed_count",
    "skipped_count",
    "rescued_unknown_by_caption_count",
    "skipped_unknown_schema_specific_count",
    "validation_error_count",
    "hard_failed_record_count",
    "stage2_figure_class_distribution",
    "initial_figure_type_distribution",
    "routing_reason_distribution",
    "candidate_risk_level_distribution",
    "figure_level_skip_success_count",
    "figure_level_replay_candidate_count",
    "figure_level_rerun_transient_count",
    "figure_level_new_live_count",
    "figure_level_missing_image_count",
    "duplicate_vlm_prevented_count",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "error_type",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch dry-run/live runner for Stage 4A universal routing.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--category", choices=KNOWN_CATEGORIES)
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--stage4-subdir", default="stage4_vision_spectra_universal")
    parser.add_argument("--routing-mode", choices=["schema_specific", "universal_compact"], default="universal_compact")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    parser.add_argument("--live", dest="dry_run", action="store_false")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--max-figures-per-paper", type=int, default=10)
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    return parser.parse_args()


def run_stage4a_batch(
    *,
    manifest: Path | str = DEFAULT_MANIFEST,
    outputs_dir: Path | str = DEFAULT_OUTPUTS_DIR,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    category: str | None = None,
    paper_ids: list[str] | None = None,
    limit: int = 0,
    stage3_subdir: str = "stage3_twopass",
    stage4_subdir: str = "stage4_vision_spectra_universal",
    routing_mode: str = "universal_compact",
    dry_run: bool = True,
    force: bool = False,
    continue_on_error: bool = True,
    estimate_only: bool = False,
    max_figures_per_paper: int = 10,
    skip_existing: bool = True,
) -> dict[str, Any]:
    manifest = Path(manifest)
    outputs_dir = Path(outputs_dir)
    report_dir = Path(report_dir)
    if not dry_run and not estimate_only:
        load_project_dotenv(PROJECT_ROOT)
    report_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_manifest_rows(manifest)
    selected_rows = _select_manifest_rows(rows, category=category, paper_ids=paper_ids, limit=limit)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_rows: list[dict[str, Any]] = []
    started_at = _now_iso()
    total = len(selected_rows)
    for index, row in enumerate(selected_rows, start=1):
        label = f"{normalize_batch_category(row.get('category'))}/{row.get('paper_id_guess') or ''}"
        _log_console(f"START [{index}/{total}] {label}")
        report_row = _process_manifest_row(
            row,
            outputs_dir=outputs_dir,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
            dry_run=dry_run,
            force=force,
            estimate_only=estimate_only,
            max_figures_per_paper=max_figures_per_paper,
            skip_existing=skip_existing,
            run_id=run_id,
        )
        report_rows.append(report_row)
        _log_console(
            f"{report_row['status'].upper()} [{index}/{total}] {label} "
            f"candidates={report_row['total_candidates']} send={report_row['processed_count']}"
        )
        if report_row["status"] == "failed" and not continue_on_error:
            break

    finished_at = _now_iso()
    summary = _build_summary(
        report_rows,
        selected_rows=selected_rows,
        manifest=manifest,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        routing_mode=routing_mode,
        dry_run=dry_run,
        estimate_only=estimate_only,
        started_at=started_at,
        finished_at=finished_at,
    )
    report_md = _build_markdown_report(summary, report_rows)
    report_csv_path = report_dir / "stage4a_batch_report.csv"
    report_md_path = report_dir / "stage4a_batch_report.md"
    summary_json_path = report_dir / "stage4a_batch_summary.json"
    _write_csv(report_csv_path, report_rows, REPORT_FIELDS)
    report_md_path.write_text(report_md, encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "rows": report_rows,
        "summary": summary,
        "report_csv_path": str(report_csv_path),
        "report_md_path": str(report_md_path),
        "summary_json_path": str(summary_json_path),
    }


def _process_manifest_row(
    row: dict[str, str],
    *,
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    dry_run: bool,
    force: bool,
    estimate_only: bool,
    max_figures_per_paper: int,
    skip_existing: bool,
    run_id: str,
) -> dict[str, Any]:
    started_at = _now_iso()
    source_id = row.get("source_id", "")
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    paper_output_dir = outputs_dir / category / paper_id_guess
    stage3_dir = paper_output_dir / stage3_subdir
    stage4_dir = paper_output_dir / stage4_subdir
    stage4_summary_path = stage4_dir / "stage4a_summary.json"
    error_type = ""
    error_message = ""
    summary: dict[str, Any] = {}

    if not _has_readable_stage3_summary(stage3_dir):
        status = "missing_stage3"
    elif skip_existing and not force and _should_skip_existing_stage4(stage4_summary_path, dry_run=dry_run, estimate_only=estimate_only):
        status = "skipped_existing"
        summary = read_json(stage4_summary_path, default={}) or {}
    else:
        try:
            extractor = Stage4VisionSpectraExtractor(
                paper_id=paper_id_guess,
                output_dir=paper_output_dir,
                max_figures=max_figures_per_paper,
                dry_run=True if estimate_only else dry_run,
                routing_mode=routing_mode,
                stage3_subdir=stage3_subdir,
                stage4_subdir=stage4_subdir,
            )
            summary = extractor.run()
            _write_stage4a_validation_report(stage4_dir, summary, routing_mode=routing_mode)
            status = "estimate_only" if estimate_only else "success"
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)

    finished_at = _now_iso()
    elapsed_seconds = round((_parse_iso(finished_at) - _parse_iso(started_at)).total_seconds(), 3)
    return {
        "run_id": run_id,
        "source_id": source_id,
        "category": category,
        "paper_id_guess": paper_id_guess,
        "paper_output_dir": str(paper_output_dir),
        "stage3_dir": str(stage3_dir),
        "stage4_dir": str(stage4_dir),
        "status": status,
        "routing_mode": routing_mode,
        "dry_run": True if estimate_only else dry_run,
        "stage4_summary_path": str(stage4_summary_path),
        "total_candidates": int(summary.get("total_candidates") or 0),
        "processed_count": int(summary.get("processed_count") or 0),
        "skipped_count": int(summary.get("skipped_count") or 0),
        "rescued_unknown_by_caption_count": int(summary.get("rescued_unknown_by_caption_count") or 0),
        "skipped_unknown_schema_specific_count": int(summary.get("skipped_unknown_schema_specific_count") or 0),
        "validation_error_count": int(summary.get("validation_error_count") or 0),
        "hard_failed_record_count": int(summary.get("hard_failed_record_count") or 0),
        "stage2_figure_class_distribution": json.dumps(summary.get("by_stage2_figure_class", {}), ensure_ascii=False),
        "initial_figure_type_distribution": json.dumps(summary.get("by_initial_figure_type", {}), ensure_ascii=False),
        "routing_reason_distribution": json.dumps(summary.get("routing_reason_distribution", {}), ensure_ascii=False),
        "candidate_risk_level_distribution": json.dumps(summary.get("candidate_risk_level_distribution", {}), ensure_ascii=False),
        "figure_level_skip_success_count": int(summary.get("figure_level_skip_success_count") or 0),
        "figure_level_replay_candidate_count": int(summary.get("figure_level_replay_candidate_count") or 0),
        "figure_level_rerun_transient_count": int(summary.get("figure_level_rerun_transient_count") or 0),
        "figure_level_new_live_count": int(summary.get("figure_level_new_live_count") or 0),
        "figure_level_missing_image_count": int(summary.get("figure_level_missing_image_count") or 0),
        "duplicate_vlm_prevented_count": int(summary.get("duplicate_vlm_prevented_count") or 0),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "error_type": error_type,
        "error_message": error_message,
    }


def export_universal_dry_run_audit(
    *,
    report_rows: list[dict[str, Any]],
    manifest_total_count: int,
    stage3_subdir: str,
) -> dict[str, Any]:
    audit_rows: list[dict[str, Any]] = []
    top_papers: list[dict[str, Any]] = []
    high_risk_mismatch: list[dict[str, Any]] = []
    stage2_distribution: Counter[str] = Counter()
    initial_distribution: Counter[str] = Counter()
    routing_distribution: Counter[str] = Counter()
    risk_distribution: Counter[str] = Counter()
    papers_with_figures_count = 0
    total_figures_count = 0
    total_candidates = 0
    total_send = 0
    rescued = 0
    skipped_unknown = 0

    for row in report_rows:
        if row["status"] not in {"success", "estimate_only", "skipped_existing"}:
            continue
        stage4_dir = Path(row["stage4_dir"])
        candidates = read_jsonl(stage4_dir / "stage4_candidates.jsonl")
        if candidates:
            papers_with_figures_count += 1
        send_count = sum(1 for candidate in candidates if candidate.get("send_to_vlm"))
        rescued_count = sum(1 for candidate in candidates if candidate.get("routing_reason") == "stage2_unknown_caption_scientific" and candidate.get("send_to_vlm"))
        skipped_unknown_count = sum(1 for candidate in candidates if candidate.get("routing_mode") == "schema_specific" and not candidate.get("send_to_vlm"))
        total_figures_count += len(candidates)
        total_candidates += len(candidates)
        total_send += send_count
        rescued += rescued_count
        skipped_unknown += skipped_unknown_count
        for candidate in candidates:
            stage2_distribution[str(candidate.get("stage2_figure_class") or "unknown")] += 1
            initial_distribution[str(candidate.get("initial_figure_type") or "unknown")] += 1
            routing_distribution[str(candidate.get("routing_reason") or "unknown")] += 1
            risk_distribution[str(candidate.get("candidate_risk_level") or "unknown")] += 1
            if candidate.get("candidate_risk_level") == "high" and candidate.get("send_to_vlm"):
                high_risk_mismatch.append(
                    {
                        "category": row["category"],
                        "paper_id": row["paper_id_guess"],
                        "figure_id": candidate.get("figure_id"),
                        "stage2_figure_class": candidate.get("stage2_figure_class"),
                        "initial_figure_type": candidate.get("initial_figure_type"),
                        "routing_reason": candidate.get("routing_reason"),
                        "caption": candidate.get("caption"),
                    }
                )
        audit_rows.append(
            {
                "category": row["category"],
                "paper_id": row["paper_id_guess"],
                "candidate_count": len(candidates),
                "send_to_vision_model_count": send_count,
                "rescued_unknown_by_caption_count": rescued_count,
                "routing_reason_distribution": json.dumps(Counter(str(item.get("routing_reason") or "unknown") for item in candidates), ensure_ascii=False),
                "candidate_risk_level_distribution": json.dumps(Counter(str(item.get("candidate_risk_level") or "unknown") for item in candidates), ensure_ascii=False),
            }
        )
    top_papers = sorted(audit_rows, key=lambda item: int(item["candidate_count"]), reverse=True)[:10]
    completed_stage3_count = sum(1 for row in report_rows if row["status"] != "missing_stage3")
    summary = {
        "manifest_total_count": manifest_total_count,
        "completed_stage3_twopass_count": completed_stage3_count,
        "missing_stage3_twopass_count": sum(1 for row in report_rows if row["status"] == "missing_stage3"),
        "papers_with_figures_count": papers_with_figures_count,
        "total_figures_count": total_figures_count,
        "send_to_vision_model_count": total_send,
        "candidate_count_schema_specific": total_candidates if any(row["routing_mode"] == "schema_specific" for row in report_rows) else 0,
        "candidate_count_universal_compact": total_candidates if any(row["routing_mode"] == "universal_compact" for row in report_rows) else 0,
        "skipped_unknown_schema_specific_count": skipped_unknown,
        "rescued_unknown_by_caption_count": rescued,
        "stage2_figure_class_distribution": dict(stage2_distribution),
        "initial_figure_type_distribution": dict(initial_distribution),
        "routing_reason_distribution": dict(routing_distribution),
        "candidate_risk_level_distribution": dict(risk_distribution),
        "estimated_vlm_call_count": total_send,
        "top_papers_by_candidate_count": top_papers,
        "high_risk_mismatch_figure_count": len(high_risk_mismatch),
        "high_risk_mismatch_figures": high_risk_mismatch[:50],
        "stage3_subdir": stage3_subdir,
    }
    audit_csv_path = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_dry_run_audit.csv"
    audit_json_path = PROJECT_ROOT / "data" / "batch_validation_reports" / "stage4a_universal_dry_run_audit_summary.json"
    audit_md_path = PROJECT_ROOT / "docs" / "refactor" / "STAGE4A_UNIVERSAL_DRY_RUN_AUDIT.md"
    _write_csv(
        audit_csv_path,
        audit_rows,
        ["category", "paper_id", "candidate_count", "send_to_vision_model_count", "rescued_unknown_by_caption_count", "routing_reason_distribution", "candidate_risk_level_distribution"],
    )
    audit_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_md_path.parent.mkdir(parents=True, exist_ok=True)
    audit_md_path.write_text(_build_audit_markdown(summary), encoding="utf-8")
    return {
        "summary": summary,
        "audit_csv_path": str(audit_csv_path),
        "audit_json_path": str(audit_json_path),
        "audit_md_path": str(audit_md_path),
    }


def _build_audit_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage4A Universal Dry-Run Audit",
        "",
        f"- manifest_total_count: {summary['manifest_total_count']}",
        f"- completed_stage3_twopass_count: {summary['completed_stage3_twopass_count']}",
        f"- missing_stage3_twopass_count: {summary['missing_stage3_twopass_count']}",
        f"- papers_with_figures_count: {summary['papers_with_figures_count']}",
        f"- total_figures_count: {summary['total_figures_count']}",
        f"- send_to_vision_model_count: {summary['send_to_vision_model_count']}",
        f"- candidate_count_universal_compact: {summary['candidate_count_universal_compact']}",
        f"- skipped_unknown_schema_specific_count: {summary['skipped_unknown_schema_specific_count']}",
        f"- rescued_unknown_by_caption_count: {summary['rescued_unknown_by_caption_count']}",
        f"- estimated_vlm_call_count: {summary['estimated_vlm_call_count']}",
        f"- high_risk_mismatch_figure_count: {summary['high_risk_mismatch_figure_count']}",
        "",
        "## Routing Reason Distribution",
        "",
    ]
    for key, value in summary["routing_reason_distribution"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Papers By Candidate Count", ""])
    for item in summary["top_papers_by_candidate_count"]:
        lines.append(f"- {item['paper_id']} ({item['category']}): {item['candidate_count']}")
    return "\n".join(lines) + "\n"


def _write_stage4a_validation_report(stage4_dir: Path, summary: dict[str, Any], *, routing_mode: str) -> None:
    lines = [
        "# Stage4A Validation Report",
        "",
        f"- routing_mode: {routing_mode}",
        f"- total_candidates: {summary.get('total_candidates', 0)}",
        f"- processed_count: {summary.get('processed_count', 0)}",
        f"- skipped_count: {summary.get('skipped_count', 0)}",
        f"- rescued_unknown_by_caption_count: {summary.get('rescued_unknown_by_caption_count', 0)}",
        f"- hard_failed_record_count: {summary.get('hard_failed_record_count', 0)}",
        "",
        "## Routing Reasons",
        "",
    ]
    for key, value in (summary.get("routing_reason_distribution") or {}).items():
        lines.append(f"- {key}: {value}")
    (stage4_dir / "stage4a_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _has_readable_stage3_summary(stage3_dir: Path) -> bool:
    summary_path = stage3_dir / "stage3_summary.json"
    if not summary_path.exists():
        return False
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(payload, dict)


def _should_skip_existing_stage4(stage4_summary_path: Path, *, dry_run: bool, estimate_only: bool) -> bool:
    if not stage4_summary_path.exists():
        return False
    summary = read_json(stage4_summary_path, default={}) or {}
    if not isinstance(summary, dict):
        return False
    existing_live_count = int(summary.get("live_count") or 0)
    existing_dry_run_count = int(summary.get("dry_run_count") or 0)
    if dry_run or estimate_only:
        return existing_live_count > 0 or existing_dry_run_count > 0
    return is_live_successful_stage4_summary(summary)


def _is_live_successful_stage4_summary(summary: dict[str, Any]) -> bool:
    return is_live_successful_stage4_summary(summary)


def _is_dry_run_only_stage4_summary(summary: dict[str, Any]) -> bool:
    return is_dry_run_only_stage4_summary(summary)


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
        normalized = normalize_batch_category(category)
        filtered = [row for row in filtered if normalize_batch_category(row.get("category")) == normalized]
    if paper_ids:
        wanted = {item.strip() for item in paper_ids if item.strip()}
        filtered = [row for row in filtered if row.get("paper_id_guess") in wanted or row.get("source_id") in wanted]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def _build_summary(
    report_rows: list[dict[str, Any]],
    *,
    selected_rows: list[dict[str, str]],
    manifest: Path,
    outputs_dir: Path,
    report_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    dry_run: bool,
    estimate_only: bool,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    counts = Counter(row["status"] for row in report_rows)
    return {
        "manifest": str(manifest),
        "outputs_dir": str(outputs_dir),
        "report_dir": str(report_dir),
        "stage3_subdir": stage3_subdir,
        "stage4_subdir": stage4_subdir,
        "routing_mode": routing_mode,
        "dry_run": dry_run,
        "estimate_only": estimate_only,
        "selected_count": len(selected_rows),
        "success_count": counts.get("success", 0),
        "estimate_only_count": counts.get("estimate_only", 0),
        "skipped_existing_count": counts.get("skipped_existing", 0),
        "missing_stage3_count": counts.get("missing_stage3", 0),
        "failed_count": counts.get("failed", 0),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_markdown_report(summary: dict[str, Any], report_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Stage4A Batch Report",
        "",
        f"- routing_mode: {summary['routing_mode']}",
        f"- stage3_subdir: {summary['stage3_subdir']}",
        f"- stage4_subdir: {summary['stage4_subdir']}",
        f"- dry_run: {summary['dry_run']}",
        f"- estimate_only: {summary['estimate_only']}",
        f"- selected_count: {summary['selected_count']}",
        f"- success_count: {summary['success_count']}",
        f"- skipped_existing_count: {summary['skipped_existing_count']}",
        f"- missing_stage3_count: {summary['missing_stage3_count']}",
        f"- failed_count: {summary['failed_count']}",
        "",
        "## Failed Rows",
        "",
    ]
    failed_rows = [row for row in report_rows if row["status"] == "failed"]
    if failed_rows:
        for row in failed_rows:
            lines.append(f"- {row['paper_id_guess']} ({row['category']}): {row['error_type']} - {row['error_message']}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _log_console(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_message = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    args = parse_args()
    paper_ids = [item.strip() for item in args.paper_ids.split(",") if item.strip()]
    result = run_stage4a_batch(
        manifest=args.manifest,
        outputs_dir=args.outputs_dir,
        report_dir=args.report_dir,
        category=args.category,
        paper_ids=paper_ids,
        limit=args.limit,
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        routing_mode=args.routing_mode,
        dry_run=args.dry_run,
        force=args.force,
        continue_on_error=args.continue_on_error,
        estimate_only=args.estimate_only,
        max_figures_per_paper=args.max_figures_per_paper,
        skip_existing=args.skip_existing,
    )
    audit = export_universal_dry_run_audit(
        report_rows=result["rows"],
        manifest_total_count=result["summary"]["selected_count"],
        stage3_subdir=args.stage3_subdir,
    )
    payload = json.dumps(
        {
            "summary": result["summary"],
            "report_csv_path": result["report_csv_path"],
            "report_md_path": result["report_md_path"],
            "summary_json_path": result["summary_json_path"],
            "audit": audit,
        },
        ensure_ascii=False,
        indent=2,
    )
    _log_console(payload)


if __name__ == "__main__":
    main()
