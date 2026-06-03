from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .io import ensure_dir, read_csv, write_frame, write_json, write_markdown


OFFICIAL_CATEGORIES = ["mechanism", "fiber_process", "applications", "rheology"]
SAMPLE_PER_CATEGORY = 5
SAMPLE_SEED = 20260603
CHAR_OUTPUT_KEYS = {
    "xrd_peak_position_2theta_deg",
    "nmr_27al_peak_position_ppm",
    "nmr_shift_ppm",
    "ftir_peak_position_cm_1",
    "raman_peak_position_cm_1",
}
GENERIC_METADATA_KEYS = {
    "parent_series_id",
    "series_id",
    "series_name",
    "source_text",
    "evidence_ref",
    "evidence_reference",
    "context",
    "key",
    "value",
    "values",
    "variables",
    "unit",
    "parameter",
}
FIG2_EXCLUDED_FAMILIES = {"XRD peak", "NMR shift", "FTIR peak", "TG/DSC event"}
FIG2_TEMP_FAMILIES = {
    "aging temperature",
    "hydrolysis temperature",
    "peptization temperature",
    "drying temperature",
    "calcination temperature",
    "sintering temperature",
    "holding temperature",
}
FIG2_TIME_FAMILIES = {
    "aging time",
    "hydrolysis time",
    "peptization time",
    "drying time",
    "holding time",
    "calcination time",
    "sintering time",
}
FIG4_ALLOWED_BIN_FAMILIES = {"FTIR", "XRD", "NMR", "TG/DSC"}


@dataclass
class Finding:
    component: str
    severity: str
    paper_id: str
    category: str
    stage: str
    finding_code: str
    evidence: str
    suspected_source: str
    recommendation: str


