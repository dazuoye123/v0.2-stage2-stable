"""Audit Stage 2 figure classification quality from existing outputs.

This script is read-only with respect to Stage 2 outputs: it scans existing
``figures.jsonl`` and ``figure_stage2_summary.json`` files under category-aware
``data/outputs/<category>/<paper_id>/`` directories and writes aggregate audit
reports under ``data/batch_validation_reports``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CATEGORIES = {"applications", "fiber_process", "mechanism", "rheology", "uncategorized"}

MICROSCOPY_KEYWORDS = [
    "sem",
    "tem",
    "hrtem",
    "显微",
    "形貌",
    "微观结构",
    "微结构",
    "截面",
    "断面",
    "断裂面",
    "晶粒",
    "纤维内部",
    "表面结构",
    "孔洞",
    "孔隙",
    "致密",
    "烧结颈",
    "morphology",
    "micrograph",
    "microscopy",
]
MICROSCOPY_MATERIAL_KEYWORDS = [
    "纤维",
    "陶瓷",
    "氧化铝",
    "凝胶",
    "溶胶",
    "粉体",
    "煅烧",
    "烧结",
    "热处理",
    "fiber",
    "fibre",
    "ceramic",
    "grain",
]
XRD_KEYWORDS = ["xrd", "衍射", "物相", "diffraction"]
FTIR_KEYWORDS = ["ftir", "红外", "infrared", "cm-1", "cm−1", "ir spectrum"]
THERMAL_KEYWORDS = ["tg", "tga", "dsc", "dta", "热重", "差热", "失重", "mass loss", "weight loss"]
MECHANICAL_KEYWORDS = [
    "力学性能",
    "拉伸强度",
    "应力-应变",
    "应力应变",
    "断裂强度",
    "伸长率",
    "mechanical property",
    "tensile strength",
    "stress-strain",
    "stress strain",
    "modulus",
]
FORMULA_KEYWORDS = [
    "化学式",
    "分子式",
    "结构式",
    "结构简式",
    "反应式",
    "方程式",
    "分子结构",
    "化学结构",
    "chemical formula",
    "molecular formula",
    "structural formula",
    "chemical structure",
    "reaction equation",
]
STRONG_SCIENCE_KEYWORDS = (
    MICROSCOPY_KEYWORDS
    + XRD_KEYWORDS
    + FTIR_KEYWORDS
    + THERMAL_KEYWORDS
    + MECHANICAL_KEYWORDS
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit existing Stage 2 outputs.")
    parser.add_argument(
        "--outputs-dir",
        default="data/outputs",
        help="Category-aware Stage 2 outputs root",
    )
    parser.add_argument(
        "--report-dir",
        default="data/batch_validation_reports",
        help="Directory for audit reports",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def has_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def figure_text_blob(figure: dict) -> str:
    refs = figure.get("reference_sentences") or []
    refs_text = " ".join(str(item) for item in refs) if isinstance(refs, list) else str(refs)
    parts = [
        figure.get("caption") or "",
        figure.get("raw_caption") or "",
        figure.get("description_text") or "",
        refs_text,
        figure.get("context_before") or "",
        figure.get("context_after") or "",
        figure.get("alt_text") or "",
    ]
    return " ".join(parts).lower()


def summarize_one_paper(category: str, paper_dir: Path) -> tuple[dict, list[dict]]:
    figures_path = paper_dir / "figures.jsonl"
    summary_path = paper_dir / "figure_stage2_summary.json"
    figures = load_jsonl(figures_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    caption_counts = Counter((figure.get("caption_source") or "none") for figure in figures)
    class_counts = Counter((figure.get("figure_class") or "other") for figure in figures)
    total = len(figures)
    send_count = sum(1 for figure in figures if figure.get("send_to_vision_model"))
    review_count = summary.get("review_candidate_count") or sum(1 for figure in figures if figure.get("review_reason"))
    false_count = summary.get("false_candidate_count") or sum(
        1
        for figure in figures
        if figure.get("exclude_reason")
        and str(figure.get("exclude_reason")).startswith(
            ("logo", "formula", "pure_text", "qr", "cover", "table", "unknown", "clip_negative", "not_selected")
        )
    )

    paper_row = {
        "category": category,
        "paper_id": paper_dir.name,
        "total_figures": total,
        "standard_caption_count": caption_counts.get("standard_caption", 0),
        "pseudo_caption_count": caption_counts.get("pseudo_caption", 0),
        "caption_none_count": caption_counts.get("none", 0),
        "standard_caption_ratio": round(caption_counts.get("standard_caption", 0) / total, 4) if total else 0.0,
        "send_to_vision_model_count": send_count,
        "send_to_vision_model_ratio": round(send_count / total, 4) if total else 0.0,
        "other_count": class_counts.get("other", 0),
        "generic_chart_or_plot_count": class_counts.get("generic_chart_or_plot", 0),
        "photo_image_count": class_counts.get("photo_image", 0),
        "microscopy_image_count": class_counts.get("microscopy_image", 0),
        "xrd_pattern_count": class_counts.get("xrd_pattern", 0),
        "ftir_spectrum_count": class_counts.get("ftir_spectrum", 0),
        "thermal_analysis_plot_count": class_counts.get("thermal_analysis_plot", 0),
        "mechanical_property_plot_count": class_counts.get("mechanical_property_plot", 0),
        "formula_or_text_count": class_counts.get("formula_or_text", 0),
        "review_candidate_count": review_count,
        "false_candidate_count": false_count,
    }

    issues: list[dict] = []
    for index, figure in enumerate(figures, start=1):
        blob = figure_text_blob(figure)
        figure_class = figure.get("figure_class") or "other"
        send_to_vision = bool(figure.get("send_to_vision_model"))
        caption_source = figure.get("caption_source") or "none"
        subfigure_label = str(figure.get("subfigure_label") or "")
        issue_types: list[str] = []

        if has_any(blob, MICROSCOPY_KEYWORDS) and has_any(blob, MICROSCOPY_MATERIAL_KEYWORDS) and figure_class != "microscopy_image":
            issue_types.append("microscopy_false_negative")
        if has_any(blob, XRD_KEYWORDS) and figure_class != "xrd_pattern":
            issue_types.append("xrd_false_negative")
        if has_any(blob, FTIR_KEYWORDS) and figure_class != "ftir_spectrum":
            issue_types.append("ftir_false_negative")
        if has_any(blob, THERMAL_KEYWORDS) and figure_class != "thermal_analysis_plot":
            issue_types.append("thermal_false_negative")
        if has_any(blob, MECHANICAL_KEYWORDS) and figure_class != "mechanical_property_plot":
            issue_types.append("mechanical_false_negative")
        if has_any(blob, FORMULA_KEYWORDS) and send_to_vision and not has_any(blob, STRONG_SCIENCE_KEYWORDS) and figure_class != "schematic_or_flow":
            issue_types.append("formula_false_positive_to_vision")
        if any(tag in subfigure_label.lower() for tag in ["<details>", "<summary>", "</details>", "</summary>", "<div", "<p>"]):
            issue_types.append("html_subfigure_label")
        if caption_source == "mineru_layout_caption":
            issue_types.append("forbidden_mineru_layout_caption")
        if figure_class == "other" and has_any(blob, STRONG_SCIENCE_KEYWORDS):
            issue_types.append("other_with_science_keywords")
        if issue_types:
            issues.append(
                {
                    "category": category,
                    "paper_id": paper_dir.name,
                    "figure_index": index,
                    "figure_id": figure.get("figure_id"),
                    "subfigure_label": figure.get("subfigure_label"),
                    "caption_source": caption_source,
                    "figure_class": figure_class,
                    "send_to_vision_model": send_to_vision,
                    "exclude_reason": figure.get("exclude_reason"),
                    "clip_label": figure.get("clip_label") or "",
                    "resnet_top_class": figure.get("resnet_raw_class") or "",
                    "issue_types": ";".join(issue_types),
                    "caption_preview": (figure.get("caption") or "")[:120],
                }
            )

    return paper_row, issues


def write_reports(report_dir: Path, paper_rows: list[dict], issues: list[dict]) -> None:
    issue_counts = Counter()
    category_issue_counts: dict[str, Counter] = defaultdict(Counter)
    paper_issue_counts = Counter()

    for issue in issues:
        issue_type_list = [item for item in issue["issue_types"].split(";") if item]
        for issue_type in issue_type_list:
            issue_counts[issue_type] += 1
            category_issue_counts[issue["category"]][issue_type] += 1
        paper_issue_counts[(issue["category"], issue["paper_id"])] += len(issue_type_list)

    for row in paper_rows:
        row["suspicious_issue_count"] = paper_issue_counts[(row["category"], row["paper_id"])]

    paper_rows.sort(
        key=lambda row: (
            -row["suspicious_issue_count"],
            -row["other_count"],
            -row["generic_chart_or_plot_count"],
            -row["photo_image_count"],
        )
    )
    issues.sort(key=lambda row: (len(row["issue_types"].split(";")), row["category"], row["paper_id"]), reverse=True)

    csv_path = report_dir / "stage2_quality_audit.csv"
    summary_path = report_dir / "stage2_quality_audit_summary.json"
    md_path = report_dir / "stage2_quality_audit.md"

    fieldnames = list(paper_rows[0].keys()) if paper_rows else ["category", "paper_id"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(paper_rows)

    summary = {
        "paper_count": len(paper_rows),
        "issue_figure_count": len(issues),
        "issue_type_counts": dict(issue_counts.most_common()),
        "top_error_types": [issue_type for issue_type, _ in issue_counts.most_common(3)],
        "top_30_papers": paper_rows[:30],
        "top_100_figures": issues[:100],
        "by_category": {category: dict(counts) for category, counts in category_issue_counts.items()},
        "report_csv_path": str(csv_path),
        "report_md_path": str(md_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Stage 2 Quality Audit")
    lines.append("")
    lines.append(f"- scanned papers: {len(paper_rows)}")
    lines.append(f"- suspicious figures: {len(issues)}")
    lines.append("")
    lines.append("## Top error types")
    lines.append("")
    lines.append("| error_type | count |")
    lines.append("|---|---:|")
    for issue_type, count in issue_counts.most_common():
        lines.append(f"| {issue_type} | {count} |")
    lines.append("")
    lines.append("## Suspicious papers Top 30")
    lines.append("")
    lines.append("| category | paper_id | total_figures | suspicious_issue_count | standard_caption_count | pseudo_caption_count | other_count | generic_chart_or_plot_count | photo_image_count | microscopy_image_count | xrd_pattern_count | thermal_analysis_plot_count | mechanical_property_plot_count |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in paper_rows[:30]:
        lines.append(
            f"| {row['category']} | {row['paper_id']} | {row['total_figures']} | {row['suspicious_issue_count']} | "
            f"{row['standard_caption_count']} | {row['pseudo_caption_count']} | {row['other_count']} | "
            f"{row['generic_chart_or_plot_count']} | {row['photo_image_count']} | {row['microscopy_image_count']} | "
            f"{row['xrd_pattern_count']} | {row['thermal_analysis_plot_count']} | {row['mechanical_property_plot_count']} |"
        )
    lines.append("")
    lines.append("## Suspicious figures Top 100")
    lines.append("")
    lines.append("| category | paper_id | idx | figure_id | class | vision | issues | clip | resnet | caption |")
    lines.append("|---|---|---:|---|---|---|---|---|---|---|")
    for row in issues[:100]:
        caption = (row["caption_preview"] or "").replace("|", "/").replace("\n", " ")[:80]
        clip = (row["clip_label"] or "").replace("|", "/")[:30]
        resnet = (row["resnet_top_class"] or "").replace("|", "/")[:30]
        lines.append(
            f"| {row['category']} | {row['paper_id']} | {row['figure_index']} | {row['figure_id']} | "
            f"{row['figure_class']} | {row['send_to_vision_model']} | {row['issue_types']} | {clip} | {resnet} | {caption} |"
        )
    lines.append("")
    lines.append("## Most worth fixing first")
    lines.append("")
    for index, (issue_type, count) in enumerate(issue_counts.most_common(3), start=1):
        lines.append(f"{index}. `{issue_type}`: {count}")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    outputs_dir = Path(args.outputs_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    paper_rows: list[dict] = []
    issues: list[dict] = []

    for category_dir in outputs_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name not in CATEGORIES:
            continue
        for paper_dir in category_dir.iterdir():
            if not paper_dir.is_dir():
                continue
            figures_path = paper_dir / "figures.jsonl"
            if not figures_path.exists():
                continue
            paper_row, paper_issues = summarize_one_paper(category_dir.name, paper_dir)
            paper_rows.append(paper_row)
            issues.extend(paper_issues)

    write_reports(report_dir, paper_rows, issues)
    print(
        json.dumps(
            {
                "paper_count": len(paper_rows),
                "issue_figure_count": len(issues),
                "report_dir": str(report_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
