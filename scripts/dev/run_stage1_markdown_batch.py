from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
import sys
from collections import Counter
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.pipeline.stage1_pdf_to_markdown import run_stage1_pdf_to_markdown
from alumina_sol_extractor.utils.batch_categories import (
    CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED,
    normalize_batch_category,
)


KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "batch_validation_reports"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_MIN_MARKDOWN_CHARS = 1000
REQUIRED_MANIFEST_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "markdown_expected_path",
    "markdown_status",
]
REPORT_FIELDS = [
    "run_id",
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "markdown_path",
    "paper_output_dir",
    "stage1_output_root",
    "stage1_raw_output_path",
    "status",
    "markdown_char_count",
    "pdf_file_size_mb",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "overwritten",
    "error_type",
    "error_message",
    "recommended_action",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch runner for Stage 1 PDF -> Markdown using source_manifest.csv.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Examples:
              python .\\scripts\\dev\\build_source_manifest.py `
                --pdf-dir "G:\\paper\\Sorted_Database" `
                --markdown-dir ".\\data\\markdown" `
                --outputs-dir ".\\data\\outputs" `
                --out-dir ".\\data\\batch_manifest"

              python .\\scripts\\dev\\run_stage1_markdown_batch.py `
                --manifest ".\\data\\batch_manifest\\source_manifest.csv" `
                --markdown-dir ".\\data\\markdown" `
                --report-dir ".\\data\\batch_validation_reports" `
                --dry-run `
                --limit 0
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
    parser.add_argument("--min-markdown-chars", type=int, default=DEFAULT_MIN_MARKDOWN_CHARS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")
    return parser.parse_args()


def run_stage1_markdown_batch(
    *,
    manifest: Path | str = DEFAULT_MANIFEST,
    markdown_dir: Path | str = DEFAULT_MARKDOWN_DIR,
    outputs_dir: Path | str = DEFAULT_OUTPUTS_DIR,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    category: str | None = None,
    paper_ids: list[str] | None = None,
    limit: int = 0,
    force: bool = False,
    min_markdown_chars: int = DEFAULT_MIN_MARKDOWN_CHARS,
    dry_run: bool = False,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    manifest = Path(manifest)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    report_dir = Path(report_dir)
    if not manifest.exists():
        raise FileNotFoundError(_manifest_missing_message(manifest))

    rows = _load_manifest_rows(manifest)
    _validate_manifest_fields(rows)
    selected_rows = _select_manifest_rows(rows, category=category, paper_ids=paper_ids, limit=limit)
    report_dir.mkdir(parents=True, exist_ok=True)

    run_started = _now_iso()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    settings_template = None if dry_run else build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    report_rows: list[dict[str, Any]] = []

    for row in selected_rows:
        report_row = _process_manifest_row(
            row,
            markdown_dir=markdown_dir,
            outputs_dir=outputs_dir,
            force=force,
            min_markdown_chars=min_markdown_chars,
            dry_run=dry_run,
            run_id=run_id,
            settings_template=settings_template,
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
        min_markdown_chars=min_markdown_chars,
        dry_run=dry_run,
        started_at=run_started,
        finished_at=run_finished,
    )
    report_md = _build_markdown_report(summary, report_rows)

    report_csv_path = report_dir / "stage1_markdown_batch_report.csv"
    report_md_path = report_dir / "stage1_markdown_batch_report.md"
    summary_json_path = report_dir / "stage1_markdown_batch_summary.json"

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


def _process_manifest_row(
    row: dict[str, str],
    *,
    markdown_dir: Path,
    outputs_dir: Path,
    force: bool,
    min_markdown_chars: int,
    dry_run: bool,
    run_id: str,
    settings_template: dict[str, Any] | None,
) -> dict[str, Any]:
    started_at = _now_iso()
    source_id = row.get("source_id", "")
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    pdf_path = Path(row.get("pdf_path") or "")
    markdown_path = _resolve_markdown_path(row, markdown_dir=markdown_dir)
    stage1_output_root, paper_output_dir = _resolve_output_paths(
        row,
        outputs_dir=outputs_dir,
    )
    markdown_exists = markdown_path.exists()
    markdown_char_count = _read_char_count(markdown_path) if markdown_exists else 0
    pdf_file_size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 3) if pdf_path.exists() else 0.0
    overwritten = force and markdown_exists

    status = ""
    stage1_raw_output_path = ""
    error_type = ""
    error_message = ""
    recommended_action = ""

    if not pdf_path.exists():
        status = "missing_pdf"
        recommended_action = "check_pdf_path_then_rerun"
    elif not force and markdown_exists and markdown_char_count >= min_markdown_chars:
        status = "skipped_existing"
        recommended_action = "skip_existing"
    elif not force and markdown_exists and markdown_char_count < min_markdown_chars:
        status = "skipped_too_short_existing"
        recommended_action = "rerun_with_force"
    elif dry_run:
        status = "dry_run_planned"
        recommended_action = "run_without_dry_run"
    else:
        try:
            stage1_result = _run_stage1_for_row(
                row,
                markdown_path=markdown_path,
                stage1_output_root=stage1_output_root,
                settings_template=settings_template or {},
            )
            stage1_raw_output_path = str(stage1_result.cleaned_markdown_path)
            if Path(stage1_raw_output_path) != markdown_path:
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage1_raw_output_path, markdown_path)
            markdown_char_count = _read_char_count(markdown_path) if markdown_path.exists() else 0
            status = "success"
            recommended_action = "ready_for_supplementary_manifest"
        except Exception as exc:
            status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)
            recommended_action = "inspect_error_and_retry"

    finished_at = _now_iso()
    elapsed_seconds = round((_parse_iso(finished_at) - _parse_iso(started_at)).total_seconds(), 3)
    return {
        "run_id": run_id,
        "source_id": source_id,
        "category": category,
        "paper_id_guess": paper_id_guess,
        "pdf_path": str(pdf_path),
        "markdown_path": str(markdown_path),
        "paper_output_dir": str(paper_output_dir),
        "stage1_output_root": str(stage1_output_root),
        "stage1_raw_output_path": stage1_raw_output_path,
        "status": status,
        "markdown_char_count": markdown_char_count,
        "pdf_file_size_mb": pdf_file_size_mb,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "overwritten": overwritten,
        "error_type": error_type,
        "error_message": error_message,
        "recommended_action": recommended_action,
    }


def _run_stage1_for_row(
    row: dict[str, str],
    *,
    markdown_path: Path,
    stage1_output_root: Path,
    settings_template: dict[str, Any],
) -> Any:
    category = normalize_batch_category(row.get("category"))
    pdf_path = Path(row.get("pdf_path") or "")
    settings = copy.deepcopy(settings_template)
    settings.setdefault("paths", {})
    settings["paths"]["input_pdf"] = str(pdf_path)
    settings["paths"]["markdown_output_dir"] = str(markdown_path.parent)
    settings["paths"]["mineru_raw_dir"] = str(PROJECT_ROOT / "data" / "mineru_raw" / category)
    settings["paths"]["output_dir"] = str(stage1_output_root)

    result = run_stage1_pdf_to_markdown(PROJECT_ROOT, settings)
    if is_dataclass(result):
        return result
    return result


def _resolve_output_paths(row: dict[str, str], *, outputs_dir: Path) -> tuple[Path, Path]:
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    stage1_output_root = outputs_dir / category
    paper_output_dir = stage1_output_root / paper_id_guess
    return stage1_output_root, paper_output_dir


def _resolve_markdown_path(row: dict[str, str], *, markdown_dir: Path) -> Path:
    expected = row.get("markdown_expected_path") or ""
    if expected:
        return Path(expected)
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    return markdown_dir / category / f"{paper_id_guess}.md"


def _build_summary(
    rows: list[dict[str, Any]],
    *,
    manifest: Path,
    markdown_dir: Path,
    outputs_dir: Path,
    report_dir: Path,
    category: str | None,
    paper_ids: list[str],
    limit: int,
    force: bool,
    min_markdown_chars: int,
    dry_run: bool,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    by_category: dict[str, dict[str, Any]] = {}
    for category_name in sorted({row["category"] for row in rows} | set(KNOWN_CATEGORIES)):
        category_rows = [row for row in rows if row["category"] == category_name]
        by_category[category_name] = {
            "total": len(category_rows),
            "success_count": sum(1 for row in category_rows if row["status"] == "success"),
            "skipped_existing_count": sum(1 for row in category_rows if row["status"] == "skipped_existing"),
            "skipped_too_short_existing_count": sum(1 for row in category_rows if row["status"] == "skipped_too_short_existing"),
            "missing_pdf_count": sum(1 for row in category_rows if row["status"] == "missing_pdf"),
            "failed_count": sum(1 for row in category_rows if row["status"] == "failed"),
            "dry_run_count": sum(1 for row in category_rows if row["status"] == "dry_run_planned"),
        }
    return {
        "manifest": str(manifest),
        "markdown_dir": str(markdown_dir),
        "outputs_dir": str(outputs_dir),
        "report_dir": str(report_dir),
        "category_filter": category,
        "paper_ids_filter": paper_ids,
        "limit": limit,
        "force": force,
        "min_markdown_chars": min_markdown_chars,
        "dry_run": dry_run,
        "total_candidates": len(rows),
        "attempted_count": status_counts.get("success", 0) + status_counts.get("failed", 0),
        "success_count": status_counts.get("success", 0),
        "skipped_existing_count": status_counts.get("skipped_existing", 0),
        "skipped_too_short_existing_count": status_counts.get("skipped_too_short_existing", 0),
        "missing_pdf_count": status_counts.get("missing_pdf", 0),
        "failed_count": status_counts.get("failed", 0),
        "dry_run_count": status_counts.get("dry_run_planned", 0),
        "by_category": by_category,
        "report_csv_path": str(report_dir / "stage1_markdown_batch_report.csv"),
        "report_md_path": str(report_dir / "stage1_markdown_batch_report.md"),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_markdown_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failed_rows = [row for row in rows if row["status"] == "failed"]
    short_rows = [row for row in rows if row["status"] == "skipped_too_short_existing"]
    lines = [
        "# Stage 1 Markdown Batch Report",
        "",
        "## Command Parameters",
        f"- manifest: {summary['manifest']}",
        f"- markdown_dir: {summary['markdown_dir']}",
        f"- outputs_dir: {summary['outputs_dir']}",
        f"- report_dir: {summary['report_dir']}",
        f"- category_filter: {summary['category_filter'] or 'all'}",
        f"- paper_ids_filter: {', '.join(summary['paper_ids_filter']) or 'none'}",
        f"- limit: {summary['limit']}",
        f"- force: {summary['force']}",
        f"- min_markdown_chars: {summary['min_markdown_chars']}",
        f"- dry_run: {summary['dry_run']}",
        "",
        "## Overall Statistics",
        f"- total_candidates: {summary['total_candidates']}",
        f"- attempted_count: {summary['attempted_count']}",
        f"- success_count: {summary['success_count']}",
        f"- skipped_existing_count: {summary['skipped_existing_count']}",
        f"- skipped_too_short_existing_count: {summary['skipped_too_short_existing_count']}",
        f"- missing_pdf_count: {summary['missing_pdf_count']}",
        f"- failed_count: {summary['failed_count']}",
        f"- dry_run_count: {summary['dry_run_count']}",
        "",
        "## By Category",
    ]
    for category_name, counts in summary["by_category"].items():
        lines.extend(
            [
                f"### {category_name}",
                f"- total: {counts['total']}",
                f"- success_count: {counts['success_count']}",
                f"- skipped_existing_count: {counts['skipped_existing_count']}",
                f"- skipped_too_short_existing_count: {counts['skipped_too_short_existing_count']}",
                f"- missing_pdf_count: {counts['missing_pdf_count']}",
                f"- failed_count: {counts['failed_count']}",
                f"- dry_run_count: {counts['dry_run_count']}",
                "",
            ]
        )
    lines.append("## Failed Items")
    if failed_rows:
        for row in failed_rows:
            lines.append(f"- {row['source_id']}: {row['error_type']} | {row['error_message']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Skipped Too Short Existing"])
    if short_rows:
        for row in short_rows:
            lines.append(f"- {row['source_id']}: {row['markdown_path']} ({row['markdown_char_count']} chars)")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Next Step Suggestions",
            "- If failed_count > 0, inspect the failed items first and retry those PDFs.",
            "- If skipped_too_short_existing_count > 0, review whether they should be rerun with --force.",
            "- After main PDF markdown generation is complete, run build_supplementary_manifest for better supplementary detection.",
            "- If success_count is high enough, the next operational step is supplementary manifest planning or a controlled Stage 3 smoke batch.",
            "",
            "## Example Commands",
            "```powershell",
            "python .\\scripts\\dev\\build_source_manifest.py `",
            '  --pdf-dir "G:\\paper\\Sorted_Database" `',
            '  --markdown-dir ".\\data\\markdown" `',
            '  --outputs-dir ".\\data\\outputs" `',
            '  --out-dir ".\\data\\batch_manifest"',
            "",
            "python .\\scripts\\dev\\run_stage1_markdown_batch.py `",
            '  --manifest ".\\data\\batch_manifest\\source_manifest.csv" `',
            '  --markdown-dir ".\\data\\markdown" `',
            '  --outputs-dir ".\\data\\outputs" `',
            '  --report-dir ".\\data\\batch_validation_reports" `',
            "  --dry-run `",
            "  --limit 0",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _manifest_missing_message(path: Path) -> str:
    return dedent(
        f"""
        source_manifest.csv not found: {path}

        Please generate it first with:
        python .\\scripts\\dev\\build_source_manifest.py `
          --pdf-dir "G:\\paper\\Sorted_Database" `
          --markdown-dir ".\\data\\markdown" `
          --outputs-dir ".\\data\\outputs" `
          --out-dir ".\\data\\batch_manifest"
        """
    ).strip()


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _read_char_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return len(path.read_text(encoding="utf-8", errors="ignore"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> int:
    args = parse_args()
    try:
        result = run_stage1_markdown_batch(
            manifest=args.manifest,
            markdown_dir=args.markdown_dir,
            outputs_dir=args.outputs_dir,
            report_dir=args.report_dir,
            category=args.category,
            paper_ids=[item.strip() for item in args.paper_ids.split(",") if item.strip()],
            limit=max(0, args.limit),
            force=args.force,
            min_markdown_chars=max(0, args.min_markdown_chars),
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "summary": result["summary"],
                "report_csv_path": result["report_csv_path"],
                "report_md_path": result["report_md_path"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
