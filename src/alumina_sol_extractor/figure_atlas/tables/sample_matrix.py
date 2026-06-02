from __future__ import annotations

import pandas as pd

from ..normalization import normalize_category


def build_normalized_sample_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_id", "sample_id", "sample_name", "parameter_count", "linked_parameter_count", "spectra_count"])
    columns = [
        column
        for column in [
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
        ]
        if column in frame.columns
    ]
    result = frame[columns].copy()
    result["category"] = result["category"].map(normalize_category)
    return result
