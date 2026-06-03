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


def _build_dataset(tmp_path: Path) -> Path:
    dataset_dir = tmp_path / "mechanism" / "paper-semantic" / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-semantic", "title": "Semantic Test"})
    _write_jsonl(dataset_dir / "samples.jsonl", [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["p1"]}])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "p1",
                "paper_id": "paper-semantic",
                "sample_id": "S1",
                "canonical_key": "pH",
                "raw_name": "pH",
                "value": 4.5,
                "unit": "dimensionless",
                "source_scope": "data_point",
                "evidence_refs": [],
            },
            {
                "parameter_id": "p2",
                "paper_id": "paper-semantic",
                "sample_id": None,
                "canonical_key": "parent_series_id",
                "raw_name": "parent_series_id",
                "value": "series-1",
                "unit": "",
                "source_scope": "extended_data.parent_series_id",
                "evidence_refs": [],
            },
            {
                "parameter_id": "p3",
                "paper_id": "paper-semantic",
                "sample_id": None,
                "canonical_key": "xrd_peak_position_2theta_deg",
                "raw_name": "XRD peak",
                "value": 25.5,
                "unit": "2theta_deg",
                "source_scope": "stage4.spectra.peaks",
                "evidence_refs": [],
            },
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {})
    _write_jsonl(dataset_dir / "linking" / "links.jsonl", [])
    _write_json(dataset_dir / "linking" / "linking_summary.json", {})
    return dataset_dir


def test_parameter_semantic_filtering_excludes_metadata_and_characterization_outputs(tmp_path: Path) -> None:
    dataset_dir = _build_dataset(tmp_path)
    result = generate_link_aware_exports(dataset_dir, write_outputs=False)

    linked_ids = {row["parameter_id"] for row in result["final_parameters_linked"]}
    excluded_lookup = {row["parameter_id"]: row for row in result["excluded_parameters"]}
    semantic_lookup = {row["parameter_id"]: row for row in result["parameter_semantic_qa"]}

    assert linked_ids == {"p1"}
    assert excluded_lookup["p2"]["parameter_semantic_role"] == "metadata_or_bookkeeping"
    assert excluded_lookup["p2"]["exclusion_reason"] == "metadata_like_key"
    assert excluded_lookup["p3"]["parameter_semantic_role"] == "characterization_output"
    assert excluded_lookup["p3"]["exclusion_reason"] == "characterization_peak_from_stage4"
    assert semantic_lookup["p1"]["included_in_main_parameter_landscape"] is True
