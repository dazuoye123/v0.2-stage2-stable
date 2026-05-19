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


def test_link_aware_export_surfaces_process_step_links_and_can_skip_showcase(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Test Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["param-1"]}])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-1",
                "paper_id": "paper-1",
                "sample_id": "S1",
                "canonical_key": "applied_voltage_kV",
                "raw_name": "applied voltage",
                "value": 18,
                "unit": "kV",
                "source_scope": "process_parameters",
                "evidence_refs": [],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            }
        ],
    )
    _write_jsonl(
        dataset_dir / "process_steps.jsonl",
        [
            {
                "step_id": "step-01",
                "step_order": 1,
                "action": "electrospin",
                "action_zh": "静电纺丝",
                "condition_key": "electrospin",
                "linked_parameter_keys": ["applied_voltage_kV"],
                "evidence_text": "外加电场 18 kV。",
                "confidence": "high",
                "needs_manual_review": False,
            }
        ],
    )
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(
        dataset_dir / "linking" / "links.jsonl",
        [
            {
                "link_id": "link-1",
                "paper_id": "paper-1",
                "source_type": "process_step",
                "source_id": "step-01",
                "target_type": "parameter",
                "target_id": "param-1",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "18 kV value match",
                "created_by": "deterministic_process_step_value_match",
            }
        ],
    )
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 1})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    assert result["summary"]["parameters_with_evidence_link"] == 1
    assert result["summary"]["showcase_is_complete"] is False
    assert result["summary"]["recommended_primary_tables"][0] == "final_parameters_linked.csv"
    assert result["evidence_parameter_links"]
    assert result["evidence_parameter_links"][0]["source_type"] == "process_step"
    assert result["process_steps_table"][0]["linked_parameter_ids"] == "param-1"
    assert result["final_parameters_linked"][0]["evidence_status"] == "process_step_evidence"
    showcase_path = dataset_dir / "link_aware_exports" / "final_showcase_table.csv"
    assert showcase_path.exists()


def test_link_aware_export_surfaces_spectra_links(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Test Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-ftir-467",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "ftir_peak_position_cm_1",
                "raw_name": "FTIR peak",
                "value": 467,
                "unit": "cm^-1",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.5-peak-01", "figure_id": "Fig.5"}],
                "quality_flags": ["derived_from_stage4_spectra"],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.5"],
                "linked_spectra_ids": ["Fig.5"],
            }
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(
        dataset_dir / "spectra.jsonl",
        [
            {
                "figure_id": "Fig.5",
                "figure_type": "ftir_spectrum",
                "schema_name": "VibrationalSpectrumExtraction",
                "technique": "FTIR",
                "peaks": [
                    {
                        "position": 467,
                        "unit": "cm^-1",
                        "assignment": "Al-O",
                        "source": "image_and_text",
                    }
                ],
            }
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
                "target_id": "param-ftir-467",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "467 cm^-1 FTIR peak matches parameter",
                "created_by": "deterministic_spectra_peak_value_match",
            }
        ],
    )
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 1})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    assert result["summary"]["parameters_with_spectra_link"] == 1
    assert result["summary"]["total_spectra_parameter_links"] == 1
    assert result["spectra_parameter_links"]
    assert result["spectra_parameter_links"][0]["canonical_key"] == "ftir_peak_position_cm_1"
    assert result["final_parameters_linked"][0]["evidence_status"] == "linked_spectra"


def test_link_aware_export_normalizes_peak_units_by_spectrum_type(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Unit Test Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-ftir-468",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "ftir_peak_position_cm_1",
                "raw_name": "FTIR peak",
                "value": 468,
                "unit": "2theta_deg",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.4-peak-01", "figure_id": "Fig.4"}],
                "quality_flags": ["derived_from_stage4_spectra"],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.4"],
                "linked_spectra_ids": ["Fig.4"],
            },
            {
                "parameter_id": "param-xrd-25",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "xrd_peak_position_2theta_deg",
                "raw_name": "XRD peak",
                "value": 25.4,
                "unit": "cm^-1",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.5-peak-01", "figure_id": "Fig.5"}],
                "quality_flags": ["derived_from_stage4_spectra"],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.5"],
                "linked_spectra_ids": ["Fig.5"],
            },
            {
                "parameter_id": "param-nmr-62",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "nmr_27Al_peak_position_ppm",
                "raw_name": "NMR peak",
                "value": 62.5,
                "unit": "2theta_deg",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [{"source_id": "spectra-Fig.6-peak-01", "figure_id": "Fig.6"}],
                "quality_flags": ["derived_from_stage4_spectra"],
                "normalization_note": None,
                "linked_figure_ids": ["Fig.6"],
                "linked_spectra_ids": ["Fig.6"],
            },
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(
        dataset_dir / "spectra.jsonl",
        [
            {
                "figure_id": "Fig.4",
                "figure_type": "ftir_spectrum",
                "schema_name": "XRDExtraction",
                "technique": "FTIR",
                "peaks": [{"position": 468, "unit": "2theta_deg", "assignment": "Al-O", "source": "image_and_text"}],
            },
            {
                "figure_id": "Fig.5",
                "figure_type": "xrd_pattern",
                "schema_name": "XRDExtraction",
                "technique": "XRD",
                "peaks": [{"position": 25.4, "unit": "cm^-1", "assignment": "(400)", "source": "image_and_text"}],
            },
            {
                "figure_id": "Fig.6",
                "figure_type": "nmr_spectrum",
                "schema_name": "NMRExtraction",
                "technique": "27Al NMR",
                "peaks": [{"position": 62.5, "unit": "2theta_deg", "assignment": "AlO4", "source": "image_and_text"}],
            },
        ],
    )
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(
        dataset_dir / "linking" / "links.jsonl",
        [
            {
                "link_id": "link-ftir",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "spectra-Fig.4-peak-01",
                "target_type": "parameter",
                "target_id": "param-ftir-468",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "468 FTIR peak matches parameter",
                "created_by": "deterministic_spectra_peak_value_match",
            },
            {
                "link_id": "link-xrd",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "spectra-Fig.5-peak-01",
                "target_type": "parameter",
                "target_id": "param-xrd-25",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "25.4 XRD peak matches parameter",
                "created_by": "deterministic_spectra_peak_value_match",
            },
            {
                "link_id": "link-nmr",
                "paper_id": "paper-1",
                "source_type": "spectra_peak",
                "source_id": "spectra-Fig.6-peak-01",
                "target_type": "parameter",
                "target_id": "param-nmr-62",
                "link_type": "supports",
                "confidence": "high",
                "reasoning": "62.5 NMR peak matches parameter",
                "created_by": "deterministic_spectra_peak_value_match",
            },
        ],
    )
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 3})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    final_by_key = {row["canonical_key"]: row for row in result["final_parameters_linked"]}
    spectra_by_key = {row["canonical_key"]: row for row in result["spectra_parameter_links"]}
    assert final_by_key["ftir_peak_position_cm_1"]["unit"] == "cm-1"
    assert final_by_key["xrd_peak_position_2theta_deg"]["unit"] == "2theta_deg"
    assert final_by_key["nmr_27Al_peak_position_ppm"]["unit"] == "ppm"
    assert spectra_by_key["ftir_peak_position_cm_1"]["peak_unit"] == "cm-1"
    assert spectra_by_key["xrd_peak_position_2theta_deg"]["peak_unit"] == "2theta_deg"
    assert spectra_by_key["nmr_27Al_peak_position_ppm"]["peak_unit"] == "ppm"


