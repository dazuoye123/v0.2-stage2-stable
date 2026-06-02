from __future__ import annotations

from pathlib import Path

import pandas as pd

from alumina_sol_extractor.figure_atlas.auto_figures import generate_auto_figures


def test_auto_figures_can_be_generated(tmp_path: Path) -> None:
    tables = {
        "demo_table": pd.DataFrame(
            [
                {"category": "applications", "family": "XRD", "count": 4, "value": 1.0},
                {"category": "applications", "family": "FTIR", "count": 2, "value": 2.0},
            ]
        )
    }
    artifacts = generate_auto_figures(
        figures_root=tmp_path / "figures",
        tables_root=tmp_path / "tables",
        json_root=tmp_path / "json",
        tables=tables,
        max_auto_figures=5,
    )
    assert artifacts
    assert any((tmp_path / "tables").glob("*_source.csv"))
