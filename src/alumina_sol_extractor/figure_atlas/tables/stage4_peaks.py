from __future__ import annotations

from typing import Any

import pandas as pd

from ..io import normalize_text, safe_float
from ..normalization import normalize_category, normalize_numeric_value, normalize_spectra_type


def build_normalized_stage4_peaks(frame: pd.DataFrame) -> pd.DataFrame:
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


def _spectra_family_to_parameter_family(spectra_type: str) -> str:
    mapping = {
        "NMR": "NMR shift",
        "FTIR": "FTIR peak",
        "XRD": "XRD peak",
        "TG/DSC": "TG/DSC event",
        "Raman": "FTIR peak",
    }
    return mapping.get(spectra_type, "other")
