from __future__ import annotations

import csv
import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import export_batch_link_aware_dataset


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_export_dir(root: Path, paper_id: str, *, include_spectra: bool = True) -> Path:
    export_dir = root / paper_id / "final_dataset" / "link_aware_exports"
    _write_csv(
        export_dir / "final_parameters_linked.csv",
        ["paper_id", "parameter_id", "canonical_key"],
        [[paper_id, "param-1", "pH"]],
    )
    _write_csv(
        export_dir / "sample_parameter_matrix.csv",
        ["paper_id", "sample_id", "sample_name"],
        [[paper_id, "S1", "sample"]],
    )
    _write_csv(
        export_dir / "evidence_parameter_links.csv",
        ["paper_id", "evidence_id", "parameter_id"],
        [[paper_id, "ev-1", "param-1"]],
    )
    _write_csv(
        export_dir / "process_step_parameter_links.csv",
        ["paper_id", "evidence_id", "parameter_id"],
        [[paper_id, "step-1", "param-1"]],
    )
    _write_csv(
        export_dir / "spectra_parameter_links.csv",
        ["paper_id", "spectra_id", "parameter_id"],
        [[paper_id, "spectra-1", "param-1"]] if include_spectra else [],
    )
    _write_csv(
        export_dir / "process_steps_table.csv",
        ["paper_id", "process_step_id", "step_order"],
        [[paper_id, "step-1", "1"]],
    )
    _write_csv(
        export_dir / "final_showcase_table.csv",
        ["paper_id", "paper_short", "sample"],
        [[paper_id, paper_id[:8], "sample"]],
    )
    _write_json(
        export_dir / "link_aware_export_summary.json",
        {
            "total_parameters": 1,
            "parameters_with_any_link": 1,
            "parameters_with_sample_link": 1,
            "parameters_with_evidence_link": 1,
            "parameters_with_spectra_link": 1 if include_spectra else 0,
            "parameters_missing_all_links": 0,
            "total_evidence_parameter_links": 1,
            "process_step_parameter_links": 1,
            "total_spectra_parameter_links": 1 if include_spectra else 0,
            "total_samples": 1,
            "showcase_rows": 1,
        },
    )
    (export_dir / "link_aware_export_readme.md").write_text("readme", encoding="utf-8")
    return export_dir


def test_export_batch_link_aware_dataset_merges_multiple_papers(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    _build_export_dir(outputs_dir, "paper-a")
    _build_export_dir(outputs_dir, "paper-b")
    result = export_batch_link_aware_dataset(outputs_dir, output_dir=tmp_path / "_batch")

    assert result["summary"]["paper_count"] == 2
    showcase_path = tmp_path / "_batch" / "all_papers_final_showcase_table.csv"
    assert showcase_path.exists()
    content = showcase_path.read_text(encoding="utf-8")
    assert "paper-a" in content
    assert "paper-b" in content


def test_export_batch_link_aware_dataset_skips_missing_exports_with_warning(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    _build_export_dir(outputs_dir, "paper-a")
    (outputs_dir / "paper-missing" / "final_dataset").mkdir(parents=True, exist_ok=True)

    result = export_batch_link_aware_dataset(outputs_dir, output_dir=tmp_path / "_batch")

    warnings = result["summary"]["warnings"]
    assert any("paper-missing" in item for item in warnings)


def test_export_batch_link_aware_dataset_handles_empty_spectra_table(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    _build_export_dir(outputs_dir, "paper-a", include_spectra=False)

    export_batch_link_aware_dataset(outputs_dir, output_dir=tmp_path / "_batch")

    spectra_path = tmp_path / "_batch" / "all_papers_spectra_parameter_links.csv"
    assert spectra_path.exists()
    lines = spectra_path.read_text(encoding="utf-8").splitlines()
    assert lines
    assert lines[0].startswith("paper_id,")


def test_export_batch_link_aware_dataset_does_not_modify_sources(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    export_dir = _build_export_dir(outputs_dir, "paper-a")
    before = (export_dir / "final_showcase_table.csv").read_text(encoding="utf-8")

    export_batch_link_aware_dataset(outputs_dir, output_dir=tmp_path / "_batch")

    after = (export_dir / "final_showcase_table.csv").read_text(encoding="utf-8")
    assert before == after
