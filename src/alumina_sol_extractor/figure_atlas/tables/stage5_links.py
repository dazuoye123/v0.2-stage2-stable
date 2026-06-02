from __future__ import annotations

from typing import Any

import pandas as pd

from ..io import normalize_text
from ..normalization import normalize_category, normalize_parameter_family, normalize_process_step_family, normalize_spectra_type


def build_normalized_links(
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
                "normalized_spectra_type": spectra_type_lookup.get(
                    (paper_id, figure_id),
                    normalize_spectra_type(row.get("figure_type"), row.get("technique"), row.get("source_type")) if link_family == "spectra" else "Unknown",
                ),
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
    _ = sample_matrix
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
