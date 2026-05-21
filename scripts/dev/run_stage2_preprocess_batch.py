from __future__ import annotations

import argparse
import copy
import csv
import json
import re
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

from alumina_sol_extractor.config import build_runtime_settings
from alumina_sol_extractor.pipeline.stage2_figure_pipeline import run_stage2_figure_pipeline
from alumina_sol_extractor.utils.batch_categories import (
    CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED,
    normalize_batch_category,
)


KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "batch_validation_reports"
REQUIRED_MANIFEST_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
]
REPORT_FIELDS = [
    "run_id",
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "markdown_path",
    "paper_output_dir",
    "legacy_figures_all_dir",
    "category_figures_all_dir",
    "status",
    "legacy_image_link_detected",
    "image_link_normalized",
    "image_link_replacement_count",
    "image_file_missing_count",
    "figure_stage2_summary_path",
    "raw_mineru_image_count",
    "tables_count",
    "figures_all_count",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "error_type",
    "error_message",
    "recommended_action",
]
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch runner for Stage 2 figure/table preprocessing using source_manifest.csv.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Examples:
              python .\\scripts\\dev\\run_stage2_preprocess_batch.py `
                --manifest ".\\data\\batch_manifest\\source_manifest.csv" `
                --markdown-dir ".\\data\\markdown" `
                --outputs-dir ".\\data\\outputs" `
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
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    parser.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")
    parser.add_argument("--disable-vision-classifiers", action="store_true")
    return parser.parse_args()


def run_stage2_preprocess_batch(
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
    disable_vision_classifiers: bool = False,
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
            dry_run=dry_run,
            run_id=run_id,
            settings_template=settings_template,
            disable_vision_classifiers=disable_vision_classifiers,
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
        disable_vision_classifiers=disable_vision_classifiers,
        started_at=run_started,
        finished_at=run_finished,
    )
    report_md = _build_markdown_report(summary, report_rows)

    report_csv_path = report_dir / "stage2_preprocess_batch_report.csv"
    report_md_path = report_dir / "stage2_preprocess_batch_report.md"
    summary_json_path = report_dir / "stage2_preprocess_batch_summary.json"

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
    dry_run: bool,
    run_id: str,
    settings_template: dict[str, Any] | None,
    disable_vision_classifiers: bool,
) -> dict[str, Any]:
    started_at = _now_iso()
    source_id = row.get("source_id", "")
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    pdf_path = Path(row.get("pdf_path") or "")
    markdown_path = _resolve_markdown_path(row, markdown_dir=markdown_dir)
    paper_output_dir = outputs_dir / category / paper_id_guess
    legacy_paper_output_dir = outputs_dir / paper_id_guess
    legacy_figures_all_dir = legacy_paper_output_dir / "figures_all"
    category_figures_all_dir = paper_output_dir / "figures_all"
    summary_path = paper_output_dir / "figure_stage2_summary.json"

    status = ""
    raw_mineru_image_count = 0
    tables_count = 0
    figures_all_count = 0
    legacy_image_link_detected = False
    image_link_normalized = False
    image_link_replacement_count = 0
    image_file_missing_count = 0
    error_type = ""
    error_message = ""
    recommended_action = ""

    if not markdown_path.exists():
        status = "missing_markdown"
        recommended_action = "generate_markdown_then_rerun"
    elif summary_path.exists() and not force:
        status = "skipped_existing"
        raw_mineru_image_count, tables_count, figures_all_count = _read_existing_stage2_counts(summary_path)
        recommended_action = "skip_existing"
    elif dry_run:
        status = "dry_run_planned"
        recommended_action = "run_without_dry_run"
    else:
        try:
            (
                legacy_image_link_detected,
                image_link_normalized,
                image_link_replacement_count,
                image_file_missing_count,
            ) = _normalize_markdown_image_links(
                markdown_path=markdown_path,
                outputs_dir=outputs_dir,
                category=category,
                paper_id_guess=paper_id_guess,
            )
            result = _run_stage2_for_row(
                row,
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                paper_output_dir=paper_output_dir,
                settings_template=settings_template or {},
                disable_vision_classifiers=disable_vision_classifiers,
            )
            _validate_stage2_jsonl_outputs(paper_output_dir)
            status = "success"
            summary_path = paper_output_dir / "figure_stage2_summary.json"
            raw_mineru_image_count = int(getattr(result, "raw_mineru_image_count", 0) or 0)
            tables_count = int(getattr(result, "tables_count", 0) or 0)
            figures_all_count = _resolve_figures_all_count(paper_output_dir, getattr(result, "summary", {}) or {})
            recommended_action = "ready_for_stage3_or_supplementary_review"
            if image_file_missing_count > 0:
                recommended_action = "inspect_missing_category_figure_paths_then_continue"
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
        "legacy_figures_all_dir": str(legacy_figures_all_dir),
        "category_figures_all_dir": str(category_figures_all_dir),
        "status": status,
        "legacy_image_link_detected": legacy_image_link_detected,
        "image_link_normalized": image_link_normalized,
        "image_link_replacement_count": image_link_replacement_count,
        "image_file_missing_count": image_file_missing_count,
        "figure_stage2_summary_path": str(summary_path),
        "raw_mineru_image_count": raw_mineru_image_count,
        "tables_count": tables_count,
        "figures_all_count": figures_all_count,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "error_type": error_type,
        "error_message": error_message,
        "recommended_action": recommended_action,
    }


