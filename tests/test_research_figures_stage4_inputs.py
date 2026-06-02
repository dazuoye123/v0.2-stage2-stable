from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.research_figures.stage4_inputs import load_stage4_batch_data


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def test_stage4_outputs_are_aggregated_to_batch_statistics(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "data" / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper-1"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    _write_json(stage4_dir / "stage4a_summary.json", {"total_candidates": 2, "successful_extractions_count": 1, "failed_record_count": 1, "validation_error_count": 0, "by_stage2_figure_class": {"generic_chart_or_plot": 1, "microscopy_image": 1}})
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [{"figure_id": "Fig.1", "figure_type": "xrd_pattern", "technique": "XRD", "peaks": [{"position": 25.6, "unit": "2theta_deg"}]}])
    _write_jsonl(stage4_dir / "failed_records.jsonl", [{"figure_id": "Fig.2", "error_type": "ValueError"}])
    _write_jsonl(paper_dir / "final_dataset" / "linking" / "links.jsonl", [{"link_id": "l1", "source_type": "spectra_peak", "source_id": "spectra-Fig.1", "target_type": "parameter", "target_id": "param-1"}])
    _write_jsonl(paper_dir / "final_dataset" / "parameters.jsonl", [{"parameter_id": "param-1", "canonical_key": "calcination_temperature_C"}])
    _write_jsonl(paper_dir / "final_dataset" / "samples.jsonl", [{"sample_id": "s1", "sample_name": "Sample 1"}])

    payload = load_stage4_batch_data(outputs_dir)

    assert len(payload["per_paper_rows"]) == 1
    assert payload["extraction_overview"]["count"].sum() >= 2
    assert not payload["spectra_type_distribution"].empty
    assert not payload["peak_summary"].empty

    filtered = load_stage4_batch_data(outputs_dir, selected_pairs={("fiber_process", "paper-1")}, selected_paper_ids={"paper-1"})
    assert len(filtered["per_paper_rows"]) == 1
    missing = load_stage4_batch_data(outputs_dir, selected_pairs={("fiber_process", "paper-x")}, selected_paper_ids={"paper-x"})
    assert missing["extraction_overview"]["count"].sum() == 0
