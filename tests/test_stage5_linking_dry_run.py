from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.linking.candidate_builder import load_final_dataset_inputs
from alumina_sol_extractor.linking.llm_linker import EvidenceSpectraParameterLinker


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_final_dataset(tmp_path: Path) -> Path:
    dataset_dir = tmp_path / "final_dataset"
    _write_json(
        dataset_dir / "paper.json",
        {
            "paper_id": "paper-1",
            "title": "Test Paper",
        },
    )
    _write_jsonl(
        dataset_dir / "samples.jsonl",
        [{"sample_id": "sample-1", "sample_name": "sample", "linked_parameters": ["param-1"], "linked_evidence": [], "linked_spectra": []}],
    )
    _write_jsonl(
        dataset_dir / "parameters.jsonl",
        [
            {
                "parameter_id": "param-1",
                "paper_id": "paper-1",
                "sample_id": "sample-1",
                "canonical_key": "nmr_27Al_peak_position_ppm",
                "raw_name": "27Al NMR peak",
                "value": 62.5,
                "unit": "ppm",
                "evidence_refs": [],
                "linked_figure_ids": [],
                "linked_spectra_ids": ["图2.2"],
            }
        ],
    )
    _write_jsonl(
        dataset_dir / "evidence.jsonl",
        [{"evidence_id": "图2.2", "figure_id": "图2.2", "figure_type": "nmr_spectrum", "caption": "NMR figure"}],
    )
    _write_jsonl(
        dataset_dir / "spectra.jsonl",
        [
            {
                "figure_id": "图2.2",
                "figure_type": "nmr_spectrum",
                "schema_name": "NMRExtraction",
                "technique": "27Al NMR",
                "peaks": [{"position": 62.5, "unit": "ppm", "assignment": "Al13"}],
            }
        ],
    )
    _write_json(dataset_dir / "quality_summary.json", {"stage4_overall_status": "warning"})
    (dataset_dir / "fusion_report.md").write_text("# fusion report", encoding="utf-8")
    return dataset_dir


def test_dry_run_loader_and_no_llm_key_required(tmp_path: Path):
    dataset_dir = build_final_dataset(tmp_path)
    payload = load_final_dataset_inputs(dataset_dir)
    assert payload["paper"]["paper_id"] == "paper-1"
    linker = EvidenceSpectraParameterLinker(dry_run=True)
    links, raw, failed = linker.run([], paper_context=payload["paper"])
    assert links == []
    assert raw == []
    assert failed == []


def test_linking_does_not_write_back_parameters(tmp_path: Path):
    dataset_dir = build_final_dataset(tmp_path)
    original = (dataset_dir / "parameters.jsonl").read_text(encoding="utf-8")
    _ = load_final_dataset_inputs(dataset_dir)
    assert (dataset_dir / "parameters.jsonl").read_text(encoding="utf-8") == original
