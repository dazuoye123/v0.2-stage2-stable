from __future__ import annotations

from typing import Any

import pandas as pd


def build_category_summary(
    normalized_parameters: pd.DataFrame,
    normalized_process_steps: pd.DataFrame,
    normalized_stage4_spectra: pd.DataFrame,
    normalized_stage5_links: pd.DataFrame,
) -> pd.DataFrame:
    categories = sorted(
        set(normalized_parameters["category"].tolist())
        | set(normalized_process_steps["category"].tolist())
        | set(normalized_stage4_spectra["category"].tolist())
        | set(normalized_stage5_links["category"].tolist())
    )
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
