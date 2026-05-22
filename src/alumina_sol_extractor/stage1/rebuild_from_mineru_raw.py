from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.utils.batch_categories import (  # noqa: E402
    CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED,
    normalize_batch_category,
)
from alumina_sol_extractor.utils.chemical_text_normalizer import (  # noqa: E402
    normalize_mineru_markdown_chemistry,
)
from alumina_sol_extractor.utils.figure_utils import IMAGE_PATTERN, rewrite_mineru_image_paths  # noqa: E402


KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES_WITH_UNCATEGORIZED
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"
DEFAULT_MINERU_RAW_DIR = PROJECT_ROOT / "data" / "mineru_raw"
DEFAULT_MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "batch_validation_reports"
REQUIRED_MANIFEST_FIELDS = ["source_id", "category", "paper_id_guess"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
REPORT_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "expected_raw_dir",
    "actual_raw_dir",
    "raw_dir_match_method",
    "cache_has_raw_mineru_md",
    "cache_has_extracted_markdown",
    "cache_has_zip",
    "mineru_markdown_path",
    "output_markdown_path",
    "paper_output_dir",
    "figures_all_dir",
    "status",
    "raw_image_reference_count",
    "figures_all_file_count",
    "markdown_written",
    "error_type",
    "error_message",
    "recommended_action",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild Stage 1 outputs from cached MinerU raw results without calling MinerU API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--mineru-raw-dir", default=str(DEFAULT_MINERU_RAW_DIR))
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


def rebuild_stage1_from_mineru_raw(
    *,
    manifest: Path | str = DEFAULT_MANIFEST,
    mineru_raw_dir: Path | str = DEFAULT_MINERU_RAW_DIR,
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
    mineru_raw_dir = Path(mineru_raw_dir)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    report_dir = Path(report_dir)
    if not manifest.exists():
        raise FileNotFoundError(_manifest_missing_message(manifest))

    rows = _load_manifest_rows(manifest)
    _validate_manifest_fields(rows)
    selected_rows = _select_manifest_rows(rows, category=category, paper_ids=paper_ids, limit=limit)
    report_dir.mkdir(parents=True, exist_ok=True)
    mineru_cache_index = build_mineru_cache_index(mineru_raw_dir)

    run_started = _now_iso()
    report_rows: list[dict[str, Any]] = []
    for row in selected_rows:
        report_row = _process_manifest_row(
            row,
            mineru_raw_dir=mineru_raw_dir,
            mineru_cache_index=mineru_cache_index,
            markdown_dir=markdown_dir,
            outputs_dir=outputs_dir,
            force=force,
            dry_run=dry_run,
        )
        report_rows.append(report_row)
        if report_row["status"] == "failed" and not continue_on_error:
            break

    run_finished = _now_iso()
    summary = _build_summary(
        report_rows,
        manifest=manifest,
        mineru_raw_dir=mineru_raw_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mineru_cache_index=mineru_cache_index,
        category=category,
        paper_ids=paper_ids or [],
        limit=limit,
        force=force,
        dry_run=dry_run,
        started_at=run_started,
        finished_at=run_finished,
    )
    report_md = _build_markdown_report(summary, report_rows)

    report_csv_path = report_dir / "rebuild_stage1_from_mineru_raw_report.csv"
    report_md_path = report_dir / "rebuild_stage1_from_mineru_raw_report.md"
    summary_json_path = report_dir / "rebuild_stage1_from_mineru_raw_summary.json"

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
    mineru_raw_dir: Path,
    mineru_cache_index: list[dict[str, Any]],
    markdown_dir: Path,
    outputs_dir: Path,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    category = normalize_batch_category(row.get("category"))
    paper_id_guess = row.get("paper_id_guess") or ""
    expected_raw_dir = mineru_raw_dir / paper_id_guess
    output_markdown_path = _resolve_markdown_path(row, markdown_dir=markdown_dir)
    paper_output_dir = outputs_dir / category / paper_id_guess
    figures_all_dir = paper_output_dir / "figures_all"
    matched_cache = _match_mineru_cache_row(
        row,
        category=category,
        mineru_raw_dir=mineru_raw_dir,
        mineru_cache_index=mineru_cache_index,
    )
    actual_raw_dir = Path(matched_cache["actual_raw_dir"]) if matched_cache else None

    status = ""
    mineru_markdown_path = ""
    raw_image_reference_count = 0
    figures_all_file_count = _count_figure_files(figures_all_dir)
    markdown_written = False
    error_type = ""
    error_message = ""
    recommended_action = ""
    raw_dir_match_method = matched_cache["match_method"] if matched_cache else "not_found"
    cache_has_raw_mineru_md = bool(matched_cache["has_raw_mineru_md"]) if matched_cache else False
    cache_has_extracted_markdown = bool(matched_cache["has_extracted_markdown"]) if matched_cache else False
    cache_has_zip = bool(matched_cache["has_zip"]) if matched_cache else False

    if actual_raw_dir is None:
        status = "missing_mineru_raw"
        recommended_action = "check_mineru_raw_cache"
    else:
        mineru_md = _find_mineru_markdown(actual_raw_dir)
        if mineru_md is None:
            status = "missing_mineru_markdown"
            recommended_action = "inspect_mineru_raw_contents"
        else:
            mineru_markdown_path = str(mineru_md)
            raw_markdown = mineru_md.read_text(encoding="utf-8", errors="ignore")
            raw_image_reference_count = len(IMAGE_PATTERN.findall(raw_markdown))
            if not force and output_markdown_path.exists() and _count_figure_files(figures_all_dir) > 0:
                status = "skipped_existing"
                figures_all_file_count = _count_figure_files(figures_all_dir)
                recommended_action = "skip_existing"
            elif dry_run:
                status = "dry_run_planned"
                recommended_action = "run_without_dry_run"
            else:
                try:
                    if force:
                        _reset_figures_all_dir(figures_all_dir)
                    else:
                        figures_all_dir.mkdir(parents=True, exist_ok=True)

                    cleaned_markdown = rewrite_mineru_image_paths(
                        markdown=raw_markdown,
                        markdown_dir=mineru_md.parent,
                        project_root=PROJECT_ROOT,
                        paper_id=paper_id_guess,
                        figures_all_dir=figures_all_dir,
                    )
                    normalized_markdown = normalize_mineru_markdown_chemistry(cleaned_markdown)
                    output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
                    output_markdown_path.write_text(normalized_markdown, encoding="utf-8")

                    figures_all_file_count = _count_figure_files(figures_all_dir)
                    markdown_written = True
                    status = "success"
                    recommended_action = "ready_for_stage2_preprocess"
                except Exception as exc:
                    status = "failed"
                    error_type = type(exc).__name__
                    error_message = str(exc)
                    figures_all_file_count = _count_figure_files(figures_all_dir)
                    recommended_action = "inspect_error_and_retry"

    return {
        "source_id": row.get("source_id", ""),
        "category": category,
        "paper_id_guess": paper_id_guess,
        "expected_raw_dir": str(expected_raw_dir),
        "actual_raw_dir": str(actual_raw_dir) if actual_raw_dir else "",
        "raw_dir_match_method": raw_dir_match_method,
        "cache_has_raw_mineru_md": cache_has_raw_mineru_md,
        "cache_has_extracted_markdown": cache_has_extracted_markdown,
        "cache_has_zip": cache_has_zip,
        "mineru_markdown_path": mineru_markdown_path,
        "output_markdown_path": str(output_markdown_path),
        "paper_output_dir": str(paper_output_dir),
        "figures_all_dir": str(figures_all_dir),
        "status": status,
        "raw_image_reference_count": raw_image_reference_count,
        "figures_all_file_count": figures_all_file_count,
        "markdown_written": markdown_written,
        "error_type": error_type,
        "error_message": error_message,
        "recommended_action": recommended_action,
    }


def _find_mineru_markdown(raw_dir: Path) -> Path | None:
    direct = raw_dir / "raw_mineru.md"
    if direct.exists():
        return direct

    extracted_dir = raw_dir / "extracted"
    if extracted_dir.exists():
        full_candidates = sorted(extracted_dir.rglob("full.md"))
        if full_candidates:
            return full_candidates[0]
        md_candidates = sorted(extracted_dir.rglob("*.md"))
        if md_candidates:
            return md_candidates[0]
    return None


def build_mineru_cache_index(mineru_raw_dir: Path) -> list[dict[str, Any]]:
    if not mineru_raw_dir.exists():
        return []

    candidates: dict[Path, dict[str, Any]] = {}
    for raw_md in mineru_raw_dir.rglob("raw_mineru.md"):
        _upsert_cache_candidate(candidates, raw_md.parent, has_raw_mineru_md=True)
    for zip_path in mineru_raw_dir.rglob("mineru_result.zip"):
        _upsert_cache_candidate(candidates, zip_path.parent, has_zip=True)
    for markdown_path in mineru_raw_dir.rglob("*.md"):
        raw_dir = _infer_cache_dir_from_markdown(markdown_path, mineru_raw_dir)
        if raw_dir is not None:
            _upsert_cache_candidate(candidates, raw_dir, has_extracted_markdown=True)

    index = list(candidates.values())
    index.sort(key=lambda item: item["actual_raw_dir"])
    return index


def _upsert_cache_candidate(
    candidates: dict[Path, dict[str, Any]],
    raw_dir: Path,
    *,
    has_raw_mineru_md: bool = False,
    has_extracted_markdown: bool = False,
    has_zip: bool = False,
) -> None:
    raw_dir = raw_dir.resolve()
    item = candidates.setdefault(
        raw_dir,
        {
            "actual_raw_dir": str(raw_dir),
            "folder_name": raw_dir.name,
            "normalized_folder_name": _normalize_cache_name(raw_dir.name),
            "has_raw_mineru_md": False,
            "has_extracted_markdown": False,
            "has_zip": False,
        },
    )
    item["has_raw_mineru_md"] = item["has_raw_mineru_md"] or has_raw_mineru_md
    item["has_extracted_markdown"] = item["has_extracted_markdown"] or has_extracted_markdown
    item["has_zip"] = item["has_zip"] or has_zip


def _infer_cache_dir_from_markdown(markdown_path: Path, mineru_raw_dir: Path) -> Path | None:
    if markdown_path.name == "raw_mineru.md":
        return markdown_path.parent
    try:
        relative_parts = markdown_path.resolve().relative_to(mineru_raw_dir.resolve()).parts
    except ValueError:
        return None
    if "extracted" not in relative_parts:
        return None
    extracted_index = relative_parts.index("extracted")
    if extracted_index == 0:
        return None
    raw_dir_parts = relative_parts[:extracted_index]
    return mineru_raw_dir.joinpath(*raw_dir_parts)


def _normalize_cache_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").strip().lower()
    normalized = re.sub(r"[\s\-_—–－,，、.:。：；;()\[\]（）【】<>《》\"“”'‘’·]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _match_mineru_cache_row(
    row: dict[str, str],
    *,
    category: str,
    mineru_raw_dir: Path,
    mineru_cache_index: list[dict[str, Any]],
) -> dict[str, Any] | None:
    paper_id_guess = (row.get("paper_id_guess") or "").strip()
    source_id = (row.get("source_id") or "").strip()
    pdf_stem = Path((row.get("pdf_path") or "").strip()).stem if (row.get("pdf_path") or "").strip() else ""

    folder_name_map = _build_cache_lookup(mineru_cache_index, "folder_name")
    normalized_name_map = _build_cache_lookup(mineru_cache_index, "normalized_folder_name")
    raw_dir_map = {Path(item["actual_raw_dir"]).resolve(): item for item in mineru_cache_index}

    for method, key in (
        ("exact_paper_id", paper_id_guess),
        ("exact_source_id", source_id),
        ("exact_pdf_stem", pdf_stem),
    ):
        matched = _unique_lookup(folder_name_map, key)
        if matched is not None:
            return {**matched, "match_method": method}

    for method, key in (
        ("normalized_paper_id", _normalize_cache_name(paper_id_guess)),
        ("normalized_source_id", _normalize_cache_name(source_id)),
        ("normalized_pdf_stem", _normalize_cache_name(pdf_stem)),
    ):
        matched = _unique_lookup(normalized_name_map, key)
        if matched is not None:
            return {**matched, "match_method": method}

    if paper_id_guess:
        category_raw_dir = (mineru_raw_dir / category / paper_id_guess).resolve()
        matched = raw_dir_map.get(category_raw_dir)
        if matched is not None:
            return {**matched, "match_method": "category_exact"}

    fuzzy = _fuzzy_unique_match(
        mineru_cache_index,
        keys=[paper_id_guess, source_id, pdf_stem],
    )
    if fuzzy is not None:
        return {**fuzzy, "match_method": "fuzzy_unique"}
    return None


def _build_cache_lookup(index: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for item in index:
        value = item.get(key) or ""
        if not value:
            continue
        lookup.setdefault(str(value), []).append(item)
    return lookup


def _unique_lookup(lookup: dict[str, list[dict[str, Any]]], key: str) -> dict[str, Any] | None:
    if not key:
        return None
    matches = lookup.get(key, [])
    if len(matches) == 1:
        return matches[0]
    return None


def _fuzzy_unique_match(index: list[dict[str, Any]], *, keys: list[str]) -> dict[str, Any] | None:
    normalized_keys = [_normalize_cache_name(key) for key in keys if key and _normalize_cache_name(key)]
    if not normalized_keys:
        return None
    matches: list[dict[str, Any]] = []
    for item in index:
        folder_name = item["folder_name"]
        normalized_folder_name = item["normalized_folder_name"]
        for key in normalized_keys:
            if (
                folder_name.startswith(key)
                or normalized_folder_name.startswith(key)
                or key in folder_name
                or key in normalized_folder_name
            ):
                matches.append(item)
                break
    unique = {item["actual_raw_dir"]: item for item in matches}
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def _reset_figures_all_dir(figures_all_dir: Path) -> None:
    if figures_all_dir.exists():
        shutil.rmtree(figures_all_dir)
    figures_all_dir.mkdir(parents=True, exist_ok=True)


def _count_figure_files(figures_all_dir: Path) -> int:
    if not figures_all_dir.exists():
        return 0
    return sum(1 for path in figures_all_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


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
    mineru_raw_dir: Path,
    markdown_dir: Path,
    outputs_dir: Path,
    report_dir: Path,
    mineru_cache_index: list[dict[str, Any]],
    category: str | None,
    paper_ids: list[str],
    limit: int,
    force: bool,
    dry_run: bool,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    match_method_counts = Counter(row["raw_dir_match_method"] for row in rows)
    matched_count = sum(1 for row in rows if row["raw_dir_match_method"] != "not_found")
    unmatched_sample = [row["source_id"] for row in rows if row["raw_dir_match_method"] == "not_found"][:20]
    by_category: dict[str, dict[str, Any]] = {}
    for category_name in sorted({row["category"] for row in rows} | set(KNOWN_CATEGORIES)):
        category_rows = [row for row in rows if row["category"] == category_name]
        by_category[category_name] = {
            "total": len(category_rows),
            "success_count": sum(1 for row in category_rows if row["status"] == "success"),
            "skipped_existing_count": sum(1 for row in category_rows if row["status"] == "skipped_existing"),
            "missing_mineru_raw_count": sum(1 for row in category_rows if row["status"] == "missing_mineru_raw"),
            "missing_mineru_markdown_count": sum(1 for row in category_rows if row["status"] == "missing_mineru_markdown"),
            "failed_count": sum(1 for row in category_rows if row["status"] == "failed"),
            "dry_run_count": sum(1 for row in category_rows if row["status"] == "dry_run_planned"),
            "matched_count": sum(1 for row in category_rows if row["raw_dir_match_method"] != "not_found"),
            "raw_dir_match_method_counts": dict(Counter(row["raw_dir_match_method"] for row in category_rows)),
        }
    return {
        "manifest": str(manifest),
        "mineru_raw_dir": str(mineru_raw_dir),
        "markdown_dir": str(markdown_dir),
        "outputs_dir": str(outputs_dir),
        "report_dir": str(report_dir),
        "category_filter": category,
        "paper_ids_filter": paper_ids,
        "limit": limit,
        "force": force,
        "dry_run": dry_run,
        "total_candidates": len(rows),
        "attempted_count": status_counts.get("success", 0) + status_counts.get("failed", 0),
        "success_count": status_counts.get("success", 0),
        "skipped_existing_count": status_counts.get("skipped_existing", 0),
        "missing_mineru_raw_count": status_counts.get("missing_mineru_raw", 0),
        "missing_mineru_markdown_count": status_counts.get("missing_mineru_markdown", 0),
        "failed_count": status_counts.get("failed", 0),
        "dry_run_count": status_counts.get("dry_run_planned", 0),
        "mineru_cache_candidate_count": len(mineru_cache_index),
        "raw_dir_match_method_counts": dict(match_method_counts),
        "matched_count": matched_count,
        "unmatched_sample": unmatched_sample,
        "by_category": by_category,
        "total_figures_all_file_count": sum(int(row["figures_all_file_count"]) for row in rows),
        "report_csv_path": str(report_dir / "rebuild_stage1_from_mineru_raw_report.csv"),
        "report_md_path": str(report_dir / "rebuild_stage1_from_mineru_raw_report.md"),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _build_markdown_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failed_rows = [row for row in rows if row["status"] == "failed"]
    missing_rows = [
        row
        for row in rows
        if row["status"] in {"missing_mineru_raw", "missing_mineru_markdown"}
    ]
    lines = [
        "# Rebuild Stage 1 From MinerU Raw Report",
        "",
        "## Overall Statistics",
        f"- total_candidates: {summary['total_candidates']}",
        f"- attempted_count: {summary['attempted_count']}",
        f"- success_count: {summary['success_count']}",
        f"- skipped_existing_count: {summary['skipped_existing_count']}",
        f"- missing_mineru_raw_count: {summary['missing_mineru_raw_count']}",
        f"- missing_mineru_markdown_count: {summary['missing_mineru_markdown_count']}",
        f"- failed_count: {summary['failed_count']}",
        f"- dry_run_count: {summary['dry_run_count']}",
        f"- mineru_cache_candidate_count: {summary['mineru_cache_candidate_count']}",
        f"- matched_count: {summary['matched_count']}",
        f"- total_figures_all_file_count: {summary['total_figures_all_file_count']}",
        "",
        "## Raw Cache Match Methods",
    ]
    for method, count in sorted(summary["raw_dir_match_method_counts"].items()):
        lines.append(f"- {method}: {count}")
    lines.extend([
        "",
        "## By Category",
    ])
    for category_name, counts in summary["by_category"].items():
        lines.extend(
            [
                f"### {category_name}",
                f"- total: {counts['total']}",
                f"- success_count: {counts['success_count']}",
                f"- skipped_existing_count: {counts['skipped_existing_count']}",
                f"- missing_mineru_raw_count: {counts['missing_mineru_raw_count']}",
                f"- missing_mineru_markdown_count: {counts['missing_mineru_markdown_count']}",
                f"- failed_count: {counts['failed_count']}",
                f"- dry_run_count: {counts['dry_run_count']}",
                f"- matched_count: {counts['matched_count']}",
                "",
            ]
        )

    lines.append("## Failed Items")
    if failed_rows:
        for row in failed_rows:
            lines.append(f"- {row['source_id']}: {row['error_type']} | {row['error_message']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Missing MinerU Raw / Markdown"])
    if missing_rows:
        for row in missing_rows:
            lines.append(f"- {row['source_id']}: {row['status']} | match_method={row['raw_dir_match_method']}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Next Step Suggestions",
            "- If missing_mineru_raw_count > 0, verify whether the paper was converted by MinerU and cached under data/mineru_raw.",
            "- If missing_mineru_markdown_count > 0, inspect the cached extracted directory layout for those papers.",
            "- After a healthy rebuild, the next step is category-aware Stage 2 preprocessing from the rebuilt markdown and figures_all outputs.",
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


def main() -> int:
    args = parse_args()
    try:
        result = rebuild_stage1_from_mineru_raw(
            manifest=args.manifest,
            mineru_raw_dir=args.mineru_raw_dir,
            markdown_dir=args.markdown_dir,
            outputs_dir=args.outputs_dir,
            report_dir=args.report_dir,
            category=args.category,
            paper_ids=[item.strip() for item in args.paper_ids.split(",") if item.strip()],
            limit=max(0, args.limit),
            force=args.force,
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