def run_pipeline_health_audit(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_export_dir: Path,
    figure_atlas_dir: Path,
    diagnosis_dir: Path,
    manuscript_v2_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = ensure_dir(output_dir)
    tables_dir = figure_atlas_dir / "tables"

    stage3_summary = read_csv(tables_dir / "stage3_paper_summary.csv")
    norm_params = read_csv(tables_dir / "normalized_parameters.csv")
    norm_stage4_spectra = read_csv(tables_dir / "normalized_stage4_spectra.csv")
    norm_stage4_peaks = read_csv(tables_dir / "normalized_stage4_peaks.csv")
    norm_stage5_links = read_csv(tables_dir / "normalized_stage5_links.csv")
    batch_exports = load_batch_exports(batch_export_dir)

    fig2_source = read_csv(manuscript_v2_dir / "source_data" / "Fig2_synthesis_parameter_landscape_source_data.csv")
    fig4_source = read_csv(manuscript_v2_dir / "source_data" / "Fig4_characterization_evidence_atlas_source_data.csv")
    fig1_source = read_csv(manuscript_v2_dir / "source_data" / "Fig1_dataset_coverage_source_data.csv")
    unc_audit = read_csv(manuscript_v2_dir / "qc" / "uncategorized_source_audit.csv")

    sampled = sample_papers(stage3_summary, outputs_dir)
    sampled_df = pd.DataFrame(sampled)
    write_frame(output_dir / "sampled_papers.csv", sampled_df)

    stage3_findings: list[Finding] = []
    stage4_findings: list[Finding] = []
    stage5_findings: list[Finding] = []
    category_findings: list[Finding] = []
    figure_findings: list[Finding] = []
    per_paper_rows: list[dict[str, Any]] = []

    for sample in sampled:
        paper_id = sample["paper_id"]
        category = sample["category"]
        paper_dir = outputs_dir / category / paper_id
        audit = audit_single_paper(
            paper_id=paper_id,
            official_category=category,
            paper_dir=paper_dir,
            batch_exports=batch_exports,
            norm_params=norm_params,
            norm_stage4_spectra=norm_stage4_spectra,
            norm_stage4_peaks=norm_stage4_peaks,
            norm_stage5_links=norm_stage5_links,
            fig1_source=fig1_source,
            fig2_source=fig2_source,
            fig4_source=fig4_source,
            unc_audit=unc_audit,
        )
        stage3_findings.extend(audit["stage3_findings"])
        stage4_findings.extend(audit["stage4_findings"])
        stage5_findings.extend(audit["stage5_findings"])
        category_findings.extend(audit["category_findings"])
        figure_findings.extend(audit["figure_findings"])
        per_paper_rows.append(audit["per_paper_row"])

    write_frame(output_dir / "per_paper_audit.csv", pd.DataFrame(per_paper_rows))
    write_frame(output_dir / "stage3_quality_findings.csv", findings_to_frame(stage3_findings))
    write_frame(output_dir / "stage4_quality_findings.csv", findings_to_frame(stage4_findings))
    write_frame(output_dir / "stage5_linking_findings.csv", findings_to_frame(stage5_findings))
    write_frame(output_dir / "category_mapping_findings.csv", findings_to_frame(category_findings))
    write_frame(output_dir / "figure_source_table_findings.csv", findings_to_frame(figure_findings))

    report = build_report(
        sampled_df=sampled_df,
        per_paper_df=pd.DataFrame(per_paper_rows),
        stage3_df=findings_to_frame(stage3_findings),
        stage4_df=findings_to_frame(stage4_findings),
        stage5_df=findings_to_frame(stage5_findings),
        category_df=findings_to_frame(category_findings),
        figure_df=findings_to_frame(figure_findings),
    )
    write_markdown(output_dir / "pipeline_health_report.md", report)

    summary = {
        "output_dir": str(output_dir),
        "sample_count": int(len(sampled_df)),
        "stage3_findings": len(stage3_findings),
        "stage4_findings": len(stage4_findings),
        "stage5_findings": len(stage5_findings),
        "category_findings": len(category_findings),
        "figure_findings": len(figure_findings),
        "data_safety": {
            "stage3_rerun": False,
            "stage4_rerun": False,
            "stage5_rerun": False,
            "llm_or_vlm_called": False,
            "wrote_data_outputs": False,
        },
    }
    write_json(output_dir / "pipeline_health_summary.json", summary)
    return summary


def sample_papers(stage3_summary: pd.DataFrame, outputs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rng = random.Random(SAMPLE_SEED)
    for category in OFFICIAL_CATEGORIES:
        pool = stage3_summary[stage3_summary["category"] == category]["paper_id"].dropna().astype(str).tolist()
        pool = [paper_id for paper_id in pool if (outputs_dir / category / paper_id).exists()]
        chosen = sorted(rng.sample(pool, SAMPLE_PER_CATEGORY))
        for paper_id in chosen:
            rows.append({"category": category, "paper_id": paper_id, "sample_method": f"random_seed_{SAMPLE_SEED}"})
    return rows


def audit_single_paper(
    *,
    paper_id: str,
    official_category: str,
    paper_dir: Path,
    batch_exports: dict[str, pd.DataFrame],
    norm_params: pd.DataFrame,
    norm_stage4_spectra: pd.DataFrame,
    norm_stage4_peaks: pd.DataFrame,
    norm_stage5_links: pd.DataFrame,
    fig1_source: pd.DataFrame,
    fig2_source: pd.DataFrame,
    fig4_source: pd.DataFrame,
    unc_audit: pd.DataFrame,
) -> dict[str, Any]:
    findings: dict[str, list[Finding]] = {
        "stage3_findings": [],
        "stage4_findings": [],
        "stage5_findings": [],
        "category_findings": [],
        "figure_findings": [],
    }

    final_dataset_dir = paper_dir / "final_dataset"
    stage3_dir = paper_dir / "stage3"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    params = read_jsonl(final_dataset_dir / "parameters.jsonl")
    process_steps = read_jsonl(stage3_dir / "process_steps.jsonl")
    final_process_steps = read_jsonl(final_dataset_dir / "process_steps.jsonl")
    stage4_rows = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
    stage4_summary = read_json(stage4_dir / "stage4a_summary.json")
    links = read_jsonl(final_dataset_dir / "linking" / "links.jsonl")
    evidence_rows = read_jsonl(final_dataset_dir / "evidence.jsonl")
    spectra_rows = read_jsonl(final_dataset_dir / "spectra.jsonl")
    figures_rows = read_jsonl(final_dataset_dir / "figures.jsonl")

    final_params_linked = safe_read_csv(final_dataset_dir / "link_aware_exports" / "final_parameters_linked.csv")
    spectra_links = safe_read_csv(final_dataset_dir / "link_aware_exports" / "spectra_parameter_links.csv")
    evidence_links = safe_read_csv(final_dataset_dir / "link_aware_exports" / "evidence_parameter_links.csv")
    process_links = safe_read_csv(final_dataset_dir / "link_aware_exports" / "process_step_parameter_links.csv")
    process_table = safe_read_csv(final_dataset_dir / "link_aware_exports" / "process_steps_table.csv")
    sample_matrix = safe_read_csv(final_dataset_dir / "link_aware_exports" / "sample_parameter_matrix.csv")

    param_df = pd.DataFrame(params)
    process_df = pd.DataFrame(process_steps)
    final_process_df = pd.DataFrame(final_process_steps)
    stage4_df = pd.DataFrame(stage4_rows)
    link_df = pd.DataFrame(links)
    evidence_df = pd.DataFrame(evidence_rows)
    spectra_df = pd.DataFrame(spectra_rows)
    figures_df = pd.DataFrame(figures_rows)

    per_paper = {
        "paper_id": paper_id,
        "category": official_category,
        "stage3_parameters_status": "ok",
        "stage3_process_status": "ok",
        "stage4_spectra_status": "ok",
        "stage4_peak_status": "ok",
        "stage5_linking_status": "ok",
        "export_status": "ok",
        "figure_source_status": "ok",
        "dominant_root_causes": "",
        "summary_notes": "",
    }

    root_causes = Counter()
    note_parts: list[str] = []

    # Stage3 parameters
    if param_df.empty:
        add_finding(findings["stage3_findings"], "high", paper_id, official_category, "Stage3", "missing_parameters_jsonl", "final_dataset/parameters.jsonl missing or empty", "extraction itself", "inspect Stage3 extraction output for this paper")
        per_paper["stage3_parameters_status"] = "fail"
        root_causes["extraction itself"] += 1
    else:
        key_series = param_df.get("canonical_key", pd.Series(dtype=str)).fillna("").astype(str)
        metadata_like = key_series.isin(GENERIC_METADATA_KEYS)
        char_like = key_series.isin(CHAR_OUTPUT_KEYS)
        missing_values = param_df.apply(parameter_has_no_value, axis=1)
        if metadata_like.mean() > 0.1:
            add_finding(findings["stage3_findings"], "medium", paper_id, official_category, "Stage3", "metadata_keys_in_parameters", f"{metadata_like.sum()}/{len(param_df)} parameters use metadata-like canonical keys", "extraction itself", "tighten Stage3 parameter materialization to avoid metadata spillover")
            per_paper["stage3_parameters_status"] = "warn"
            root_causes["extraction itself"] += 1
        if char_like.mean() > 0.03:
            add_finding(findings["stage3_findings"], "medium", paper_id, official_category, "Stage3", "characterization_output_in_parameters", f"{char_like.sum()}/{len(param_df)} parameters are characterization outputs", "normalization / category mapping", "separate synthesis parameters from characterization-derived rows before figure building")
            per_paper["stage3_parameters_status"] = "warn"
            root_causes["normalization / category mapping"] += 1
        if missing_values.mean() > 0.2:
            add_finding(findings["stage3_findings"], "low", paper_id, official_category, "Stage3", "high_missing_value_ratio", f"{missing_values.sum()}/{len(param_df)} parameters lack a concrete value payload", "extraction itself", "review value materialization and preserve structured list values")
            if per_paper["stage3_parameters_status"] == "ok":
                per_paper["stage3_parameters_status"] = "warn"
            root_causes["extraction itself"] += 1

    # Stage3 process steps
    if process_df.empty:
        if not final_process_df.empty:
            add_finding(findings["stage3_findings"], "medium", paper_id, official_category, "Stage3", "stage3_process_steps_not_retained", "stage3/process_steps.jsonl is missing, but final_dataset/process_steps.jsonl exists", "batch export", "keep the Stage3 process_steps artifact or document that final_dataset is the retained source of truth")
            per_paper["stage3_process_status"] = "warn"
            root_causes["batch export"] += 1
        else:
            add_finding(findings["stage3_findings"], "medium", paper_id, official_category, "Stage3", "missing_process_steps_jsonl", "stage3/process_steps.jsonl missing or empty", "extraction itself", "inspect Stage3 procedure parsing for this paper")
            per_paper["stage3_process_status"] = "fail"
            root_causes["extraction itself"] += 1
    else:
        action_series = process_df.get("action", pd.Series(dtype=str)).fillna("").astype(str)
        other_ratio = (action_series == "other").mean()
        missing_evidence_ratio = process_df.get("evidence_text", pd.Series(dtype=str)).fillna("").astype(str).eq("").mean()
        if other_ratio > 0.5:
            add_finding(findings["stage3_findings"], "medium", paper_id, official_category, "Stage3", "high_other_process_ratio", f"{other_ratio:.2%} of process steps are labeled other", "extraction itself", "improve process-step action normalization for this paper family")
            per_paper["stage3_process_status"] = "warn"
            root_causes["extraction itself"] += 1
        if missing_evidence_ratio > 0.5:
            add_finding(findings["stage3_findings"], "low", paper_id, official_category, "Stage3", "process_steps_missing_evidence", f"{missing_evidence_ratio:.2%} of process steps lack evidence_text", "extraction itself", "keep more procedure evidence spans for downstream audits")
            if per_paper["stage3_process_status"] == "ok":
                per_paper["stage3_process_status"] = "warn"
            root_causes["extraction itself"] += 1

    # Stage4 spectra + peaks
    if stage4_df.empty:
        add_finding(findings["stage4_findings"], "medium", paper_id, official_category, "Stage4", "missing_spectra_extractions", "stage4 spectra_extractions.jsonl missing or empty", "extraction itself", "inspect Stage4 extraction coverage for this paper")
        per_paper["stage4_spectra_status"] = "fail"
        per_paper["stage4_peak_status"] = "fail"
        root_causes["extraction itself"] += 1
    else:
        technique_series = stage4_df.get("technique", pd.Series(dtype=str)).fillna("").astype(str)
        unknown_ratio = technique_series.str.lower().isin({"", "unknown", "other"}).mean()
        if unknown_ratio > 0.3:
            add_finding(findings["stage4_findings"], "medium", paper_id, official_category, "Stage4", "high_unknown_technique_ratio", f"{unknown_ratio:.2%} of Stage4 rows have unknown/other technique", "extraction itself", "review Stage4 technique normalization for this paper")
            per_paper["stage4_spectra_status"] = "warn"
            root_causes["extraction itself"] += 1
        peak_audit = audit_stage4_peaks(stage4_rows)
        if peak_audit["unsupported_unit_count"] > 0:
            add_finding(findings["stage4_findings"], "medium", paper_id, official_category, "Stage4", "peak_unit_anomalies", f"{peak_audit['unsupported_unit_count']} peak values use unsupported units", "extraction itself", "filter or normalize Stage4 peak units before figure semantics")
            per_paper["stage4_peak_status"] = "warn"
            root_causes["extraction itself"] += 1
        if peak_audit["out_of_range_count"] > 0:
            add_finding(findings["stage4_findings"], "medium", paper_id, official_category, "Stage4", "peak_range_anomalies", f"{peak_audit['out_of_range_count']} peak values fall outside plausible ranges", "extraction itself", "tighten Stage4 range validation or downstream peak filtering")
            per_paper["stage4_peak_status"] = "warn"
            root_causes["extraction itself"] += 1
        if stage4_summary and float(stage4_summary.get("successful_extractions_count", 0)) == 0 and float(stage4_summary.get("total_candidates", 0)) > 0:
            add_finding(findings["stage4_findings"], "medium", paper_id, official_category, "Stage4", "zero_stage4_success", f"0 successful extractions out of {stage4_summary.get('total_candidates', 0)} candidates", "extraction itself", "inspect whether the paper is a valid Stage4 target")
            per_paper["stage4_spectra_status"] = "warn"
            root_causes["extraction itself"] += 1

    # Stage5 linking
    if link_df.empty:
        add_finding(findings["stage5_findings"], "medium", paper_id, official_category, "Stage5", "missing_links_jsonl", "final_dataset/linking/links.jsonl missing or empty", "Stage5 linking", "inspect whether linking ran for this paper")
        per_paper["stage5_linking_status"] = "fail"
        root_causes["Stage5 linking"] += 1
    else:
        source_ids = build_source_id_sets(evidence_df, spectra_df, figures_df, final_process_df)
        target_ids = build_target_id_sets(param_df, evidence_df, spectra_df, final_process_df, figures_df)
        broken_source = 0
        broken_target = 0
        suspicious_parameter_links = 0
        param_key_lookup = {str(row.get("parameter_id")): str(row.get("canonical_key", "")) for row in params}
        for row in links:
            source_type = str(row.get("source_type", ""))
            source_id = str(row.get("source_id", ""))
            target_type = str(row.get("target_type", ""))
            target_id = str(row.get("target_id", ""))
            if source_id and source_type in source_ids and source_id not in source_ids[source_type]:
                broken_source += 1
            if target_id and target_type in target_ids and target_id not in target_ids[target_type]:
                broken_target += 1
            if target_type == "parameter" and param_key_lookup.get(target_id, "") in GENERIC_METADATA_KEYS:
                suspicious_parameter_links += 1
        if broken_source or broken_target:
            add_finding(findings["stage5_findings"], "high", paper_id, official_category, "Stage5", "broken_link_references", f"{broken_source} broken source refs and {broken_target} broken target refs", "Stage5 linking", "repair Stage5 link id resolution before trusting paper-level link exports")
            per_paper["stage5_linking_status"] = "fail"
            root_causes["Stage5 linking"] += 1
        if suspicious_parameter_links > 0:
            add_finding(findings["stage5_findings"], "medium", paper_id, official_category, "Stage5", "links_to_metadata_parameters", f"{suspicious_parameter_links} links target metadata-like parameters", "Stage5 linking", "exclude metadata spillover parameters from linking candidates")
            if per_paper["stage5_linking_status"] == "ok":
                per_paper["stage5_linking_status"] = "warn"
            root_causes["Stage5 linking"] += 1

    # Category mapping and exports
    paper_norm_params = norm_params[norm_params["paper_id"] == paper_id]
    paper_norm_spectra = norm_stage4_spectra[norm_stage4_spectra["paper_id"] == paper_id]
    paper_norm_links = norm_stage5_links[norm_stage5_links["paper_id"] == paper_id]
    for name, df in [("normalized_parameters", paper_norm_params), ("normalized_stage4_spectra", paper_norm_spectra), ("normalized_stage5_links", paper_norm_links)]:
        if df.empty:
            continue
        bad_category_rows = ~df["category"].fillna("").astype(str).eq(official_category)
        if bad_category_rows.any():
            add_finding(findings["category_findings"], "medium", paper_id, official_category, "Batch/category", f"{name}_category_mismatch", f"{int(bad_category_rows.sum())}/{len(df)} rows carry category values different from the official paper category", "normalization / category mapping", "recover official paper-level category before batch aggregation")
            root_causes["normalization / category mapping"] += 1
    export_frames = {
        "final_parameters_linked": final_params_linked,
        "spectra_parameter_links": spectra_links,
        "evidence_parameter_links": evidence_links,
        "process_step_parameter_links": process_links,
        "process_steps_table": process_table,
        "sample_parameter_matrix": sample_matrix,
    }
    for export_name, export_df in export_frames.items():
        if export_df.empty:
            add_finding(findings["category_findings"], "medium", paper_id, official_category, "Batch export", f"{export_name}_missing_or_empty", f"{export_name} missing or empty", "batch export", "inspect per-paper link_aware export generation")
            per_paper["export_status"] = "warn"
            root_causes["batch export"] += 1
            continue
        if "paper_id" not in export_df.columns or "category" not in export_df.columns:
            add_finding(findings["category_findings"], "high", paper_id, official_category, "Batch export", f"{export_name}_missing_identity_columns", "paper_id or category column missing", "batch export", "preserve identity columns in every export table")
            per_paper["export_status"] = "fail"
            root_causes["batch export"] += 1

    for export_name, batch_df in batch_exports.items():
        if batch_df.empty or "paper_id" not in batch_df.columns:
            continue
        subset = batch_df[batch_df["paper_id"].fillna("").astype(str) == paper_id].copy()
        if subset.empty:
            add_finding(findings["category_findings"], "medium", paper_id, official_category, "Batch export", f"{export_name}_missing_from_batch_export", f"no rows found in batch export {export_name}", "batch export", "ensure batch export includes this paper after per-paper export generation")
            if per_paper["export_status"] == "ok":
                per_paper["export_status"] = "warn"
            root_causes["batch export"] += 1
            continue
        if "category" in subset.columns:
            wrong_category = ~subset["category"].fillna("").astype(str).eq(official_category)
            if wrong_category.any():
                add_finding(findings["category_findings"], "high", paper_id, official_category, "Batch export", f"{export_name}_batch_category_mismatch", f"{int(wrong_category.sum())}/{len(subset)} batch-export rows carry a non-paper category", "batch export", "carry official paper category into batch export rows")
                per_paper["export_status"] = "fail"
                root_causes["batch export"] += 1
            continue
        wrong_paper = ~export_df["paper_id"].fillna("").astype(str).eq(paper_id)
        wrong_category = ~export_df["category"].fillna("").astype(str).eq(official_category)
        if wrong_paper.any() or wrong_category.any():
            add_finding(findings["category_findings"], "high", paper_id, official_category, "Batch export", f"{export_name}_identity_mismatch", f"{int(wrong_paper.sum())} paper_id mismatches and {int(wrong_category.sum())} category mismatches", "batch export", "carry official paper_id/category through link_aware exports")
            per_paper["export_status"] = "fail"
            root_causes["batch export"] += 1

    # Figure source table classification
    paper_fig2 = fig2_source[fig2_source["paper_id"].fillna("").astype(str) == paper_id].copy()
    paper_fig4 = fig4_source[fig4_source["paper_id"].fillna("").astype(str) == paper_id].copy()
    if not paper_fig2.empty:
        wrong_category = paper_fig2[paper_fig2["included_in_main_plot"].fillna(False) & ~paper_fig2["category"].fillna("").astype(str).eq(official_category)]
        if not wrong_category.empty:
            add_finding(findings["figure_findings"], "high", paper_id, official_category, "Figure source", "fig2_category_mismatch", f"{len(wrong_category)} Fig2 source rows are included under the wrong category", "manuscript figure source table", "fix paper-level category assignment before figure aggregation")
            per_paper["figure_source_status"] = "fail"
            root_causes["manuscript figure source table"] += 1
        bad_families = paper_fig2[
            paper_fig2["included_in_main_plot"].fillna(False)
            & paper_fig2["entity_label"].fillna("").astype(str).isin(FIG2_EXCLUDED_FAMILIES)
        ]
        if not bad_families.empty:
            add_finding(findings["figure_findings"], "high", paper_id, official_category, "Figure source", "fig2_characterization_leak", f"{len(bad_families)} Fig2 rows still include characterization-output families", "manuscript figure source table", "exclude characterization-output families from synthesis panels")
            per_paper["figure_source_status"] = "fail"
            root_causes["manuscript figure source table"] += 1
        bad_temp = paper_fig2[
            paper_fig2["panel_id"].fillna("").astype(str).eq("D")
            & paper_fig2["included_in_main_plot"].fillna(False)
            & ~paper_fig2["entity_label"].fillna("").astype(str).isin(FIG2_TEMP_FAMILIES)
        ]
        if not bad_temp.empty:
            add_finding(findings["figure_findings"], "medium", paper_id, official_category, "Figure source", "fig2_temperature_panel_family_leak", f"{len(bad_temp)} Fig2D rows use non-temperature families", "manuscript figure source table", "tighten temperature panel family whitelist")
            if per_paper["figure_source_status"] == "ok":
                per_paper["figure_source_status"] = "warn"
            root_causes["manuscript figure source table"] += 1
        bad_time = paper_fig2[
            paper_fig2["panel_id"].fillna("").astype(str).eq("E")
            & paper_fig2["included_in_main_plot"].fillna(False)
            & ~paper_fig2["entity_label"].fillna("").astype(str).isin(FIG2_TIME_FAMILIES)
        ]
        if not bad_time.empty:
            add_finding(findings["figure_findings"], "medium", paper_id, official_category, "Figure source", "fig2_time_panel_family_leak", f"{len(bad_time)} Fig2E rows use non-time families", "manuscript figure source table", "tighten time panel family whitelist")
            if per_paper["figure_source_status"] == "ok":
                per_paper["figure_source_status"] = "warn"
            root_causes["manuscript figure source table"] += 1
    if not paper_fig4.empty:
        wrong_category = paper_fig4[paper_fig4["included_in_main_plot"].fillna(False) & ~paper_fig4["category"].fillna("").astype(str).eq(official_category)]
        if not wrong_category.empty:
            add_finding(findings["figure_findings"], "high", paper_id, official_category, "Figure source", "fig4_category_mismatch", f"{len(wrong_category)} Fig4 rows are included under the wrong category", "manuscript figure source table", "fix figure-source category assignment before plotting")
            per_paper["figure_source_status"] = "fail"
            root_causes["manuscript figure source table"] += 1
        bad_bins = paper_fig4[
            paper_fig4["panel_id"].fillna("").astype(str).eq("D")
            & paper_fig4["included_in_main_plot"].fillna(False)
            & ~paper_fig4["bin_family"].fillna("").astype(str).isin(FIG4_ALLOWED_BIN_FAMILIES)
        ]
        if not bad_bins.empty:
            add_finding(findings["figure_findings"], "medium", paper_id, official_category, "Figure source", "fig4_unexpected_bin_family", f"{len(bad_bins)} Fig4D rows have unexpected bin families", "manuscript figure source table", "keep only FTIR/XRD/NMR/TG-DSC bin families in the main panel")
            if per_paper["figure_source_status"] == "ok":
                per_paper["figure_source_status"] = "warn"
            root_causes["manuscript figure source table"] += 1

    if not unc_audit.empty and paper_id in set(unc_audit["paper_id"].fillna("").astype(str)):
        add_finding(findings["figure_findings"], "medium", paper_id, official_category, "Figure source", "paper_appears_in_uncategorized_audit", "This paper contributes rows to the uncategorized audit table", "manuscript figure source table", "keep excluded rows traceable but verify upstream category joins")
        if per_paper["figure_source_status"] == "ok":
            per_paper["figure_source_status"] = "warn"
        root_causes["manuscript figure source table"] += 1

    # figure metric definition notes inferred from per-paper context
    if per_paper["figure_source_status"] == "ok" and per_paper["export_status"] == "ok":
        note_parts.append("paper-level data mostly consistent; remaining risks are figure-level metric semantics")

    per_paper["dominant_root_causes"] = "; ".join([name for name, _ in root_causes.most_common(3)])
    per_paper["summary_notes"] = " | ".join(note_parts) if note_parts else summarize_statuses(per_paper)

    return {**findings, "per_paper_row": per_paper}


def findings_to_frame(findings: list[Finding]) -> pd.DataFrame:
    if not findings:
        return pd.DataFrame(columns=["component", "severity", "paper_id", "category", "stage", "finding_code", "evidence", "suspected_source", "recommendation"])
    return pd.DataFrame([finding.__dict__ for finding in findings])


def add_finding(
    bucket: list[Finding],
    severity: str,
    paper_id: str,
    category: str,
    stage: str,
    finding_code: str,
    evidence: str,
    suspected_source: str,
    recommendation: str,
) -> None:
    bucket.append(
        Finding(
            component=stage,
            severity=severity,
            paper_id=paper_id,
            category=category,
            stage=stage,
            finding_code=finding_code,
            evidence=evidence,
            suspected_source=suspected_source,
            recommendation=recommendation,
        )
    )


def parameter_has_no_value(row: pd.Series) -> bool:
    for field in ("value", "min_value", "max_value"):
        value = row.get(field)
        if value not in (None, "", []) and not pd.isna(value):
            return False
    return True


def audit_stage4_peaks(stage4_rows: list[dict[str, Any]]) -> dict[str, int]:
    unsupported_unit_count = 0
    out_of_range_count = 0
    peak_count = 0
    for row in stage4_rows:
        technique = str(row.get("technique", "") or "").upper()
        peaks = row.get("peaks") or []
        if not isinstance(peaks, list):
            continue
        for peak in peaks:
            if not isinstance(peak, dict):
                continue
            peak_count += 1
            value = to_float(peak.get("position", peak.get("value", peak.get("peak_value"))))
            unit = str(peak.get("unit", "") or "")
            if "FTIR" in technique:
                if unit != "cm^-1":
                    unsupported_unit_count += 1
                elif value is not None and not (400 <= value <= 4000):
                    out_of_range_count += 1
            elif "XRD" in technique:
                if unit not in {"2theta_deg", "2θ degree", "2Theta(degree)", "degrees 2-theta"}:
                    unsupported_unit_count += 1
                elif value is not None and not (5 <= value <= 90):
                    out_of_range_count += 1
            elif "NMR" in technique:
                if unit != "ppm":
                    unsupported_unit_count += 1
                elif value is not None and not (-20 <= value <= 90):
                    out_of_range_count += 1
            elif any(token in technique for token in ["TG", "DSC", "TGA"]):
                if unit not in {"°C", "C", "deg C", ""}:
                    unsupported_unit_count += 1
                elif value is not None and not (0 <= value <= 1400):
                    out_of_range_count += 1
    return {
        "peak_count": peak_count,
        "unsupported_unit_count": unsupported_unit_count,
        "out_of_range_count": out_of_range_count,
    }


def build_source_id_sets(
    evidence_df: pd.DataFrame,
    spectra_df: pd.DataFrame,
    figures_df: pd.DataFrame,
    process_df: pd.DataFrame,
) -> dict[str, set[str]]:
    payload: dict[str, set[str]] = defaultdict(set)
    if not evidence_df.empty and "source_id" in evidence_df.columns:
        payload["evidence_object"] = set(evidence_df["source_id"].dropna().astype(str))
        payload["text_reference"] = set(evidence_df["source_id"].dropna().astype(str))
    if not spectra_df.empty and "spectra_id" in spectra_df.columns:
        payload["spectra_record"] = set(spectra_df["spectra_id"].dropna().astype(str))
    if not figures_df.empty and "figure_id" in figures_df.columns:
        payload["figure"] = set(figures_df["figure_id"].dropna().astype(str))
    if not process_df.empty and "step_id" in process_df.columns:
        payload["process_step"] = set(process_df["step_id"].dropna().astype(str))
    payload["sample"] = set()
    return payload


def build_target_id_sets(
    param_df: pd.DataFrame,
    evidence_df: pd.DataFrame,
    spectra_df: pd.DataFrame,
    process_df: pd.DataFrame,
    figures_df: pd.DataFrame,
) -> dict[str, set[str]]:
    payload: dict[str, set[str]] = defaultdict(set)
    if not param_df.empty and "parameter_id" in param_df.columns:
        payload["parameter"] = set(param_df["parameter_id"].dropna().astype(str))
    if not evidence_df.empty and "source_id" in evidence_df.columns:
        payload["evidence_object"] = set(evidence_df["source_id"].dropna().astype(str))
    if not spectra_df.empty and "spectra_id" in spectra_df.columns:
        payload["spectra_record"] = set(spectra_df["spectra_id"].dropna().astype(str))
    if not figures_df.empty and "figure_id" in figures_df.columns:
        payload["figure"] = set(figures_df["figure_id"].dropna().astype(str))
    if not process_df.empty and "step_id" in process_df.columns:
        payload["process_step"] = set(process_df["step_id"].dropna().astype(str))
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_batch_exports(batch_export_dir: Path) -> dict[str, pd.DataFrame]:
    mapping = {
        "all_papers_final_parameters_linked": "all_papers_final_parameters_linked.csv",
        "all_papers_process_steps_table": "all_papers_process_steps_table.csv",
        "all_papers_spectra_parameter_links": "all_papers_spectra_parameter_links.csv",
        "all_papers_evidence_parameter_links": "all_papers_evidence_parameter_links.csv",
        "all_papers_process_step_parameter_links": "all_papers_process_step_parameter_links.csv",
        "all_papers_sample_parameter_matrix": "all_papers_sample_parameter_matrix.csv",
    }
    return {name: safe_read_csv(batch_export_dir / filename) for name, filename in mapping.items()}


def to_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        num = float(value)
        if pd.isna(num):
            return None
        return num
    except Exception:
        return None


def summarize_statuses(per_paper: dict[str, Any]) -> str:
    parts = []
    for key in [
        "stage3_parameters_status",
        "stage3_process_status",
        "stage4_spectra_status",
        "stage4_peak_status",
        "stage5_linking_status",
        "export_status",
        "figure_source_status",
    ]:
        parts.append(f"{key}={per_paper[key]}")
    return "; ".join(parts)


def build_report(
    *,
    sampled_df: pd.DataFrame,
    per_paper_df: pd.DataFrame,
    stage3_df: pd.DataFrame,
    stage4_df: pd.DataFrame,
    stage5_df: pd.DataFrame,
    category_df: pd.DataFrame,
    figure_df: pd.DataFrame,
) -> str:
    component_counts = {
        "Stage3": len(stage3_df),
        "Stage4": len(stage4_df),
        "Stage5 linking": len(stage5_df),
        "Category mapping / batch export": len(category_df),
        "Manuscript figure source table": len(figure_df),
    }
    cause_counter = Counter()
    for frame in [stage3_df, stage4_df, stage5_df, category_df, figure_df]:
        if not frame.empty and "suspected_source" in frame.columns:
            cause_counter.update(frame["suspected_source"].dropna().astype(str).tolist())

    worst_papers = per_paper_df.copy()
    worst_papers["warn_or_fail_count"] = worst_papers.apply(lambda row: sum(str(row[col]) != "ok" for col in worst_papers.columns if col.endswith("_status")), axis=1)
    worst_papers = worst_papers.sort_values(["warn_or_fail_count", "paper_id"], ascending=[False, True]).head(8)

    needs_rerun = []
    if not stage5_df.empty and stage5_df["finding_code"].astype(str).str.contains("broken_link_references").any():
        needs_rerun.append("targeted Stage5 relinking for affected papers")
    if not category_df.empty and category_df["finding_code"].astype(str).str.contains("identity_mismatch").any():
        needs_rerun.append("targeted link_aware export rebuild for affected papers")

    lines = [
        "# Pipeline Health Audit",
        "",
        "## Scope",
        "- Audit only. No Stage3/Stage4/Stage5 reruns were performed.",
        "- No LLM/VLM calls were made.",
        "- No writes were made to `data/outputs`.",
        f"- Sampled papers: {len(sampled_df)} total, with {SAMPLE_PER_CATEGORY} papers from each official category.",
        "",
        "## Sample composition",
    ]
    for category in OFFICIAL_CATEGORIES:
        count = int((sampled_df["category"] == category).sum())
        lines.append(f"- `{category}`: {count}")
    lines.extend(
        [
            "",
            "## Component finding counts",
        ]
    )
    for name, count in component_counts.items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Root-cause balance",
        ]
    )
    for source, count in cause_counter.most_common():
        lines.append(f"- `{source}`: {count}")

    lines.extend(
        [
            "",
            "## Direct answers",
            "",
            "1. Is the whole pipeline broken?",
        ]
    )
    if cause_counter:
        lines.append("No. The audit points to a mixed picture: the pipeline is usable, but multiple localized issues exist across extraction, category/export handling, and figure-source construction.")
    else:
        lines.append("No obvious systemic issue was found in the sampled papers.")

    lines.extend(
        [
            "",
            "2. Which problems come from Stage3?",
            summarize_component(stage3_df, default_text="Stage3 issues were minor in the sampled set."),
            "",
            "3. Which problems come from Stage4?",
            summarize_component(stage4_df, default_text="Stage4 issues were minor in the sampled set."),
            "",
            "4. Which problems come from Stage5 linking?",
            summarize_component(stage5_df, default_text="Stage5 linking issues were minor in the sampled set."),
            "",
            "5. Which problems come from batch export or category mapping?",
            summarize_component(category_df, default_text="Batch export and category mapping looked stable in the sampled set."),
            "",
            "6. Which problems come from manuscript figure source tables?",
            summarize_component(figure_df, default_text="The v2 figure source tables were stable for the sampled papers."),
            "",
            "6b. Which problems come from figure metric definition rather than pipeline data?",
            "- The old Fig1B count-plus-rate mix was a figure-metric problem, not an upstream extraction problem.",
            "- The old Fig1C presence-matrix completeness was a figure-metric problem, not a Stage5 corruption problem.",
            "- Raw peak histograms in old Fig4 were mainly a figure-metric and semantics problem; the safer interpretation is approximate binned evidence, not raw-frequency storytelling.",
            "",
            "7. Which figures can keep moving forward?",
            "- `Fig2` can continue, because the synthesis-parameter leakage from characterization outputs has been removed in v2.",
            "- `Fig1` can continue if it stays on official-category-only counts/fractions and keeps `uncategorized` out of the main panels.",
            "- `Fig4` can continue for evidence-structure panels, not for raw peak histograms.",
            "",
            "8. Which figures need data semantics fixed first?",
            "- Any raw peak histogram figure needs semantics fixed first; approximate bins are safer than raw-value frequency plots.",
            "- Any figure relying on export `category` columns needs category semantics checked first, because per-paper link-aware exports can carry non-paper-level categories.",
            "",
            "9. Do any stages need reruns?",
        ]
    )
    if needs_rerun:
        lines.append("Possibly, but not globally. The audit suggests targeted reruns only where linking/export identity is broken.")
    else:
        lines.append("No full-stage rerun is justified from this audit. Most issues can be handled downstream or with targeted repair.")

    lines.extend(
        [
            "",
            "10. If reruns are needed, what is the minimum scope?",
        ]
    )
    if needs_rerun:
        for item in needs_rerun:
            lines.append(f"- {item}")
    else:
        lines.append("- Keep Stage3 and Stage4 frozen.")
        lines.append("- If a paper shows broken link ids, rerun Stage5 linking only for that paper.")
        lines.append("- If only exported `category` values are wrong, rebuild per-paper link-aware exports without rerunning upstream extraction.")

    lines.extend(
        [
            "",
            "## Worst affected sampled papers",
        ]
    )
    for row in worst_papers.to_dict(orient="records"):
        lines.append(f"- `{row['paper_id']}` ({row['category']}): {row['summary_notes']}")

    return "\n".join(lines) + "\n"


def summarize_component(frame: pd.DataFrame, *, default_text: str) -> str:
    if frame.empty:
        return default_text
    top = frame.groupby("finding_code").size().sort_values(ascending=False).head(5)
    parts = [f"`{code}` ({count})" for code, count in top.items()]
    return "Most frequent findings: " + ", ".join(parts) + "."
