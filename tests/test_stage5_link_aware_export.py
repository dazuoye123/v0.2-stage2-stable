from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alumina_sol_extractor.dataset_fusion.link_aware_export import generate_link_aware_exports
from alumina_sol_extractor.dataset_fusion.link_aware_io import build_link_aware_diagnosis


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _build_dataset(tmp_path: Path, *, links: list[dict] | None = None, spectra: list[dict] | None = None) -> Path:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(
        dataset_dir / "paper.json",
        {
            "paper_id": "paper-1",
            "title": "Test Paper",
            "material_system": "alumina",
            "process_route": "test route",
        },
    )
    _write_jsonl(
        dataset_dir / "samples.jsonl",
        [
            {"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["param-1", "param-3"]},
            {"sample_id": "S2", "sample_name": "Sample 2", "linked_parameters": ["param-2"]},
        ],
    )
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-1",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "aluminum_source",
                "raw_name": "aluminum source",
                "value": "异丙醇铝",
                "unit": "text",
                "source_scope": "global_constants.additional_parameter_records",
                "evidence_refs": [{"evidence_id": "ev-1"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            },
            {
                "parameter_id": "param-2",
                "paper_id": "paper-1",
                "sample_id": "S2",
                "canonical_key": "pH",
                "raw_name": "pH",
                "value": "18-24",
                "unit": "dimensionless",
                "source_scope": "data_point",
                "evidence_refs": [],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            },
            {
                "parameter_id": "param-3",
                "paper_id": "paper-1",
                "sample_id": None,
                "canonical_key": "nmr_27Al_peak_position_ppm",
                "raw_name": "27Al NMR peak",
                "value": 62.5,
                "unit": "ppm",
                "source_scope": "global_constants.additional_parameter_records",
                "evidence_refs": [],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            },
            {
                "parameter_id": "param-4",
                "paper_id": "paper-1",
                "sample_id": "S1",
                "canonical_key": "Al13_fraction_percent",
                "raw_name": "Al13 fraction",
                "value": 50,
                "unit": "%",
                "source_scope": "sample",
                "evidence_refs": [{"evidence_id": "ev-2"}],
                "quality_flags": [],
                "normalization_note": None,
                "linked_figure_ids": [],
                "linked_spectra_ids": [],
            },
        ],
    )
    _write_jsonl(
        dataset_dir / "evidence.jsonl",
        [
            {
                "evidence_id": "ev-1",
                "evidence_type": "figure",
                "figure_id": "图1",
                "table_id": None,
                "figure_type": "photo_image",
                "caption": "图1 evidence",
                "fact_summary": ["evidence summary"],
                "detailed_observation": "evidence details",
            },
            {
                "evidence_id": "ev-2",
                "evidence_type": "figure",
                "figure_id": "图2.2",
                "table_id": None,
                "figure_type": "nmr_spectrum",
                "caption": "图2.2 NMR",
                "fact_summary": ["62.5 ppm peak"],
                "detailed_observation": "NMR evidence",
            },
        ],
    )
    _write_jsonl(dataset_dir / "spectra.jsonl", spectra or [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    if links is not None:
        _write_jsonl(dataset_dir / "linking" / "links.jsonl", links)
        _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": len(links)})
    return dataset_dir


def test_link_aware_export_uses_links_and_does_not_modify_sources(tmp_path: Path) -> None:
    links = [
        {
            "link_id": "link-1",
            "paper_id": "paper-1",
            "source_type": "parameter",
            "source_id": "param-1",
            "target_type": "sample",
            "target_id": "S1",
            "link_type": "describes",
            "confidence": "high",
            "reasoning": "sample match",
            "created_by": "deterministic",
        },
        {
            "link_id": "link-2",
            "paper_id": "paper-1",
            "source_type": "parameter",
            "source_id": "param-3",
            "target_type": "sample",
            "target_id": "S1",
            "link_type": "describes",
            "confidence": "high",
            "reasoning": "sample match",
            "created_by": "deterministic",
        },
        {
            "link_id": "link-3",
            "paper_id": "paper-1",
            "source_type": "spectra_record",
            "source_id": "spectra-图2.2",
            "target_type": "evidence_object",
            "target_id": "ev-2",
            "link_type": "same_figure",
            "confidence": "high",
            "reasoning": "same figure",
            "created_by": "deterministic",
        },
        {
            "link_id": "link-4",
            "paper_id": "paper-1",
            "source_type": "spectra_peak",
            "source_id": "spectra-图2.2-peak-01",
            "target_type": "parameter",
            "target_id": "param-3",
            "link_type": "supports",
            "confidence": "high",
            "reasoning": "peak match",
            "created_by": "deterministic",
        },
    ]
    spectra = [
        {
            "figure_id": "图2.2",
            "figure_type": "nmr_spectrum",
            "schema_name": "NMRExtraction",
            "technique": "27Al NMR",
            "peaks": [
                {
                    "position": 62.5,
                    "unit": "ppm",
                    "assignment": "Al13",
                    "source": "image_and_text",
                }
            ],
        }
    ]
    dataset_dir = _build_dataset(tmp_path, links=links, spectra=spectra)
    parameters_before = (dataset_dir / "parameters.jsonl").read_text(encoding="utf-8")

    result = generate_link_aware_exports(dataset_dir)

    linked_rows = result["final_parameters_linked"]
    param1 = next(row for row in linked_rows if row["parameter_id"] == "param-1")
    assert param1["value_type"] == "text"
    assert param1["unit"] is None
    assert param1["resolved_sample_id"] == "S1"
    assert param1["sample_resolution_source"] == "parameter_sample_link"
    assert param1["linked_evidence_ids"] == "ev-1"
    assert param1["evidence_status"] == "strong_evidence"

    param2 = next(row for row in linked_rows if row["parameter_id"] == "param-2")
    assert param2["value_type"] == "range"

    param3 = next(row for row in linked_rows if row["parameter_id"] == "param-3")
    assert param3["linked_spectra_ids"] == "spectra-图2.2"
    assert param3["linked_peak_positions"] == "62.5"
    assert param3["evidence_status"] == "linked_spectra"

    sample_matrix = result["sample_parameter_matrix"]
    row_s1 = next(row for row in sample_matrix if row["sample_id"] == "S1")
    assert row_s1["aluminum_source"] == "异丙醇铝"
    assert row_s1["nmr_27Al_peak_position_ppm"] == "62.5 ppm"

    evidence_links = result["evidence_parameter_links"]
    assert len(evidence_links) == 2
    assert {row["parameter_id"] for row in evidence_links} == {"param-1", "param-4"}
    assert {row["evidence_id"] for row in evidence_links} == {"ev-1", "ev-2"}

    spectra_links = result["spectra_parameter_links"]
    assert len(spectra_links) >= 1
    assert any(row["peak_position"] == 62.5 for row in spectra_links)
    assert any(row["link_type"] == "indirect_spectra_evidence_parameter" and row["parameter_id"] == "param-4" for row in spectra_links)

    showcase = result["final_showcase_table"]
    assert showcase
    assert showcase[0]["link_status"] != "missing"

    assert (dataset_dir / "parameters.jsonl").read_text(encoding="utf-8") == parameters_before
    assert (dataset_dir / "link_aware_exports" / "final_parameters_linked.csv").exists()
    assert (dataset_dir / "link_aware_exports" / "final_parameters_linked.parquet").exists()
    assert (dataset_dir / "link_aware_exports" / "sample_parameter_matrix.csv").exists()
    assert (dataset_dir / "link_aware_exports" / "evidence_parameter_links.csv").exists()
    assert (dataset_dir / "link_aware_exports" / "spectra_parameter_links.csv").exists()
    assert (dataset_dir / "link_aware_exports" / "final_showcase_table.csv").exists()


def test_link_aware_export_handles_missing_links_and_empty_spectra(tmp_path: Path) -> None:
    dataset_dir = _build_dataset(tmp_path, links=None, spectra=[])
    result = generate_link_aware_exports(dataset_dir)

    assert result["summary"]["parameters_missing_all_links"] >= 1
    spectra_table = dataset_dir / "link_aware_exports" / "spectra_parameter_links.csv"
    frame = pd.read_csv(spectra_table)
    assert list(frame.columns) == [
        "paper_id",
        "spectra_id",
        "figure_id",
        "figure_type",
        "technique",
        "peak_position",
        "peak_unit",
        "assignment",
        "source",
        "observed_value",
        "observed_unit",
        "parameter_id",
        "canonical_key",
        "parameter_value",
        "unit",
        "sample_id",
        "link_type",
        "confidence",
        "reasoning",
        "created_by",
    ]
    assert frame.empty


def test_link_aware_export_diagnosis_matches_latest_summary_and_tables(tmp_path: Path) -> None:
    dataset_dir = _build_dataset(tmp_path, links=None, spectra=[])
    result = generate_link_aware_exports(dataset_dir, include_showcase=False)
    output_dir = dataset_dir / "link_aware_exports"

    summary = json.loads((output_dir / "link_aware_export_summary.json").read_text(encoding="utf-8"))
    diagnosis = (output_dir / "link_aware_export_diagnosis.md").read_text(encoding="utf-8")
    process_steps_rows = len(pd.read_csv(output_dir / "process_steps_table.csv"))
    evidence_rows = len(pd.read_csv(output_dir / "evidence_parameter_links.csv"))
    sample_rows = len(pd.read_csv(output_dir / "sample_parameter_matrix.csv"))

    assert result["summary"] == summary
    assert f"- `total_parameters`: {summary['total_parameters']}" in diagnosis
    assert f"- `parameters_missing_all_links`: {summary['parameters_missing_all_links']}" in diagnosis
    assert f"- `process_step_parameter_links`: {summary['process_step_parameter_links']}" in diagnosis
    assert f"- `sample_matrix_rows`: {summary['sample_matrix_rows']}" in diagnosis
    assert f"- `process_steps_table.csv` rows: {process_steps_rows}" in diagnosis
    assert f"- `evidence_parameter_links.csv` rows: {evidence_rows}" in diagnosis
    assert f"- `sample_parameter_matrix.csv` rows: {sample_rows}" in diagnosis


def test_link_aware_export_diagnosis_rebuilds_updated_summary_and_warns_on_missing_file(tmp_path: Path) -> None:
    dataset_dir = _build_dataset(tmp_path, links=None, spectra=[])
    generate_link_aware_exports(dataset_dir, include_showcase=False)
    output_dir = dataset_dir / "link_aware_exports"
    summary_path = output_dir / "link_aware_export_summary.json"

    updated_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    updated_summary["total_parameters"] = 99
    updated_summary["parameters_missing_all_links"] = 7
    updated_summary["process_step_parameter_links"] = 3
    updated_summary["sample_matrix_rows"] = 4
    summary_path.write_text(json.dumps(updated_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "process_steps_table.csv").unlink()

    diagnosis = build_link_aware_diagnosis(output_dir)

    assert f"- `total_parameters`: {updated_summary['total_parameters']}" in diagnosis
    assert f"- `parameters_missing_all_links`: {updated_summary['parameters_missing_all_links']}" in diagnosis
    assert f"- `process_step_parameter_links`: {updated_summary['process_step_parameter_links']}" in diagnosis
    assert f"- `sample_matrix_rows`: {updated_summary['sample_matrix_rows']}" in diagnosis
    assert "- `process_steps_table.csv` rows: warning" in diagnosis
    assert "- `missing_file:process_steps_table.csv`" in diagnosis
