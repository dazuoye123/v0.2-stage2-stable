from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .io import read_csv


OFFICIAL_CATEGORIES = ["mechanism", "fiber_process", "applications", "rheology"]
NON_PRIMARY_CATEGORIES = {"uncategorized", "unknown", "other", "", "nan", "none", "na"}
CHARACTERIZATION_OUTPUT_FAMILIES = {
    "xrd peak",
    "nmr shift",
    "ftir peak",
    "tg/dsc event",
    "dsc event",
    "raman peak",
    "mass spectrum peak",
    "ferron curve peak",
}
UNKNOWN_OTHER_GROUP = "unknown/other"
TEMPERATURE_FAMILIES = {
    "aging temperature",
    "hydrolysis temperature",
    "peptization temperature",
    "drying temperature",
    "calcination temperature",
    "sintering temperature",
    "holding temperature",
}
TIME_FAMILIES = {
    "aging time",
    "hydrolysis time",
    "peptization time",
    "drying time",
    "holding time",
    "calcination time",
    "sintering time",
}


def load_support_tables(diagnosis_dir: Path) -> dict[str, Any]:
    batch_root = Path(diagnosis_dir).parent
    atlas_root = batch_root / "figure_atlas" / "tables"
    v1_root = batch_root / "manuscript_figures_nature_v1" / "source_data"
    return {
        "atlas_root": atlas_root,
        "v1_root": v1_root,
        "normalized_parameters": read_csv(atlas_root / "normalized_parameters.csv"),
        "normalized_process_steps": read_csv(atlas_root / "normalized_process_steps.csv"),
        "normalized_stage4_spectra": read_csv(atlas_root / "normalized_stage4_spectra.csv"),
        "normalized_stage4_peaks": read_csv(atlas_root / "normalized_stage4_peaks.csv"),
        "normalized_stage5_links": read_csv(atlas_root / "normalized_stage5_links.csv"),
        "stage3_paper_summary": read_csv(atlas_root / "stage3_paper_summary.csv"),
        "stage4_paper_summary": read_csv(atlas_root / "stage4_paper_summary.csv"),
        "fig1_v1_source": read_csv(v1_root / "Fig1_dataset_coverage_source_data.csv"),
    }


def prepare_v2_payload(diagnosis_dir: Path) -> dict[str, Any]:
    tables = load_support_tables(Path(diagnosis_dir))
    paper_category_map = build_paper_category_map(tables)
    fig1_frame, fig1_context, unc_audit = build_fig1_source_data(tables, paper_category_map)
    fig2_frame, fig2_context, fig2_audit = build_fig2_source_data(tables, paper_category_map)
    fig4_frame, fig4_context, fig4_audit = build_fig4_source_data(tables, paper_category_map, fig2_context)
    return {
        "figures": {"Fig1": fig1_frame, "Fig2": fig2_frame, "Fig4": fig4_frame},
        "contexts": {"Fig1": fig1_context, "Fig2": fig2_context, "Fig4": fig4_context},
        "audits": {
            "uncategorized_source_audit.csv": unc_audit,
            "Fig2_unit_filter_audit.csv": fig2_audit,
            "Fig4_peak_bin_audit.csv": fig4_audit,
        },
    }


def build_paper_category_map(tables: dict[str, Any]) -> dict[str, str]:
    frames = []
    for key in ("stage3_paper_summary", "stage4_paper_summary", "normalized_parameters", "normalized_stage4_spectra", "normalized_stage5_links"):
        frame = tables[key].copy()
        category_col = "paper_category" if "paper_category" in frame.columns else "category"
        if "paper_id" not in frame.columns or category_col not in frame.columns:
            continue
        subset = frame[["paper_id", category_col]].dropna().rename(columns={category_col: "category"})
        subset["category"] = subset["category"].astype(str)
        subset = subset[subset["category"].isin(OFFICIAL_CATEGORIES)]
        frames.append(subset)
    combined = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["paper_id", "category"])
    combined = combined.sort_values(["paper_id", "category"])
    return combined.drop_duplicates(subset=["paper_id"], keep="first").set_index("paper_id")["category"].to_dict()


