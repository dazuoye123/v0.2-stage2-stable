from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "run_stage5_batch.py"
SPEC = importlib.util.spec_from_file_location("run_stage5_batch_script_runner", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _build_success_paper(paper_dir: Path) -> None:
    stage3_dir = paper_dir / "stage3_twopass"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    _write_json(stage3_dir / "paper_basic_info.json", {"title": "Paper", "authors": ["A"]})
    _write_json(stage3_dir / "global_constants.json", {})
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [
            {
                "sample_id": "sample-1",
                "sample_label": "sample 1",
                "independent_variable_values": [
                    {
                        "canonical_key": "pH",
                        "raw_name": "pH",
                        "value": 4,
                        "unit": "dimensionless",
                        "evidence_refs": [{"evidence_id": "ev-1", "figure_id": "fig-1"}],
                    }
                ],
                "process_parameters": {},
                "results": {},
                "additional_parameter_records": [],
                "extended_data": {},
            }
        ],
    )
    _write_jsonl(stage3_dir / "experiment_series.jsonl", [])
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [
            {
                "step_id": "step-1",
                "step_order": 1,
                "action": "mix",
                "action_zh": "混合",
                "evidence_text": "mixing solution",
                "linked_parameter_keys": ["pH"],
            }
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [
            {"evidence_id": "ev-1", "figure_id": "fig-1", "figure_type": "ftir_spectrum", "caption": "FTIR", "fact_summary": ["peak"]},
        ],
    )
    _write_json(stage3_dir / "paper_extraction.schema_v2.json", {})
    _write_json(stage3_dir / "stage3_summary.json", {"schema_valid": True, "canonical_key_errors_count": 0})
    (stage3_dir / "stage3_validation_report.md").write_text("ok", encoding="utf-8")
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "fig-1",
                "figure_type": "ftir_spectrum",
                "schema_name": "VibrationalSpectrumExtraction",
                "technique": "FTIR",
                "extraction_mode": "live",
                "peaks": [{"position": 1040, "unit": "cm-1", "source": "image_and_text"}],
            }
        ],
    )
    _write_json(stage4_dir / "stage4a_summary.json", {"total_candidates": 1, "live_count": 1})
    _write_json(stage4_dir / "stage4_quality_review.json", {"summary": {"overall_status": "usable"}, "figures": []})
    (stage4_dir / "stage4_quality_review.md").write_text("ok", encoding="utf-8")


def test_stage5_batch_runner_records_missing_stage3_without_stopping(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    _build_success_paper(outputs_dir / "fiber_process" / "paper-good")
    (outputs_dir / "fiber_process" / "paper-missing").mkdir(parents=True, exist_ok=True)
    report_dir = tmp_path / "reports"

    result = MODULE.run_stage5_batch(
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        categories=["fiber_process"],
        limit=None,
        paper_filter=None,
        force=False,
        skip_existing=False,
        with_linking=True,
        dry_run=False,
        continue_on_error=True,
        workers=1,
    )

    assert result["summary"]["total_success"] == 1
    assert result["summary"]["total_failed"] == 1
    failure_rows = list(csv.DictReader((report_dir / "stage5_batch_failure_manifest.csv").open("r", encoding="utf-8-sig", newline="")))
    assert any(row["paper_id"] == "paper-missing" and row["failure_type"] == "missing_stage3" for row in failure_rows)


def test_stage5_batch_runner_dry_run_does_not_write_final_dataset(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper-dry"
    _build_success_paper(paper_dir)
    report_dir = tmp_path / "reports"

    MODULE.run_stage5_batch(
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        categories=["fiber_process"],
        limit=None,
        paper_filter=None,
        force=False,
        skip_existing=False,
        with_linking=True,
        dry_run=True,
        continue_on_error=False,
        workers=1,
    )

    assert not (paper_dir / "final_dataset").exists()


def test_stage5_batch_runner_skip_existing_reuses_complete_outputs(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper-skip"
    _build_success_paper(paper_dir)
    report_dir = tmp_path / "reports"

    MODULE.run_stage5_batch(
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        categories=["fiber_process"],
        limit=None,
        paper_filter=None,
        force=False,
        skip_existing=False,
        with_linking=True,
        dry_run=False,
        continue_on_error=False,
        workers=1,
    )

    result = MODULE.run_stage5_batch(
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        categories=["fiber_process"],
        limit=None,
        paper_filter=None,
        force=False,
        skip_existing=True,
        with_linking=True,
        dry_run=False,
        continue_on_error=False,
        workers=1,
    )

    row = list(csv.DictReader((report_dir / "stage5_batch_paper_summary.csv").open("r", encoding="utf-8-sig", newline="")))[0]
    assert row["planned_action"] == "skip_existing"
    assert row["attempted_stage5"] == "False"
    assert result["summary"]["total_success"] == 1