def test_link_aware_export_counts_direct_text_refs_as_conservative_evidence(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Text Evidence Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-heat-rate",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "heating_rate_C_min",
                "raw_name": "heating rate",
                "value": 2,
                "unit": "C/min",
                "source_scope": "data_point.process_parameters",
                "evidence_refs": [
                    {
                        "source_id": "text:methods-01",
                        "section": "3.2 Fiber preparation",
                        "quote_or_context": "The heating rate was controlled at 2 C/min before calcination.",
                        "confidence": 0.8,
                    }
                ],
                "quality_flags": [],
                "normalization_note": "matched_full_text:text:methods-01",
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            }
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

    assert result["evidence_parameter_links"][0]["source_type"] == "text_reference"
    assert result["evidence_parameter_links"][0]["source_id"] == "text:methods-01"
    assert "2 C/min" in result["evidence_parameter_links"][0]["evidence_text_preview"]
    assert result["summary"]["parameters_with_any_link"] == 1
    assert result["summary"]["parameters_missing_all_links"] == 0
    final_row = result["final_parameters_linked"][0]
    assert final_row["link_count"] == 1
    assert final_row["evidence_status"] == "linked_evidence"


def test_link_aware_export_counts_direct_evidence_refs_as_evidence_links(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Evidence Ref Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-1",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "take_up_speed_m_min",
                "raw_name": "take-up speed",
                "value": 160,
                "unit": "m/min",
                "source_scope": "text",
                "evidence_refs": [{"evidence_id": "ev-1"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            }
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(
        dataset_dir / "evidence.jsonl",
        [
            {
                "evidence_id": "ev-1",
                "evidence_type": "text",
                "caption": "Method section",
                "fact_summary": ["The take-up speed was 160 m/min during dry spinning."],
                "detailed_observation": "The take-up speed was 160 m/min during dry spinning.",
            }
        ],
    )
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(dataset_dir / "linking" / "links.jsonl", [])
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 0})

    result = generate_link_aware_exports(dataset_dir, include_showcase=False)

    evidence_rows = result["evidence_parameter_links"]
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["source_type"] == "evidence_object"
    assert evidence_rows[0]["evidence_id"] == "ev-1"
    final_row = result["final_parameters_linked"][0]
    assert final_row["link_count"] == 1
    assert final_row["evidence_status"] == "strong_evidence"


def test_link_aware_export_uses_normalization_note_text_ref_without_faking_evidence_object(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Normalization Note Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-1",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "concentration_temperature_C",
                "raw_name": "concentration temperature",
                "value": 45,
                "unit": "C",
                "source_scope": "text",
                "evidence_refs": [],
                "quality_flags": [],
                "normalization_note": "matched_full_text:text:methods-28; moved_from_global_constants_top_level",
                "source_text": "The sol was concentrated at 45 C in a water bath under reduced pressure.",
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            }
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

    evidence_rows = result["evidence_parameter_links"]
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["source_type"] == "text_reference"
    assert evidence_rows[0]["source_id"] == "text:methods-28"
    assert evidence_rows[0]["confidence"] == "medium"
    assert evidence_rows[0]["evidence_id"] is None
    assert evidence_rows[0]["reasoning"] == "derived from normalization_note matched_full_text text reference"
    assert result["summary"]["parameters_with_any_link"] == 1
    assert result["summary"]["parameters_missing_all_links"] == 0
    final_row = result["final_parameters_linked"][0]
    assert final_row["link_count"] == 1
    assert final_row["evidence_status"] == "linked_evidence"
