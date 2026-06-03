from __future__ import annotations

import pandas as pd

from ..io import normalize_text
from ..normalization import normalize_category, normalize_process_step_family


def build_normalized_process_steps(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "paper_category", "paper_category_status", "paper_id", "paper_dir", "process_step_id", "process_step_name", "process_step_family", "raw_text", "source_table"])
    rows = []
    for row in frame.to_dict(orient="records"):
        family = normalize_process_step_family(row.get("action"), row.get("action_zh"), row.get("section"), row.get("product_or_outcome"))
        raw_text = "; ".join(
            part
            for part in [
                normalize_text(row.get("action")),
                normalize_text(row.get("action_zh")),
                normalize_text(row.get("reagent_name")),
                normalize_text(row.get("condition_key")),
                normalize_text(row.get("evidence_text")),
            ]
            if part
        )
        rows.append(
            {
                "category": normalize_category(row.get("paper_category") or row.get("category")),
                "paper_category": normalize_category(row.get("paper_category") or row.get("category")),
                "paper_category_status": normalize_text(row.get("paper_category_status")),
                "paper_id": row.get("paper_id"),
                "paper_dir": normalize_text(row.get("paper_dir")),
                "process_step_id": row.get("step_id"),
                "process_step_name": normalize_text(row.get("action") or row.get("action_zh")),
                "process_step_family": family,
                "raw_text": raw_text,
                "source_table": "all_papers_process_steps_table.csv",
            }
        )
    return pd.DataFrame(rows)
