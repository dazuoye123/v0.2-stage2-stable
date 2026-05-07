from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs


def test_exporters_generate_csv_and_parquet(tmp_path: Path) -> None:
    bundle = {
        "paper": {"paper_id": "paper-1"},
        "samples": [{"sample_id": "sample-1"}],
        "parameters": [{"parameter_id": "param-1"}],
        "evidence": [{"evidence_id": "ev-1"}],
        "figures": [{"figure_id": "图2.2"}],
        "spectra": [{"figure_id": "图2.2"}],
        "quality_summary": {"stage3_schema_valid": True},
        "final_dataset_rows": [
            {"paper_id": "paper-1", "sample_id": "sample-1", "canonical_key": "k", "value": 1},
            {"paper_id": "paper-1", "sample_id": "sample-2", "canonical_key": "k2", "value": "中文值"},
        ],
        "fusion_report": "ok",
    }
    output_paths = export_fusion_outputs(bundle, tmp_path / "final_dataset")
    assert Path(output_paths["final_dataset_csv"]).exists()
    assert Path(output_paths["final_dataset_parquet"]).exists()
