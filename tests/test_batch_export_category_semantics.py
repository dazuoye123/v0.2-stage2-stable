from __future__ import annotations

import csv
import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import export_batch_link_aware_dataset


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _build_dataset(outputs_dir: Path) -> None:
    dataset_dir = outputs_dir / "mechanism" / "paper-batch" / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-batch", "title": "Batch Test"})
    _write_jsonl(dataset_dir / "samples.jsonl", [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": ["p1"]}])
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "p1",
                "paper_id": "paper-batch",
                "sample_id": "S1",
                "canonical_key": "pH",
                "raw_name": "pH",
                "value": 4.1,
                "unit": "dimensionless",
                "source_scope": "data_point",
                "evidence_refs": [],
            }
        ],
    )
    _write_jsonl(dataset_dir / "process_steps.jsonl", [])
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {})
    _write_jsonl(dataset_dir / "linking" / "links.jsonl", [])
    _write_json(dataset_dir / "linking" / "linking_summary.json", {})


def test_batch_export_rebuilds_official_paper_category_semantics(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    _build_dataset(outputs_dir)

    result = export_batch_link_aware_dataset(outputs_dir, output_dir=tmp_path / "_batch_semantic")

    assert result["summary"]["rebuilt_paper_count"] == 1
    assert result["summary"]["official_paper_count"] == 1
    assert result["summary"]["missing_identity_row_count"] == 0

    aggregate_path = tmp_path / "_batch_semantic" / "all_papers_final_parameters_linked.csv"
    with aggregate_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["paper_category"] == "mechanism"
    assert rows[0]["category"] == "mechanism"
    assert rows[0]["paper_category_status"] == "official"

    semantic_path = tmp_path / "_batch_semantic" / "all_papers_parameter_semantic_qa.csv"
    assert semantic_path.exists()
