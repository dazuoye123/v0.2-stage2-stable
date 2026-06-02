from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_csv, read_json


def load_stage3_inputs(
    *,
    project_root: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
) -> dict[str, Any]:
    primary_dir = stage3_analysis_dir or _first_existing(
        project_root / "data" / "analysis_outputs_stage3_v2",
        project_root / "data" / "analysis_outputs_stage3",
    )
    fallback_dir = project_root / "data" / "analysis_outputs_stage3"
    publication_dir = stage3_publication_dir or _first_existing(project_root / "data" / "analysis_outputs_stage3_publication")
    if primary_dir is None:
        raise FileNotFoundError("Stage3 analysis outputs not found.")

    return {
        "analysis_dir": str(primary_dir),
        "publication_dir": str(publication_dir) if publication_dir else None,
        "summary": read_json(_first_existing(primary_dir / "analysis_outputs_stage3_summary.json", primary_dir / "stage3_analysis_summary.json", fallback_dir / "stage3_analysis_summary.json"), default={}) or {},
        "parameter_distribution": read_csv(_first_existing(primary_dir / "parameter_distribution.csv", fallback_dir / "parameter_distribution.csv")),
        "sample_parameter_long": read_csv(_first_existing(primary_dir / "sample_parameter_long.csv", fallback_dir / "sample_parameter_long.csv")),
        "paper_stage3_summary": read_csv(_first_existing(primary_dir / "paper_stage3_summary.csv", fallback_dir / "paper_stage3_summary.csv")),
        "canonical_key_category_summary": read_csv(_first_existing(primary_dir / "canonical_key_category_summary.csv", primary_dir / "canonical_key_by_category.csv", fallback_dir / "canonical_key_category_summary.csv", fallback_dir / "canonical_key_by_category.csv")),
        "time_condition_distribution": read_csv(_first_existing(primary_dir / "time_condition_distribution_by_type.csv", primary_dir / "process_condition_distribution.csv", fallback_dir / "time_condition_distribution_by_type.csv", fallback_dir / "process_condition_distribution.csv")),
        "coverage_matrix_plotting_data": read_csv(publication_dir / "fig3_coverage_matrix_plotting_data.csv") if publication_dir and (publication_dir / "fig3_coverage_matrix_plotting_data.csv").exists() else pd.DataFrame(),
        "paper_metadata_plotting_data": read_csv(publication_dir / "fig3_paper_metadata_plotting_data.csv") if publication_dir and (publication_dir / "fig3_paper_metadata_plotting_data.csv").exists() else pd.DataFrame(),
        "label_mapping": read_csv(publication_dir / "label_mapping.csv") if publication_dir and (publication_dir / "label_mapping.csv").exists() else pd.DataFrame(),
    }


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
