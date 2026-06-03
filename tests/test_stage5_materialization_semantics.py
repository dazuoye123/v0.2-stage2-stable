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
    dataset_dir = tmp_path / "fiber_process" / "paper-materialization" / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-materialization", "title": "Materialization Test"})
    _write_jsonl(dataset_dir / "samples.jsonl", [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["p1"]}])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "p1",
                "paper_id": "paper-materialization",
                "sample_id": "S1",
                "canonical_key": "pH",
                "raw_name": "pH",
                "value": 3.8,
                "unit": "dimensionless",
                "source_scope": "data_point",
                "evidence_refs": [],
            },
            {
                "parameter_id": "p2",
                "paper_id": "paper-materialization",
                "sample_id": None,
                "canonical_key": "series_id",
                "raw_name": "series_id",
                "value": "abc",
                "unit": "",
                "source_scope": "global_constants.additional_parameter_records",
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


def test_stage5_materialization_fields_are_preserved_on_included_rows(tmp_path: Path) -> None:
    dataset_dir = _build_dataset(tmp_path)
    result = generate_link_aware_exports(dataset_dir, write_outputs=False)

    row = result["final_parameters_linked"][0]
    assert row["paper_category"] == "fiber_process"
    assert row["category"] == "fiber_process"
    assert row["paper_category_status"] == "official"
    assert row["parameter_semantic_role"] == "synthesis_process_property"
    assert row["included_in_main_parameter_landscape"] is True
    assert row["source_file"].endswith("final_dataset/parameters.jsonl")
    assert row["source_stage"] == "stage3.final_dataset.parameters"
