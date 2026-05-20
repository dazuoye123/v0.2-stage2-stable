from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.utils.batch_categories import (
    BATCH_CATEGORY_PRIORITY,
    CANONICAL_BATCH_CATEGORIES,
    infer_batch_category_from_path,
)

KNOWN_CATEGORIES = CANONICAL_BATCH_CATEGORIES
CATEGORY_PRIORITY = BATCH_CATEGORY_PRIORITY
SOURCE_MANIFEST_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "pdf_relative_path",
    "pdf_exists",
    "pdf_file_size_mb",
    "markdown_expected_path",
    "markdown_actual_path",
    "markdown_exists",
    "markdown_char_count",
    "markdown_status",
    "output_dir",
    "legacy_output_dir",
    "resolved_output_dir",
    "output_dir_layout",
    "has_output_dir",
    "has_stage3",
    "has_stage4a",
    "has_final_dataset",
    "has_link_aware_export",
    "current_pipeline_status",
    "recommended_next_action",
]
DEFAULT_MIN_MARKDOWN_CHARS = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a category-aware source manifest for PDF/markdown/pipeline coverage.")
    parser.add_argument("--pdf-dir", default=str(PROJECT_ROOT / "data" / "pdfs"))
    parser.add_argument("--markdown-dir", default=str(PROJECT_ROOT / "data" / "markdown"))
    parser.add_argument("--outputs-dir", default=str(PROJECT_ROOT / "data" / "outputs"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "data" / "batch_manifest"))
    parser.add_argument("--min-markdown-chars", type=int, default=DEFAULT_MIN_MARKDOWN_CHARS)
    return parser.parse_args()


