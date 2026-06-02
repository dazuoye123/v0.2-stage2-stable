from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "check_stage5_batch_outputs.py"
SPEC = importlib.util.spec_from_file_location("check_stage5_batch_outputs_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_stage5_file_set(paper_dir: Path, *, include_process_steps_table: bool = True) -> None:
    dataset_dir = paper_dir / "final_dataset"
    export_dir = dataset_dir / "link_aware_exports"
    _write_text(dataset_dir / "stage5_summary.json", json.dumps({"status": "success"}, ensure_ascii=False))
    _write_text(export_dir / "final_parameters_linked.csv", "paper_id,parameter_id\npaper-a,param-1\n")
    _write_text(export_dir / "sample_parameter_matrix.csv", "paper_id,sample_id\npaper-a,sample-1\n")
    _write_text(export_dir / "spectra_parameter_links.csv", "paper_id,spectra_id\n")
    _write_text(export_dir / "evidence_parameter_links.csv", "paper_id,source_type\npaper-a,evidence_object\n")
    if include_process_steps_table:
        _write_text(export_dir / "process_steps_table.csv", "paper_id,step_id\npaper-a,step-1\n")


def test_integrity_checker_warns_for_zero_process_step_links(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    paper_dir = tmp_path / "outputs" / "fiber_process" / "paper-a"
    _write_stage5_file_set(paper_dir)
    _write_csv(
        report_dir / "stage5_batch_paper_summary.csv",
        [
            {
                "category": "fiber_process",
                "paper_id": "paper-a",
                "paper_dir": str(paper_dir),
                "status": "success",
                "process_steps_count": 1,
                "spectra_count_used": 0,
                "evidence_objects_count": 1,
                "stage4a_dry_run_excluded_count": 1,
                "evidence_parameter_links_count": 1,
                "spectra_parameter_links_count": 0,
                "process_step_parameter_links_count": 0,
            }
        ],
    )
    result = MODULE.check_stage5_batch_outputs(report_dir)
    rows = list(csv.DictReader((report_dir / "stage5_batch_integrity_check.csv").open("r", encoding="utf-8-sig", newline="")))
    assert result["warnings"] == 1
    assert rows[0]["integrity_status"] == "warning"
    assert "zero_process_step_links" in rows[0]["warnings"]
    assert "dry_run_excluded_present" in rows[0]["warnings"]


def test_integrity_checker_errors_when_process_steps_table_missing_for_success(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    paper_dir = tmp_path / "outputs" / "fiber_process" / "paper-b"
    _write_stage5_file_set(paper_dir, include_process_steps_table=False)
    _write_csv(
        report_dir / "stage5_batch_paper_summary.csv",
        [
            {
                "category": "fiber_process",
                "paper_id": "paper-b",
                "paper_dir": str(paper_dir),
                "status": "success",
                "process_steps_count": 1,
                "spectra_count_used": 0,
                "evidence_objects_count": 0,
                "stage4a_dry_run_excluded_count": 0,
                "evidence_parameter_links_count": 0,
                "spectra_parameter_links_count": 0,
                "process_step_parameter_links_count": 0,
            }
        ],
    )
    result = MODULE.check_stage5_batch_outputs(report_dir)
    rows = list(csv.DictReader((report_dir / "stage5_batch_integrity_check.csv").open("r", encoding="utf-8-sig", newline="")))
    assert result["errors"] == 1
    assert rows[0]["integrity_status"] == "error"
    assert "empty_process_steps_table" in rows[0]["errors"]