def _run_stage2_for_row(
    row: dict[str, str],
    *,
    pdf_path: Path,
    markdown_path: Path,
    paper_output_dir: Path,
    settings_template: dict[str, Any],
    disable_vision_classifiers: bool,
) -> Any:
    paper_id_guess = row.get("paper_id_guess") or ""
    category = normalize_batch_category(row.get("category"))
    settings = copy.deepcopy(settings_template)
    settings.setdefault("paths", {})
    settings["paths"]["input_pdf"] = str(pdf_path)
    settings["paths"]["markdown_output_dir"] = str(markdown_path.parent)
    settings["paths"]["mineru_raw_dir"] = str(PROJECT_ROOT / "data" / "mineru_raw" / category)
    settings["paths"]["output_dir"] = str((paper_output_dir.parent))
    if disable_vision_classifiers:
        settings.setdefault("figures", {})
        settings["figures"]["run_resnet"] = False
        settings["figures"]["run_clip"] = False

    return run_stage2_figure_pipeline(
        project_root=PROJECT_ROOT,
        settings=settings,
        input_pdf=pdf_path,
        paper_id=paper_id_guess,
        cleaned_markdown_path=markdown_path,
        output_dir=paper_output_dir,
    )


def _resolve_markdown_path(row: dict[str, str], *, markdown_dir: Path) -> Path:
    actual = row.get("markdown_actual_path") or ""
    if actual:
        return Path(actual)
    expected = row.get("markdown_expected_path") or ""
    if expected:
        return Path(expected)
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    return markdown_dir / category / f"{paper_id_guess}.md"


def _normalize_markdown_image_links(
    *,
    markdown_path: Path,
    outputs_dir: Path,
    category: str,
    paper_id_guess: str,
) -> tuple[bool, bool, int, int]:
    text = markdown_path.read_text(encoding="utf-8")
    replacements = _build_markdown_link_replacements(category=category, paper_id_guess=paper_id_guess)
    legacy_image_link_detected = False
    replacement_count = 0
    updated_text = text
    for old_value, new_value in replacements.items():
        hits = updated_text.count(old_value)
        if hits:
            legacy_image_link_detected = True
            updated_text = updated_text.replace(old_value, new_value)
            replacement_count += hits
    image_file_missing_count = _count_missing_category_figure_links(updated_text, outputs_dir=outputs_dir) if replacement_count else 0
    if replacement_count:
        markdown_path.write_text(updated_text, encoding="utf-8")
    return legacy_image_link_detected, replacement_count > 0, replacement_count, image_file_missing_count


def _build_markdown_link_replacements(*, category: str, paper_id_guess: str) -> dict[str, str]:
    relative_old = f"data/outputs/{paper_id_guess}/figures_all/"
    relative_new = f"data/outputs/{category}/{paper_id_guess}/figures_all/"
    relative_old_windows = f"data\\outputs\\{paper_id_guess}\\figures_all\\"
    relative_new_windows = f"data\\outputs\\{category}\\{paper_id_guess}\\figures_all\\"
    absolute_old = f"{PROJECT_ROOT.as_posix()}/data/outputs/{paper_id_guess}/figures_all/"
    absolute_new = f"{PROJECT_ROOT.as_posix()}/data/outputs/{category}/{paper_id_guess}/figures_all/"
    absolute_old_windows = str(PROJECT_ROOT / "data" / "outputs" / paper_id_guess / "figures_all") + "\\"
    absolute_new_windows = str(PROJECT_ROOT / "data" / "outputs" / category / paper_id_guess / "figures_all") + "\\"
    return {
        relative_old: relative_new,
        relative_old_windows: relative_new_windows,
        absolute_old: absolute_new,
        absolute_old_windows: absolute_new_windows,
    }


