from __future__ import annotations

import pandas as pd

from alumina_sol_extractor.manuscript_figures.data_logic import attach_resolved_category, build_paper_category_map


def test_manuscript_source_category_resolution_prefers_paper_category() -> None:
    tables = {
        "stage3_paper_summary": pd.DataFrame([{"paper_id": "p1", "category": "applications"}]),
        "stage4_paper_summary": pd.DataFrame([{"paper_id": "p1", "category": "applications"}]),
        "normalized_parameters": pd.DataFrame(
            [
                {
                    "paper_id": "p1",
                    "paper_category": "applications",
                    "category": "spectroscopy",
                    "parameter_id": "param-1",
                }
            ]
        ),
        "normalized_stage4_spectra": pd.DataFrame([{"paper_id": "p1", "paper_category": "applications", "category": "applications"}]),
        "normalized_stage5_links": pd.DataFrame([{"paper_id": "p1", "paper_category": "applications", "category": "applications"}]),
    }

    paper_category_map = build_paper_category_map(tables)
    resolved = attach_resolved_category(tables["normalized_parameters"], paper_category_map)

    assert paper_category_map["p1"] == "applications"
    assert resolved.iloc[0]["original_category"] == "spectroscopy"
    assert resolved.iloc[0]["paper_category_original"] == "applications"
    assert resolved.iloc[0]["resolved_category"] == "applications"
