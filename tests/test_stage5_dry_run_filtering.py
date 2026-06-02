from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.loaders import load_paper_inputs
from alumina_sol_extractor.stage5 import batch_runner as MODULE


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _build_paper(paper_dir: Path, *, stage4_rows: list[dict]) -> None:
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
                "independent_variable_values": [],
                "process_parameters": {},
                "results": {},
                "additional_parameter_records": [
                    {
                        "canonical_key": "calcination_temperature_C",
                        "raw_name": "calcination temperature",
                        "value": 1200,
                        "unit": "C",
                        "evidence_refs": [],
                    }
                ],
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
                "action": "calcine",
                "action_zh": "煅烧",
                "evidence_text": "calcined at 1200 C",
                "linked_parameter_keys": ["calcination_temperature_C"],
            }
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [
            {
                "evidence_id": "ev-1",
                "figure_id": "fig-1",
                "figure_type": "ftir_spectrum",
                "caption": "FTIR",
                "fact_summary": ["ftir peak"],
            }
        ],
    )
    _write_json(stage3_dir / "paper_extraction.schema_v2.json", {})
    _write_json(stage3_dir / "stage3_summary.json", {"schema_valid": True, "canonical_key_errors_count": 0})
    (stage3_dir / "stage3_validation_report.md").write_text("ok", encoding="utf-8")
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", stage4_rows)
    _write_json(stage4_dir / "stage4a_summary.json", {"total_candidates": len(stage4_rows), "live_count": sum(1 for row in stage4_rows if row.get("extraction_mode") == "live")})
    _write_json(stage4_dir / "stage4_quality_review.json", {"summary": {"overall_status": "usable"}, "figures": []})
    (stage4_dir / "stage4_quality_review.md").write_text("ok", encoding="utf-8")


def test_load_paper_inputs_excludes_dry_run_spectra() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        paper_dir = Path(tmp) / "fiber_process" / "paper-a"
        _build_paper(
            paper_dir,
            stage4_rows=[
                {"figure_id": "fig-1", "figure_type": "ftir_spectrum", "extraction_mode": "dry_run", "peaks": [{"position": 1030, "unit": "cm-1"}]},
                {"figure_id": "fig-1", "figure_type": "ftir_spectrum", "extraction_mode": "live", "peaks": [{"position": 1040, "unit": "cm-1"}]},
                {"figure_id": "fig-2", "figure_type": "ftir_spectrum", "extraction_mode": "reused_previous_success", "peaks": [{"position": 800, "unit": "cm-1"}]},
            ],
        )
        payload = load_paper_inputs(
            paper_dir,
            stage3_dir=paper_dir / "stage3_twopass",
            stage4_dir=paper_dir / "stage4_vision_spectra_universal",
        )
        assert len(payload["stage4"]["spectra_extractions"]) == 2
        assert payload["stage4"]["usage_summary"]["spectra_live_count"] == 1
        assert payload["stage4"]["usage_summary"]["spectra_fallback_count"] == 1
        assert payload["stage4"]["usage_summary"]["spectra_dry_run_excluded_count"] == 1


def test_stage5_batch_marks_dry_run_only_spectra_as_partial_success(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper-b"
    _build_paper(
        paper_dir,
        stage4_rows=[
            {"figure_id": "fig-1", "figure_type": "ftir_spectrum", "extraction_mode": "dry_run", "peaks": [{"position": 1030, "unit": "cm-1"}]},
        ],
    )
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
        continue_on_error=False,
        workers=1,
    )
    summary = json.loads((report_dir / "stage5_batch_overall_summary.json").read_text(encoding="utf-8"))
    assert result["summary"]["total_partial_success"] == 1
    assert summary["total_stage4a_dry_run_excluded"] == 1
    rows = list(__import__("csv").DictReader((report_dir / "stage5_batch_paper_summary.csv").open("r", encoding="utf-8-sig", newline="")))
    assert rows[0]["spectra_count_used"] == "0"
    assert "dry_run_only_spectra" in rows[0]["warnings"]
