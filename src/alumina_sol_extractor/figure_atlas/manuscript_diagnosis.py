from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .io import ensure_dir, read_csv, read_json, write_frame, write_json, write_markdown


ATLAS_TABLES = [
    "normalized_parameters.csv",
    "normalized_process_steps.csv",
    "normalized_stage4_spectra.csv",
    "normalized_stage4_peaks.csv",
    "normalized_stage5_links.csv",
    "normalized_sample_matrix.csv",
    "parameter_family_by_category.csv",
    "spectra_type_by_category.csv",
    "process_step_by_category.csv",
    "spectra_parameter_matrix.csv",
    "process_parameter_matrix.csv",
    "evidence_parameter_matrix.csv",
    "category_summary.csv",
    "stage3_paper_summary.csv",
    "stage4_paper_summary.csv",
]

UNKNOWN_TOKENS = {"unknown", "other", "uncategorized", "missing", "nan", ""}
EXCLUDED_PARAMETER_FAMILIES = {"other", "unknown", "uncategorized"}
EXCLUDED_SPECTRA_TYPES = {"other", "unknown"}
EXCLUDED_PROCESS_FAMILIES = {"other", "unknown", "uncategorized"}

FALLBACK_EMPTY_FIGURES = {
    "qa_fig21_unlinked_parameters_qa",
    "qa_fig22_unknown_spectra_type_examples",
    "stage5_fig9_unlinked_parameter_distribution",
}


@dataclass
class FigurePlanRow:
    figure_id: str
    title: str
    scientific_question: str
    expected_claim: str
    why_this_is_meaningful: str
    required_tables: str
    required_fields: str
    panels: str
    panel_data_logic: str
    recommended_plot_type: str
    filtering_rules: str
    unknown_other_handling: str
    unit_handling: str
    risk_and_limitations: str
    ready_to_plot: str
    priority: str
    nature_skills_recommendation: str


