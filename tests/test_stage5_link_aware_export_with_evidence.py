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