def build_fig1_source_data(tables: dict[str, Any], paper_category_map: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    stage3 = tables["stage3_paper_summary"].copy()
    stage4 = tables["stage4_paper_summary"].copy()
    params = attach_resolved_category(tables["normalized_parameters"].copy(), paper_category_map)
    process_steps = attach_resolved_category(tables["normalized_process_steps"].copy(), paper_category_map)
    spectra = attach_resolved_category(tables["normalized_stage4_spectra"].copy(), paper_category_map)
    links = attach_resolved_category(tables["normalized_stage5_links"].copy(), paper_category_map)

    official_stage3 = stage3[stage3["category"].isin(OFFICIAL_CATEGORIES)].copy()
    official_stage4 = stage4[stage4["category"].isin(OFFICIAL_CATEGORIES)].copy()
    total_papers = int(official_stage3["paper_id"].nunique())

    rows: list[dict[str, Any]] = []
    object_metrics = {
        "paper": official_stage3.groupby("category")["paper_id"].nunique(),
        "sample": official_stage3.groupby("category")["sample_count"].sum(),
        "parameter": params[params["resolved_category"].isin(OFFICIAL_CATEGORIES)].groupby("resolved_category")["parameter_id"].nunique(),
        "process_step": process_steps[process_steps["resolved_category"].isin(OFFICIAL_CATEGORIES)].groupby("resolved_category")["process_step_id"].nunique(),
        "spectra": spectra[spectra["resolved_category"].isin(OFFICIAL_CATEGORIES)].groupby("resolved_category")["spectra_id"].nunique(),
        "link": links[links["resolved_category"].isin(OFFICIAL_CATEGORIES)]["link_count_or_weight"].fillna(1).groupby(links["resolved_category"]).sum(),
    }

    for category in OFFICIAL_CATEGORIES:
        for object_type, series in object_metrics.items():
            value = float(series.get(category, 0.0))
            rows.append(
                base_row(
                    figure_id="Fig1",
                    panel_id="A",
                    panel_title="Dataset object counts by category",
                    source_table=f"{object_type}_summary",
                    category=category,
                    entity_type="object_type",
                    entity_label=object_type,
                    metric="count",
                    value=value,
                    unit="count",
                    raw_value=value,
                    included=True,
                )
            )

    b_rows = [
        ("paper_stage_completion", "papers_with_stage3", official_stage3["paper_id"].nunique() / max(total_papers, 1), official_stage3["paper_id"].nunique(), "stage3_paper_summary.csv"),
        ("paper_stage_completion", "papers_with_stage4", official_stage4["paper_id"].nunique() / max(total_papers, 1), official_stage4["paper_id"].nunique(), "stage4_paper_summary.csv"),
        ("paper_stage_completion", "papers_with_final_dataset", params[params["resolved_category"].isin(OFFICIAL_CATEGORIES)]["paper_id"].nunique() / max(total_papers, 1), params[params["resolved_category"].isin(OFFICIAL_CATEGORIES)]["paper_id"].nunique(), "normalized_parameters.csv"),
        ("paper_stage_completion", "papers_with_link_export", links[links["resolved_category"].isin(OFFICIAL_CATEGORIES)]["paper_id"].nunique() / max(total_papers, 1), links[links["resolved_category"].isin(OFFICIAL_CATEGORIES)]["paper_id"].nunique(), "normalized_stage5_links.csv"),
    ]
    stage4_candidate_sum = float(official_stage4["candidate_count"].fillna(0).sum())
    stage4_success_sum = float(official_stage4["success_count"].fillna(0).sum())
    stage4_validated_sum = float(official_stage4["validated_count"].fillna(0).sum())
    stage4_failed_sum = float(official_stage4["failed_count"].fillna(0).sum())
    if stage4_candidate_sum > 0:
        b_rows.extend(
            [
                ("stage4_extraction_rate", "success_over_candidate", stage4_success_sum / stage4_candidate_sum, stage4_success_sum, "stage4_paper_summary.csv"),
                ("stage4_extraction_rate", "validated_over_candidate", stage4_validated_sum / stage4_candidate_sum, stage4_validated_sum, "stage4_paper_summary.csv"),
                ("stage4_extraction_rate", "failed_over_candidate", stage4_failed_sum / stage4_candidate_sum, stage4_failed_sum, "stage4_paper_summary.csv"),
            ]
        )
    for metric_group, entity_label, fraction, numerator, source_table in b_rows:
        rows.append(
            base_row(
                figure_id="Fig1",
                panel_id="B",
                panel_title="Stage coverage summary",
                source_table=source_table,
                category="all_official_categories",
                entity_type="coverage_metric",
                entity_label=entity_label,
                metric=metric_group,
                value=float(fraction),
                unit="fraction",
                raw_value=float(numerator),
                numeric_value=float(fraction),
                included=True,
                notes=f"fraction={numerator}/{total_papers if metric_group == 'paper_stage_completion' else stage4_candidate_sum}",
            )
        )

    total_parameters = params[params["resolved_category"].isin(OFFICIAL_CATEGORIES)].groupby("resolved_category")["parameter_id"].nunique()
    join_key_used = "parameter_id"
    for category in OFFICIAL_CATEGORIES:
        category_total = int(total_parameters.get(category, 0))
        for link_type in ["sample", "evidence", "process_step", "spectra"]:
            linked = int(
                links[
                    (links["resolved_category"] == category)
                    & (links["link_family"].astype(str) == link_type)
                    & (links["parameter_id"].notna())
                ]["parameter_id"].nunique()
            )
            fraction = float(linked / category_total) if category_total else 0.0
            rows.append(
                base_row(
                    figure_id="Fig1",
                    panel_id="C",
                    panel_title="Link completeness by category",
                    source_table="normalized_parameters.csv;normalized_stage5_links.csv",
                    category=category,
                    entity_type="link_family",
                    entity_label=link_type,
                    metric="completeness_fraction",
                    value=fraction,
                    unit="fraction",
                    raw_value=float(linked),
                    numeric_value=float(category_total),
                    relationship_type="linked_parameters/total_parameters",
                    included=True,
                    notes=f"linked={linked}; total={category_total}",
                    total_parameters=category_total,
                    linked_parameters=linked,
                    completeness_fraction=fraction,
                    join_key_used=join_key_used,
                    limitation="parameter_id-based join",
                )
            )

    availability_rows = []
    for category in OFFICIAL_CATEGORIES:
        paper_count = float(object_metrics["paper"].get(category, 0))
        for object_type, series in object_metrics.items():
            raw_count = float(series.get(category, 0))
            per_paper_mean = raw_count / paper_count if paper_count else 0.0
            availability_rows.append(
                {
                    "category": category,
                    "object_type": object_type,
                    "raw_count": raw_count,
                    "paper_count": paper_count,
                    "per_paper_mean": per_paper_mean,
                }
            )
    availability_df = pd.DataFrame(availability_rows)
    availability_df["normalized_value"] = availability_df.groupby("object_type")["per_paper_mean"].transform(lambda s: s / max(float(s.max()), 1.0))
    for row in availability_df.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig1",
                panel_id="D",
                panel_title="Data availability matrix",
                source_table="derived_from_panel_A_counts",
                category=str(row["category"]),
                entity_type="object_type",
                entity_label=str(row["object_type"]),
                metric="normalized_per_paper_mean",
                value=float(row["normalized_value"]),
                unit="fraction",
                raw_value=float(row["raw_count"]),
                numeric_value=float(row["per_paper_mean"]),
                included=True,
                notes=f"per_paper_mean={row['per_paper_mean']:.4f}",
                paper_count=float(row["paper_count"]),
            )
        )

    unc_audit = build_uncategorized_source_audit(tables["fig1_v1_source"], paper_category_map)
    for row in unc_audit.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig1",
                panel_id=str(row["panel_id"]),
                panel_title="Excluded non-primary category rows",
                source_table=str(row["source_table"]),
                category=row["category"] if pd.notna(row["category"]) else "",
                entity_type=str(row["entity_type"]),
                entity_label=str(row.get("entity_label", row.get("metric", "uncategorized"))),
                metric=str(row["metric"]),
                value=float(row["value"]) if pd.notna(row["value"]) else 0.0,
                unit="count_or_fraction",
                raw_value=float(row["value"]) if pd.notna(row["value"]) else 0.0,
                paper_id=str(row["paper_id"]) if pd.notna(row["paper_id"]) else "",
                included=False,
                exclusion_reason="missing_or_non_primary_category",
                filter_reason=str(row["likely_reason"]),
                notes=str(row["recommended_action"]),
            )
        )

    frame = pd.DataFrame(rows)
    context = {
        "title": "Dataset coverage and extraction reliability",
        "panel_descriptions": [
            "A. Dataset object counts by official research category across papers, parameters, samples, process steps, spectra, and links.",
            "B. Fraction-based stage coverage summary separating paper-level completion from Stage4 figure extraction rates.",
            "C. Link completeness calculated as linked parameters divided by total parameters for each category and link type.",
            "D. Category by object-type availability matrix using normalized per-paper mean counts.",
        ],
        "filters_applied": [
            "Only official categories entered the main panels: mechanism, fiber_process, applications, rheology.",
            "Non-primary and uncategorized rows were retained in source data with included_in_main_plot=false.",
            "Count panels and fraction panels were separated to avoid mixed-axis interpretation.",
        ],
        "unknown_other_handling": "Non-primary and uncategorized rows were excluded from main panels and retained in source data for traceability.",
        "unit_handling": "Panel A uses raw counts on a log-scaled axis when needed; panels B-D use fractions or normalized per-paper means only.",
        "category_handling": "Categories were resolved from paper-level Stage3/Stage4 summaries before plotting; unresolved rows stayed excluded.",
        "limitations": [
            "Availability and completeness describe structured extraction coverage, not semantic correctness of every upstream record.",
        ],
        "official_categories": OFFICIAL_CATEGORIES,
        "uncategorized_excluded_count": int(len(unc_audit)),
        "link_completeness_formula": "linked_parameters / total_parameters",
        "join_key_used": join_key_used,
        "completeness_value_range": [0.0, 1.0],
        "excluded_row_counts": {"uncategorized_or_non_primary": int(len(unc_audit))},
        "expected_claim": "The database provides broad multi-category coverage and a traceable extraction/linking basis for downstream synthesis and characterization analysis.",
        "normalization_method_panel_d": "normalized per-paper mean within each object type",
    }
    return frame, context, unc_audit


