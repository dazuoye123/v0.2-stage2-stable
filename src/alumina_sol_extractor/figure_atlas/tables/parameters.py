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
                "paper_id",
                "sample_id",
                "parameter_id",
                "parameter_name",
                "parameter_key",
                "raw_value",
                "numeric_value",
                "raw_unit",
                "normalized_unit",
                "parameter_family",
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
