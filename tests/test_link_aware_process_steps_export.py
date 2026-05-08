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


def test_link_aware_export_generates_process_steps_table(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(dataset_dir / "paper.json", {"paper_id": "paper-1", "title": "Test Paper"})
    _write_jsonl(dataset_dir / "samples.jsonl", [{"sample_id": "S1", "sample_name": "Sample 1", "linked_parameters": []}])
    _write_jsonl(dataset_dir / "parameters.jsonl", [])
    _write_jsonl(
        dataset_dir / "process_steps.jsonl",
        [
            {
                "step_id": "step-01",
                "step_order": 1,
                "action": "dissolve",
                "action_zh": "溶解",
                "reagent_name": "AlCl3·6H2O",
                "reagent_amount": 0.005,
                "reagent_unit": "mol",
                "linked_parameter_keys": ["aluminum_source"],
                "evidence_text": "0.005 mol AlCl3·6H2O 溶于一定量去离子水中。",
                "confidence": "high",
                "needs_manual_review": False,
            }
        ],
    )
    _write_jsonl(dataset_dir / "evidence.jsonl", [])
    _write_jsonl(dataset_dir / "spectra.jsonl", [])
    _write_jsonl(dataset_dir / "figures.jsonl", [])
    _write_json(dataset_dir / "quality_summary.json", {"invalid_canonical_key_count": 0})
    _write_jsonl(dataset_dir / "linking" / "links.jsonl", [])
    _write_json(dataset_dir / "linking" / "linking_summary.json", {"accepted_links": 0})

    result = generate_link_aware_exports(dataset_dir)
    assert len(result["process_steps_table"]) == 1
    row = result["process_steps_table"][0]
    assert row["reagent_name"] == "AlCl3·6H2O"
    assert row["linked_parameter_keys"] == "aluminum_source"
    assert (dataset_dir / "link_aware_exports" / "process_steps_table.csv").exists()