def build_uncategorized_source_audit(fig1_v1_source: pd.DataFrame, paper_category_map: dict[str, str]) -> pd.DataFrame:
    unc = fig1_v1_source[
        fig1_v1_source["category"].isna()
        | fig1_v1_source["category"].astype(str).str.strip().str.lower().isin(NON_PRIMARY_CATEGORIES)
    ].copy()
    reasons = []
    actions = []
    for row in unc.to_dict(orient="records"):
        source_table = str(row.get("source_table", ""))
        raw_paper_id = row.get("paper_id", "")
        paper_id = "" if pd.isna(raw_paper_id) else str(raw_paper_id or "")
        category = str(row.get("category", "") or "")
        metric = str(row.get("metric", "") or "")
        if paper_id and "flat" in paper_id.lower():
            reason = "flat_test_paper"
        elif source_table == "category_summary.csv":
            reason = "aggregate_row_without_category"
        elif source_table == "normalized_parameters.csv":
            reason = "failed_category_join"
        elif paper_id and paper_id not in paper_category_map:
            reason = "missing category"
        elif "test" in source_table.lower():
            reason = "old_test_output"
        elif category and category.lower() in NON_PRIMARY_CATEGORIES:
            reason = "non_primary_category"
        else:
            reason = "unknown"
        if metric.endswith("count"):
            action = "recompute from official-category tables; exclude from main panels"
        else:
            action = "retain in source_data only; exclude from main panels"
        reasons.append(reason)
        actions.append(action)
    unc = unc.assign(likely_reason=reasons, recommended_action=actions)
    ordered_cols = [
        "source_table",
        "panel_id",
        "metric",
        "entity_type",
        "paper_id",
        "category",
        "value",
        "likely_reason",
        "recommended_action",
    ]
    for col in ordered_cols:
        if col not in unc.columns:
            unc[col] = ""
    return unc[ordered_cols].copy()


