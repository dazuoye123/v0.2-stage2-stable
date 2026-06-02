from __future__ import annotations

import csv
import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import (
    discover_link_aware_export_dirs,
    export_batch_link_aware_dataset,
)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_export_dir(base: Path, *, category: str | None, paper_id: str) -> Path:
    paper_dir = (base / category / paper_id) if category else (base / paper_id)
    export_dir = paper_dir / "final_dataset" / "link_aware_exports"
    _write_csv(export_dir / "final_parameters_linked.csv", ["paper_id", "parameter_id"], [[paper_id, "param-1"]])
    _write_csv(export_dir / "sample_parameter_matrix.csv", ["paper_id", "sample_id"], [[paper_id, "sample-1"]])
    _write_csv(export_dir / "evidence_parameter_links.csv", ["paper_id", "evidence_id"], [[paper_id, "ev-1"]])
    _write_csv(export_dir / "process_step_parameter_links.csv", ["paper_id", "evidence_id"], [[paper_id, "step-1"]])
    _write_csv(export_dir / "spectra_parameter_links.csv", ["paper_id", "spectra_id"], [[paper_id, "sp-1"]])
    _write_csv(export_dir / "process_steps_table.csv", ["paper_id", "process_step_id"], [[paper_id, "step-1"]])
    _write_csv(export_dir / "final_showcase_table.csv", ["paper_id", "sample"], [[paper_id, "sample"]])
    _write_json(
        export_dir / "link_aware_export_summary.json",
        {
            "total_parameters": 1,
            "parameters_with_any_link": 1,
            "parameters_with_sample_link": 1,
            "parameters_with_evidence_link": 1,
            "parameters_with_spectra_link": 1,
            "parameters_missing_all_links": 0,
            "total_evidence_parameter_links": 1,
            "process_step_parameter_links": 1,
            "total_spectra_parameter_links": 1,
            "total_samples": 1,
            "sample_matrix_rows": 1,
            "showcase_rows": 1,
        },
    )
    return export_dir


def test_discover_link_aware_export_dirs_supports_flat_and_category_layouts(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _build_export_dir(outputs, category=None, paper_id="paper_a")
    _build_export_dir(outputs, category="mechanism", paper_id="paper_b")
    (outputs / "_batch_final_exports").mkdir(parents=True, exist_ok=True)

    rows = discover_link_aware_export_dirs(outputs)
    qualified_ids = {row["qualified_paper_id"] for row in rows}

    assert "paper_a" in qualified_ids
    assert "mechanism/paper_b" in qualified_ids
    assert all("_batch_final_exports" not in row["paper_dir"].name for row in rows)


def test_discover_link_aware_export_dirs_supports_paper_id_filters(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _build_export_dir(outputs, category="mechanism", paper_id="paper_b")
    _build_export_dir(outputs, category="fiber_process", paper_id="paper_c")

    rows_plain = discover_link_aware_export_dirs(outputs, paper_ids=["paper_b"])
    rows_qualified = discover_link_aware_export_dirs(outputs, paper_ids=["mechanism/paper_b"])

    assert [row["qualified_paper_id"] for row in rows_plain] == ["mechanism/paper_b"]
    assert [row["qualified_paper_id"] for row in rows_qualified] == ["mechanism/paper_b"]


def test_export_batch_link_aware_dataset_writes_new_aggregate_tables(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    _build_export_dir(outputs, category=None, paper_id="paper_a")
    _build_export_dir(outputs, category="mechanism", paper_id="paper_b")

    result = export_batch_link_aware_dataset(outputs, output_dir=tmp_path / "_batch")

    out = tmp_path / "_batch"
    assert (out / "all_papers_final_parameters_linked.csv").exists()
    assert (out / "all_papers_process_steps_table.csv").exists()
    assert (out / "all_papers_process_step_parameter_links.csv").exists()
    summary = json.loads((out / "all_papers_link_aware_summary.json").read_text(encoding="utf-8"))
    assert summary["discovered_papers"] == 2
    assert summary["paper_count"] == 2
    assert summary["exported_flat_paper_count"] == 1
    assert summary["exported_category_paper_count"] == 1
    assert summary["by_category"]["uncategorized"]["paper_count"] == 1
    assert summary["by_category"]["mechanism"]["paper_count"] == 1
    assert result["summary"]["total_process_step_parameter_links"] == 2
