from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.config import build_runtime_settings  # noqa: E402
from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402
from alumina_sol_extractor.stage3.pipeline import run_stage3_dspy_pipeline  # noqa: E402
from alumina_sol_extractor.utils.batch_categories import (  # noqa: E402
    CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED,
    normalize_batch_category,
)


KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "batch_validation_reports"
REQUIRED_MANIFEST_FIELDS = ["source_id", "category", "paper_id_guess"]
REPORT_FIELDS = [
    "run_id",
    "source_id",
    "category",
    "paper_id_guess",
    "markdown_path",
    "paper_output_dir",
    "stage3_dir",
    "status",
    "stage3_summary_path",
    "stage3_mode",
    "stage3_dspy",
    "samples_count",
    "parameters_count",
    "process_steps_count",
    "evidence_count",
    "procedure_sections_count",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "error_type",
    "error_message",
    "recommended_action",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch runner for Stage 3 DSPy extraction using source_manifest.csv.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Example:
              python .\\scripts\\dev\\run_stage3_batch.py `
                --manifest ".\\data\\batch_manifest\\source_manifest.csv" `
                --markdown-dir ".\\data\\markdown" `
                --outputs-dir ".\\data\\outputs" `
                --report-dir ".\\data\\batch_validation_reports\\stage3_limit3" `
                --limit 3 `
                --force
            """
        ).strip(),
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--markdown-dir", default=str(DEFAULT_MARKDOWN_DIR))
    parser.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--category", choices=KNOWN_CATEGORIES)
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")
    return parser.parse_args()


def run_stage3_batch(
    *,
    manifest: Path | str = DEFAULT_MANIFEST,
    markdown_dir: Path | str = DEFAULT_MARKDOWN_DIR,
    outputs_dir: Path | str = DEFAULT_OUTPUTS_DIR,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    category: str | None = None,
    paper_ids: list[str] | None = None,
    limit: int = 0,
    force: bool = False,
    dry_run: bool = False,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    manifest = Path(manifest)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    report_dir = Path(report_dir)
    if not manifest.exists():
        raise FileNotFoundError(f"source_manifest.csv not found: {manifest}")

    rows = _load_manifest_rows(manifest)
    _validate_manifest_fields(rows)
    selected_rows = _select_manifest_rows(rows, category=category, paper_ids=paper_ids, limit=limit)
    report_dir.mkdir(parents=True, exist_ok=True)

    load_project_dotenv(PROJECT_ROOT)
    settings_template = None if dry_run else build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")

    run_started = _now_iso()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_rows: list[dict[str, Any]] = []

    for row in selected_rows:
        report_row = _process_manifest_row(
            row,
            markdown_dir=markdown_dir,
            outputs_dir=outputs_dir,
            settings_template=settings_template,
            force=force,
            dry_run=dry_run,
            run_id=run_id,
        )
        report_rows.append(report_row)
        if report_row["status"] == "failed" and not continue_on_error:
            break

    run_finished = _now_iso()
    summary = _build_summary(
        report_rows,
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        category=category,
        paper_ids=paper_ids or [],
        limit=limit,
        force=force,
        dry_run=dry_run,
        started_at=run_started,
        finished_at=run_finished,
    )
    report_md = _build_markdown_report(summary, report_rows)

    report_csv_path = report_dir / "stage3_batch_report.csv"
    report_md_path = report_dir / "stage3_batch_report.md"
    summary_json_path = report_dir / "stage3_batch_summary.json"
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
    markdown_dir: Path,
    outputs_dir: Path,
    settings_template: dict[str, Any] | None,
    force: bool,
    dry_run: bool,
    run_id: str,
) -> dict[str, Any]:
    started_at = _now_iso()
    source_id = row.get("source_id", "")
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    markdown_path = _resolve_markdown_path(row, markdown_dir=markdown_dir)
    paper_output_dir = outputs_dir / category / paper_id_guess
    stage3_dir = paper_output_dir / "stage3"
    stage3_summary_path = stage3_dir / "stage3_summary.json"

    status = ""
    stage3_mode = ""
    stage3_dspy = ""
    samples_count = 0
    parameters_count = 0
    process_steps_count = 0
    evidence_count = 0
    procedure_sections_count = 0
    error_type = ""
    error_message = ""
    recommended_action = ""

    if not markdown_path.exists():
        status = "missing_markdown"
        recommended_action = "generate_markdown_then_rerun_stage3"
    elif stage3_summary_path.exists() and not force:
        status = "skipped_existing"
        (
            stage3_mode,
            stage3_dspy,
            samples_count,
            parameters_count,
            process_steps_count,
            evidence_count,
            procedure_sections_count,
        ) = _read_stage3_counts(stage3_summary_path, stage3_dir)
        recommended_action = "skip_existing"
    elif dry_run:
        status = "dry_run_planned"
        recommended_action = "run_without_dry_run"
    else:
        try:
            settings = dict(settings_template or {})
            settings.setdefault("dspy", {})
            settings["dspy"]["enabled"] = True
            settings.setdefault("stage3", {})
            settings["stage3"]["dry_run_validator"] = False

            result = run_stage3_dspy_pipeline(
                project_root=PROJECT_ROOT,
                settings=settings,
                paper_id=paper_id_guess,
                cleaned_markdown_path=markdown_path,
                output_dir=paper_output_dir,
            )
            stage3_dir = result.output_dir
            stage3_summary_path = stage3_dir / "stage3_summary.json"
            (
                stage3_mode,
                stage3_dspy,
                samples_count,
                parameters_count,
                process_steps_count,
                evidence_count,
                procedure_sections_count,
            ) = _read_stage3_counts(stage3_summary_path, stage3_dir, fallback_summary=result.summary)
            status = "success"
            recommended_action = "ready_for_stage4_or_stage5"
            if process_steps_count == 0:
                recommended_action = "inspect_procedure_sections_and_process_steps"
        except Exception as exc:
            status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)
            recommended_action = "inspect_stage3_error_and_retry"

    finished_at = _now_iso()
    elapsed_seconds = round((_parse_iso(finished_at) - _parse_iso(started_at)).total_seconds(), 3)
    return {
        "run_id": run_id,
        "source_id": source_id,
        "category": category,
        "paper_id_guess": paper_id_guess,
        "markdown_path": str(markdown_path),
        "paper_output_dir": str(paper_output_dir),
        "stage3_dir": str(stage3_dir),
        "status": status,
        "stage3_summary_path": str(stage3_summary_path),
        "stage3_mode": stage3_mode,
        "stage3_dspy": stage3_dspy,
        "samples_count": samples_count,
        "parameters_count": parameters_count,
        "process_steps_count": process_steps_count,
        "evidence_count": evidence_count,
        "procedure_sections_count": procedure_sections_count,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "error_type": error_type,
        "error_message": error_message,
        "recommended_action": recommended_action,
    }


def _load_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _validate_manifest_fields(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    header_fields = set(rows[0].keys())
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in header_fields]
    if missing:
        raise ValueError(f"source_manifest.csv is missing required fields: {', '.join(missing)}")


def _select_manifest_rows(
    rows: list[dict[str, str]],
    *,
    category: str | None,
    paper_ids: list[str] | None,
    limit: int,
) -> list[dict[str, str]]:
    filtered = rows
    if category:
        normalized_category = normalize_batch_category(category)
        filtered = [row for row in filtered if normalize_batch_category(row.get("category")) == normalized_category]
    if paper_ids:
        wanted = {item.strip() for item in paper_ids if item.strip()}
        filtered = [
            row
            for row in filtered
            if row.get("paper_id_guess") in wanted or row.get("source_id") in wanted
        ]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def _resolve_markdown_path(row: dict[str, str], *, markdown_dir: Path) -> Path:
    actual = row.get("markdown_actual_path") or ""
    expected = row.get("markdown_expected_path") or ""
    paper_id_guess = row.get("paper_id_guess") or ""
    category = normalize_batch_category(row.get("category"))

    for candidate in [actual, expected]:
        if candidate:
            path = Path(candidate)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            return path
    return markdown_dir / category / f"{paper_id_guess}.md"


def _read_stage3_counts(
    summary_path: Path,
    stage3_dir: Path,
    *,
    fallback_summary: dict[str, Any] | None = None,
) -> tuple[str, str, int, int, int, int, int]:
    summary = fallback_summary or {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    procedure_sections_count = _count_json_items(stage3_dir / "stage3_procedure_sections.json")
    return (
        str(summary.get("stage3_mode") or ""),
        str(summary.get("stage3_dspy") or ""),
        int(summary.get("experiment_series_count") or 0),
        int(summary.get("data_point_count") or 0),
        int(summary.get("process_steps_count") or 0),
        int(summary.get("evidence_object_count") or 0),
        procedure_sections_count,
    )


def _count_json_items(path: Path) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return len(payload)
    return 0


def _build_summary(
    report_rows: list[dict[str, Any]],
    *,
    manifest: Path,
    markdown_dir: Path,
    outputs_dir: Path,
    report_dir: Path,
    category: str | None,
    paper_ids: list[str],
    limit: int,
    force: bool,
    dry_run: bool,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    counts = Counter(row["status"] for row in report_rows)
    by_category: dict[str, dict[str, int]] = {}
    for category_name in KNOWN_CATEGORIES:
        rows = [row for row in report_rows if row["category"] == category_name]
        by_category[category_name] = {
            "total": len(rows),
            "success_count": sum(1 for row in rows if row["status"] == "success"),
            "skipped_existing_count": sum(1 for row in rows if row["status"] == "skipped_existing"),
            "missing_markdown_count": sum(1 for row in rows if row["status"] == "missing_markdown"),
            "failed_count": sum(1 for row in rows if row["status"] == "failed"),
            "dry_run_count": sum(1 for row in rows if row["status"] == "dry_run_planned"),
        }

    return {
        "manifest": str(manifest.relative_to(PROJECT_ROOT)) if manifest.is_relative_to(PROJECT_ROOT) else str(manifest),
        "markdown_dir": str(markdown_dir.relative_to(PROJECT_ROOT)) if markdown_dir.is_relative_to(PROJECT_ROOT) else str(markdown_dir),
        "outputs_dir": str(outputs_dir.relative_to(PROJECT_ROOT)) if outputs_dir.is_relative_to(PROJECT_ROOT) else str(outputs_dir),
        "report_dir": str(report_dir.relative_to(PROJECT_ROOT)) if report_dir.is_relative_to(PROJECT_ROOT) else str(report_dir),
        "category_filter": category,
        "paper_ids_filter": paper_ids,
        "limit": limit,
        "force": force,
        "dry_run": dry_run,
        "total_candidates": len(report_rows),
        "attempted_count": sum(1 for row in report_rows if row["status"] in {"success", "failed"}),
        "success_count": counts.get("success", 0),
        "failed_count": counts.get("failed", 0),
        "missing_markdown_count": counts.get("missing_markdown", 0),
        "skipped_existing_count": counts.get("skipped_existing", 0),
        "dry_run_count": counts.get("dry_run_planned", 0),
        "by_category": by_category,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_markdown_report(summary: dict[str, Any], report_rows: list[dict[str, Any]]) -> str:
    failed_rows = [row for row in report_rows if row["status"] == "failed"]
    missing_rows = [row for row in report_rows if row["status"] == "missing_markdown"]
    zero_process_rows = [
        row
        for row in report_rows
        if row["status"] == "success" and int(row.get("process_steps_count") or 0) == 0
    ]

    lines = [
        "# Stage 3 Batch Report",
        "",
        "## Summary",
        "",
        f"- total_candidates: {summary['total_candidates']}",
        f"- attempted_count: {summary['attempted_count']}",
        f"- success_count: {summary['success_count']}",
        f"- failed_count: {summary['failed_count']}",
        f"- missing_markdown_count: {summary['missing_markdown_count']}",
        f"- skipped_existing_count: {summary['skipped_existing_count']}",
        f"- dry_run_count: {summary['dry_run_count']}",
        "",
        "## By Category",
        "",
        "| category | total | success | failed | missing_markdown | skipped_existing | dry_run |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category_name, stats in summary["by_category"].items():
        lines.append(
            f"| {category_name} | {stats['total']} | {stats['success_count']} | {stats['failed_count']} | "
            f"{stats['missing_markdown_count']} | {stats['skipped_existing_count']} | {stats['dry_run_count']} |"
        )

    lines.extend(["", "## Failed", ""])
    if failed_rows:
        for row in failed_rows:
            lines.append(
                f"- {row['paper_id_guess']} ({row['category']}): {row['error_type']} - {row['error_message']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Missing Markdown", ""])
    if missing_rows:
        for row in missing_rows:
            lines.append(f"- {row['paper_id_guess']} ({row['category']})")
    else:
        lines.append("- None")

    lines.extend(["", "## Zero Process Steps", ""])
    if zero_process_rows:
        for row in zero_process_rows[:20]:
            lines.append(
                f"- {row['paper_id_guess']} ({row['category']}): process_steps_count=0, evidence_count={row['evidence_count']}"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    args = parse_args()
    paper_ids = [item.strip() for item in args.paper_ids.split(",") if item.strip()]
    result = run_stage3_batch(
        manifest=args.manifest,
        markdown_dir=args.markdown_dir,
        outputs_dir=args.outputs_dir,
        report_dir=args.report_dir,
        category=args.category,
        paper_ids=paper_ids,
        limit=args.limit,
        force=args.force,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
    )
    print(
        json.dumps(
            {
                "summary": result["summary"],
                "report_csv_path": result["report_csv_path"],
                "report_md_path": result["report_md_path"],
                "summary_json_path": result["summary_json_path"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