def build_fig2_source_data(tables: dict[str, Any], paper_category_map: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    params = attach_resolved_category(tables["normalized_parameters"].copy(), paper_category_map)
    params["display_family"] = params.apply(infer_display_family, axis=1)
    params["manuscript_parameter_group"] = params.apply(map_manuscript_parameter_group, axis=1)
    params["is_characterization_output"] = params["display_family"].astype(str).str.lower().isin(CHARACTERIZATION_OUTPUT_FAMILIES)
    params["is_official_category"] = params["resolved_category"].isin(OFFICIAL_CATEGORIES)
    params["is_unknown_other_group"] = params["manuscript_parameter_group"].eq(UNKNOWN_OTHER_GROUP)
    params["base_included"] = params["is_official_category"] & ~params["is_characterization_output"] & ~params["is_unknown_other_group"]
    params["category"] = params["resolved_category"]

    audit = params.copy()
    audit["panel_id"] = "QC"
    audit["included_in_plot"] = audit["base_included"]
    audit["filter_reason"] = np.where(~audit["is_official_category"], "missing_or_non_primary_category", "")
    audit["exclusion_reason"] = np.where(audit["is_characterization_output"], "characterization_output_not_synthesis_parameter", "")
    audit.loc[audit["is_unknown_other_group"], "exclusion_reason"] = "unknown_or_other_parameter_group"

    rows: list[dict[str, Any]] = []

    a_counts = (
        params[params["base_included"]]
        .groupby(["resolved_category", "manuscript_parameter_group"])["parameter_id"]
        .nunique()
        .reset_index(name="count")
    )
    for row in a_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig2",
                panel_id="A",
                panel_title="Category x manuscript parameter group heatmap",
                source_table="normalized_parameters.csv",
                category=str(row["resolved_category"]),
                entity_type="manuscript_parameter_group",
                entity_label=str(row["manuscript_parameter_group"]),
                metric="parameter_count",
                value=float(row["count"]),
                unit="count",
                raw_value=float(row["count"]),
                included=True,
                manuscript_parameter_group=str(row["manuscript_parameter_group"]),
            )
        )

    b_counts = (
        params[params["base_included"]]
        .groupby(["display_family", "manuscript_parameter_group"])["parameter_id"]
        .nunique()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(15)
    )
    for row in b_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig2",
                panel_id="B",
                panel_title="Top synthesis, process, and property parameter families",
                source_table="normalized_parameters.csv",
                category="all_official_categories",
                entity_type="parameter_family",
                entity_label=str(row["display_family"]),
                metric="parameter_count",
                value=float(row["count"]),
                unit="count",
                raw_value=float(row["count"]),
                included=True,
                manuscript_parameter_group=str(row["manuscript_parameter_group"]),
            )
        )

    pH_rows = params[
        params["is_official_category"]
        & (params["display_family"].astype(str) == "pH")
    ].copy()
    pH_rows["panel_id"] = "C"
    pH_rows["included_in_main_plot"] = pH_rows["numeric_value"].apply(lambda x: pd.notna(x)) & pH_rows["normalized_unit"].fillna("unitless").astype(str).eq("unitless")
    pH_rows["filter_reason"] = np.where(pH_rows["included_in_main_plot"], "", "non_unitless_or_missing_pH_value")
    pH_rows["exclusion_reason"] = np.where(~pH_rows["included_in_main_plot"], "invalid_pH_numeric_row", "")
    for row in pH_rows.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig2",
                panel_id="C",
                panel_title="Solution chemistry distributions",
                source_table="normalized_parameters.csv",
                category=str(row["resolved_category"]),
                entity_type="parameter_row",
                entity_label="pH",
                metric="numeric_distribution",
                value=safe_float(row.get("numeric_value")),
                unit="unitless",
                raw_value=safe_float(row.get("raw_value")),
                numeric_value=safe_float(row.get("numeric_value")),
                paper_id=str(row["paper_id"]),
                included=bool(row["included_in_main_plot"]),
                exclusion_reason=str(row["exclusion_reason"]),
                filter_reason=str(row["filter_reason"]),
                manuscript_parameter_group="solution chemistry",
                parameter_family="pH",
                raw_unit=row.get("raw_unit"),
                normalized_unit=row.get("normalized_unit"),
            )
        )

    temp_candidates = params.copy()
    temp_candidates["panel_id"] = "D"
    temp_candidates[["converted_value", "panel_included", "panel_filter_reason", "panel_normalized_unit"]] = temp_candidates.apply(
        lambda row: pd.Series(normalize_temperature_row(row)),
        axis=1,
    )
    for row in temp_candidates[temp_candidates["is_official_category"]].to_dict(orient="records"):
        if is_temperature_or_time_related(row):
            rows.append(
                base_row(
                    figure_id="Fig2",
                    panel_id="D",
                    panel_title="Temperature condition windows",
                    source_table="normalized_parameters.csv",
                    category=str(row["resolved_category"]),
                    entity_type="temperature_parameter",
                    entity_label=str(row["display_family"]),
                    metric="temperature_C",
                    value=safe_float(row["converted_value"]),
                    unit="deg C",
                    raw_value=safe_float(row.get("raw_value")),
                    numeric_value=safe_float(row["converted_value"]),
                    paper_id=str(row["paper_id"]),
                    included=bool(row["panel_included"]),
                    exclusion_reason="" if bool(row["panel_included"]) else "temperature_filter_exclusion",
                    filter_reason=str(row["panel_filter_reason"]),
                    manuscript_parameter_group=str(row["manuscript_parameter_group"]),
                    parameter_family=str(row["display_family"]),
                    raw_unit=row.get("raw_unit"),
                    normalized_unit=row.get("panel_normalized_unit"),
                )
            )

    time_candidates = params.copy()
    time_candidates["panel_id"] = "E"
    time_candidates[["converted_value", "panel_included", "panel_filter_reason", "panel_normalized_unit"]] = time_candidates.apply(
        lambda row: pd.Series(normalize_time_row(row)),
        axis=1,
    )
    for row in time_candidates[time_candidates["is_official_category"]].to_dict(orient="records"):
        if is_temperature_or_time_related(row):
            rows.append(
                base_row(
                    figure_id="Fig2",
                    panel_id="E",
                    panel_title="Time condition windows",
                    source_table="normalized_parameters.csv",
                    category=str(row["resolved_category"]),
                    entity_type="time_parameter",
                    entity_label=str(row["display_family"]),
                    metric="time_h",
                    value=safe_float(row["converted_value"]),
                    unit="h",
                    raw_value=safe_float(row.get("raw_value")),
                    numeric_value=safe_float(row["converted_value"]),
                    paper_id=str(row["paper_id"]),
                    included=bool(row["panel_included"]),
                    exclusion_reason="" if bool(row["panel_included"]) else "time_filter_exclusion",
                    filter_reason=str(row["panel_filter_reason"]),
                    manuscript_parameter_group=str(row["manuscript_parameter_group"]),
                    parameter_family=str(row["display_family"]),
                    raw_unit=row.get("raw_unit"),
                    normalized_unit=row.get("panel_normalized_unit"),
                )
            )

    co_source = params[params["base_included"]].copy()
    co_source["co_group_id"] = co_source["sample_id"].fillna("") + "::" + co_source["paper_id"].astype(str)
    co_source.loc[co_source["sample_id"].fillna("") == "", "co_group_id"] = co_source.loc[co_source["sample_id"].fillna("") == "", "paper_id"].astype(str)
    family_freq = co_source.groupby("display_family")["parameter_id"].nunique().sort_values(ascending=False)
    top_families = family_freq.head(12).index.tolist()
    diag_counts = (
        co_source[co_source["display_family"].isin(top_families)]
        .groupby(["co_group_id"])["display_family"]
        .unique()
    )
    pair_counts: dict[tuple[str, str], int] = {}
    for families in diag_counts.tolist():
        families = sorted(set(f for f in families if f in top_families))
        for fam in families:
            pair_counts[(fam, fam)] = pair_counts.get((fam, fam), 0) + 1
        for idx, left in enumerate(families):
            for right in families[idx + 1 :]:
                pair_counts[(left, right)] = pair_counts.get((left, right), 0) + 1
                pair_counts[(right, left)] = pair_counts.get((right, left), 0) + 1
    for (left, right), count in pair_counts.items():
        rows.append(
            base_row(
                figure_id="Fig2",
                panel_id="F",
                panel_title="Parameter co-occurrence matrix",
                source_table="normalized_parameters.csv",
                category="all_official_categories",
                entity_type="parameter_pair",
                entity_label=f"{left} -> {right}",
                metric="co_occurrence",
                value=float(count),
                unit="count",
                raw_value=float(count),
                relationship_type="co_occurrence",
                included=True,
            )
        )

    qc_cols = [
        "raw_value",
        "numeric_value",
        "raw_unit",
        "normalized_unit",
        "parameter_family",
        "manuscript_parameter_group",
        "panel_id",
        "included_in_plot",
        "filter_reason",
        "exclusion_reason",
    ]
    for col in qc_cols:
        if col not in audit.columns:
            audit[col] = ""
    fig2_audit = audit[qc_cols].copy()

    excluded_characterization = sorted(params.loc[params["is_characterization_output"], "display_family"].dropna().astype(str).unique().tolist())
    number_excluded_by_unit = int((temp_candidates["panel_filter_reason"].astype(str).str.contains("unsupported_")).sum() + (time_candidates["panel_filter_reason"].astype(str).str.contains("unsupported_")).sum())
    number_excluded_by_range = int((temp_candidates["panel_filter_reason"].astype(str).str.contains("outside_")).sum() + (time_candidates["panel_filter_reason"].astype(str).str.contains("outside_")).sum())

    source_qc_rows = audit.copy()
    source_qc_rows = source_qc_rows.assign(
        figure_id="Fig2",
        panel_id="QC",
        panel_title="Traceability and exclusion audit",
        source_table="normalized_parameters.csv",
        category=source_qc_rows["resolved_category"].fillna(""),
        entity_type="parameter_row",
        entity_label=source_qc_rows["display_family"],
        metric="parameter_audit",
        value=source_qc_rows["numeric_value"].fillna(0),
        unit=source_qc_rows["normalized_unit"].fillna(""),
        relationship_type="audit",
        included_in_main_plot=source_qc_rows["included_in_plot"],
        notes="row-level parameter audit",
    )
    frame = pd.concat([pd.DataFrame(rows), source_qc_rows.reindex(columns=pd.DataFrame(rows).columns, fill_value="")], ignore_index=True)

    context = {
        "title": "Synthesis parameter landscape of alumina sols",
        "panel_descriptions": [
            "A. Category by manuscript-parameter-group heatmap restricted to synthesis, process, rheology, and property descriptors.",
            "B. Top synthesis, process, and property parameter families after excluding characterization-output families.",
            "C. pH distribution with concentration-like variables retained as availability-only trace rows because their units remained mixed.",
            "D. Temperature condition windows after unit-aware conversion to degrees Celsius and range filtering.",
            "E. Time condition windows after unit-aware conversion to hours and range filtering.",
            "F. Parameter co-occurrence matrix showing only co-occurrence, not causal relations.",
        ],
        "filters_applied": [
            "Characterization-output families were excluded from synthesis-parameter panels.",
            "Unknown/other groups were retained in source data and excluded from main panels.",
            "Temperature and time windows were separated after unit-aware filtering.",
        ],
        "unknown_other_handling": "Unknown/other groups stayed in source data with included_in_main_plot=false and were excluded from main panels.",
        "unit_handling": "Panel D converts supported temperature units to deg C in the 0-1800 range; panel E converts supported time units to hours in the 0-10000 range.",
        "category_handling": "Only official categories were plotted; recovered categories were joined from paper-level summaries when possible.",
        "limitations": [
            "Concentration-like variables remain availability summaries only because their units are still mixed across papers.",
        ],
        "expected_claim": "The extracted literature reveals a structured synthesis-parameter landscape centered on solution chemistry, composition/additive choices, aging or hydrolysis, thermal processing, rheology, and morphology or property descriptors.",
        "excluded_characterization_families": excluded_characterization,
        "manuscript_parameter_group_mapping": manuscript_parameter_group_mapping_description(),
        "temperature_unit_conversion": {"°C": "deg C", "C": "deg C", "℃": "deg C", "deg C": "deg C", "Celsius": "deg C"},
        "time_unit_conversion": {"s": "h", "sec": "h", "second": "h", "seconds": "h", "min": "h", "minute": "h", "minutes": "h", "h": "h", "hr": "h", "hour": "h", "hours": "h", "day": "h", "days": "h"},
        "temperature_filter_range": [0, 1800],
        "time_filter_range": [0, 10000],
        "number_of_rows_excluded_by_unit": number_excluded_by_unit,
        "number_of_rows_excluded_by_range": number_excluded_by_range,
        "excluded_row_counts": {
            "characterization_output": int(params["is_characterization_output"].sum()),
            "unknown_or_other_group": int(params["is_unknown_other_group"].sum()),
            "non_primary_category": int((~params["is_official_category"]).sum()),
        },
    }
    return frame, context, fig2_audit


