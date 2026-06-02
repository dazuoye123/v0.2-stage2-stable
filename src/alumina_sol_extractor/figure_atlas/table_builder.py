from __future__ import annotations

from typing import Any

import pandas as pd

from .io import normalize_text, safe_float
from .normalization import (
    normalize_category,
    normalize_numeric_value,
    normalize_parameter_family,
    normalize_process_step_family,
    normalize_spectra_type,
)


def build_normalized_tables(payload: dict[str, Any]) -> dict[str, pd.DataFrame]:
    stage3 = payload["stage3"]
    stage4 = payload["stage4"]
    stage5 = payload["stage5"]

    normalized_parameters = _build_normalized_parameters(stage5["final_parameters_linked"])
    normalized_process_steps = _build_normalized_process_steps(stage5["process_steps_table"])
    normalized_stage4_spectra = _build_normalized_stage4_spectra(stage4["spectra"])
    normalized_stage4_peaks = _build_normalized_stage4_peaks(stage4["peaks"])
    normalized_stage5_links = _build_normalized_links(
        stage5["evidence_parameter_links"],
        stage5["process_step_parameter_links"],
        stage5["spectra_parameter_links"],
        normalized_parameters,
        normalized_process_steps,
        normalized_stage4_spectra,
        stage5["sample_parameter_matrix"],
    )
    normalized_sample_matrix = _build_normalized_sample_matrix(stage5["sample_parameter_matrix"])

    parameter_family_by_category = (
        normalized_parameters.groupby(["category", "parameter_family"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    spectra_type_by_category = (
        normalized_stage4_spectra.groupby(["category", "normalized_spectra_type"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    process_step_by_category = (
        normalized_process_steps.groupby(["category", "process_step_family"]).size().reset_index(name="count").sort_values(["category", "count"], ascending=[True, False])
    )
    spectra_parameter_matrix = _link_matrix(normalized_stage5_links, link_family="spectra", row_col="normalized_spectra_type", col_col="normalized_parameter_family")
    process_parameter_matrix = _link_matrix(normalized_stage5_links, link_family="process_step", row_col="normalized_process_step_family", col_col="normalized_parameter_family")
    evidence_parameter_matrix = _link_matrix(normalized_stage5_links, link_family="evidence", row_col="raw_source_type", col_col="normalized_parameter_family")
    category_summary = _build_category_summary(normalized_parameters, normalized_process_steps, normalized_stage4_spectra, normalized_stage5_links)

    return {
        "normalized_parameters": normalized_parameters,
        "normalized_process_steps": normalized_process_steps,
        "normalized_stage4_spectra": normalized_stage4_spectra,
        "normalized_stage4_peaks": normalized_stage4_peaks,
        "normalized_stage5_links": normalized_stage5_links,
        "normalized_sample_matrix": normalized_sample_matrix,
        "parameter_family_by_category": parameter_family_by_category,
        "spectra_type_by_category": spectra_type_by_category,
        "process_step_by_category": process_step_by_category,
        "spectra_parameter_matrix": spectra_parameter_matrix,
        "process_parameter_matrix": process_parameter_matrix,
        "evidence_parameter_matrix": evidence_parameter_matrix,
        "category_summary": category_summary,
        "stage4_paper_summary": stage4["paper_summary"],
        "stage4_failed": stage4["failed"],
        "stage4_quality": stage4["quality"],
        "stage3_parameter_distribution": stage3["parameter_distribution"],
        "stage3_sample_parameter_long": stage3["sample_parameter_long"],
        "stage3_paper_summary": stage3["paper_stage3_summary"],
        "stage3_coverage_matrix_plotting_data": stage3["coverage_matrix_plotting_data"],
        "stage3_paper_metadata_plotting_data": stage3["paper_metadata_plotting_data"],
        "stage5_final_showcase_table": stage5["final_showcase_table"],
    }


def _build_normalized_parameters(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[
            "category", "paper_id", "sample_id", "parameter_id", "parameter_name", "parameter_key", "raw_value",
            "numeric_value", "raw_unit", "normalized_unit", "parameter_family", "source_table", "has_sample_link",
            "has_evidence_link", "has_process_step_link", "has_spectra_link", "normalization_warning",
        ])
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        family = normalize_parameter_family(row.get("canonical_key"), row.get("zh_name"), row.get("en_name"), row.get("unit"), row.get("value_raw"), row.get("normalization_note"))
        numeric_value, normalized_unit, warning = normalize_numeric_value(row.get("value_num") if row.get("value_num") == row.get("value_num") else row.get("value_raw"), row.get("unit"), family)
        link_types = normalize_text(row.get("link_types"))
        rows.append(
            {
                "category": normalize_category(row.get("category")),
                "paper_id": row.get("paper_id"),
                "sample_id": normalize_text(row.get("resolved_sample_id") or row.get("sample_id_original")),
                "parameter_id": row.get("parameter_id"),
                "parameter_name": normalize_text(row.get("zh_name") or row.get("en_name") or row.get("canonical_key")),
                "parameter_key": normalize_text(row.get("canonical_key")),
                "raw_value": normalize_text(row.get("value_raw") or row.get("value_text")),
                "numeric_value": numeric_value,
                "raw_unit": normalize_text(row.get("unit")),
                "normalized_unit": normalized_unit,
                "parameter_family": family,
                "source_table": "all_papers_final_parameters_linked.csv",
                "has_sample_link": bool(normalize_text(row.get("resolved_sample_id"))),
                "has_evidence_link": bool(normalize_text(row.get("linked_evidence_ids"))),
                "has_process_step_link": "process" in link_types.lower(),
                "has_spectra_link": bool(normalize_text(row.get("linked_spectra_ids"))),
                "normalization_warning": warning,
            }
        )
    return pd.DataFrame(rows)


def _build_normalized_process_steps(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_id", "process_step_id", "process_step_name", "process_step_family", "raw_text", "source_table"])
    rows = []
    for row in frame.to_dict(orient="records"):
        family = normalize_process_step_family(row.get("action"), row.get("action_zh"), row.get("section"), row.get("product_or_outcome"))
        raw_text = "; ".join(part for part in [
            normalize_text(row.get("action")),
            normalize_text(row.get("action_zh")),
            normalize_text(row.get("reagent_name")),
            normalize_text(row.get("condition_key")),
            normalize_text(row.get("evidence_text")),
        ] if part)
        rows.append(
            {
                "category": normalize_category(row.get("category")),
                "paper_id": row.get("paper_id"),
                "process_step_id": row.get("step_id"),
                "process_step_name": normalize_text(row.get("action") or row.get("action_zh")),
                "process_step_family": family,
                "raw_text": raw_text,
                "source_table": "all_papers_process_steps_table.csv",
            }
        )
    return pd.DataFrame(rows)


def _build_normalized_stage4_spectra(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_id", "figure_id", "spectra_id", "raw_spectra_type", "normalized_spectra_type", "figure_class", "technique", "caption", "source_table"])
    cols = ["category", "paper_id", "figure_id", "spectra_id", "raw_spectra_type", "normalized_spectra_type", "figure_class", "technique", "caption", "source_table"]
    result = frame[cols].copy()
    result["category"] = result["category"].map(normalize_category)
    result["normalized_spectra_type"] = [
        normalize_spectra_type(raw, technique, figure_class)
        for raw, technique, figure_class in zip(result["raw_spectra_type"], result["technique"], result["figure_class"])
    ]
    return result


def _build_normalized_stage4_peaks(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_id", "figure_id", "normalized_spectra_type", "peak_source_field", "peak_value", "peak_unit", "peak_label", "source_table"])
    rows = []
    for row in frame.to_dict(orient="records"):
        spectra_type = normalize_spectra_type(row.get("raw_spectra_type"), row.get("normalized_spectra_type"), row.get("figure_class"))
        _, normalized_unit, _ = normalize_numeric_value(row.get("peak_value"), row.get("peak_unit"), _spectra_family_to_parameter_family(spectra_type))
        rows.append(
            {
                "category": normalize_category(row.get("category")),
                "paper_id": row.get("paper_id"),
                "figure_id": row.get("figure_id"),
                "normalized_spectra_type": spectra_type,
                "peak_source_field": normalize_text(row.get("peak_source_field")),
                "peak_value": safe_float(row.get("peak_value")),
                "peak_unit": normalized_unit or normalize_text(row.get("peak_unit")),
                "peak_label": normalize_text(row.get("peak_label")),
                "source_table": "normalized_stage4_spectra",
            }
        )
    return pd.DataFrame(rows)


def _build_normalized_links(
    evidence_links: pd.DataFrame,
    process_links: pd.DataFrame,
    spectra_links: pd.DataFrame,
    normalized_parameters: pd.DataFrame,
    normalized_process_steps: pd.DataFrame,
    normalized_stage4_spectra: pd.DataFrame,
    sample_matrix: pd.DataFrame,
) -> pd.DataFrame:
    parameter_family_lookup = {
        row["parameter_id"]: row["parameter_family"]
        for row in normalized_parameters[["parameter_id", "parameter_family"]].dropna().to_dict(orient="records")
    }
    process_family_lookup = {
        row["process_step_id"]: row["process_step_family"]
        for row in normalized_process_steps[["process_step_id", "process_step_family"]].dropna().to_dict(orient="records")
    }
    spectra_type_lookup = {
        (row["paper_id"], row["figure_id"]): row["normalized_spectra_type"]
        for row in normalized_stage4_spectra[["paper_id", "figure_id", "normalized_spectra_type"]].dropna().to_dict(orient="records")
    }

    rows: list[dict[str, Any]] = []
    rows.extend(_materialize_link_rows(evidence_links, "evidence", parameter_family_lookup, process_family_lookup, spectra_type_lookup, source_table="all_papers_evidence_parameter_links.csv"))
    rows.extend(_materialize_link_rows(process_links, "process_step", parameter_family_lookup, process_family_lookup, spectra_type_lookup, source_table="all_papers_process_step_parameter_links.csv"))
    rows.extend(_materialize_link_rows(spectra_links, "spectra", parameter_family_lookup, process_family_lookup, spectra_type_lookup, source_table="all_papers_spectra_parameter_links.csv"))
    rows.extend(_materialize_sample_links(normalized_parameters, sample_matrix))
    return pd.DataFrame(rows)


def _materialize_link_rows(
    frame: pd.DataFrame,
    link_family: str,
    parameter_family_lookup: dict[str, str],
    process_family_lookup: dict[str, str],
    spectra_type_lookup: dict[tuple[str, str], str],
    *,
    source_table: str,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        paper_id = normalize_text(row.get("paper_id"))
        figure_id = normalize_text(row.get("figure_id"))
        source_id = normalize_text(row.get("source_id"))
        parameter_id = normalize_text(row.get("parameter_id"))
        rows.append(
            {
                "category": normalize_category(row.get("category")),
                "paper_id": paper_id,
                "link_family": link_family,
                "source_id": source_id,
                "target_id": normalize_text(row.get("parameter_id")),
                "parameter_id": parameter_id,
                "raw_source_type": normalize_text(row.get("source_type")),
                "raw_target_type": normalize_text(row.get("evidence_type") or row.get("figure_type") or row.get("link_type")),
                "normalized_spectra_type": spectra_type_lookup.get((paper_id, figure_id), normalize_spectra_type(row.get("figure_type"), row.get("technique"), row.get("source_type")) if link_family == "spectra" else "Unknown"),
                "normalized_parameter_family": parameter_family_lookup.get(parameter_id, normalize_parameter_family(row.get("canonical_key"))),
                "normalized_process_step_family": process_family_lookup.get(source_id, normalize_process_step_family(row.get("source_type"), row.get("evidence_type"))),
                "link_count_or_weight": 1,
                "source_table": source_table,
                "match_method": normalize_text(row.get("created_by") or row.get("reasoning")),
            }
        )
    return rows


def _materialize_sample_links(normalized_parameters: pd.DataFrame, sample_matrix: pd.DataFrame) -> list[dict[str, Any]]:
    if normalized_parameters.empty:
        return []
    rows: list[dict[str, Any]] = []
    sample_lookup = sample_matrix.set_index(["paper_id", "sample_id"]) if not sample_matrix.empty and {"paper_id", "sample_id"}.issubset(sample_matrix.columns) else None
    for row in normalized_parameters.to_dict(orient="records"):
        if not normalize_text(row.get("sample_id")):
            continue
        rows.append(
            {
                "category": row.get("category"),
                "paper_id": row.get("paper_id"),
                "link_family": "sample",
                "source_id": row.get("sample_id"),
                "target_id": row.get("parameter_id"),
                "parameter_id": row.get("parameter_id"),
                "raw_source_type": "sample",
                "raw_target_type": row.get("parameter_key"),
                "normalized_spectra_type": "Unknown",
                "normalized_parameter_family": row.get("parameter_family"),
                "normalized_process_step_family": "Unknown",
                "link_count_or_weight": 1,
                "source_table": "all_papers_final_parameters_linked.csv",
                "match_method": "sample_link",
            }
        )
    return rows


def _build_normalized_sample_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_id", "sample_id", "sample_name", "parameter_count", "linked_parameter_count", "spectra_count"])
    columns = [column for column in [
        "category",
        "paper_id",
        "sample_id",
        "sample_name",
        "parameter_count",
        "linked_parameter_count",
        "spectra_count",
        "evidence_count",
        "linked_spectra_count",
        "linked_spectra_techniques",
    ] if column in frame.columns]
    result = frame[columns].copy()
    result["category"] = result["category"].map(normalize_category)
    return result


def _link_matrix(frame: pd.DataFrame, *, link_family: str, row_col: str, col_col: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[row_col, col_col, "count"])
    subset = frame[frame["link_family"] == link_family].copy()
    if subset.empty:
        return pd.DataFrame(columns=[row_col, col_col, "count"])
    return subset.groupby([row_col, col_col]).size().reset_index(name="count").sort_values("count", ascending=False)


def _build_category_summary(
    normalized_parameters: pd.DataFrame,
    normalized_process_steps: pd.DataFrame,
    normalized_stage4_spectra: pd.DataFrame,
    normalized_stage5_links: pd.DataFrame,
) -> pd.DataFrame:
    categories = sorted(set(normalized_parameters["category"].tolist()) | set(normalized_process_steps["category"].tolist()) | set(normalized_stage4_spectra["category"].tolist()) | set(normalized_stage5_links["category"].tolist()))
    rows: list[dict[str, Any]] = []
    for category in categories:
        rows.append(
            {
                "category": category,
                "paper_count": int(normalized_parameters.loc[normalized_parameters["category"] == category, "paper_id"].nunique()),
                "parameter_count": int((normalized_parameters["category"] == category).sum()),
                "process_step_count": int((normalized_process_steps["category"] == category).sum()),
                "spectra_count": int((normalized_stage4_spectra["category"] == category).sum()),
                "link_count": int((normalized_stage5_links["category"] == category).sum()),
            }
        )
    return pd.DataFrame(rows)


def _spectra_family_to_parameter_family(spectra_type: str) -> str:
    mapping = {
        "NMR": "NMR shift",
        "FTIR": "FTIR peak",
        "XRD": "XRD peak",
        "TG/DSC": "TG/DSC event",
        "Raman": "FTIR peak",
    }
    return mapping.get(spectra_type, "other")
