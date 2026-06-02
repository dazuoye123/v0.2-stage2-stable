from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd

from .io import ensure_dir, read_csv, read_json, write_frame, write_json, write_markdown
from .plot_style import configure_plot_style


FALLBACK_EMPTY_FIGURES = {
    "qa_fig21_unlinked_parameters_qa",
    "qa_fig22_unknown_spectra_type_examples",
    "stage5_fig9_unlinked_parameter_distribution",
}

MAIN_CANDIDATE_IDS = [
    "main_fig2_parameter_landscape",
    "main_fig3_spectroscopic_fingerprint_atlas",
    "main_fig4_synthesis_process_atlas",
    "main_fig5_linked_evidence_map",
    "main_fig8_process_spectra_parameter_relationship",
    "cross_fig7_parameter_family_vs_characterization_family",
    "stage3_fig12_sample_parameter_matrix_top",
    "main_fig9_knowledge_graph_overview",
]

SUPPLEMENTARY_PRIORITY_IDS = [
    "main_fig1_dataset_overview",
    "main_fig6_category_research_patterns",
    "main_fig7_stage4_characterization_coverage",
    "cross_fig1_stage3_stage4_coverage",
    "cross_fig2_stage4_success_vs_parameter_count",
    "cross_fig4_category_integrated_coverage",
    "cross_fig8_process_step_vs_spectra_type",
    "cross_fig10_stage4_characterization_vs_stage5_spectra_links",
    "stage3_fig3_parameter_family_by_category",
    "stage3_fig5_temperature_distributions",
    "stage3_fig6_time_distributions",
    "stage3_fig8_concentration_solid_content",
    "stage3_fig10_parameter_cooccurrence_matrix",
    "stage3_fig15_process_step_by_category",
    "stage3_fig17_numeric_value_availability_by_family",
    "stage4_fig1_extraction_overview",
    "stage4_fig5_full_figure_class_distribution",
    "stage4_fig6_characterization_family_distribution",
    "stage4_fig7_spectra_type_by_category",
    "stage4_fig18_peak_value_availability",
    "stage4_fig20_characterization_coverage_by_category",
    "stage5_fig2_link_family_by_category",
    "stage5_fig6_spectra_type_parameter_matrix",
    "stage5_fig7_process_step_parameter_matrix",
    "stage5_fig8_sample_matrix_coverage",
    "stage5_fig14_link_completeness_heatmap",
    "stage5_fig15_top_linked_parameter_families",
]

NEEDS_REDRAW_IDS = {
    "main_fig10_research_atlas_summary",
    "stage3_fig11_parameter_cooccurrence_network",
    "stage4_fig8_ftir_peak_distribution",
    "stage4_fig9_xrd_peak_distribution",
    "stage4_fig10_nmr_shift_distribution",
    "stage4_fig12_thermal_event_distribution",
    "stage4_fig14_ferron_distribution",
    "stage4_fig15_unknown_other_breakdown",
    "stage4_fig17_validation_error_summary",
    "cross_fig6_research_pattern_cluster_preview",
}

DISCARD_IDS = FALLBACK_EMPTY_FIGURES.copy()


@dataclass
class FigureReview:
    figure_id: str
    tier: str
    title: str
    original_png: str
    original_svg: str
    source_csv: str
    source_json: str
    row_count: int
    column_count: int
    scientific_value: int
    data_density: int
    interpretability: int
    publication_potential: int
    uniqueness: int
    reliability: int
    total_score: int
    recommendation: str
    suggested_manuscript_role: str
    reason: str
    redraw_or_polish_notes: str


