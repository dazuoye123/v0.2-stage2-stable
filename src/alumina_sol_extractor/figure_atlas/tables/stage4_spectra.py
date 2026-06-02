from __future__ import annotations

import pandas as pd

from ..normalization import normalize_category, normalize_spectra_type


def build_normalized_stage4_spectra(frame: pd.DataFrame) -> pd.DataFrame:
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
