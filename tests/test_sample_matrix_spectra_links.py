from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.link_aware_export import generate_link_aware_exports


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_sample_matrix_collects_spectra_linked_counts_for_single_sample(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Test Paper"})
    _write_jsonl(
        dataset_dir / "samples.jsonl",
        [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["param-ftir", "param-xrd"]}],
    )
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-ftir",
                "paper_id": "paper-1",
                "sample_id": "S1",
                "canonical_key": "ftir_peak_position_cm_1",
                "raw_name": "FTIR peak",
                "value": 467,
                "unit": "cm^-1",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.5-peak-01", "figure_id": "Fig.5"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.5"],
                "linked_spectra_ids": ["Fig.5"],
            },
            {
                "parameter_id": "param-xrd",
                "paper_id": "paper-1",
                "sample_id": "S1",
                "canonical_key": "xrd_peak_position_2theta_deg",
                "raw_name": "XRD peak",
                "value": 25.5,
                "unit": "2theta_deg",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.3-peak-01", "figure_id": "Fig.3"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.3"],
                "linked_spectra_ids": ["Fig.3"],
            },
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(
        dataset_dir / "spectra.jsonl",
        [
            {"figure_id": "Fig.5", "figure_type": "ftir_spectrum", "technique": "FTIR", "peaks": [{"position": 467, "unit": "cm^-1"}]},
            {"figure_id": "Fig.3", "figure_type": "xrd_pattern", "technique": "XRD", "peaks": [{"position": 25.5, "unit": "2theta_deg"}]},
        ],
    )
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(
        dataset_dir / "linking" / "links.jsonl",
        [
            {
                "link_id": "link-1",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "spectra-Fig.5-peak-01",
                "target_type": "parameter",
                "target_id": "param-ftir",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "FTIR peak match",
                "created_by": "deterministic_spectra_peak_value_match",
            },
            {
                "link_id": "link-2",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "spectra-Fig.3-peak-01",
                "target_type": "parameter",
                "target_id": "param-xrd",
                "link_type": "supports",
                "confidence": "medium",
                "reasoning": "XRD peak match",
                "created_by": "deterministic_spectra_peak_value_match",
            },
        ],
    )
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 2})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    matrix = result["sample_parameter_matrix"][0]
    assert matrix["spectra_linked_parameter_count"] == 2
    assert matrix["linked_spectra_count"] == 2
    assert set(matrix["linked_spectra_ids"].split("; ")) == {"spectra-Fig.3", "spectra-Fig.5"}
    assert set(matrix["linked_spectra_figure_ids"].split("; ")) == {"Fig.3", "Fig.5"}
    assert set(matrix["linked_spectra_techniques"].split("; ")) == {"XRD", "FTIR"}



def test_sample_matrix_display_omits_none_units(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Test Paper"})
    _write_jsonl(
        dataset_dir / "samples.jsonl",
        [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["param-ph", "param-temp", "param-time"]}],
    )
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {"parameter_id": "param-ph", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "pH", "value": 2, "unit": None, "source_scope": "text", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-temp", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "calcination_temperature_C", "value": 600, "unit": None, "source_scope": "text", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-time", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "holding_time_h", "value": 2, "unit": None, "source_scope": "text", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(dataset_dir / "linking" / "links.jsonl", [])
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 0})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)
    matrix = result["sample_parameter_matrix"][0]
    assert matrix["pH"] == "2"
    assert matrix["calcination_temperature_C"] == "600 C"
    assert matrix["holding_time_h"] == "2 h"
    assert "None" not in json.dumps(matrix, ensure_ascii=False)
