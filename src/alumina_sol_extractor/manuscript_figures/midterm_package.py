from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd


def build_midterm_package(
    *,
    v3_dir: Path,
    semantic_export_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    root = Path(output_dir)
    figures_root = root / "figures"
    figures_root.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((Path(v3_dir) / "manuscript_figures_manifest.json").read_text(encoding="utf-8"))
    index_rows: list[dict[str, Any]] = []

    workflow_paths = _build_workflow_figure(figures_root / "Figure1_workflow")
    index_rows.extend(_index_rows("Figure 1", "Overall extraction and analysis workflow", workflow_paths))

    figure_order = [
        ("Figure 2", "Fig1", "Dataset coverage and extraction reliability"),
        ("Figure 3", "Fig2", "Synthesis-process-property parameter landscape"),
        ("Figure 4", "Fig4", "Characterization evidence atlas"),
    ]
    copied_pngs: list[Path] = []
    figure_lookup = {row["figure_id"]: row for row in manifest.get("figures", [])}
    for display_id, figure_id, title in figure_order:
        row = figure_lookup[figure_id]
        copied = _copy_bundle(row, figures_root / f"{display_id.replace(' ', '_')}_{figure_id}")
        copied_pngs.append(Path(copied["png"]))
        index_rows.extend(_index_rows(display_id, title, copied))

    case_study_paths, case_meta = _build_case_study_figure(
        semantic_export_dir=semantic_export_dir,
        output_prefix=figures_root / "Figure5_case_study",
    )
    copied_pngs.append(Path(case_study_paths["png"]))
    index_rows.extend(_index_rows("Figure 5", "Representative paper-level case study", case_study_paths, extra=case_meta))

    index_frame = pd.DataFrame(index_rows)
    index_frame.to_csv(root / "midterm_figure_index.csv", index=False, encoding="utf-8-sig")
    contact_sheet = _build_contact_sheet(copied_pngs, root / "midterm_contact_sheet.png")
    (root / "midterm_figures_readme.md").write_text(_build_readme(index_frame, contact_sheet), encoding="utf-8")
    (root / "suggested_slide_order.md").write_text(_slide_order_text(case_meta), encoding="utf-8")
    (root / "midterm_claims_and_talking_points.md").write_text(_talking_points(case_meta), encoding="utf-8")
    (root / "limitations_and_next_steps.md").write_text(_limitations_text(), encoding="utf-8")
    return {
        "output_dir": str(root),
        "contact_sheet": str(contact_sheet),
        "case_study_paper_id": case_meta["paper_id"],
    }


def _index_rows(display_id: str, title: str, bundle: dict[str, str], *, extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    extra = extra or {}
    return [
        {"display_id": display_id, "title": title, "format": fmt.upper(), "path": path, **extra}
        for fmt, path in bundle.items()
    ]


def _copy_bundle(record: dict[str, Any], output_prefix: Path) -> dict[str, str]:
    result = {}
    for fmt_key, ext in [("output_png", "png"), ("output_svg", "svg"), ("output_pdf", "pdf")]:
        src = Path(record[fmt_key])
        dst = output_prefix.with_suffix(f".{ext}")
        shutil.copy2(src, dst)
        result[ext] = str(dst)
    return result


def _build_workflow_figure(output_prefix: Path) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.axis("off")
    labels = [
        "PDF / Markdown",
        "Stage3 text extraction",
        "Stage4 figure / spectra extraction",
        "Stage5 fusion / linking",
        "semantic export",
        "manuscript figures",
    ]
    xs = [0.05, 0.23, 0.43, 0.63, 0.80, 0.93]
    for x, label in zip(xs, labels):
        ax.text(
            x,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=10,
            bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#2f4f4f", "linewidth": 1.2},
            transform=ax.transAxes,
        )
    for start, end in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(end - 0.06, 0.55), xytext=(start + 0.06, 0.55), arrowprops={"arrowstyle": "->", "lw": 1.2, "color": "#2f4f4f"}, xycoords=ax.transAxes)
    fig.tight_layout()
    paths = {}
    for ext in ("png", "svg", "pdf"):
        out = output_prefix.with_suffix(f".{ext}")
        dpi = 600 if ext == "png" else None
        fig.savefig(out, dpi=dpi, bbox_inches="tight")
        paths[ext] = str(out)
    plt.close(fig)
    return paths


def _build_case_study_figure(*, semantic_export_dir: Path, output_prefix: Path) -> tuple[dict[str, str], dict[str, Any]]:
    final_params = pd.read_csv(Path(semantic_export_dir) / "all_papers_final_parameters_linked.csv", encoding="utf-8-sig")
    evidence_links = pd.read_csv(Path(semantic_export_dir) / "all_papers_evidence_parameter_links.csv", encoding="utf-8-sig")
    spectra_links = pd.read_csv(Path(semantic_export_dir) / "all_papers_spectra_parameter_links.csv", encoding="utf-8-sig")
    official = final_params[final_params["paper_category_status"].astype(str) == "official"].copy()
    scores = (
        official.groupby(["paper_id", "paper_category"])
        .agg(parameter_count=("parameter_id", "count"), sample_count=("resolved_sample_id", "nunique"))
        .reset_index()
    )
    evidence_counts = evidence_links.groupby("paper_id").size().reset_index(name="evidence_link_count")
    spectra_counts = spectra_links.groupby("paper_id").size().reset_index(name="spectra_link_count")
    scores = scores.merge(evidence_counts, on="paper_id", how="left").merge(spectra_counts, on="paper_id", how="left").fillna(0)
    scores["score"] = scores["parameter_count"] + 2 * scores["evidence_link_count"] + 3 * scores["spectra_link_count"]
    scores = scores.sort_values(["score", "parameter_count"], ascending=False)
    best = scores.iloc[0]
    paper_id = str(best["paper_id"])
    subset = official[official["paper_id"].astype(str) == paper_id].copy()
    family_counts = subset.groupby("local_category").size().reset_index(name="count").sort_values("count", ascending=False).head(8)
    display_paper = paper_id.encode("ascii", "ignore").decode().strip() or f"{best['paper_category']} case study"

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].bar(
        ["parameters", "samples", "evidence links", "spectra links"],
        [int(best["parameter_count"]), int(best["sample_count"]), int(best["evidence_link_count"]), int(best["spectra_link_count"])],
        color=["#486581", "#7b9e89", "#d17b49", "#8b5c7e"],
    )
    axes[0].set_title("Case-study coverage")
    axes[0].tick_params(axis="x", rotation=20)
    axes[1].barh(family_counts["local_category"].fillna("other"), family_counts["count"], color="#486581")
    axes[1].invert_yaxis()
    axes[1].set_title("Top parameter families")
    fig.suptitle(f"Representative case study: {display_paper}", fontsize=11)
    fig.tight_layout()

    paths = {}
    for ext in ("png", "svg", "pdf"):
        out = output_prefix.with_suffix(f".{ext}")
        dpi = 600 if ext == "png" else None
        fig.savefig(out, dpi=dpi, bbox_inches="tight")
        paths[ext] = str(out)
    plt.close(fig)
    return paths, {
        "paper_id": paper_id,
        "paper_category": str(best["paper_category"]),
        "parameter_count": int(best["parameter_count"]),
        "sample_count": int(best["sample_count"]),
        "evidence_link_count": int(best["evidence_link_count"]),
        "spectra_link_count": int(best["spectra_link_count"]),
    }