def run_figure_atlas_shortlist(*, atlas_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    atlas_root = Path(atlas_dir)
    shortlist_root = ensure_dir(output_dir or atlas_root.parent / "figure_atlas_shortlist")
    category_dirs = {
        "main_candidate": ensure_dir(shortlist_root / "main_candidates"),
        "supplementary_candidate": ensure_dir(shortlist_root / "supplementary_candidates"),
        "qa_only": ensure_dir(shortlist_root / "qa_only"),
        "needs_redraw": ensure_dir(shortlist_root / "needs_redraw"),
        "discard_or_low_value": ensure_dir(shortlist_root / "discard_or_low_value"),
    }
    contact_dir = ensure_dir(shortlist_root / "contact_sheets")

    index = read_csv(atlas_root / "figure_index.csv")
    manifest = read_json(atlas_root / "figure_atlas_manifest.json", default={}) or {}
    _validate_index(index)

    reviews = [_review_row(row) for _, row in index.iterrows()]
    review_frame = pd.DataFrame([review.__dict__ for review in reviews]).sort_values(
        ["recommendation", "total_score", "tier", "figure_id"],
        ascending=[True, False, True, True],
    )
    write_frame(shortlist_root / "shortlist_table.csv", review_frame)

    copied_files: list[str] = []
    for review in reviews:
        copied_files.extend(_copy_review_assets(review, category_dirs[review.recommendation]))

    contact_sheets = {}
    for recommendation, stem in [
        ("main_candidate", "main_candidates_contact_sheet.png"),
        ("supplementary_candidate", "supplementary_candidates_contact_sheet.png"),
        ("qa_only", "qa_only_contact_sheet.png"),
        ("needs_redraw", "needs_redraw_contact_sheet.png"),
    ]:
        subset = [review for review in reviews if review.recommendation == recommendation]
        path = contact_dir / stem
        _build_contact_sheet(subset, path)
        contact_sheets[recommendation] = str(path)

    report_text = _build_report(reviews, atlas_root=atlas_root, shortlist_root=shortlist_root)
    report_path = write_markdown(shortlist_root / "shortlist_report.md", report_text)

    manifest_payload = _build_manifest(
        reviews=reviews,
        atlas_root=atlas_root,
        shortlist_root=shortlist_root,
        copied_files=copied_files,
        contact_sheets=contact_sheets,
    )
    manifest_path = write_json(shortlist_root / "shortlist_manifest.json", manifest_payload)

    return {
        "input_atlas_dir": str(atlas_root),
        "output_shortlist_dir": str(shortlist_root),
        "shortlist_table": str(shortlist_root / "shortlist_table.csv"),
        "shortlist_manifest": str(manifest_path),
        "shortlist_report": str(report_path),
        "contact_sheets": contact_sheets,
        "source_manifest_counts": manifest.get("counts", {}),
    }


def _validate_index(index: pd.DataFrame) -> None:
    required = {"figure_id", "tier", "title", "png", "svg", "source_csv", "source_json"}
    missing = sorted(required - set(index.columns))
    if missing:
        raise ValueError(f"figure_index.csv is missing required columns: {missing}")


def _review_row(row: pd.Series) -> FigureReview:
    figure_id = str(row["figure_id"])
    tier = str(row["tier"])
    title = str(row["title"])
    source_json = Path(str(row["source_json"]))
    json_payload = read_json(source_json, default={}) or {}
    row_count = int(json_payload.get("row_count") or 0)
    columns = json_payload.get("columns") or []
    column_count = len(columns)
    empty_note = str(json_payload.get("empty_data_note") or row.get("empty_data_note") or "").strip()

    scientific_value = _scientific_value(figure_id, tier)
    data_density = _data_density(row_count)
    interpretability = _interpretability(figure_id, tier, row_count, column_count)
    publication_potential = _publication_potential(figure_id, tier)
    uniqueness = _uniqueness(figure_id, tier)
    reliability = _reliability(figure_id, tier, row_count, empty_note)

    recommendation = _recommendation(
        figure_id=figure_id,
        tier=tier,
        row_count=row_count,
        total_score=scientific_value + data_density + interpretability + publication_potential + uniqueness + reliability,
    )
    if figure_id in FALLBACK_EMPTY_FIGURES:
        recommendation = "discard_or_low_value"
        scientific_value = 1
        data_density = 1
        interpretability = 1
        publication_potential = 1
        uniqueness = 1
        reliability = 2

    total_score = scientific_value + data_density + interpretability + publication_potential + uniqueness + reliability
    suggested_role = _suggested_role(recommendation, figure_id, tier)
    reason = _reason_text(figure_id, tier, row_count, recommendation)
    notes = _polish_notes(figure_id, tier, recommendation)
    return FigureReview(
        figure_id=figure_id,
        tier=tier,
        title=title,
        original_png=str(row["png"]),
        original_svg=str(row["svg"]),
        source_csv=str(row["source_csv"]),
        source_json=str(source_json),
        row_count=row_count,
        column_count=column_count,
        scientific_value=scientific_value,
        data_density=data_density,
        interpretability=interpretability,
        publication_potential=publication_potential,
        uniqueness=uniqueness,
        reliability=reliability,
        total_score=total_score,
        recommendation=recommendation,
        suggested_manuscript_role=suggested_role,
        reason=reason,
        redraw_or_polish_notes=notes,
    )


def _scientific_value(figure_id: str, tier: str) -> int:
    if figure_id in MAIN_CANDIDATE_IDS:
        return 5
    if tier in {"main", "cross_stage"}:
        return 5
    if tier in {"stage3", "stage4", "stage5"}:
        return 4
    if tier == "qa":
        return 2
    return 1


def _data_density(row_count: int) -> int:
    if row_count <= 0:
        return 1
    if row_count <= 4:
        return 2
    if row_count <= 24:
        return 3
    if row_count <= 199:
        return 4
    return 5


def _interpretability(figure_id: str, tier: str, row_count: int, column_count: int) -> int:
    score = {
        "main": 4,
        "cross_stage": 4,
        "stage3": 4,
        "stage4": 3,
        "stage5": 4,
        "qa": 3,
        "auto": 2,
    }.get(tier, 3)
    if "distribution" in figure_id and tier == "stage4":
        score -= 1
    if "network" in figure_id:
        score -= 1
    if row_count <= 4:
        score -= 1
    if column_count >= 20:
        score -= 1
    return max(1, min(5, score))


def _publication_potential(figure_id: str, tier: str) -> int:
    if figure_id in MAIN_CANDIDATE_IDS:
        return 5
    if figure_id in SUPPLEMENTARY_PRIORITY_IDS:
        return 4
    if figure_id in NEEDS_REDRAW_IDS:
        return 2
    if tier in {"main", "cross_stage"}:
        return 4
    if tier in {"stage3", "stage4", "stage5"}:
        return 3
    if tier == "qa":
        return 2
    return 1


def _uniqueness(figure_id: str, tier: str) -> int:
    if figure_id in MAIN_CANDIDATE_IDS:
        return 5
    if tier == "cross_stage":
        return 5
    if tier == "main":
        return 4
    if tier in {"stage3", "stage4", "stage5"}:
        return 3
    if tier == "qa":
        return 2
    return 1


def _reliability(figure_id: str, tier: str, row_count: int, empty_note: str) -> int:
    score = 4 if tier != "qa" else 5
    if not row_count:
        score = 2
    if empty_note:
        score -= 1
    if "unknown" in figure_id or "other_breakdown" in figure_id:
        score -= 1
    if "distribution" in figure_id and tier == "stage4":
        score -= 1
    return max(1, min(5, score))


def _recommendation(*, figure_id: str, tier: str, row_count: int, total_score: int) -> str:
    if figure_id in DISCARD_IDS or row_count <= 0:
        return "discard_or_low_value"
    if tier == "auto":
        return "discard_or_low_value"
    if figure_id in MAIN_CANDIDATE_IDS:
        return "main_candidate"
    if figure_id in NEEDS_REDRAW_IDS:
        return "needs_redraw"
    if tier == "qa":
        return "qa_only"
    if figure_id in SUPPLEMENTARY_PRIORITY_IDS:
        return "supplementary_candidate"
    if row_count <= 2 and tier in {"stage4", "stage5"}:
        return "needs_redraw"
    if total_score >= 22:
        return "supplementary_candidate"
    return "discard_or_low_value"


def _suggested_role(recommendation: str, figure_id: str, tier: str) -> str:
    if recommendation == "main_candidate":
        if figure_id == "stage3_fig12_sample_parameter_matrix_top":
            return "Main text compact heatmap or extended data panel"
        if figure_id.startswith("cross_fig"):
            return "Main text integration panel"
        return "Main text figure"
    if recommendation == "supplementary_candidate":
        if tier == "stage4":
            return "Supplementary characterization support"
        if tier == "stage5":
            return "Supplementary linkage support"
        return "Supplementary methods or coverage figure"
    if recommendation == "qa_only":
        return "QA or validation supplement"
    if recommendation == "needs_redraw":
        return "Potential supplementary figure after redraw"
    return "Archive or internal reference only"


def _reason_text(figure_id: str, tier: str, row_count: int, recommendation: str) -> str:
    if figure_id in FALLBACK_EMPTY_FIGURES:
        return "Fallback empty figure caused by genuinely empty source data, not a pipeline failure."
    if recommendation == "main_candidate":
        return "Strong scientific narrative value, clear batch-level signal, and good manuscript positioning."
    if recommendation == "supplementary_candidate":
        return "Useful supporting evidence with real source data, but less central than the shortlisted main figures."
    if recommendation == "qa_only":
        return "Best suited for pipeline validation, data quality checks, or supplementary QA context."
    if recommendation == "needs_redraw":
        return "Scientifically relevant, but current composition or data presentation limits publication readiness."
    if tier == "auto":
        return "Auto-generated exploratory view with low uniqueness relative to curated atlas figures."
    if row_count <= 4:
        return "Very limited source rows reduce interpretability and publication value."
    return "Redundant or lower-value relative to stronger atlas figures covering the same story."


def _polish_notes(figure_id: str, tier: str, recommendation: str) -> str:
    if figure_id in FALLBACK_EMPTY_FIGURES:
        return "Keep as empty-data audit evidence only if needed; do not redraw unless new data appear."
    notes: list[str] = []
    if recommendation == "main_candidate":
        notes.append("Tighten labels, reduce 'other' dominance, and align color scale across the main figure set.")
    if recommendation == "supplementary_candidate":
        notes.append("Minor typography cleanup and axis-label shortening are sufficient.")
    if recommendation == "qa_only":
        notes.append("Keep white-background QA style; no publication polish needed unless moved to supplement.")
    if recommendation == "needs_redraw":
        notes.append("Rebuild with unit-aware grouping, better axis scaling, and fewer overloaded categories.")
    if "distribution" in figure_id and tier == "stage4":
        notes.append("Consider log scaling, clipping extreme outliers, or faceting by peak unit.")
    if "network" in figure_id:
        notes.append("Replace with a simpler adjacency heatmap or thresholded node-link diagram.")
    if "knowledge_graph_overview" in figure_id or "research_atlas_summary" in figure_id:
        notes.append("Rebalance the multi-panel layout and fix label crowding before publication use.")
    return " ".join(notes).strip()


def _copy_review_assets(review: FigureReview, destination_dir: Path) -> list[str]:
    copied: list[str] = []
    for original in [review.original_png, review.original_svg]:
        source = Path(original)
        if not source.exists():
            continue
        target = destination_dir / source.name
        shutil.copy2(source, target)
        copied.append(str(target))
    return copied


def _build_contact_sheet(reviews: list[FigureReview], output_path: Path, *, columns: int = 4) -> None:
    configure_plot_style()
    if not reviews:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.axis("off")
        ax.text(0.5, 0.5, "No figures in this group", ha="center", va="center", fontsize=12)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return

    rows = math.ceil(len(reviews) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(columns * 4.0, rows * 3.6))
    axes_list = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for axis, review in zip(axes_list, reviews):
        axis.axis("off")
        image_path = Path(review.original_png)
        if image_path.exists():
            axis.imshow(mpimg.imread(image_path))
        axis.set_title(f"{review.figure_id}\n{review.title}", fontsize=7)
    for axis in axes_list[len(reviews) :]:
        axis.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _build_manifest(
    *,
    reviews: list[FigureReview],
    atlas_root: Path,
    shortlist_root: Path,
    copied_files: list[str],
    contact_sheets: dict[str, str],
) -> dict[str, Any]:
    frame = pd.DataFrame([review.__dict__ for review in reviews])
    recommendation_counts = frame["recommendation"].value_counts().to_dict()
    top_main = (
        frame[frame["recommendation"] == "main_candidate"]
        .sort_values(["total_score", "figure_id"], ascending=[False, True])["figure_id"]
        .tolist()
    )
    generated_files = [
        str(shortlist_root / "shortlist_table.csv"),
        str(shortlist_root / "shortlist_manifest.json"),
        str(shortlist_root / "shortlist_report.md"),
        *contact_sheets.values(),
    ]
    return {
        "input_atlas_dir": str(atlas_root),
        "output_shortlist_dir": str(shortlist_root),
        "total_figures_reviewed": int(len(reviews)),
        "main_candidate_count": int(recommendation_counts.get("main_candidate", 0)),
        "supplementary_candidate_count": int(recommendation_counts.get("supplementary_candidate", 0)),
        "qa_only_count": int(recommendation_counts.get("qa_only", 0)),
        "needs_redraw_count": int(recommendation_counts.get("needs_redraw", 0)),
        "discard_or_low_value_count": int(recommendation_counts.get("discard_or_low_value", 0)),
        "top_main_candidates": top_main[:8],
        "fallback_empty_figures": sorted(FALLBACK_EMPTY_FIGURES),
        "generated_files": generated_files,
        "copied_candidate_assets": copied_files,
    }


def _build_report(reviews: list[FigureReview], *, atlas_root: Path, shortlist_root: Path) -> str:
    frame = pd.DataFrame([review.__dict__ for review in reviews])
    counts = frame["recommendation"].value_counts().to_dict()
    top_main = frame[frame["recommendation"] == "main_candidate"].sort_values(
        ["total_score", "figure_id"], ascending=[False, True]
    )
    supplementary = frame[frame["recommendation"] == "supplementary_candidate"].sort_values(
        ["total_score", "figure_id"], ascending=[False, True]
    )
    qa_only = frame[frame["recommendation"] == "qa_only"].sort_values(
        ["total_score", "figure_id"], ascending=[False, True]
    )
    redraw = frame[frame["recommendation"] == "needs_redraw"].sort_values(
        ["total_score", "figure_id"], ascending=[False, True]
    )
    discard = frame[frame["recommendation"] == "discard_or_low_value"].sort_values(
        ["total_score", "figure_id"], ascending=[False, True]
    )

    lines = [
        "# Figure Atlas Shortlist Review",
        "",
        "## Overall assessment",
        f"- Input atlas: {atlas_root}",
        f"- Output shortlist: {shortlist_root}",
        f"- Reviewed figures: {len(reviews)}",
        f"- Main candidates: {counts.get('main_candidate', 0)}",
        f"- Supplementary candidates: {counts.get('supplementary_candidate', 0)}",
        f"- QA-only: {counts.get('qa_only', 0)}",
        f"- Needs redraw: {counts.get('needs_redraw', 0)}",
        f"- Discard or low value: {counts.get('discard_or_low_value', 0)}",
        "",
        "## Recommended main-text figures",
    ]
    for _, row in top_main.head(8).iterrows():
        lines.append(
            f"- {row['figure_id']}: {row['reason']} Source: `{Path(row['source_csv']).name}` and `{Path(row['source_json']).name}`."
        )
    lines.extend(["", "## Ranked supplementary candidates"])
    for _, row in supplementary.head(20).iterrows():
        lines.append(f"- {row['figure_id']}: {row['reason']}")
    lines.extend(["", "## QA-only figures"])
    for _, row in qa_only.head(20).iterrows():
        lines.append(f"- {row['figure_id']}: {row['reason']}")
    lines.extend(["", "## Needs redraw or major polish"])
    for _, row in redraw.iterrows():
        lines.append(f"- {row['figure_id']}: {row['redraw_or_polish_notes']}")
    lines.extend(["", "## Discard or low-value figures"])
    for _, row in discard.head(25).iterrows():
        lines.append(f"- {row['figure_id']}: {row['reason']}")
    lines.extend(
        [
            "",
            "## Next-round polish priorities",
            "- Tighten the main heatmaps by reducing the dominance of `other` and shortening long tick labels.",
            "- Redraw Stage4 peak histograms with unit-aware facets or clipped/log-scaled axes.",
            "- Simplify the knowledge-graph style overview into a cleaner manuscript-ready layout.",
            "- Keep QA dashboards in supplement only; do not promote them to main text without a story-driven rewrite.",
            "- Use the shortlist contact sheets to assemble a 6-8 figure publication set before final redrawing.",
        ]
    )
    return "\n".join(lines) + "\n"