def run_manuscript_figure_diagnosis(
    *,
    atlas_dir: Path,
    shortlist_dir: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    atlas_root = Path(atlas_dir)
    shortlist_root = Path(shortlist_dir)
    diagnosis_root = ensure_dir(output_dir or atlas_root.parent / "manuscript_figure_diagnosis")
    source_root = ensure_dir(diagnosis_root / "source_tables")
    qc_root = ensure_dir(diagnosis_root / "qc")

    tables = {name: read_csv(atlas_root / "tables" / name) for name in ATLAS_TABLES}
    figure_index = read_csv(atlas_root / "figure_index.csv")
    shortlist_table = read_csv(shortlist_root / "shortlist_table.csv")
    shortlist_manifest = read_json(shortlist_root / "shortlist_manifest.json", default={}) or {}
    shortlist_report = (shortlist_root / "shortlist_report.md").read_text(encoding="utf-8")

    inventory = build_table_inventory(tables)
    write_frame(diagnosis_root / "table_inventory.csv", inventory)

    quality_summary = build_data_quality_summary(tables, inventory)
    write_json(diagnosis_root / "data_quality_summary.json", quality_summary)
    write_markdown(diagnosis_root / "data_quality_report.md", build_data_quality_report(quality_summary, inventory))

    figure_diagnosis = build_old_figure_diagnosis(
        figure_index=figure_index,
        shortlist_table=shortlist_table,
        tables=tables,
    )
    write_frame(diagnosis_root / "old_figure_diagnosis.csv", figure_diagnosis)
    write_markdown(diagnosis_root / "old_figure_diagnosis.md", build_old_figure_diagnosis_md(figure_diagnosis))

    figure_plan = build_manuscript_figure_plan(tables)
    plan_frame = pd.DataFrame([row.__dict__ for row in figure_plan])
    write_frame(diagnosis_root / "manuscript_figure_plan.csv", plan_frame)
    write_json(diagnosis_root / "manuscript_figure_plan.json", [row.__dict__ for row in figure_plan])
    write_markdown(diagnosis_root / "manuscript_figure_plan.md", build_manuscript_figure_plan_md(figure_plan))

    source_tables = build_source_tables(tables)
    manifest_rows: list[dict[str, Any]] = []
    qc_rows: list[dict[str, Any]] = []
    for name, frame in source_tables.items():
        write_frame(source_root / name, frame)
        included = int(frame["included_in_main_plot"].fillna(False).astype(bool).sum()) if "included_in_main_plot" in frame.columns else 0
        excluded = int(len(frame) - included)
        panels = sorted(set(frame["panel_id"].dropna().astype(str))) if "panel_id" in frame.columns else []
        manifest_rows.append(
            {
                "file": name,
                "row_count": int(len(frame)),
                "column_count": int(len(frame.columns)),
                "included_rows": included,
                "excluded_rows": excluded,
                "panel_ids": panels,
                "categories": sorted(set(frame["category"].dropna().astype(str)))[:20] if "category" in frame.columns else [],
            }
        )
        qc_rows.append(
            {
                "file": name,
                "row_count": int(len(frame)),
                "included_rows": included,
                "excluded_rows": excluded,
                "missing_value_ratio": float(frame["value"].isna().mean()) if "value" in frame.columns and len(frame) else 0.0,
                "missing_numeric_ratio": float(frame["numeric_value"].isna().mean()) if "numeric_value" in frame.columns and len(frame) else 0.0,
                "relationship_types": json.dumps(sorted(set(frame["relationship_type"].dropna().astype(str)))) if "relationship_type" in frame.columns else "[]",
            }
        )
    write_json(source_root / "source_table_manifest.json", manifest_rows)
    write_frame(qc_root / "source_table_qc_summary.csv", pd.DataFrame(qc_rows))

    diagnosis_report = build_diagnosis_report(
        quality_summary=quality_summary,
        figure_diagnosis=figure_diagnosis,
        figure_plan=figure_plan,
        shortlist_manifest=shortlist_manifest,
        shortlist_report=shortlist_report,
        source_table_manifest=manifest_rows,
    )
    write_markdown(diagnosis_root / "diagnosis_report.md", diagnosis_report)

    return {
        "atlas_dir": str(atlas_root),
        "shortlist_dir": str(shortlist_root),
        "diagnosis_dir": str(diagnosis_root),
        "generated_files": [
            str(diagnosis_root / "table_inventory.csv"),
            str(diagnosis_root / "data_quality_summary.json"),
            str(diagnosis_root / "data_quality_report.md"),
            str(diagnosis_root / "old_figure_diagnosis.csv"),
            str(diagnosis_root / "old_figure_diagnosis.md"),
            str(diagnosis_root / "manuscript_figure_plan.csv"),
            str(diagnosis_root / "manuscript_figure_plan.json"),
            str(diagnosis_root / "manuscript_figure_plan.md"),
            str(diagnosis_root / "diagnosis_report.md"),
            *[str(source_root / name) for name in source_tables],
            str(source_root / "source_table_manifest.json"),
            str(qc_root / "source_table_qc_summary.csv"),
        ],
    }


def build_table_inventory(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in tables.items():
        important_cols = [
            "paper_id",
            "category",
            "parameter_family",
            "process_step_family",
            "normalized_spectra_type",
            "link_family",
            "numeric_value",
            "peak_value",
            "peak_unit",
        ]
        row = {
            "table_name": name,
            "row_count": int(len(frame)),
            "column_count": int(len(frame.columns)),
            "columns": json.dumps(frame.columns.tolist(), ensure_ascii=False),
            "missing_value_ratio_by_important_columns": json.dumps(_missing_ratios(frame, important_cols), ensure_ascii=False),
            "unique_paper_id_count": _nunique(frame, "paper_id"),
            "unique_category_count": _nunique(frame, "category"),
            "category_distribution": json.dumps(_value_distribution(frame, "category"), ensure_ascii=False),
            "parameter_family_distribution": json.dumps(_value_distribution(frame, "parameter_family"), ensure_ascii=False),
            "process_step_family_distribution": json.dumps(_value_distribution(frame, "process_step_family"), ensure_ascii=False),
            "normalized_spectra_type_distribution": json.dumps(_value_distribution(frame, "normalized_spectra_type"), ensure_ascii=False),
            "link_family_distribution": json.dumps(_value_distribution(frame, "link_family"), ensure_ascii=False),
            "unknown_other_ratio": json.dumps(_unknown_other_ratio_by_column(frame), ensure_ascii=False),
            "numeric_value_availability": _availability(frame, "numeric_value"),
            "peak_value_availability": _availability(frame, "peak_value"),
            "peak_unit_distribution": json.dumps(_value_distribution(frame, "peak_unit"), ensure_ascii=False),
            "obvious_outlier_ranges": json.dumps(_outlier_ranges(frame), ensure_ascii=False),
            "suitable_for_main_figures": _table_role(name),
            "suitable_for_supplementary": _table_role(name) in {"main", "supplementary"},
            "suitable_for_qa_only": _table_role(name) == "qa",
        }
        rows.append(row)
    return pd.DataFrame(rows)


def build_data_quality_summary(tables: dict[str, pd.DataFrame], inventory: pd.DataFrame) -> dict[str, Any]:
    parameters = tables["normalized_parameters.csv"]
    process = tables["normalized_process_steps.csv"]
    spectra = tables["normalized_stage4_spectra.csv"]
    peaks = tables["normalized_stage4_peaks.csv"]
    links = tables["normalized_stage5_links.csv"]

    parameter_other_ratio = _token_ratio(parameters, "parameter_family", EXCLUDED_PARAMETER_FAMILIES)
    process_other_ratio = _token_ratio(process, "process_step_family", EXCLUDED_PROCESS_FAMILIES)
    spectra_other_ratio = _token_ratio(spectra, "normalized_spectra_type", EXCLUDED_SPECTRA_TYPES)
    link_unknown_ratio = _token_ratio(links, "normalized_spectra_type", EXCLUDED_SPECTRA_TYPES)
    peak_unit_summary = _peak_unit_summary(peaks)
    findings = []
    if parameter_other_ratio > 0.2:
        findings.append("Parameter-family space still has a strong Other/uncategorized component and needs semantic filtering before main-text plotting.")
    if process_other_ratio > 0.2:
        findings.append("Process-step normalization remains coarse, especially for rows mapped to 'other'.")
    if spectra_other_ratio > 0.1:
        findings.append("Stage4 spectra types still contain non-trivial Other/Unknown categories that should not dominate manuscript panels.")
    if peak_unit_summary["mixed_unit_types"]:
        findings.append("Stage4 peak distributions show unit mixing and outlier ranges; peak panels must be rebuilt with unit-aware filters.")
    findings.append("Fig. 1 and Fig. 2 source tables are the safest starting point because their core tables are dense and mostly count-based.")

    return {
        "main_table_candidates": [
            "category_summary.csv",
            "parameter_family_by_category.csv",
            "normalized_parameters.csv",
            "normalized_process_steps.csv",
            "process_parameter_matrix.csv",
            "spectra_type_by_category.csv",
            "spectra_parameter_matrix.csv",
            "normalized_stage5_links.csv",
        ],
        "supplement_only_candidates": [
            "stage3_paper_summary.csv",
            "stage4_paper_summary.csv",
            "normalized_sample_matrix.csv",
        ],
        "qa_only_candidates": [
            "stage4_failed.csv",
            "stage4_quality.csv",
        ],
        "parameter_other_ratio": parameter_other_ratio,
        "process_other_ratio": process_other_ratio,
        "spectra_other_ratio": spectra_other_ratio,
        "link_unknown_ratio": link_unknown_ratio,
        "peak_unit_summary": peak_unit_summary,
        "inventory_summary": {
            "table_count": int(len(inventory)),
            "main_capable_table_count": int((inventory["suitable_for_main_figures"] == "main").sum()),
            "supplement_capable_table_count": int(inventory["suitable_for_supplementary"].sum()),
            "qa_only_table_count": int(inventory["suitable_for_qa_only"].sum()),
        },
        "major_findings": findings,
    }


def build_data_quality_report(summary: dict[str, Any], inventory: pd.DataFrame) -> str:
    lines = [
        "# Data Quality Report",
        "",
        "## Main findings",
    ]
    for finding in summary["major_findings"]:
        lines.append(f"- {finding}")
    lines.extend(
        [
            "",
            "## High-value tables for manuscript figures",
        ]
    )
    for name in summary["main_table_candidates"]:
        lines.append(f"- {name}")
    lines.extend(
        [
            "",
            "## Table roles",
        ]
    )
    for _, row in inventory.sort_values(["suitable_for_main_figures", "row_count"], ascending=[True, False]).iterrows():
        lines.append(f"- {row['table_name']}: role={row['suitable_for_main_figures']}, rows={row['row_count']}, categories={row['unique_category_count']}")
    return "\n".join(lines) + "\n"


def build_old_figure_diagnosis(
    *,
    figure_index: pd.DataFrame,
    shortlist_table: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    merged = figure_index.merge(
        shortlist_table[
            [
                "figure_id",
                "recommendation",
                "scientific_value",
                "interpretability",
                "publication_potential",
                "uniqueness",
                "reliability",
                "row_count",
            ]
        ].rename(
            columns={
                "recommendation": "shortlist_recommendation",
                "scientific_value": "shortlist_scientific_value",
                "interpretability": "shortlist_interpretability",
                "publication_potential": "shortlist_publication_potential",
                "uniqueness": "shortlist_uniqueness",
                "reliability": "shortlist_reliability",
                "row_count": "shortlist_row_count",
            }
        ),
        on="figure_id",
        how="left",
    )
    rows: list[dict[str, Any]] = []
    table_risk = {
        "normalized_parameters.csv": "needs_semantic_normalization",
        "normalized_stage4_peaks.csv": "unit_mixing",
        "normalized_stage5_links.csv": "needs_reaggregation",
    }
    for _, row in merged.iterrows():
        figure_id = str(row["figure_id"])
        source_csv = Path(str(row["source_csv"]))
        source_df = read_csv(source_csv) if source_csv.exists() else pd.DataFrame()
        row_count = int(row.get("shortlist_row_count") or len(source_df))
        problem_types: list[str] = []
        if str(row["tier"]) == "auto":
            problem_types.extend(["over_auto_plot", "duplicate"])
        if str(row.get("recommendation", "")) == "qa_only":
            problem_types.append("qa_only")
        if row_count <= 0:
            problem_types.append("not_worth_continuing")
        if "unknown" in figure_id or "other" in figure_id:
            problem_types.append("too_many_unknown_other")
        if "distribution" in figure_id and str(row["tier"]) == "stage4":
            problem_types.append("extreme_values")
        if "hist" in figure_id or "distribution" in figure_id:
            problem_types.append("needs_reaggregation")
        if figure_id in FALLBACK_EMPTY_FIGURES:
            problem_types.extend(["qa_only", "not_worth_continuing"])
        if source_df.shape[1] >= 20:
            problem_types.append("over_dense")
        if str(row["tier"]) in {"main", "cross_stage"}:
            problem_types.append("useful_as_source")
        if figure_id in {"main_fig9_knowledge_graph_overview", "main_fig10_research_atlas_summary"}:
            problem_types.append("duplicate")
        if figure_id.startswith("qa_fig"):
            problem_types.append("qa_only")
        if source_csv.name in table_risk:
            problem_types.append(table_risk[source_csv.name])
        problem_types = sorted(set(problem_types))

        shortlist_role = str(row.get("shortlist_recommendation", "discard_or_low_value"))
        recommendation = _old_figure_recommendation(shortlist_role, figure_id)
        rows.append(
            {
                "figure_id": figure_id,
                "tier": row["tier"],
                "old_title": row["title"],
                "shortlist_role": shortlist_role,
                "source_csv": str(source_csv),
                "source_json": str(row["source_json"]),
                "can_reuse_data": recommendation in {"rebuild_as_main", "rebuild_as_extended", "keep_as_supplement"},
                "can_reuse_design": recommendation == "keep_as_supplement" and str(row["tier"]) == "qa",
                "scientific_value_score": int(row.get("shortlist_scientific_value") or 1),
                "visual_value_score": _visual_value_score(problem_types, str(row["tier"])),
                "data_risk_score": _data_risk_score(problem_types),
                "main_text_potential": _main_text_potential(shortlist_role, recommendation),
                "problem_types": "|".join(problem_types),
                "recommendation": recommendation,
                "notes": _old_figure_notes(figure_id, recommendation, problem_types),
            }
        )
    return pd.DataFrame(rows).sort_values(["recommendation", "scientific_value_score", "figure_id"], ascending=[True, False, True])


def build_old_figure_diagnosis_md(frame: pd.DataFrame) -> str:
    lines = [
        "# Old Figure Diagnosis",
        "",
        "## Recommendation counts",
    ]
    for key, value in frame["recommendation"].value_counts().to_dict().items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Figures to rebuild as main"])
    for _, row in frame[frame["recommendation"] == "rebuild_as_main"].head(12).iterrows():
        lines.append(f"- {row['figure_id']}: {row['notes']}")
    lines.extend(["", "## Figures not worth continuing"])
    for _, row in frame[frame["recommendation"] == "discard"].head(20).iterrows():
        lines.append(f"- {row['figure_id']}: {row['notes']}")
    return "\n".join(lines) + "\n"


def build_manuscript_figure_plan(tables: dict[str, pd.DataFrame]) -> list[FigurePlanRow]:
    fig4_ready = _peak_unit_summary(tables["normalized_stage4_peaks.csv"])["ready_for_main_hist_panels"]
    fig3_ready = "conditional" if _token_ratio(tables["normalized_process_steps.csv"], "process_step_family", EXCLUDED_PROCESS_FAMILIES) > 0.2 else "yes"
    fig5_ready = "conditional"
    return [
        FigurePlanRow(
            figure_id="Fig1",
            title="Dataset coverage and extraction reliability",
            scientific_question="How many papers, samples, parameters, process steps, spectra, and links are covered, and is the extraction base reliable enough for downstream analysis?",
            expected_claim="The atlas has broad paper coverage and enough structured extraction depth to support quantitative synthesis-level analysis.",
            why_this_is_meaningful="This figure justifies the credibility and usable scope of the database before any scientific pattern claims.",
            required_tables="category_summary.csv; stage3_paper_summary.csv; stage4_paper_summary.csv; normalized_sample_matrix.csv; normalized_stage5_links.csv",
            required_fields="category; paper_count; sample_id; parameter_count; process_step_count; spectra_count; link_count; stage3_status; candidate_count; success_count; failed_count; validated_count",
            panels="A object counts by category; B Stage3/4/5 coverage summary; C link completeness by category; D data availability matrix",
            panel_data_logic="Count-based overview with paper-level and category-level aggregation only; no semantic filtering required beyond category cleanup.",
            recommended_plot_type="Multi-panel bar + heatmap overview",
            filtering_rules="Keep all categories; aggregate rare missing labels into explicit QA rows only if needed.",
            unknown_other_handling="Show explicitly in QA, but do not let Unknown dominate the main panels.",
            unit_handling="Not unit-sensitive because the main panels are count- and coverage-based.",
            risk_and_limitations="Coverage metrics can overstate quality if not paired with validation/error context.",
            ready_to_plot="yes",
            priority="highest",
            nature_skills_recommendation="Use nature-figure after source-table QC to build the opening manuscript overview.",
        ),
        FigurePlanRow(
            figure_id="Fig2",
            title="Synthesis parameter landscape of alumina sols",
            scientific_question="Which synthesis parameters are most frequently reported, and how do parameter emphases vary across alumina-sol research directions?",
            expected_claim="A small set of synthesis parameter families dominates the literature, while category-specific parameter emphasis reveals distinct experimental traditions.",
            why_this_is_meaningful="This is the strongest scientific synthesis figure because it turns dispersed reporting habits into a coherent parameter space.",
            required_tables="normalized_parameters.csv; parameter_family_by_category.csv",
            required_fields="category; paper_id; parameter_family; parameter_name; numeric_value; normalized_unit; raw_value",
            panels="A category x parameter-family heatmap; B top parameter families; C pH/Al concentration/solid content distributions; D temperature/time condition windows; E parameter co-occurrence matrix",
            panel_data_logic="Use category-level counts for the heatmap, global top-family counts for the bar panel, numeric rows for distributions, and sample-level co-occurrence for panel E.",
            recommended_plot_type="Hero heatmap with supporting bar, distribution, and co-occurrence panels",
            filtering_rules="Exclude Other/Unknown from the main heatmap; mark them as included_in_main_plot=false in the source table; keep only numeric rows with unit-safe families for distributions.",
            unknown_other_handling="Retain in source tables with exclusion_reason=semantic_noise.",
            unit_handling="Do not mix non-comparable units inside the same numeric panel; downgrade to count-based availability if unit consistency is poor.",
            risk_and_limitations="Al concentration and solid-content families still need careful unit normalization checks before publication plotting.",
            ready_to_plot="yes",
            priority="highest",
            nature_skills_recommendation="Use nature-figure to redraw as the core manuscript result figure once the rebuilt source table is accepted.",
        ),
        FigurePlanRow(
            figure_id="Fig3",
            title="Process route and condition windows",
            scientific_question="What process routes recur from precursor to sol/fiber/material, and what temperature-time windows are most often linked to these steps?",
            expected_claim="A recurring route structure emerges, but process semantics remain coarser than parameter semantics and require manuscript-friendly relabeling.",
            why_this_is_meaningful="It can turn the Stage3 process extraction into a genuine process map instead of a simple frequency chart.",
            required_tables="normalized_process_steps.csv; process_step_by_category.csv; process_parameter_matrix.csv; normalized_parameters.csv; normalized_stage5_links.csv",
            required_fields="process_step_family; category; parameter_family; parameter_id; numeric_value; normalized_unit; match_method",
            panels="A simplified process-route schematic; B process-step frequency; C category x process-step heatmap; D process-step x parameter-family heatmap; E temperature/time windows by process step",
            panel_data_logic="Panels A-D are count-based; panel E should be built from process-step links merged back to parameter numeric values.",
            recommended_plot_type="Schematic-led composite with one route panel and four supporting quantitative panels",
            filtering_rules="Collapse manuscript-unfriendly labels; exclude Other from the route schematic; keep process-step families with direct numeric parameter links for panel E only.",
            unknown_other_handling="Retain in source tables but exclude from the route schematic and primary heatmap panels.",
            unit_handling="Separate temperature and time families; do not force incompatible units onto one axis.",
            risk_and_limitations="Process-step family normalization is still coarse, so Fig3 should follow Fig1/Fig2/Fig4 rather than precede them.",
            ready_to_plot=fig3_ready,
            priority="medium",
            nature_skills_recommendation="Use nature-figure only after checking whether process-step semantics are clean enough for a main-text schematic.",
        ),
        FigurePlanRow(
            figure_id="Fig4",
            title="Characterization evidence atlas",
            scientific_question="Which characterization techniques most often support alumina-sol studies, and which parameter families are most tightly associated with those techniques?",
            expected_claim="A few characterization families dominate evidence generation, but peak-level panels require unit-aware filtering before they can support manuscript claims.",
            why_this_is_meaningful="This is the clearest place to show the added scientific value of Stage4 beyond simple figure counting.",
            required_tables="normalized_stage4_spectra.csv; normalized_stage4_peaks.csv; spectra_type_by_category.csv; spectra_parameter_matrix.csv",
            required_fields="category; normalized_spectra_type; figure_class; parameter_family; peak_value; peak_unit; peak_source_field; raw_value; numeric_value",
            panels="A characterization type x category heatmap; B spectra type x parameter-family heatmap; C FTIR peak distribution; D XRD peak distribution; E NMR/thermal event distributions",
            panel_data_logic="Use count-based matrices for panels A-B and unit-filtered peak rows for panels C-E, with included_in_main_plot controlling which rows survive manuscript plotting.",
            recommended_plot_type="Two heatmaps plus three filtered distribution panels",
            filtering_rules="FTIR 400-4000 cm^-1; XRD 5-90 degree 2theta; NMR only ppm-like rows in a reasonable range; TG/DSC only temperature-like rows within a bounded thermal window.",
            unknown_other_handling="Other/Unknown spectra types stay in source tables but are excluded from the main characterization heatmap.",
            unit_handling="Peak panels must keep raw_value, numeric_value, unit, source_field, included_in_main_plot, and filter_reason.",
            risk_and_limitations="Peak histograms are not ready without unit and outlier cleanup, especially for NMR and TG/DSC.",
            ready_to_plot="conditional" if not fig4_ready else "yes",
            priority="highest",
            nature_skills_recommendation="Use nature-figure after reviewing the rebuilt peak source table and confirming unit-safe subsets.",
        ),
        FigurePlanRow(
            figure_id="Fig5",
            title="Link-aware process-spectra-parameter structure",
            scientific_question="Do Stage3 parameters, Stage4 spectra, and Stage5 links form a traceable knowledge structure rather than a flat extraction table?",
            expected_claim="The database contains meaningful deterministic links, but any process-to-spectra relationship panel must be labeled as aggregated co-occurrence unless a direct link exists.",
            why_this_is_meaningful="This figure sells the database architecture and link-aware value rather than the material science itself.",
            required_tables="normalized_stage5_links.csv; evidence_parameter_matrix.csv; process_parameter_matrix.csv; spectra_parameter_matrix.csv; category_summary.csv; normalized_parameters.csv",
            required_fields="link_family; raw_source_type; normalized_spectra_type; normalized_process_step_family; normalized_parameter_family; link_count_or_weight; match_method; parameter_id",
            panels="A link-family counts; B link completeness by category; C evidence-type x parameter-family matrix; D process-step x parameter-family matrix; E spectra-type x parameter-family matrix; F optional aggregated process-parameter-spectra bridge",
            panel_data_logic="Use deterministic link counts for panels A-E and only label panel F as co_occurrence_via_parameter_family unless direct process-spectra evidence exists.",
            recommended_plot_type="Methods-style multi-panel structure figure with one optional aggregated bridge panel",
            filtering_rules="Separate deterministic links from co-occurrence bridges; exclude Other/Unknown from the main matrices unless they are explicitly being audited.",
            unknown_other_handling="Keep in source tables with included_in_main_plot=false unless they are part of a QC appendix.",
            unit_handling="Mostly count-based; unit handling matters only when link panels merge back to numeric parameter rows.",
            risk_and_limitations="This figure is structurally valuable but less manuscript-essential than Fig1/Fig2/Fig4 until the bridge panel semantics are stable.",
            ready_to_plot=fig5_ready,
            priority="medium",
            nature_skills_recommendation="Use nature-figure only after the relationship_type field is frozen and co-occurrence is clearly separated from deterministic links.",
        ),
    ]


def build_manuscript_figure_plan_md(rows: list[FigurePlanRow]) -> str:
    lines = ["# Manuscript Figure Plan", ""]
    for row in rows:
        lines.extend(
            [
                f"## {row.figure_id} {row.title}",
                f"- Scientific question: {row.scientific_question}",
                f"- Expected claim: {row.expected_claim}",
                f"- Ready to plot: {row.ready_to_plot}",
                f"- Priority: {row.priority}",
                f"- Risks: {row.risk_and_limitations}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def build_source_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {
        "Fig1_dataset_coverage_source.csv": _build_fig1_source(tables),
        "Fig2_synthesis_parameter_landscape_source.csv": _build_fig2_source(tables),
        "Fig3_process_route_condition_windows_source.csv": _build_fig3_source(tables),
        "Fig4_characterization_evidence_atlas_source.csv": _build_fig4_source(tables),
        "Fig5_link_aware_structure_source.csv": _build_fig5_source(tables),
    }


def build_diagnosis_report(
    *,
    quality_summary: dict[str, Any],
    figure_diagnosis: pd.DataFrame,
    figure_plan: list[FigurePlanRow],
    shortlist_manifest: dict[str, Any],
    shortlist_report: str,
    source_table_manifest: list[dict[str, Any]],
) -> str:
    lines = [
        "# Manuscript Figure Diagnosis Report",
        "",
        "## What these data can support",
        "- The strongest claims are about dataset coverage, synthesis-parameter landscapes, and characterization evidence structure.",
        "- Process-route and link-aware bridge figures are viable, but they depend more heavily on semantic normalization and careful wording.",
        "",
        "## Why the old atlas figures looked wrong",
        "- Many old panels were auto-generated atlas diagnostics rather than question-driven manuscript figures.",
        "- Other/Unknown/uncategorized labels and mixed units were allowed to dominate visual space.",
        "- Several Stage4 peak plots used raw numeric ranges without manuscript-safe unit filtering.",
        "- Some panels were valid QA checks but visually resembled scientific result figures.",
        "",
        "## Data problems vs design problems",
        "- Data problems: Other/Unknown inflation, mixed peak units, outliers in Stage4 peak rows, coarse process-step normalization, and missing numeric values in some parameter families.",
        "- Design problems: over-dense heatmaps, duplicated overview panels, histograms without bounded scientific ranges, and QA panels that were not visually separated from result panels.",
        "- Semantic-normalization problems: process-step relabeling, relationship_type separation for link-aware figures, and better handling of count-based vs numeric panels.",
        "",
        "## Figures not worth continuing",
    ]
    for _, row in figure_diagnosis[figure_diagnosis["recommendation"] == "discard"].head(20).iterrows():
        lines.append(f"- {row['figure_id']}: {row['notes']}")
    lines.extend(
        [
            "",
            "## Best candidates for Nature-style redraw later",
            "- Fig1 Dataset coverage and extraction reliability",
            "- Fig2 Synthesis parameter landscape of alumina sols",
            "- Fig4 Characterization evidence atlas",
            "",
            "## Which three figures should be drawn first",
            "- Fig1 because it establishes dataset credibility and extraction reliability with minimal unit risk.",
            "- Fig2 because it is the strongest scientific synthesis figure and already has a workable source-table basis.",
            "- Fig4 because it is the clearest Stage4-value figure once unit-aware peak filtering is enforced.",
            "",
            "## Which figures should wait",
            "- Fig3 should wait until process-step labels are reviewed and the direct temperature/time windows look manuscript-clean.",
            "- Fig5 should wait until deterministic links and co-occurrence bridges are clearly separated in the final source table.",
            "",
            "## Shortlist context",
            f"- Shortlist top main candidates: {', '.join(shortlist_manifest.get('top_main_candidates', [])[:8])}",
            f"- Fallback empty figures: {', '.join(shortlist_manifest.get('fallback_empty_figures', []))}",
            "",
            "## Source tables generated",
        ]
    )
    for item in source_table_manifest:
        lines.append(f"- {item['file']}: rows={item['row_count']}, included={item['included_rows']}, excluded={item['excluded_rows']}")
    lines.extend(
        [
            "",
            "## Note",
            "This run did not generate final manuscript figures and did not reuse old PNG/SVG files; it only rebuilt diagnosis outputs and tidy source tables.",
            "",
            "## Shortlist note excerpt",
            shortlist_report.splitlines()[0] if shortlist_report else "",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_fig1_source(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    category_summary = tables["category_summary.csv"].copy()
    sample_counts = (
        tables["normalized_sample_matrix.csv"]
        .groupby("category")["sample_id"]
        .nunique()
        .reset_index(name="sample_count")
    )
    merged = category_summary.merge(sample_counts, on="category", how="left").fillna({"sample_count": 0})
    rows: list[dict[str, Any]] = []
    for _, record in merged.iterrows():
        for metric in ["paper_count", "sample_count", "parameter_count", "process_step_count", "spectra_count", "link_count"]:
            rows.append(
                _source_row(
                    figure_id="Fig1",
                    panel_id="A",
                    panel_title="Dataset object counts by category",
                    source_table="category_summary.csv",
                    category=record["category"],
                    entity_type="category",
                    entity_label=record["category"],
                    metric=metric,
                    value=record[metric],
                    unit="count",
                    included=True,
                )
            )
    stage3 = tables["stage3_paper_summary.csv"]
    stage4 = tables["stage4_paper_summary.csv"]
    for category, group in stage3.groupby("category"):
        status_counts = group["stage3_status"].fillna("missing").value_counts()
        for status, count in status_counts.items():
            rows.append(_source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage3_paper_summary.csv", category=category, entity_type="stage3_status", entity_label=status, metric="paper_count", value=count, unit="count", included=True))
    for category, group in stage4.groupby("category"):
        rows.extend(
            [
                _source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage4_paper_summary.csv", category=category, entity_type="stage4_metric", entity_label="candidate_count", metric="sum", value=group["candidate_count"].sum(), unit="count", included=True),
                _source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage4_paper_summary.csv", category=category, entity_type="stage4_metric", entity_label="success_count", metric="sum", value=group["success_count"].sum(), unit="count", included=True),
                _source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage4_paper_summary.csv", category=category, entity_type="stage4_metric", entity_label="failed_count", metric="sum", value=group["failed_count"].sum(), unit="count", included=True),
                _source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage4_paper_summary.csv", category=category, entity_type="stage4_metric", entity_label="validated_count", metric="sum", value=group["validated_count"].sum(), unit="count", included=True),
                _source_row("Fig1", "B", "Stage3/4/5 coverage summary", "stage4_paper_summary.csv", category=category, entity_type="stage4_metric", entity_label="mean_coverage_rate", metric="mean", value=group["coverage_rate"].mean(), unit="ratio", included=True),
            ]
        )
    params = tables["normalized_parameters.csv"].copy()
    completeness = params.groupby("category").agg(
        total_parameters=("parameter_id", "size"),
        sample_linked=("has_sample_link", lambda s: int(s.fillna(False).sum())),
        evidence_linked=("has_evidence_link", lambda s: int(s.fillna(False).sum())),
        process_linked=("has_process_step_link", lambda s: int(s.fillna(False).sum())),
        spectra_linked=("has_spectra_link", lambda s: int(s.fillna(False).sum())),
    ).reset_index()
    for _, record in completeness.iterrows():
        total = max(int(record["total_parameters"]), 1)
        for label in ["sample_linked", "evidence_linked", "process_linked", "spectra_linked"]:
            rows.append(_source_row("Fig1", "C", "Link completeness by category", "normalized_parameters.csv", category=record["category"], entity_type="link_family", entity_label=label, metric="linked_parameter_ratio", value=record[label] / total, unit="ratio", included=True, notes=f"{int(record[label])}/{total} linked parameters"))
    for _, record in merged.iterrows():
        for metric in ["paper_count", "sample_count", "parameter_count", "process_step_count", "spectra_count", "link_count"]:
            rows.append(_source_row("Fig1", "D", "Data availability matrix", "category_summary.csv", category=record["category"], entity_type="object_type", entity_label=metric, metric="count", value=record[metric], unit="count", included=True))
    return pd.DataFrame(rows)


def _build_fig2_source(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    family_by_category = tables["parameter_family_by_category.csv"].copy()
    for _, record in family_by_category.iterrows():
        family = str(record["parameter_family"])
        included = not _is_unknown_token(family)
        rows.append(_source_row("Fig2", "A", "Category by parameter-family heatmap", "parameter_family_by_category.csv", category=record["category"], entity_type="parameter_family", entity_label=family, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="aggregated_count"))
    params = tables["normalized_parameters.csv"].copy()
    top_families = params.groupby("parameter_family").size().reset_index(name="count").sort_values("count", ascending=False)
    for _, record in top_families.iterrows():
        family = str(record["parameter_family"])
        included = not _is_unknown_token(family)
        rows.append(_source_row("Fig2", "B", "Top reported parameter families", "normalized_parameters.csv", entity_type="parameter_family", entity_label=family, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="aggregated_count"))
    distribution_families = {"pH", "Al concentration", "solid content"}
    for _, record in params[params["parameter_family"].isin(distribution_families)].iterrows():
        unit_ok = _unit_safe_for_parameter_family(params, str(record["parameter_family"]))
        rows.append(_source_row("Fig2", "C", "pH / Al concentration / solid content distributions", "normalized_parameters.csv", paper_id=record["paper_id"], category=record["category"], entity_type="parameter_record", entity_label=record["parameter_family"], metric="distribution_value", value=record["numeric_value"], unit=_norm_unit(record["normalized_unit"]), raw_value=record["raw_value"], numeric_value=record["numeric_value"], included=bool(unit_ok and pd.notna(record["numeric_value"])), exclusion_reason="" if unit_ok else "unit_mixing", filter_reason="missing_numeric_value" if pd.isna(record["numeric_value"]) else "", relationship_type="reported_value", notes=str(record["parameter_name"])))
    temp_time_families = [family for family in sorted(params["parameter_family"].dropna().unique()) if ("temperature" in str(family).lower() or "time" in str(family).lower())]
    for _, record in params[params["parameter_family"].isin(temp_time_families)].iterrows():
        unit_ok = _unit_safe_for_parameter_family(params, str(record["parameter_family"]))
        rows.append(_source_row("Fig2", "D", "Temperature/time condition windows", "normalized_parameters.csv", paper_id=record["paper_id"], category=record["category"], entity_type="parameter_record", entity_label=record["parameter_family"], metric="numeric_window_value", value=record["numeric_value"], unit=_norm_unit(record["normalized_unit"]), raw_value=record["raw_value"], numeric_value=record["numeric_value"], included=bool(unit_ok and pd.notna(record["numeric_value"]) and not _is_unknown_token(str(record["parameter_family"]))), exclusion_reason="semantic_noise" if _is_unknown_token(str(record["parameter_family"])) else ("" if unit_ok else "unit_mixing"), filter_reason="missing_numeric_value" if pd.isna(record["numeric_value"]) else "", relationship_type="reported_value", notes=str(record["parameter_name"])))
    cooc = _parameter_cooccurrence(params)
    for _, record in cooc.iterrows():
        included = not (_is_unknown_token(str(record["row_parameter_family"])) or _is_unknown_token(str(record["col_parameter_family"])))
        rows.append(_source_row("Fig2", "E", "Parameter co-occurrence matrix", "normalized_parameters.csv", entity_type="parameter_pair", entity_label=f"{record['row_parameter_family']} -> {record['col_parameter_family']}", metric="co_occurrence_count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="sample_level_co_occurrence"))
    return pd.DataFrame(rows)


def _build_fig3_source(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    process_steps = tables["normalized_process_steps.csv"].copy()
    frequency = process_steps.groupby("process_step_family").size().reset_index(name="count").sort_values("count", ascending=False)
    for _, record in frequency.iterrows():
        family = str(record["process_step_family"])
        included = not _is_unknown_token(family)
        rows.append(_source_row("Fig3", "A", "Simplified process-route schematic", "normalized_process_steps.csv", entity_type="process_step_family", entity_label=family, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="reported_frequency", notes="Frequency-derived route node; not causal."))
        rows.append(_source_row("Fig3", "B", "Process-step frequency", "normalized_process_steps.csv", entity_type="process_step_family", entity_label=family, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="reported_frequency"))
    process_by_category = tables["process_step_by_category.csv"].copy()
    for _, record in process_by_category.iterrows():
        family = str(record["process_step_family"])
        included = not _is_unknown_token(family)
        rows.append(_source_row("Fig3", "C", "Category by process-step heatmap", "process_step_by_category.csv", category=record["category"], entity_type="process_step_family", entity_label=family, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="aggregated_count"))
    process_parameter = tables["process_parameter_matrix.csv"].copy()
    for _, record in process_parameter.iterrows():
        step_family = str(record["normalized_process_step_family"])
        param_family = str(record["normalized_parameter_family"])
        included = not (_is_unknown_token(step_family) or _is_unknown_token(param_family))
        rows.append(_source_row("Fig3", "D", "Process-step by parameter-family heatmap", "process_parameter_matrix.csv", entity_type="process_parameter_pair", entity_label=f"{step_family} -> {param_family}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="deterministic_link"))
    links = tables["normalized_stage5_links.csv"]
    params = tables["normalized_parameters.csv"][["parameter_id", "parameter_family", "paper_id", "category", "raw_value", "numeric_value", "normalized_unit", "parameter_name"]]
    merged = links[links["link_family"] == "process_step"].merge(params, on=["parameter_id", "paper_id", "category"], how="left")
    merged = merged[merged["parameter_family"].fillna("").str.contains("temperature|time", case=False, regex=True)]
    for _, record in merged.iterrows():
        included = (
            pd.notna(record["numeric_value"])
            and not _is_unknown_token(str(record["normalized_process_step_family"]))
            and not _is_unknown_token(str(record["parameter_family"]))
        )
        if not _unit_safe_for_parameter_family(params, str(record["parameter_family"])):
            included = False
            exclusion = "unit_mixing"
        else:
            exclusion = ""
        rows.append(_source_row("Fig3", "E", "Temperature/time windows by process step", "normalized_stage5_links.csv", paper_id=record["paper_id"], category=record["category"], entity_type="process_step_parameter_record", entity_label=f"{record['normalized_process_step_family']} -> {record['parameter_family']}", metric="numeric_window_value", value=record["numeric_value"], unit=_norm_unit(record["normalized_unit"]), raw_value=record["raw_value"], numeric_value=record["numeric_value"], included=bool(included), exclusion_reason=exclusion, filter_reason="missing_numeric_value" if pd.isna(record["numeric_value"]) else "", relationship_type="deterministic_link", notes=str(record.get("parameter_name", ""))))
    return pd.DataFrame(rows)


def _build_fig4_source(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    spectra_by_category = tables["spectra_type_by_category.csv"].copy()
    for _, record in spectra_by_category.iterrows():
        spectra_type = str(record["normalized_spectra_type"])
        included = not _is_unknown_token(spectra_type)
        rows.append(_source_row("Fig4", "A", "Characterization type by category heatmap", "spectra_type_by_category.csv", category=record["category"], entity_type="spectra_type", entity_label=spectra_type, metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="aggregated_count"))
    spectra_parameter = tables["spectra_parameter_matrix.csv"].copy()
    for _, record in spectra_parameter.iterrows():
        spectra_type = str(record["normalized_spectra_type"])
        family = str(record["normalized_parameter_family"])
        included = not (_is_unknown_token(spectra_type) or _is_unknown_token(family))
        rows.append(_source_row("Fig4", "B", "Spectra type by parameter-family heatmap", "spectra_parameter_matrix.csv", entity_type="spectra_parameter_pair", entity_label=f"{spectra_type} -> {family}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="deterministic_link"))
    peaks = tables["normalized_stage4_peaks.csv"].copy()
    panel_rules = [
        ("C", "FTIR peak distribution", "FTIR", lambda r: _peak_included(r, expected_units={"cm^-1"}, min_value=400, max_value=4000)),
        ("D", "XRD peak distribution", "XRD", lambda r: _peak_included(r, expected_units={"2θ degree", "2theta_deg", "2Theta(degree)", "degrees 2-theta"}, min_value=5, max_value=90)),
        ("E", "NMR shift distribution", "NMR", lambda r: _peak_included(r, expected_units={"ppm"}, min_value=-50, max_value=250)),
        ("F", "Thermal event temperature distribution", "TG/DSC", lambda r: _peak_included(r, expected_units={"°C", "C"}, min_value=0, max_value=1400)),
    ]
    for panel_id, panel_title, spectra_type, rule in panel_rules:
        subset = peaks[peaks["normalized_spectra_type"] == spectra_type]
        for _, record in subset.iterrows():
            included, reason = rule(record)
            rows.append(_source_row("Fig4", panel_id, panel_title, "normalized_stage4_peaks.csv", paper_id=record["paper_id"], category=record["category"], entity_type="peak_record", entity_label=spectra_type, metric="peak_value", value=record["peak_value"], unit=_norm_unit(record["peak_unit"]), raw_value=record["peak_value"], numeric_value=record["peak_value"], included=included, exclusion_reason="" if included else reason, filter_reason="" if included else reason, relationship_type="spectral_peak_measurement", notes=str(record["peak_source_field"])))
    return pd.DataFrame(rows)


def _build_fig5_source(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    links = tables["normalized_stage5_links.csv"].copy()
    params = tables["normalized_parameters.csv"].copy()
    for _, record in links.groupby(["category", "link_family"]).agg(count=("link_count_or_weight", "sum")).reset_index().iterrows():
        rows.append(_source_row("Fig5", "A", "Link-family counts", "normalized_stage5_links.csv", category=record["category"], entity_type="link_family", entity_label=record["link_family"], metric="count", value=record["count"], unit="count", included=True, relationship_type="deterministic_link"))
    completeness = params.groupby("category").agg(
        total=("parameter_id", "size"),
        evidence=("has_evidence_link", lambda s: int(s.fillna(False).sum())),
        process_step=("has_process_step_link", lambda s: int(s.fillna(False).sum())),
        spectra=("has_spectra_link", lambda s: int(s.fillna(False).sum())),
        sample=("has_sample_link", lambda s: int(s.fillna(False).sum())),
    ).reset_index()
    for _, record in completeness.iterrows():
        total = max(int(record["total"]), 1)
        for family in ["sample", "evidence", "process_step", "spectra"]:
            rows.append(_source_row("Fig5", "B", "Link completeness by category", "normalized_parameters.csv", category=record["category"], entity_type="link_family", entity_label=family, metric="linked_ratio", value=float(record[family]) / total, unit="ratio", included=True, relationship_type="deterministic_link", notes=f"{int(record[family])}/{total} parameters linked"))
    for _, record in tables["evidence_parameter_matrix.csv"].iterrows():
        family = str(record["normalized_parameter_family"])
        included = not _is_unknown_token(family)
        rows.append(_source_row("Fig5", "C", "Evidence type by parameter-family matrix", "evidence_parameter_matrix.csv", entity_type="evidence_parameter_pair", entity_label=f"{record['raw_source_type']} -> {family}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="deterministic_link"))
    for _, record in tables["process_parameter_matrix.csv"].iterrows():
        step_family = str(record["normalized_process_step_family"])
        param_family = str(record["normalized_parameter_family"])
        included = not (_is_unknown_token(step_family) or _is_unknown_token(param_family))
        rows.append(_source_row("Fig5", "D", "Process-step by parameter-family matrix", "process_parameter_matrix.csv", entity_type="process_parameter_pair", entity_label=f"{step_family} -> {param_family}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="deterministic_link"))
    for _, record in tables["spectra_parameter_matrix.csv"].iterrows():
        spectra_type = str(record["normalized_spectra_type"])
        param_family = str(record["normalized_parameter_family"])
        included = not (_is_unknown_token(spectra_type) or _is_unknown_token(param_family))
        rows.append(_source_row("Fig5", "E", "Spectra type by parameter-family matrix", "spectra_parameter_matrix.csv", entity_type="spectra_parameter_pair", entity_label=f"{spectra_type} -> {param_family}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="deterministic_link"))
    process_links = links[links["link_family"] == "process_step"][["paper_id", "category", "normalized_process_step_family", "normalized_parameter_family", "parameter_id"]].dropna()
    spectra_links = links[links["link_family"] == "spectra"][["paper_id", "category", "normalized_spectra_type", "normalized_parameter_family", "parameter_id"]].dropna()
    bridge = process_links.merge(
        spectra_links,
        on=["paper_id", "category", "normalized_parameter_family", "parameter_id"],
        how="inner",
        suffixes=("_process", "_spectra"),
    )
    if not bridge.empty:
        grouped = bridge.groupby(["normalized_process_step_family", "normalized_parameter_family", "normalized_spectra_type"]).size().reset_index(name="count")
        for _, record in grouped.iterrows():
            included = not (
                _is_unknown_token(str(record["normalized_process_step_family"]))
                or _is_unknown_token(str(record["normalized_parameter_family"]))
                or _is_unknown_token(str(record["normalized_spectra_type"]))
            )
            rows.append(_source_row("Fig5", "F", "Process-parameter-spectra bridge", "normalized_stage5_links.csv", entity_type="bridge_triplet", entity_label=f"{record['normalized_process_step_family']} -> {record['normalized_parameter_family']} -> {record['normalized_spectra_type']}", metric="count", value=record["count"], unit="count", included=included, exclusion_reason="" if included else "semantic_noise", filter_reason="exclude_other_unknown" if not included else "", relationship_type="co_occurrence_via_parameter_family", notes="Aggregated bridge only; not direct causal evidence."))
    return pd.DataFrame(rows)


def _source_row(
    figure_id: str,
    panel_id: str,
    panel_title: str,
    source_table: str,
    *,
    paper_id: Any = "",
    category: Any = "",
    entity_type: str,
    entity_label: Any,
    metric: str,
    value: Any,
    unit: Any = "",
    raw_value: Any = "",
    numeric_value: Any = "",
    relationship_type: str = "",
    included: bool = True,
    exclusion_reason: str = "",
    filter_reason: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "figure_id": figure_id,
        "panel_id": panel_id,
        "panel_title": panel_title,
        "source_table": source_table,
        "paper_id": paper_id,
        "category": category,
        "entity_type": entity_type,
        "entity_label": entity_label,
        "metric": metric,
        "value": value,
        "unit": unit,
        "raw_value": raw_value,
        "numeric_value": numeric_value,
        "relationship_type": relationship_type,
        "included_in_main_plot": bool(included),
        "exclusion_reason": exclusion_reason,
        "filter_reason": filter_reason,
        "notes": notes,
    }


def _missing_ratios(frame: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    ratios = {}
    for column in columns:
        if column in frame.columns:
            ratios[column] = float(frame[column].isna().mean())
    return ratios


def _nunique(frame: pd.DataFrame, column: str) -> int:
    return int(frame[column].nunique()) if column in frame.columns else 0


def _value_distribution(frame: pd.DataFrame, column: str, top_n: int = 20) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    counts = frame[column].fillna("<NA>").astype(str).value_counts().head(top_n)
    return {key: int(value) for key, value in counts.items()}


def _unknown_other_ratio_by_column(frame: pd.DataFrame) -> dict[str, float]:
    ratios = {}
    for column in ["parameter_family", "process_step_family", "normalized_spectra_type", "link_family", "category"]:
        if column in frame.columns:
            ratios[column] = _token_ratio(frame, column, UNKNOWN_TOKENS)
    return ratios


def _availability(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns or frame.empty:
        return 0.0
    return float(frame[column].notna().mean())


def _outlier_ranges(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for column in ["numeric_value", "peak_value", "parameter_count", "candidate_count", "success_count", "coverage_rate"]:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not values.empty:
                stats[column] = {
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "q01": float(values.quantile(0.01)),
                    "q99": float(values.quantile(0.99)),
                }
    return stats


def _table_role(name: str) -> str:
    if name in {"category_summary.csv", "normalized_parameters.csv", "parameter_family_by_category.csv", "normalized_process_steps.csv", "process_step_by_category.csv", "process_parameter_matrix.csv", "normalized_stage4_spectra.csv", "normalized_stage4_peaks.csv", "spectra_type_by_category.csv", "spectra_parameter_matrix.csv", "normalized_stage5_links.csv", "evidence_parameter_matrix.csv"}:
        return "main"
    if name in {"normalized_sample_matrix.csv", "stage3_paper_summary.csv", "stage4_paper_summary.csv"}:
        return "supplementary"
    return "qa"


def _token_ratio(frame: pd.DataFrame, column: str, tokens: set[str]) -> float:
    if column not in frame.columns or frame.empty:
        return 0.0
    values = frame[column].fillna("").astype(str).str.strip().str.lower()
    return float(values.isin(tokens).mean())


def _peak_unit_summary(peaks: pd.DataFrame) -> dict[str, Any]:
    summary = {}
    mixed = []
    ready = True
    for spectra_type in ["FTIR", "XRD", "NMR", "TG/DSC"]:
        subset = peaks[peaks["normalized_spectra_type"] == spectra_type].copy()
        units = subset["peak_unit"].fillna("<NA>").astype(str).value_counts()
        values = pd.to_numeric(subset["peak_value"], errors="coerce").dropna()
        summary[spectra_type] = {
            "row_count": int(len(subset)),
            "unit_distribution": {key: int(value) for key, value in units.head(10).items()},
            "min": float(values.min()) if not values.empty else None,
            "max": float(values.max()) if not values.empty else None,
            "q01": float(values.quantile(0.01)) if not values.empty else None,
            "q99": float(values.quantile(0.99)) if not values.empty else None,
        }
        if len([unit for unit in units.index if unit not in {"<NA>"}]) > 1:
            mixed.append(spectra_type)
        if spectra_type in {"NMR", "TG/DSC"}:
            ready = False
    return {
        "by_spectra_type": summary,
        "mixed_unit_types": mixed,
        "ready_for_main_hist_panels": ready,
    }


def _old_figure_recommendation(shortlist_role: str, figure_id: str) -> str:
    if figure_id in FALLBACK_EMPTY_FIGURES:
        return "discard"
    if shortlist_role == "main_candidate":
        return "rebuild_as_main"
    if shortlist_role == "supplementary_candidate":
        return "rebuild_as_extended"
    if shortlist_role == "qa_only":
        return "qa_only"
    if shortlist_role == "needs_redraw":
        return "rebuild_as_extended"
    return "discard"


def _visual_value_score(problem_types: list[str], tier: str) -> int:
    score = 4 if tier in {"main", "cross_stage"} else 3
    if "over_auto_plot" in problem_types:
        score -= 2
    if "over_dense" in problem_types:
        score -= 1
    if "qa_only" in problem_types:
        score -= 1
    return max(1, min(5, score))


def _data_risk_score(problem_types: list[str]) -> int:
    score = 1
    for token in ["too_many_unknown_other", "unit_mixing", "extreme_values", "needs_semantic_normalization"]:
        if token in problem_types:
            score += 1
    return min(5, score)


def _main_text_potential(shortlist_role: str, recommendation: str) -> str:
    if recommendation == "rebuild_as_main":
        return "high"
    if shortlist_role in {"supplementary_candidate", "needs_redraw"}:
        return "medium"
    return "low"


def _old_figure_notes(figure_id: str, recommendation: str, problem_types: list[str]) -> str:
    if figure_id in FALLBACK_EMPTY_FIGURES:
        return "Empty fallback figure from genuinely absent data; keep only as QA evidence if needed."
    if recommendation == "rebuild_as_main":
        return "Reuse the data, but redesign around a manuscript question instead of the atlas layout."
    if recommendation == "rebuild_as_extended":
        return "Data are useful, but the current atlas form should be re-aggregated before publication reuse."
    if recommendation == "qa_only":
        return "Keep for validation/supporting diagnostics, not for main-text storytelling."
    if "over_auto_plot" in problem_types:
        return "Exploratory auto-plot with low manuscript value."
    return "Do not continue this figure in its current form."


def _is_unknown_token(value: str) -> bool:
    return str(value).strip().lower() in UNKNOWN_TOKENS


def _norm_unit(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _unit_safe_for_parameter_family(frame: pd.DataFrame, family: str) -> bool:
    subset = frame[frame["parameter_family"] == family].copy()
    if "normalized_unit" not in subset.columns:
        return True
    units = {str(value) for value in subset["normalized_unit"].dropna().astype(str) if str(value).strip()}
    return len(units) <= 1


def _parameter_cooccurrence(params: pd.DataFrame) -> pd.DataFrame:
    working = params[["paper_id", "sample_id", "parameter_family"]].dropna().copy()
    working = working[~working["parameter_family"].astype(str).str.lower().isin(EXCLUDED_PARAMETER_FAMILIES)]
    pairs: list[dict[str, Any]] = []
    for (_, _), group in working.groupby(["paper_id", "sample_id"]):
        families = sorted(set(group["parameter_family"].astype(str)))
        for row_family in families:
            for col_family in families:
                pairs.append({"row_parameter_family": row_family, "col_parameter_family": col_family, "count": 1})
    if not pairs:
        return pd.DataFrame(columns=["row_parameter_family", "col_parameter_family", "count"])
    return pd.DataFrame(pairs).groupby(["row_parameter_family", "col_parameter_family"], as_index=False)["count"].sum()


def _peak_included(record: pd.Series, *, expected_units: set[str], min_value: float, max_value: float) -> tuple[bool, str]:
    unit = str(record.get("peak_unit", "") or "")
    value = pd.to_numeric(pd.Series([record.get("peak_value")]), errors="coerce").iloc[0]
    if pd.isna(value):
        return False, "missing_numeric_value"
    if unit not in expected_units:
        return False, "unit_mismatch"
    if float(value) < min_value or float(value) > max_value:
        return False, "out_of_range"
    return True, ""