def _build_contact_sheet(png_paths: list[Path], output_path: Path) -> Path:
    cols = 2
    rows = max(1, (len(png_paths) + cols - 1) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 3.8))
    axes_list = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax, path in zip(axes_list, png_paths):
        ax.axis("off")
        ax.imshow(mpimg.imread(path))
        ax.set_title(path.stem, fontsize=8)
    for ax in axes_list[len(png_paths):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _build_readme(index_frame: pd.DataFrame, contact_sheet: Path) -> str:
    lines = ["# Midterm Figure Package", "", "## Figures"]
    for display_id in index_frame["display_id"].drop_duplicates().tolist():
        lines.append(f"- {display_id}")
    lines.extend(["", "## Contact sheet", f"- {contact_sheet}"])
    return "\n".join(lines) + "\n"


def _slide_order_text(case_meta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Suggested Slide Order",
            "",
            "1. Workflow and project scope",
            "2. Dataset coverage and extraction reliability",
            "3. Synthesis-process-property parameter landscape",
            "4. Characterization evidence atlas",
            f"5. Representative case study: {case_meta['paper_id']}",
            "6. Limitations and next steps",
            "",
        ]
    )


def _talking_points(case_meta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Midterm Claims And Talking Points",
            "",
            "- 已完成 Stage3、Stage4、Stage5 的批量抽取与 link-aware export。",
            "- 当前主数据库覆盖 343 篇 official papers，并已完成 semantic v1.1 语义修补。",
            "- metadata-like 参数和 category semantics 污染已从主参数景观中剥离。",
            "- Fig2 现在可以作为中期汇报的核心图，展示铝溶胶文献中的 synthesis-process-property 参数空间。",
            "- Fig4 更适合作为 evidence/supporting figure，用于说明表征证据结构，而不是直接做强材料机理结论。",
            f"- 代表性个案当前选中 {case_meta['paper_id']}，它具有较完整的参数、evidence 和 spectra 结构。",
            "- 下一步重点是人工审查单位归一化、targeted Stage3 修补，以及更强的材料学解释。",
            "",
        ]
    )


def _limitations_text() -> str:
    return "\n".join(
        [
            "# Limitations And Next Steps",
            "",
            "- Fig1 仍然是 overview/reliability figure，不直接提供材料机理结论。",
            "- Fig2 已经具备主文候选价值，但仍需要人工再审一次 parameter family 命名和 panel F 的叙事强度。",
            "- Fig4 的 peak/event bins 是 evidence summarization，不是 definitive assignment。",
            "- 后续优先事项是 unit normalization spot check、少量 targeted Stage3 repair，以及对最终投稿版 caption 的手工收紧。",
            "",
        ]
    )