def build_fig4_source_data(
    tables: dict[str, Any],
    paper_category_map: dict[str, str],
    fig2_context: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    spectra = attach_resolved_category(tables["normalized_stage4_spectra"].copy(), paper_category_map)
    peaks = attach_resolved_category(tables["normalized_stage4_peaks"].copy(), paper_category_map)
    links = attach_resolved_category(tables["normalized_stage5_links"].copy(), paper_category_map)
    params = attach_resolved_category(tables["normalized_parameters"].copy(), paper_category_map)
    params["display_family"] = params.apply(infer_display_family, axis=1)
    params["manuscript_parameter_group"] = params.apply(map_manuscript_parameter_group, axis=1)
    params["is_characterization_output"] = params["display_family"].astype(str).str.lower().isin(CHARACTERIZATION_OUTPUT_FAMILIES)
    params["is_unknown_other_group"] = params["manuscript_parameter_group"].eq(UNKNOWN_OTHER_GROUP)
    param_lookup = params.set_index("parameter_id")[["display_family", "manuscript_parameter_group", "is_characterization_output", "is_unknown_other_group"]].to_dict(orient="index")

    spectra["is_official_category"] = spectra["resolved_category"].isin(OFFICIAL_CATEGORIES)
    spectra["include_main"] = spectra["is_official_category"] & ~spectra["normalized_spectra_type"].astype(str).str.lower().isin({"unknown", "other"})
    spectra["category"] = spectra["resolved_category"]

    rows: list[dict[str, Any]] = []
    a_counts = (
        spectra[spectra["include_main"]]
        .groupby(["resolved_category", "normalized_spectra_type"])["spectra_id"]
        .nunique()
        .reset_index(name="count")
    )
    for row in a_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig4",
                panel_id="A",
                panel_title="Characterization family x category heatmap",
                source_table="normalized_stage4_spectra.csv",
                category=str(row["resolved_category"]),
                entity_type="spectra_type",
                entity_label=str(row["normalized_spectra_type"]),
                metric="spectra_count",
                value=float(row["count"]),
                unit="count",
                raw_value=float(row["count"]),
                included=True,
            )
        )

    det_links = links[
        links["resolved_category"].isin(OFFICIAL_CATEGORIES)
        & links["link_family"].astype(str).eq("spectra")
        & links["match_method"].astype(str).str.startswith("deterministic")
        & ~links["normalized_spectra_type"].fillna("").astype(str).str.lower().isin({"unknown", "other"})
    ].copy()
    det_links["display_family"] = det_links["parameter_id"].map(lambda x: param_lookup.get(x, {}).get("display_family", ""))
    det_links["manuscript_parameter_group"] = det_links["parameter_id"].map(lambda x: param_lookup.get(x, {}).get("manuscript_parameter_group", UNKNOWN_OTHER_GROUP))
    det_links["is_characterization_output"] = det_links["parameter_id"].map(lambda x: bool(param_lookup.get(x, {}).get("is_characterization_output", False)))
    det_links["is_unknown_other_group"] = det_links["parameter_id"].map(lambda x: bool(param_lookup.get(x, {}).get("is_unknown_other_group", True)))
    det_links = det_links[
        (~det_links["is_characterization_output"])
        & (~det_links["is_unknown_other_group"])
        & det_links["display_family"].astype(str).ne("")
    ].copy()

    top_param = det_links.groupby("display_family")["parameter_id"].nunique().sort_values(ascending=False).head(10).index.tolist()
    b_counts = (
        det_links[det_links["display_family"].isin(top_param)]
        .groupby(["normalized_spectra_type", "display_family"])["parameter_id"]
        .nunique()
        .reset_index(name="count")
    )
    for row in b_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig4",
                panel_id="B",
                panel_title="Spectra type x parameter family deterministic-link heatmap",
                source_table="normalized_stage5_links.csv;normalized_parameters.csv",
                category="all_official_categories",
                entity_type="deterministic_link",
                entity_label=f"{row['normalized_spectra_type']} -> {row['display_family']}",
                metric="deterministic_link_count",
                value=float(row["count"]),
                unit="count",
                raw_value=float(row["count"]),
                relationship_type="deterministic_link",
                included=True,
            )
        )

    linked_total = max(int(det_links["parameter_id"].nunique()), 1)
    c_counts = det_links.groupby("normalized_spectra_type")["parameter_id"].nunique().sort_values(ascending=False).reset_index(name="linked_parameter_count")
    c_counts["linked_parameter_fraction"] = c_counts["linked_parameter_count"] / linked_total
    for row in c_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig4",
                panel_id="C",
                panel_title="Characterization-family contribution to linked parameters",
                source_table="normalized_stage5_links.csv;normalized_parameters.csv",
                category="all_official_categories",
                entity_type="spectra_type",
                entity_label=str(row["normalized_spectra_type"]),
                metric="linked_parameter_count",
                value=float(row["linked_parameter_count"]),
                unit="count",
                raw_value=float(row["linked_parameter_fraction"]),
                numeric_value=float(row["linked_parameter_fraction"]),
                relationship_type="deterministic_link",
                included=True,
                notes=f"fraction={row['linked_parameter_fraction']:.4f}",
            )
        )

    peak_audit = build_peak_bin_audit(peaks)
    d_counts = (
        peak_audit[peak_audit["included_in_plot"]]
        .groupby(["spectra_type", "bin_label"])["raw_value"]
        .count()
        .reset_index(name="count")
    )
    for row in d_counts.to_dict(orient="records"):
        rows.append(
            base_row(
                figure_id="Fig4",
                panel_id="D",
                panel_title="Approximate peak and event group summary",
                source_table="normalized_stage4_peaks.csv",
                category="all_official_categories",
                entity_type="peak_bin",
                entity_label=f"{row['spectra_type']} -> {row['bin_label']}",
                metric="binned_peak_count",
                value=float(row["count"]),
                unit="count",
                raw_value=float(row["count"]),
                relationship_type="approximate_bin",
                included=True,
                bin_family=str(row["spectra_type"]),
                bin_label=str(row["bin_label"]),
            )
        )

    peak_source_rows = peak_audit.assign(
        figure_id="Fig4",
        panel_id="D_raw",
        panel_title="Raw peak and event audit rows",
        source_table="normalized_stage4_peaks.csv",
        category=peak_audit["resolved_category"].fillna(""),
        entity_type="peak_row",
        entity_label=peak_audit["spectra_type"],
        metric="peak_audit",
        value=peak_audit["numeric_value"].fillna(0),
        unit=peak_audit["normalized_unit"].fillna(""),
        relationship_type="audit",
        included_in_main_plot=peak_audit["included_in_plot"],
        notes="raw peak rows retained for traceability",
    )
    frame = pd.concat([pd.DataFrame(rows), peak_source_rows.reindex(columns=pd.DataFrame(rows).columns, fill_value="")], ignore_index=True)

    context = {
        "title": "Characterization evidence atlas",
        "panel_descriptions": [
            "A. Characterization family by category heatmap using official categories only.",
            "B. Deterministic spectra-to-parameter-family heatmap excluding co-occurrence-only relations.",
            "C. Characterization-family contribution to linked parameters based on deterministic spectra links.",
            "D. Approximate literature-informed peak and event bins for FTIR, XRD, NMR, and TG or DSC evidence summarization.",
        ],
        "filters_applied": [
            "Unknown and other spectra types were retained in source data and excluded from the main panels.",
            "Panel B uses deterministic spectra links only and excludes co-occurrence-only relations.",
            "Raw peak values were converted to approximate literature-informed bins before panel D aggregation.",
        ],
        "unknown_other_handling": "Unknown and other spectra types were excluded from the main panels and retained in source data.",
        "unit_handling": "Peak rows were filtered by spectra-type-specific accepted units and plausible numeric ranges before binning.",
        "category_handling": "Official categories only; recovered categories were joined from paper-level summaries when available.",
        "limitations": [
            "Peak and event bins are approximate literature-informed intervals and are used for evidence summarization, not definitive phase assignment.",
            "Deterministic spectra links still depend on upstream normalization quality and should be spot-checked before submission.",
        ],
        "expected_claim": "Spectroscopic, diffraction, thermal, and microscopy-derived evidence form complementary characterization fingerprints linked to different parameter families.",
        "peak_bin_definitions": peak_bin_definitions(),
        "raw_peak_count": int(len(peak_audit)),
        "binned_peak_count": int(peak_audit["included_in_plot"].sum()),
        "excluded_peak_count": int((~peak_audit["included_in_plot"]).sum()),
        "accepted_units": {
            "FTIR": ["cm^-1"],
            "XRD": ["2θ degree", "2theta_deg", "2Theta(degree)", "degrees 2-theta"],
            "NMR": ["ppm"],
            "TG/DSC": ["°C", "C", "deg C", "missing_unit_assumed_deg_C"],
        },
        "accepted_ranges": {
            "FTIR": [400, 4000],
            "XRD": [5, 90],
            "NMR": [-20, 90],
            "TG/DSC": [0, 1400],
        },
        "statement_that_bins_are_approximate": "Peak/event bins are approximate literature-informed intervals and are used for evidence summarization, not definitive phase assignment.",
        "excluded_row_counts": {
            "unknown_or_other_spectra": int((~spectra["include_main"]).sum()),
            "non_binned_peaks": int((~peak_audit["included_in_plot"]).sum()),
        },
    }
    return frame, context, peak_audit