def build_source_manifest(
    *,
    pdf_dir: Path | str,
    markdown_dir: Path | str,
    outputs_dir: Path | str,
    out_dir: Path | str,
    min_markdown_chars: int = DEFAULT_MIN_MARKDOWN_CHARS,
) -> dict[str, Any]:
    pdf_dir = Path(pdf_dir)
    markdown_dir = Path(markdown_dir)
    outputs_dir = Path(outputs_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _collect_source_rows(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        min_markdown_chars=min_markdown_chars,
    )
    summary = _build_summary(rows, pdf_dir=pdf_dir, markdown_dir=markdown_dir, outputs_dir=outputs_dir, min_markdown_chars=min_markdown_chars)
    run_groups_md = _build_stage1_run_groups(rows, summary)

    csv_path = out_dir / "source_manifest.csv"
    json_path = out_dir / "source_manifest.json"
    summary_path = out_dir / "source_manifest_summary.json"
    run_groups_path = out_dir / "stage1_run_groups.md"

    _write_csv(csv_path, rows, SOURCE_MANIFEST_FIELDS)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    run_groups_path.write_text(run_groups_md, encoding="utf-8")

    return {
        "rows": rows,
        "summary": summary,
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "summary_path": str(summary_path),
        "run_groups_path": str(run_groups_path),
    }


def _collect_source_rows(
    *,
    pdf_dir: Path,
    markdown_dir: Path,
    outputs_dir: Path,
    min_markdown_chars: int,
) -> list[dict[str, Any]]:
    pdf_paths = _discover_pdf_paths(pdf_dir)
    rows: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for pdf_path in pdf_paths:
        category = _infer_category(pdf_path, pdf_dir)
        paper_id_guess = pdf_path.stem
        source_id = _build_source_id(category, paper_id_guess)
        if source_id in seen_source_ids:
            source_id = f"{source_id}__{len(seen_source_ids) + 1}"
        seen_source_ids.add(source_id)

        markdown_expected_path = markdown_dir / category / f"{paper_id_guess}.md"
        legacy_markdown_path = markdown_dir / f"{paper_id_guess}.md"
        markdown_actual_path = markdown_expected_path if markdown_expected_path.exists() else legacy_markdown_path if legacy_markdown_path.exists() else markdown_expected_path
        markdown_exists = markdown_actual_path.exists()
        markdown_char_count = len(markdown_actual_path.read_text(encoding="utf-8")) if markdown_exists else 0
        markdown_status = _determine_markdown_status(
            pdf_exists=pdf_path.exists(),
            markdown_exists=markdown_exists,
            markdown_char_count=markdown_char_count,
            min_markdown_chars=min_markdown_chars,
        )

        recommended_output_dir = outputs_dir / category / paper_id_guess
        legacy_output_dir = outputs_dir / paper_id_guess
        resolved_output_dir, output_dir_layout = _resolve_output_dir(recommended_output_dir, legacy_output_dir)
        has_output_dir = resolved_output_dir.exists()
        has_stage3 = (resolved_output_dir / "stage3_dspy_smoke").exists()
        has_stage4a = (resolved_output_dir / "stage4_vision_spectra").exists()
        has_final_dataset = (resolved_output_dir / "final_dataset").exists()
        has_link_aware_export = (resolved_output_dir / "final_dataset" / "link_aware_exports" / "link_aware_export_summary.json").exists()
        current_pipeline_status = _determine_pipeline_status(
            markdown_status=markdown_status,
            has_stage3=has_stage3,
            has_stage4a=has_stage4a,
            has_final_dataset=has_final_dataset,
            has_link_aware_export=has_link_aware_export,
        )
        recommended_next_action = _determine_next_action(
            markdown_status=markdown_status,
            current_pipeline_status=current_pipeline_status,
        )

        rows.append(
            {
                "source_id": source_id,
                "category": category,
                "paper_id_guess": paper_id_guess,
                "pdf_path": str(pdf_path),
                "pdf_relative_path": _safe_relative(pdf_path, PROJECT_ROOT),
                "pdf_exists": pdf_path.exists(),
                "pdf_file_size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 3) if pdf_path.exists() else 0.0,
                "markdown_expected_path": str(markdown_expected_path),
                "markdown_actual_path": str(markdown_actual_path) if markdown_exists else "",
                "markdown_exists": markdown_exists,
                "markdown_char_count": markdown_char_count,
                "markdown_status": markdown_status,
                "output_dir": str(recommended_output_dir),
                "legacy_output_dir": str(legacy_output_dir),
                "resolved_output_dir": str(resolved_output_dir),
                "output_dir_layout": output_dir_layout,
                "has_output_dir": has_output_dir,
                "has_stage3": has_stage3,
                "has_stage4a": has_stage4a,
                "has_final_dataset": has_final_dataset,
                "has_link_aware_export": has_link_aware_export,
                "current_pipeline_status": current_pipeline_status,
                "recommended_next_action": recommended_next_action,
            }
        )
    return rows


def _discover_pdf_paths(pdf_dir: Path) -> list[Path]:
    if not pdf_dir.exists():
        return []
    pdf_paths = [path for path in pdf_dir.rglob("*.pdf") if path.is_file()]
    return sorted(pdf_paths, key=lambda item: (_category_sort_key(_infer_category(item, pdf_dir)), _safe_relative(item, pdf_dir).lower()))


def _category_sort_key(category: str) -> int:
    try:
        return CATEGORY_PRIORITY.index(category)
    except ValueError:
        return len(CATEGORY_PRIORITY)


def _infer_category(path: Path, pdf_dir: Path) -> str:
    return infer_batch_category_from_path(path, pdf_dir)


def _build_source_id(category: str, stem: str) -> str:
    normalized = re.sub(r"\W+", "_", stem, flags=re.UNICODE).strip("_").lower()
    normalized = normalized or "untitled"
    return f"{category}__{normalized}"


def _determine_markdown_status(
    *,
    pdf_exists: bool,
    markdown_exists: bool,
    markdown_char_count: int,
    min_markdown_chars: int,
) -> str:
    if not pdf_exists:
        return "missing_pdf"
    if not markdown_exists:
        return "not_generated"
    if markdown_char_count <= 0:
        return "exists_empty"
    if markdown_char_count < min_markdown_chars:
        return "exists_too_short"
    return "exists_ok"


def _resolve_output_dir(recommended_output_dir: Path, legacy_output_dir: Path) -> tuple[Path, str]:
    if recommended_output_dir.exists():
        return recommended_output_dir, "category_aware"
    if legacy_output_dir.exists():
        return legacy_output_dir, "legacy_flat"
    return recommended_output_dir, "category_aware"


def _determine_pipeline_status(
    *,
    markdown_status: str,
    has_stage3: bool,
    has_stage4a: bool,
    has_final_dataset: bool,
    has_link_aware_export: bool,
) -> str:
    if has_link_aware_export:
        return "link_aware_done"
    if has_final_dataset:
        return "final_dataset_done"
    if has_stage4a:
        return "stage4a_done"
    if has_stage3:
        return "stage3_done"
    if markdown_status == "exists_ok":
        return "markdown_ready"
    if markdown_status in {"exists_empty", "exists_too_short"}:
        return "partial"
    return "pdf_only"


def _determine_next_action(*, markdown_status: str, current_pipeline_status: str) -> str:
    if current_pipeline_status == "link_aware_done":
        return "skip_already_done"
    if markdown_status in {"exists_empty", "exists_too_short"}:
        return "inspect_markdown"
    if current_pipeline_status == "markdown_ready":
        return "run_stage3_next"
    if current_pipeline_status in {"stage3_done", "stage4a_done", "final_dataset_done", "partial"}:
        return "run_full_pipeline_next"
    if markdown_status == "not_generated":
        return "run_stage1_pdf_to_markdown"
    if markdown_status == "missing_pdf":
        return "needs_manual_review"
    return "needs_manual_review"


def _build_summary(
    rows: list[dict[str, Any]],
    *,
    pdf_dir: Path,
    markdown_dir: Path,
    outputs_dir: Path,
    min_markdown_chars: int,
) -> dict[str, Any]:
    category_summary: dict[str, dict[str, Any]] = {}
    action_counts = Counter(row["recommended_next_action"] for row in rows)
    pipeline_counts = Counter(row["current_pipeline_status"] for row in rows)
    markdown_counts = Counter(row["markdown_status"] for row in rows)
    for category in CATEGORY_PRIORITY:
        category_rows = [row for row in rows if row["category"] == category]
        if not category_rows and category != "uncategorized":
            category_rows = []
        category_summary[category] = {
            "pdf_count": len(category_rows),
            "markdown_exists_count": sum(1 for row in category_rows if row["markdown_exists"]),
            "markdown_missing_count": sum(1 for row in category_rows if not row["markdown_exists"]),
            "markdown_too_short_count": sum(1 for row in category_rows if row["markdown_status"] == "exists_too_short"),
            "stage3_done_count": sum(1 for row in category_rows if row["has_stage3"]),
            "stage4a_done_count": sum(1 for row in category_rows if row["has_stage4a"]),
            "final_dataset_done_count": sum(1 for row in category_rows if row["has_final_dataset"]),
            "link_aware_done_count": sum(1 for row in category_rows if row["has_link_aware_export"]),
        }
    recommended_stage1_smoke = _recommend_stage1_smoke(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf_dir": str(pdf_dir),
        "markdown_dir": str(markdown_dir),
        "outputs_dir": str(outputs_dir),
        "min_markdown_chars": min_markdown_chars,
        "total_sources": len(rows),
        "category_summary": category_summary,
        "recommended_next_action_counts": dict(action_counts),
        "pipeline_status_counts": dict(pipeline_counts),
        "markdown_status_counts": dict(markdown_counts),
        "recommended_stage1_smoke_10": recommended_stage1_smoke,
    }


def _recommend_stage1_smoke(rows: list[dict[str, Any]]) -> list[str]:
    targets = {"fiber_process": 4, "mechanism": 3, "rheology": 2, "applications": 1}
    picks: list[str] = []
    for category in CATEGORY_PRIORITY:
        if category not in targets:
            continue
        category_rows = [
            row
            for row in rows
            if row["category"] == category and row["recommended_next_action"] in {"run_stage1_pdf_to_markdown", "inspect_markdown"}
        ]
        for row in category_rows[: targets[category]]:
            picks.append(row["source_id"])
    return picks[:10]


def _build_stage1_run_groups(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    smoke_lines = [f"- {source_id}" for source_id in summary.get("recommended_stage1_smoke_10", [])] or ["- none"]
    lines = [
        "# Stage 1 Run Groups",
        "",
        "Priority order: fiber_process > mechanism > rheology > applications",
        "",
    ]
    for category in CATEGORY_PRIORITY:
        category_rows = [row for row in rows if row["category"] == category]
        category_label = category
        lines.append(f"## {category_label}")
        lines.append(f"- pdf_count: {len(category_rows)}")
        lines.append(f"- markdown_exists_count: {sum(1 for row in category_rows if row['markdown_exists'])}")
        lines.append(f"- markdown_missing_count: {sum(1 for row in category_rows if not row['markdown_exists'])}")
        next_stage1 = [row["source_id"] for row in category_rows if row["recommended_next_action"] == "run_stage1_pdf_to_markdown"]
        inspect_list = [row["source_id"] for row in category_rows if row["recommended_next_action"] == "inspect_markdown"]
        run_stage3 = [row["source_id"] for row in category_rows if row["recommended_next_action"] == "run_stage3_next"]
        lines.append(f"- run_stage1_pdf_to_markdown: {', '.join(next_stage1[:10]) or 'none'}")
        lines.append(f"- inspect_markdown: {', '.join(inspect_list[:10]) or 'none'}")
        lines.append(f"- run_stage3_next: {', '.join(run_stage3[:10]) or 'none'}")
        lines.append("")
    lines.extend(
        [
            "## Recommended Stage1 Smoke 10",
            *smoke_lines,
        ]
    )
    return "\n".join(lines).strip() + "\n"


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


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> None:
    args = parse_args()
    result = build_source_manifest(
        pdf_dir=args.pdf_dir,
        markdown_dir=args.markdown_dir,
        outputs_dir=args.outputs_dir,
        out_dir=args.out_dir,
        min_markdown_chars=args.min_markdown_chars,
    )
    print(json.dumps({"summary": result["summary"], "csv_path": result["csv_path"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
