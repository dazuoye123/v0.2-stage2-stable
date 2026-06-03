from __future__ import annotations

import pandas as pd

from ..normalization import normalize_category


def build_normalized_sample_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_category", "paper_category_status", "paper_id", "sample_id", "sample_name", "parameter_count", "linked_parameter_count", "spectra_count"])
    columns = [
        column
        for column in [
            "category",
            "paper_category",
            "paper_category_status",
            "paper_id",
            "sample_id",
            "sample_name",
            "parameter_count",
            "linked_parameter_count",
            "spectra_count",
            "evidence_count",
            "linked_spectra_count",
            "linked_spectra_techniques",
        ]
        if column in frame.columns
    ]
    result = frame[columns].copy()
    source = result["paper_category"] if "paper_category" in result.columns else result["category"]
    result["category"] = source.map(normalize_category)
    if "paper_category" not in result.columns:
        result["paper_category"] = result["category"]
    return result
