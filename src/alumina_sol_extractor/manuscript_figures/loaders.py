from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_csv, read_json


def load_diagnosis_payload(diagnosis_dir: Path) -> dict[str, Any]:
    root = Path(diagnosis_dir)
    source_root = root / "source_tables"
    figures = {
        "Fig1": read_csv(source_root / "Fig1_dataset_coverage_source.csv"),
        "Fig2": read_csv(source_root / "Fig2_synthesis_parameter_landscape_source.csv"),
        "Fig4": read_csv(source_root / "Fig4_characterization_evidence_atlas_source.csv"),
    }
    return {
        "diagnosis_dir": root,
        "source_root": source_root,
        "figures": figures,
        "figure_plan_csv": read_csv(root / "manuscript_figure_plan.csv"),
        "figure_plan_json": read_json(root / "manuscript_figure_plan.json", default=[]),
        "diagnosis_report": (root / "diagnosis_report.md").read_text(encoding="utf-8"),
        "data_quality_summary": read_json(root / "data_quality_summary.json", default={}),
    }


def figure_plan_lookup(plan_rows: list[dict[str, Any]] | pd.DataFrame) -> dict[str, dict[str, Any]]:
    if isinstance(plan_rows, pd.DataFrame):
        records = plan_rows.to_dict(orient="records")
    else:
        records = list(plan_rows)
    return {str(row["figure_id"]): row for row in records}
