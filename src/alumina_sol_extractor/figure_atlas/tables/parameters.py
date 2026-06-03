from __future__ import annotations

from typing import Any

import pandas as pd

from ..io import normalize_text
from ..normalization import normalize_category, normalize_numeric_value, normalize_parameter_family


def build_normalized_parameters(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "category",
                "paper_category",
                "paper_category_status",
                "paper_id",
                "paper_dir",
                "sample_id",
                "parameter_id",
                "parameter_name",
                "parameter_key",
                "raw_value",
                "numeric_value",
                "raw_unit",
                "normalized_unit",
                "parameter_family",
                "local_category",
                "source_category",
                "parameter_semantic_role",
                "included_in_main_parameter_landscape",
                "exclusion_reason",
                "source_table",
                "has_sample_link",
                "has_evidence_link",
                "has_process_step_link",
                "has_spectra_link",
                "normalization_warning",
            ]
        )
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        included = str(row.get("included_in_main_parameter_landscape") or "").strip().lower()
        if included in {"false", "0", "no"}:
            continue
        family = normalize_parameter_family(
            row.get("canonical_key"),
            row.get("zh_name"),
            row.get("en_name"),
            row.get("unit"),
            row.get("value_raw"),
            row.get("normalization_note"),
        )
        numeric_value, normalized_unit, warning = normalize_numeric_value(
            row.get("value_num") if row.get("value_num") == row.get("value_num") else row.get("value_raw"),
            row.get("unit"),
            family,
        )
        link_types = normalize_text(row.get("link_types"))
        rows.append(
            {
                "category": normalize_category(row.get("paper_category") or row.get("category")),
                "paper_category": normalize_category(row.get("paper_category") or row.get("category")),
                "paper_category_status": normalize_text(row.get("paper_category_status")),
                "paper_id": row.get("paper_id"),
                "paper_dir": normalize_text(row.get("paper_dir")),
                "sample_id": normalize_text(row.get("resolved_sample_id") or row.get("sample_id_original")),
                "parameter_id": row.get("parameter_id"),
                "parameter_name": normalize_text(row.get("zh_name") or row.get("en_name") or row.get("canonical_key")),
                "parameter_key": normalize_text(row.get("canonical_key")),
                "raw_value": normalize_text(row.get("value_raw") or row.get("value_text")),
                "numeric_value": numeric_value,
                "raw_unit": normalize_text(row.get("unit")),
                "normalized_unit": normalized_unit,
                "parameter_family": family,
                "local_category": normalize_text(row.get("local_category")),
                "source_category": normalize_text(row.get("source_category")),
                "parameter_semantic_role": normalize_text(row.get("parameter_semantic_role")),
                "included_in_main_parameter_landscape": True,
                "exclusion_reason": normalize_text(row.get("exclusion_reason")),
                "source_table": "all_papers_final_parameters_linked.csv",
                "has_sample_link": bool(normalize_text(row.get("resolved_sample_id"))),
                "has_evidence_link": bool(normalize_text(row.get("linked_evidence_ids"))),
                "has_process_step_link": "process" in link_types.lower(),
                "has_spectra_link": bool(normalize_text(row.get("linked_spectra_ids"))),
                "normalization_warning": warning,
            }
        )
    return pd.DataFrame(rows)
