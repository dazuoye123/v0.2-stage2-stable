from __future__ import annotations

from pathlib import Path

import pandas as pd

from alumina_sol_extractor.research_figures.figure_builders import generate_all_figures


def test_all_figures_generate_with_empty_data_fallback(tmp_path: Path) -> None:
    figure_tables = {
        "stage3_parameter_coverage": pd.DataFrame(),
        "stage3_sample_parameter_heatmap": pd.DataFrame(),
        "stage3_numeric_parameter_distribution": pd.DataFrame(),
        "stage4_extraction_overview": pd.DataFrame(),
        "stage4_figure_type_distribution": pd.DataFrame(),
        "stage4_spectra_type_distribution": pd.DataFrame(),
        "stage4_peak_summary": pd.DataFrame(),
        "stage3_stage4_link_overview": pd.DataFrame(),
        "stage4_statistics": pd.DataFrame(),
        "stage4_peak_rows": pd.DataFrame(),
    }
    generated = generate_all_figures(tmp_path / "figures", figure_tables)

    assert any(path.endswith("stage3_parameter_coverage.svg") for path in generated)
    assert (tmp_path / "figures" / "stage3_stage4_research_overview.png").exists()