def _count_missing_category_figure_links(text: str, *, outputs_dir: Path) -> int:
    normalized_text = text.replace("\\", "/")
    figure_link_pattern = re.compile(
        r'(?P<path>(?:[A-Za-z]:/|/)?[^()\[\]\s<>"\']*data/outputs/[^()\[\]\s<>"\']*/figures_all/[^()\[\]\s<>"\']+)'
    )
    missing_count = 0
    seen_paths: set[Path] = set()
    for match in figure_link_pattern.finditer(normalized_text):
        normalized_path = match.group("path")
        if "data/outputs/" not in normalized_path or "/figures_all/" not in normalized_path:
            continue
        if normalized_path.startswith(PROJECT_ROOT.as_posix()):
            candidate = Path(normalized_path)
        else:
            if "/data/outputs/" in normalized_path:
                relative_part = normalized_path.split("/data/outputs/", 1)[1]
            else:
                relative_part = normalized_path.split("data/outputs/", 1)[1]
            candidate = outputs_dir / Path(relative_part)
        candidate = candidate.resolve(strict=False)
        if candidate in seen_paths:
            continue
        seen_paths.add(candidate)
        if not candidate.exists():
            missing_count += 1
    return missing_count


def _validate_stage2_jsonl_outputs(paper_output_dir: Path) -> None:
    for filename in ("figures.jsonl", "vision_inputs.jsonl"):
        _validate_jsonl_file(paper_output_dir / filename)


def _validate_jsonl_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} at line {line_number}: {exc.msg}") from exc


def _read_existing_stage2_counts(summary_path: Path) -> tuple[int, int, int]:
    if not summary_path.exists():
        return 0, 0, 0
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0, 0
    paper_output_dir = summary_path.parent
    raw_count = int(summary.get("raw_mineru_image_count") or 0)
    tables_count = _count_files(paper_output_dir / "tables")
    figures_all_count = _resolve_figures_all_count(paper_output_dir, summary)
    return raw_count, tables_count, figures_all_count


def _resolve_figures_all_count(paper_output_dir: Path, summary: dict[str, Any]) -> int:
    figures_all_dir_value = summary.get("figures_all_dir")
    if figures_all_dir_value:
        count = _count_files(Path(figures_all_dir_value))
        if count:
            return count
    count = _count_files(paper_output_dir / "figures_all")
    if count:
        return count
    for key in ("final_figure_record_count", "keep_for_archive_count", "send_to_vision_model_count"):
        value = summary.get(key)
        if isinstance(value, int):
            return value
    return 0


def _count_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for child in path.iterdir() if child.is_file())


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
    dry_run: bool,
    disable_vision_classifiers: bool,
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
            "missing_markdown_count": sum(1 for row in category_rows if row["status"] == "missing_markdown"),
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
        "dry_run": dry_run,
        "disable_vision_classifiers": disable_vision_classifiers,
        "total_candidates": len(rows),
        "attempted_count": status_counts.get("success", 0) + status_counts.get("failed", 0),
        "success_count": status_counts.get("success", 0),
        "skipped_existing_count": status_counts.get("skipped_existing", 0),
        "missing_markdown_count": status_counts.get("missing_markdown", 0),
        "failed_count": status_counts.get("failed", 0),
        "dry_run_count": status_counts.get("dry_run_planned", 0),
        "by_category": by_category,
        "report_csv_path": str(report_dir / "stage2_preprocess_batch_report.csv"),
        "report_md_path": str(report_dir / "stage2_preprocess_batch_report.md"),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_markdown_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failed_rows = [row for row in rows if row["status"] == "failed"]
    missing_markdown_rows = [row for row in rows if row["status"] == "missing_markdown"]
    lines = [
        "# Stage 2 Preprocess Batch Report",
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
        f"- dry_run: {summary['dry_run']}",
        f"- disable_vision_classifiers: {summary['disable_vision_classifiers']}",
        "",
        "## Overall Statistics",
        f"- total_candidates: {summary['total_candidates']}",
        f"- attempted_count: {summary['attempted_count']}",
        f"- success_count: {summary['success_count']}",
        f"- skipped_existing_count: {summary['skipped_existing_count']}",
        f"- missing_markdown_count: {summary['missing_markdown_count']}",
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
                f"- missing_markdown_count: {counts['missing_markdown_count']}",
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
    lines.extend(["", "## Missing Markdown"])
    if missing_markdown_rows:
        for row in missing_markdown_rows:
            lines.append(f"- {row['source_id']}: {row['markdown_path']}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Step Suggestions",
            "- If failed_count > 0, inspect the failed items and retry those papers first.",
            "- If missing_markdown_count > 0, confirm Stage 1 markdown outputs before rerunning Stage 2.",
            "- If success_count is high enough, the next controlled step is supplementary review or a Stage 3 smoke batch.",
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> int:
    args = parse_args()
    try:
        result = run_stage2_preprocess_batch(
            manifest=args.manifest,
            markdown_dir=args.markdown_dir,
            outputs_dir=args.outputs_dir,
            report_dir=args.report_dir,
            category=args.category,
            paper_ids=[item.strip() for item in args.paper_ids.split(",") if item.strip()],
            limit=max(0, args.limit),
            force=args.force,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
            disable_vision_classifiers=args.disable_vision_classifiers,
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