def build_peak_bin_audit(peaks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in peaks.to_dict(orient="records"):
        spectra_type = str(row.get("normalized_spectra_type", "") or "")
        resolved_category = row.get("resolved_category", "")
        numeric_value = safe_float(row.get("peak_value"))
        raw_unit = row.get("peak_unit", "")
        normalized_unit = normalize_peak_unit(spectra_type, raw_unit)
        included = False
        filter_reason = ""
        bin_family = ""
        bin_label = ""
        if resolved_category not in OFFICIAL_CATEGORIES:
            filter_reason = "missing_or_non_primary_category"
        elif spectra_type in {"Unknown", "Other", ""}:
            filter_reason = "unknown_or_other_spectra_type"
        else:
            included, filter_reason, bin_family, bin_label = assign_peak_bin(spectra_type, numeric_value, normalized_unit)
        rows.append(
            {
                "raw_value": row.get("peak_value"),
                "numeric_value": numeric_value,
                "raw_unit": raw_unit,
                "normalized_unit": normalized_unit,
                "spectra_type": spectra_type,
                "peak_source_field": row.get("peak_source_field", ""),
                "bin_family": bin_family,
                "bin_label": bin_label,
                "included_in_plot": included,
                "filter_reason": filter_reason,
                "resolved_category": resolved_category,
            }
        )
    return pd.DataFrame(rows)


def attach_resolved_category(frame: pd.DataFrame, paper_category_map: dict[str, str]) -> pd.DataFrame:
    frame = frame.copy()
    original = frame["category"].fillna("").astype(str) if "category" in frame.columns else pd.Series("", index=frame.index)
    paper_category = frame["paper_category"].fillna("").astype(str) if "paper_category" in frame.columns else pd.Series("", index=frame.index)
    preferred = paper_category.where(paper_category.isin(OFFICIAL_CATEGORIES), original)
    resolved = preferred.where(preferred.isin(OFFICIAL_CATEGORIES), frame.get("paper_id", pd.Series("", index=frame.index)).map(paper_category_map))
    frame["original_category"] = original
    frame["paper_category_original"] = paper_category
    frame["resolved_category"] = resolved.fillna(preferred).fillna(original)
    return frame


def infer_display_family(row: pd.Series) -> str:
    family = str(row.get("parameter_family", "") or "")
    key = str(row.get("parameter_key", "") or "").lower()
    name = str(row.get("parameter_name", "") or "").lower()
    if family and family.lower() != "other":
        return family
    mapping = {
        "aluminum_source": "aluminum source",
        "acid_type": "acid type",
        "base_type": "base type",
        "chelating_agent": "additive",
        "dopant": "dopant",
        "solvent": "solvent",
        "precursor": "precursor",
        "stabilizer": "stabilizer",
        "gelation_time": "gel time",
        "spinnability": "spinnability",
        "spinning_parameter": "spinning parameter",
        "sol_stability_time": "sol stability time",
        "sintering_temperature": "sintering temperature",
        "crystallization_temperature": "crystallization temperature",
        "ambient_temperature": "ambient temperature",
        "relative_humidity": "relative humidity",
        "fiber_length": "fiber length",
        "collector_distance": "collector distance",
        "stirring_speed": "stirring speed",
        "feed_rate": "feed rate",
        "temperature_range": "temperature range",
    }
    for token, label in mapping.items():
        if token in key:
            return label
    if any(token in name for token in ["aluminum source", "acid type", "base type", "chelating", "dopant", "solvent", "precursor"]):
        return str(row.get("parameter_name", family or "other"))
    return family or str(row.get("parameter_name", row.get("parameter_key", "other")))


def map_manuscript_parameter_group(row: pd.Series) -> str:
    family = str(row.get("display_family", row.get("parameter_family", "")) or "").lower()
    key = str(row.get("parameter_key", "") or "").lower()
    if family in {"ph", "acid/base ratio", "al concentration", "solid content", "concentration", "base-to-aluminum ratio", "acid-to-aluminum ratio"}:
        return "solution chemistry"
    if any(token in family for token in ["aluminum source", "acid type", "base type", "stabilizer", "dopant", "solvent", "precursor", "additive", "chelating"]):
        return "composition/additive"
    if any(token in family for token in ["aging", "hydrolysis", "peptization"]):
        return "aging/hydrolysis"
    if any(token in family for token in ["drying", "calcination", "holding", "heating rate", "sintering", "crystallization temperature", "ambient temperature"]):
        return "thermal processing"
    if any(token in family for token in ["viscosity", "rheology", "gel time", "spinnability", "spinning parameter"]):
        return "rheology"
    if any(token in family for token in ["particle size", "fiber diameter", "density/porosity", "mechanical property", "bet surface area", "mass loss", "crystallinity", "phase composition", "zeta potential", "fiber length"]):
        return "morphology/property"
    if any(token in key for token in ["aluminum_source", "acid_type", "base_type", "solvent", "precursor", "chelating", "dopant", "stabilizer"]):
        return "composition/additive"
    return UNKNOWN_OTHER_GROUP


def manuscript_parameter_group_mapping_description() -> dict[str, list[str]]:
    return {
        "solution chemistry": ["pH", "acid/base ratio", "Al concentration", "solid content"],
        "composition/additive": ["aluminum source", "acid type", "base type", "solvent", "precursor", "additive", "dopant"],
        "aging/hydrolysis": ["aging temperature", "aging time", "hydrolysis temperature", "hydrolysis time", "peptization temperature", "peptization time"],
        "thermal processing": ["drying temperature", "drying time", "calcination temperature", "holding time", "heating rate", "sintering temperature"],
        "rheology": ["viscosity/rheology", "gel time", "spinnability", "spinning parameter"],
        "morphology/property": ["particle size", "fiber diameter", "density/porosity", "mechanical property", "BET surface area", "mass loss", "crystallinity", "phase composition", "zeta potential"],
        "unknown/other": ["everything else retained only in source data"],
    }


def normalize_temperature_row(row: pd.Series) -> tuple[float | None, bool, str, str]:
    family = str(row.get("display_family", "") or "").lower()
    key = str(row.get("parameter_key", "") or "").lower()
    if family not in TEMPERATURE_FAMILIES:
        return None, False, "not_temperature_parameter", ""
    value = safe_float(row.get("numeric_value"))
    if value is None or not math.isfinite(value):
        return None, False, "not_finite_numeric_value", ""
    unit = normalize_temperature_unit(row.get("normalized_unit"), key)
    if unit == "":
        return None, False, "unsupported_temperature_unit", ""
    if value < 0 or value > 1800:
        return value, False, "outside_plausible_temperature_range", unit
    return value, True, "", unit


def normalize_time_row(row: pd.Series) -> tuple[float | None, bool, str, str]:
    family = str(row.get("display_family", "") or "").lower()
    key = str(row.get("parameter_key", "") or "").lower()
    if family not in TIME_FAMILIES:
        return None, False, "not_time_parameter", ""
    value = safe_float(row.get("numeric_value"))
    if value is None or not math.isfinite(value):
        return None, False, "not_finite_numeric_value", ""
    converted = convert_time_to_hours(value, row.get("normalized_unit"), key)
    if converted is None:
        return None, False, "unsupported_time_unit", ""
    if converted <= 0 or converted > 10000:
        return converted, False, "outside_plausible_time_range", "h"
    return converted, True, "", "h"


def normalize_temperature_unit(unit: Any, key: str) -> str:
    text = str(unit or "").strip().lower()
    if text in {"°c", "c", "℃", "deg c", "celsius"}:
        return "deg C"
    if key.endswith("_c") or "temperature_c" in key:
        return "deg C"
    return ""


def convert_time_to_hours(value: float, unit: Any, key: str) -> float | None:
    text = str(unit or "").strip().lower()
    if text in {"h", "hr", "hour", "hours"} or key.endswith("_h"):
        return value
    if text in {"min", "minute", "minutes"} or key.endswith("_min"):
        return value / 60.0
    if text in {"s", "sec", "second", "seconds"} or key.endswith("_s"):
        return value / 3600.0
    if text in {"day", "days"} or key.endswith("_d"):
        return value * 24.0
    return None


def is_temperature_or_time_related(row: dict[str, Any] | pd.Series) -> bool:
    family = str(row.get("display_family", row.get("parameter_family", "")) or "").lower()
    return family in TEMPERATURE_FAMILIES or family in TIME_FAMILIES


def normalize_peak_unit(spectra_type: str, raw_unit: Any) -> str:
    unit = str(raw_unit or "").strip()
    lower = unit.lower()
    if spectra_type == "FTIR" and lower == "cm^-1":
        return "cm^-1"
    if spectra_type == "XRD" and lower in {"2θ degree", "2theta_deg", "2theta(degree)", "degrees 2-theta"}:
        return "degree 2theta"
    if spectra_type == "NMR" and lower == "ppm":
        return "ppm"
    if spectra_type == "TG/DSC":
        if lower in {"°c", "c", "deg c"}:
            return "deg C"
        if lower in {"", "na", "nan"}:
            return "missing_unit_assumed_deg_C"
    return unit


def assign_peak_bin(spectra_type: str, value: float | None, normalized_unit: str) -> tuple[bool, str, str, str]:
    if value is None or not math.isfinite(value):
        return False, "not_finite_numeric_value", "", ""
    if spectra_type == "FTIR":
        if normalized_unit != "cm^-1":
            return False, "unsupported_unit", "", ""
        if value < 400 or value > 4000:
            return False, "outside_plausible_range", "", ""
        if 400 <= value < 900:
            return True, "", "FTIR", "Al-O / lattice region"
        if 900 <= value < 1700:
            return True, "", "FTIR", "hydroxyl / water / anion-related region"
        if 3000 <= value <= 3700:
            return True, "", "FTIR", "O-H stretching region"
        return False, "outside_defined_bin", "", ""
    if spectra_type == "XRD":
        if normalized_unit != "degree 2theta":
            return False, "unsupported_unit", "", ""
        if value < 5 or value > 90:
            return False, "outside_plausible_range", "", ""
        if value < 30:
            return True, "", "XRD", "low-angle / poorly crystalline features"
        if value < 50:
            return True, "", "XRD", "alumina or boehmite common region"
        return True, "", "XRD", "high-angle crystalline reflections"
    if spectra_type == "NMR":
        if normalized_unit != "ppm":
            return False, "unsupported_unit", "", ""
        if value < -20 or value > 90:
            return False, "outside_plausible_range", "", ""
        if value < 20:
            return True, "", "NMR", "octahedral Al region"
        if value < 50:
            return True, "", "NMR", "penta-coordinated Al region"
        return True, "", "NMR", "tetrahedral Al region"
    if spectra_type == "TG/DSC":
        if normalized_unit not in {"deg C", "missing_unit_assumed_deg_C"}:
            return False, "unsupported_unit", "", ""
        if value < 0 or value > 1400:
            return False, "outside_plausible_range", "", ""
        if value < 200:
            return True, "", "TG/DSC", "adsorbed water / solvent loss"
        if value < 600:
            return True, "", "TG/DSC", "dehydroxylation / organic removal"
        if value < 1000:
            return True, "", "TG/DSC", "transition / crystallization"
        return True, "", "TG/DSC", "high-temperature transformation"
    return False, "unsupported_spectra_type", "", ""


def peak_bin_definitions() -> dict[str, list[dict[str, Any]]]:
    return {
        "FTIR": [
            {"range": [400, 900], "label": "Al-O / lattice region"},
            {"range": [900, 1700], "label": "hydroxyl / water / anion-related region"},
            {"range": [3000, 3700], "label": "O-H stretching region"},
        ],
        "XRD": [
            {"range": [5, 30], "label": "low-angle / poorly crystalline features"},
            {"range": [30, 50], "label": "alumina or boehmite common region"},
            {"range": [50, 90], "label": "high-angle crystalline reflections"},
        ],
        "NMR": [
            {"range": [-20, 20], "label": "octahedral Al region"},
            {"range": [20, 50], "label": "penta-coordinated Al region"},
            {"range": [50, 90], "label": "tetrahedral Al region"},
        ],
        "TG/DSC": [
            {"range": [0, 200], "label": "adsorbed water / solvent loss"},
            {"range": [200, 600], "label": "dehydroxylation / organic removal"},
            {"range": [600, 1000], "label": "transition / crystallization"},
            {"range": [1000, 1400], "label": "high-temperature transformation"},
        ],
    }


def base_row(
    *,
    figure_id: str,
    panel_id: str,
    panel_title: str,
    source_table: str,
    category: str,
    entity_type: str,
    entity_label: str,
    metric: str,
    value: float,
    unit: str,
    raw_value: Any = "",
    numeric_value: Any = "",
    relationship_type: str = "",
    paper_id: str = "",
    included: bool = True,
    exclusion_reason: str = "",
    filter_reason: str = "",
    notes: str = "",
    **extras: Any,
) -> dict[str, Any]:
    payload = {
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
        "included_in_main_plot": included,
        "exclusion_reason": exclusion_reason,
        "filter_reason": filter_reason,
        "notes": notes,
    }
    payload.update(extras)
    return payload


def safe_float(value: Any) -> float | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return None
    return float(number)
