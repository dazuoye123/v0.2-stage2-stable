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
                "evidence_refs": [{"evidence_id": "ev-1"}],
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
                "evidence_refs": [{"evidence_id": "ev-2"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.3"],
                "linked_spectra_ids": ["Fig.3"],
            },
        ],
    )
    _write_jsonl(
        dataset_dir / "process_steps.jsonl",
        [
            {
                "step_id": "step-1",
                "step_order": 1,
                "action": "calcine",
                "evidence_text": "The fibers were calcined before characterization.",
            }
        ],
    )
    _write_jsonl(
        dataset_dir / "evidence.jsonl",
        [
            {"evidence_id": "ev-1", "evidence_type": "figure", "figure_id": "Fig.5", "figure_type": "ftir_spectrum"},
            {"evidence_id": "ev-2", "evidence_type": "figure", "figure_id": "Fig.3", "figure_type": "xrd_pattern"},
        ],
    )
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
                "source_type": "process_step",
                "source_id": "step-1",
                "target_type": "parameter",
                "target_id": "param-ftir",
                "link_type": "supports",
                "confidence": "medium",
                "reasoning": "step context",
                "created_by": "deterministic",
            },
            {
                "link_id": "link-2",
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
                "link_id": "link-3",
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
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 3})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    matrix = result["sample_parameter_matrix"][0]
    assert "parameter_count" in matrix
    assert "linked_parameter_count" in matrix
    assert matrix["parameter_count"] == 2
    assert matrix["linked_parameter_count"] == 2
    assert matrix["matrix_parameter_field_count"] == 2
    assert matrix["sample_parameter_value_count"] == 2
    assert matrix["unique_linked_parameter_count"] == 2
    assert matrix["linked_evidence_edge_count"] == 2
    assert matrix["linked_spectra_edge_count"] == 2
    assert matrix["linked_process_step_edge_count"] == 1
    assert matrix["linked_parameter_edge_count"] == 5
    assert matrix["linked_parameter_edge_count"] > matrix["matrix_parameter_field_count"]
    assert matrix["spectra_linked_parameter_count"] == 2
    assert matrix["linked_spectra_count"] == 2
    assert set(matrix["linked_spectra_ids"].split("; ")) == {"spectra-Fig.3", "spectra-Fig.5"}
    assert set(matrix["linked_spectra_figure_ids"].split("; ")) == {"Fig.3", "Fig.5"}
    assert set(matrix["linked_spectra_techniques"].split("; ")) == {"XRD", "FTIR"}

    readme_text = (dataset_dir / "link_aware_exports" / "link_aware_export_readme.md").read_text(encoding="utf-8")
    diagnosis_text = (dataset_dir / "link_aware_exports" / "link_aware_export_diagnosis.md").read_text(encoding="utf-8")
    assert "matrix_parameter_field_count" in readme_text
    assert "linked_parameter_edge_count" in readme_text
    assert "legacy fields kept for backward compatibility" in diagnosis_text



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


def test_sample_matrix_expands_dynamic_sample_linked_fields_and_unit_fallbacks(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(
        dataset_dir / "paper.json",
        {
            "paper_id": "paper-1",
            "title": "Dynamic Sample Matrix Test",
            "material_system": "alumina",
            "process_route": "sol-gel spinning",
        },
    )
    linked_parameter_ids = [
        "param-al",
        "param-si",
        "param-reaction-temp",
        "param-cooling-water-temp",
        "param-reactor-volume",
        "param-stirring-method",
        "param-solid-content",
        "param-weight",
    ]
    _write_jsonl(
        dataset_dir / "samples.jsonl",
        [{"sample_id": "S1", "sample_name": "Batch 1", "linked_parameters": linked_parameter_ids}],
    )
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {"parameter_id": "param-al", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "aluminum_source", "raw_name": "aluminum source", "value": "aluminum nitrate", "unit": "text", "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-si", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "silicon_source", "raw_name": "silicon source", "value": "silica sol", "unit": "text", "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-reaction-temp", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "reaction_temperature_C", "raw_name": "reaction temperature", "value": 85, "unit": None, "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-cooling-water-temp", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "cooling_water_temperature_C", "raw_name": "cooling water temperature", "value": 12, "unit": None, "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-reactor-volume", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "reactor_volume_m3", "raw_name": "reactor volume", "value": 0.5, "unit": None, "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-stirring-method", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "stirring_method", "raw_name": "stirring method", "value": "mechanical stirring", "unit": "text", "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-solid-content", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "solid_content_wt_percent", "raw_name": "solid content", "value": 30, "unit": None, "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
            {"parameter_id": "param-weight", "paper_id": "paper-1", "sample_id": "S1", "canonical_key": "weight_kg", "raw_name": "weight", "value": 200.02, "unit": None, "source_scope": "sample", "evidence_refs": [], "quality_flags": [], "normalization_note": None},
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
    assert matrix["aluminum_source"] == "aluminum nitrate"
    assert matrix["silicon_source"] == "silica sol"
    assert matrix["reaction_temperature_C"] == "85 C"
    assert matrix["cooling_water_temperature_C"] == "12 C"
    assert matrix["reactor_volume_m3"] == "0.5 m3"
    assert matrix["stirring_method"] == "mechanical stirring"
    assert matrix["solid_content_wt_percent"] == "30 wt%"
    assert matrix["weight_kg"] == "200.02 kg"
    assert matrix["matrix_parameter_field_count"] == 8
    assert matrix["sample_parameter_value_count"] == 8
    assert matrix["parameter_count"] == 8
    assert matrix["linked_parameter_count"] == 8

    final_parameters = {row["parameter_id"]: row for row in result["final_parameters_linked"]}
    assert final_parameters["param-reactor-volume"]["unit"] == "m3"
    assert final_parameters["param-weight"]["unit"] == "kg"

    csv_text = (dataset_dir / "link_aware_exports" / "sample_parameter_matrix.csv").read_text(encoding="utf-8")
    for field_name in (
        "silicon_source",
        "reaction_temperature_C",
        "cooling_water_temperature_C",
        "reactor_volume_m3",
        "stirring_method",
        "solid_content_wt_percent",
        "weight_kg",
    ):
        assert field_name in csv_text
