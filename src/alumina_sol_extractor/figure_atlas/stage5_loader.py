from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import read_csv, read_json


def load_stage5_batch_exports(batch_final_export_dir: Path) -> dict[str, Any]:
    return {
        "final_parameters_linked": read_csv(batch_final_export_dir / "all_papers_final_parameters_linked.csv"),
        "evidence_parameter_links": read_csv(batch_final_export_dir / "all_papers_evidence_parameter_links.csv"),
        "process_step_parameter_links": read_csv(batch_final_export_dir / "all_papers_process_step_parameter_links.csv"),
        "spectra_parameter_links": read_csv(batch_final_export_dir / "all_papers_spectra_parameter_links.csv"),
        "process_steps_table": read_csv(batch_final_export_dir / "all_papers_process_steps_table.csv"),
        "sample_parameter_matrix": read_csv(batch_final_export_dir / "all_papers_sample_parameter_matrix.csv"),
        "final_showcase_table": read_csv(batch_final_export_dir / "all_papers_final_showcase_table.csv"),
        "link_aware_summary": read_json(batch_final_export_dir / "all_papers_link_aware_summary.json", default={}) or {},
    }
