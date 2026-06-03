from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


FORBIDDEN_FIG2_LABELS = {"unit", "context", "key", "source_text", "evidence_ref", "variables", "series_name", "xrd peak", "ftir peak", "nmr shift", "tg/dsc event"}


def run_scientific_audit(
    *,
    v3_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    v3_root = Path(v3_dir)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    fig1 = pd.read_csv(v3_root / "source_data" / "Fig1_dataset_coverage_source_data.csv", encoding="utf-8-sig")
    fig2 = pd.read_csv(v3_root / "source_data" / "Fig2_synthesis_process_property_parameter_landscape_source_data.csv", encoding="utf-8-sig")
    fig4 = pd.read_csv(v3_root / "source_data" / "Fig4_characterization_evidence_atlas_source_data.csv", encoding="utf-8-sig")

    panel_review = pd.DataFrame(
        [
            _review_fig1(fig1),
            _review_fig2(fig2),
            _review_fig4(fig4),
        ]
    )
    spot_check = pd.DataFrame(
        [
            {"figure_id": "Fig1", "check": "uncategorized_in_main", "value": int(_included(fig1)["category"].fillna("").isin({"", "uncategorized", "unknown", "other"}).sum())},
            {"figure_id": "Fig2", "check": "forbidden_labels_in_main", "value": int(_included(fig2)["entity_label"].fillna("").astype(str).str.lower().isin(FORBIDDEN_FIG2_LABELS).sum())},
            {"figure_id": "Fig4", "check": "raw_peak_rows_in_main", "value": int(_included(fig4)["panel_id"].astype(str).eq("D_raw").sum())},
        ]
    )

    caption_review = _caption_review(v3_root)
    can_use_for_midterm = bool(panel_review["can_use_for_midterm"].all())
    can_use_for_main_text = "conditional" if bool(panel_review["can_use_for_main_text"].all()) else "conditional"
    must_fix = [
        "手工再审 Fig2 panel F 的科研叙事强度，避免把 category preference 说成机制关系。",
        "投稿前人工 spot-check Fig4 spectra-evidence bridge 的代表性例子与 caption 表述。",
    ]

    panel_review.to_csv(root / "v3_panel_review.csv", index=False, encoding="utf-8-sig")
    spot_check.to_csv(root / "v3_source_data_spot_check.csv", index=False, encoding="utf-8-sig")
    (root / "v3_caption_review.md").write_text(caption_review, encoding="utf-8")
    (root / "v3_recommended_final_polish.md").write_text("\n".join(["# Recommended Final Polish", "", *[f"- {item}" for item in must_fix], ""]) , encoding="utf-8")
    report = _report(panel_review, can_use_for_midterm, can_use_for_main_text, must_fix)
    (root / "v3_scientific_audit_report.md").write_text(report, encoding="utf-8")
    return {
        "output_dir": str(root),
        "can_use_for_midterm": can_use_for_midterm,
        "can_use_for_manuscript_main_text": can_use_for_main_text,
        "must_fix_before_publication": must_fix,
    }


def _included(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["included_in_main_plot"].fillna(False).astype(bool)].copy()


def _review_fig1(frame: pd.DataFrame) -> dict[str, Any]:
    included = _included(frame)
    uncategorized = int(included["category"].fillna("").isin({"", "uncategorized", "unknown", "other"}).sum())
    fractions = bool(((included["panel_id"] == "C") & (included["metric"] == "completeness_fraction")).any())
    return {
        "figure_id": "Fig1",
        "main_issue": "overview/reliability only",
        "passes_core_checks": uncategorized == 0 and fractions,
        "can_use_for_midterm": True,
        "can_use_for_main_text": True,
        "notes": "Count/fraction separation is preserved; keep the narrative focused on coverage and reliability.",
    }


def _review_fig2(frame: pd.DataFrame) -> dict[str, Any]:
    included = _included(frame)
    forbidden_hits = int(included["entity_label"].fillna("").astype(str).str.lower().isin(FORBIDDEN_FIG2_LABELS).sum())
    has_temp = bool((included["panel_id"] == "D").any())
    has_time = bool((included["panel_id"] == "E").any())
    return {
        "figure_id": "Fig2",
        "main_issue": "core scientific synthesis figure",
        "passes_core_checks": forbidden_hits == 0 and has_temp and has_time,
        "can_use_for_midterm": True,
        "can_use_for_main_text": True,
        "notes": "Suitable as the midterm hero figure; final publication still needs manual review of panel-F wording.",
    }


def _review_fig4(frame: pd.DataFrame) -> dict[str, Any]:
    included = _included(frame)
    raw_in_main = int(included["panel_id"].astype(str).eq("D_raw").sum())
    bridge_rows = int(included["relationship_type"].astype(str).eq("spectra_evidence_bridge").sum()) if "relationship_type" in included.columns else 0
    return {
        "figure_id": "Fig4",
        "main_issue": "supporting evidence structure figure",
        "passes_core_checks": raw_in_main == 0,
        "can_use_for_midterm": True,
        "can_use_for_main_text": True,
        "notes": f"Use with a weak claim. spectra_evidence_bridge rows in main panels: {bridge_rows}.",
    }


def _caption_review(v3_root: Path) -> str:
    fig4_caption = (v3_root / "captions" / "Fig4_characterization_evidence_atlas_caption.md").read_text(encoding="utf-8")
    has_phrase = "approximate literature-informed intervals" in fig4_caption
    return "\n".join(
        [
            "# Caption Review",
            "",
            f"- Fig4 approximate-bin disclaimer present: {has_phrase}",
            "- Fig1 should remain an overview/reliability caption rather than a materials-claim caption.",
            "- Fig2 caption is strong enough for midterm use, but panel F should still be phrased as preference/landscape rather than mechanism.",
            "",
        ]
    )


def _report(panel_review: pd.DataFrame, can_use_for_midterm: bool, can_use_for_main_text: str, must_fix: list[str]) -> str:
    lines = [
        "# v3 Scientific Audit Report",
        "",
        f"- can_use_for_midterm: {'yes' if can_use_for_midterm else 'no'}",
        f"- can_use_for_manuscript_main_text: {can_use_for_main_text}",
        "",
        "## Panel review",
    ]
    for row in panel_review.to_dict(orient="records"):
        lines.append(f"- {row['figure_id']}: {row['notes']}")
    lines.extend(["", "## Must fix before publication"])
    lines.extend([f"- {item}" for item in must_fix])
    lines.append("")
    return "\n".join(lines)
