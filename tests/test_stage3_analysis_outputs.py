from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "build_stage3_analysis_outputs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("stage3_analysis_outputs", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(text + ("\n" if rows else ""), encoding="utf-8")


def _make_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "category",
        "paper_id_guess",
        "resolved_output_dir",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_paper(
    root: Path,
    *,
    category: str = "fiber_process",
    paper_id: str = "paper_a",
    record_name: str = "paper_extraction.schema_v2.json",
    record_payload: dict | None = None,
    summary_payload: dict | None = None,
) -> Path:
    paper_dir = root / "data" / "outputs" / category / paper_id
    stage3_dir = paper_dir / "stage3_twopass"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage3_text_dir = paper_dir / "stage3_text"
    stage3_text_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "schema_valid": True,
        "stage3_mode": "two-pass",
        "data_point_count": 1,
        "process_steps_count": 1,
        "evidence_object_count": 1,
        "experiment_series_count": 1,
        "canonical_key_errors_count": 0,
        "rejected_parameter_records_count": 0,
        "cleaned_body_char_count": 24,
        "input_truncated": False,
    }
    if summary_payload:
        summary.update(summary_payload)
    _write_json(stage3_dir / "stage3_summary.json", summary)
    _write_json(stage3_dir / "stage3_procedure_sections.json", {"sections": []})
    _write_json(
        stage3_text_dir / "markdown_trim_report.json",
        {"reason": "trim_obvious_front_matter_and_back_matter_only", "cleaned_body_char_count": 24},
    )
    (stage3_text_dir / "cleaned_body.md").write_text("Experimental body text.", encoding="utf-8")

    if record_payload is None:
        record_payload = {
            "schema_version": "2.0",
            "paper_basic_info": {"title": paper_id},
            "global_constants": {},
            "experiment_series": [
                {
                    "series_id": "series-1",
                    "series_name": "series-1",
                    "series_type": "single_factor",
                    "research_question": "",
                    "controlled_variable_keys": [],
                    "independent_variables": [],
                    "series_constants": [],
                    "data_points": [
                        {
                            "sample_id": "sample-1",
                            "sample_label": "Sample 1",
                            "sample_role": "",
                            "independent_variable_values": [],
                            "process_parameters": {"forming": {"applied_voltage_kV": 15}},
                            "results": {"mechanical_properties": {"tensile_strength_MPa": 120}},
                            "qualitative_observations": [],
                            "additional_parameter_records": [
                                {
                                    "canonical_key": "calcination_temperature_C",
                                    "raw_name": "calcination temperature",
                                    "value": 900,
                                    "unit": "C",
                                    "raw_text": "calcined at 900 C",
                                    "evidence_refs": [{"quote_or_context": "calcined at 900 C"}],
                                }
                            ],
                            "evidence_refs": [{"quote_or_context": "calcined at 900 C"}],
                            "extended_data": {},
                        }
                    ],
                    "relevant_source_sections": [],
                    "relevant_figure_ids": [],
                    "relevant_table_ids": [],
                    "extended_data": {},
                }
            ],
            "process_steps": [
                {
                    "step_id": "step-1",
                    "step_order": 1,
                    "action": "calcine",
                    "action_zh": "煅烧",
                    "temperature_value": 900,
                    "temperature_unit": "C",
                    "duration_value": 2,
                    "duration_unit": "h",
                    "heating_rate_value": 5,
                    "heating_rate_unit": "C/min",
                    "condition_value": "",
                    "condition_unit": "",
                    "condition_key": "",
                    "evidence_text": "calcined at 900 C for 2 h",
                    "description": "calcined at 900 C for 2 h",
                }
            ],
            "evidence_objects": [{"evidence_id": "ev-1", "figure_id": "Fig.1"}],
            "multimodal_extractions": [],
            "cross_modal_links": [],
            "data_provenance": {},
        }
    _write_json(stage3_dir / record_name, record_payload)
    _write_jsonl(stage3_dir / "data_points.jsonl", [])
    _write_jsonl(stage3_dir / "process_steps.jsonl", [])
    _write_jsonl(stage3_dir / "evidence_objects.jsonl", [])
    _write_jsonl(stage3_dir / "experiment_series.jsonl", [])
    return paper_dir


def test_extracts_data_points_from_minimal_paper_record(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = _make_paper(
        tmp_path,
        record_name="paper_record.json",
        record_payload={
            "data_points": [
                {
                    "sample_id": "s1",
                    "sample_label": "S1",
                    "process_parameters": {},
                    "results": {},
                    "additional_parameter_records": [
                        {
                            "canonical_key": "pH",
                            "raw_name": "pH",
                            "value": 4,
                            "unit": "",
                            "evidence_refs": [{"quote_or_context": "pH = 4"}],
                        }
                    ],
                    "evidence_refs": [{"quote_or_context": "pH = 4"}],
                }
            ],
            "process_steps": [],
            "evidence_objects": [],
        },
        summary_payload={"data_point_count": 1, "process_steps_count": 0, "evidence_object_count": 0},
    )
    paper = module.load_stage3_paper(
        category="fiber_process",
        paper_id="paper_a",
        paper_output_dir=paper_dir,
        stage3_subdir="stage3_twopass",
    )
    assert paper["data_point_count"] == 1
    assert len(paper["data_points"]) == 1
    assert paper["parameters"][0]["canonical_key"] == "pH"


def test_counts_process_step_actions(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = _make_paper(tmp_path, paper_id="paper_actions")
    paper = module.load_stage3_paper(
        category="fiber_process",
        paper_id="paper_actions",
        paper_output_dir=paper_dir,
        stage3_subdir="stage3_twopass",
    )
    distribution = module.build_process_step_action_distribution([paper])
    assert not distribution.empty
    row = distribution.iloc[0].to_dict()
    assert row["action"] == "calcine"
    assert row["count"] == 1


def test_generates_parameter_distribution_csv(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = _make_paper(tmp_path)
    manifest_path = tmp_path / "data" / "batch_manifest" / "source_manifest.csv"
    _make_manifest(
        manifest_path,
        [
            {
                "source_id": "fiber_process__paper_a",
                "category": "fiber_process",
                "paper_id_guess": "paper_a",
                "resolved_output_dir": str(paper_dir),
            }
        ],
    )
    output_dir = tmp_path / "analysis_outputs_stage3"
    result = module.build_analysis_outputs(
        manifest_path=manifest_path,
        outputs_dir=tmp_path / "data" / "outputs",
        output_dir=output_dir,
        stage3_subdir="stage3_twopass",
        top_n=10,
        report_path=tmp_path / "report.md",
    )
    parameter_distribution_path = output_dir / "parameter_distribution.csv"
    sample_long_path = output_dir / "sample_parameter_long.csv"
    assert parameter_distribution_path.exists()
    assert sample_long_path.exists()
    parameter_distribution = result["parameter_distribution"]
    assert "calcination_temperature_C" in parameter_distribution["canonical_key"].tolist()


def test_generates_sample_parameter_long_csv(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = _make_paper(tmp_path, paper_id="paper_long")
    manifest_path = tmp_path / "data" / "batch_manifest" / "source_manifest.csv"
    _make_manifest(
        manifest_path,
        [
            {
                "source_id": "fiber_process__paper_long",
                "category": "fiber_process",
                "paper_id_guess": "paper_long",
                "resolved_output_dir": str(paper_dir),
            }
        ],
    )
    output_dir = tmp_path / "analysis_outputs_stage3"
    module.build_analysis_outputs(
        manifest_path=manifest_path,
        outputs_dir=tmp_path / "data" / "outputs",
        output_dir=output_dir,
        stage3_subdir="stage3_twopass",
        top_n=10,
        report_path=tmp_path / "report.md",
    )
    rows = list(csv.DictReader((output_dir / "sample_parameter_long.csv").open("r", encoding="utf-8-sig")))
    assert rows
    assert rows[0]["sample_id"] == "sample-1"


def test_missing_files_do_not_crash(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = tmp_path / "data" / "outputs" / "fiber_process" / "paper_missing"
    (paper_dir / "stage3_twopass").mkdir(parents=True, exist_ok=True)
    _write_json((paper_dir / "stage3_twopass" / "stage3_summary.json"), {"schema_valid": True})
    manifest_path = tmp_path / "data" / "batch_manifest" / "source_manifest.csv"
    _make_manifest(
        manifest_path,
        [
            {
                "source_id": "fiber_process__paper_missing",
                "category": "fiber_process",
                "paper_id_guess": "paper_missing",
                "resolved_output_dir": str(paper_dir),
            }
        ],
    )
    result = module.build_analysis_outputs(
        manifest_path=manifest_path,
        outputs_dir=tmp_path / "data" / "outputs",
        output_dir=tmp_path / "analysis_outputs_stage3",
        stage3_subdir="stage3_twopass",
        top_n=10,
        report_path=tmp_path / "report.md",
    )
    assert result["analysis_summary"]["total_papers"] == 1
    assert (tmp_path / "analysis_outputs_stage3" / "paper_stage3_summary.csv").exists()


def test_empty_data_figures_do_not_crash(tmp_path: Path) -> None:
    module = _load_module()
    paper_dir = _make_paper(
        tmp_path,
        paper_id="paper_empty",
        record_payload={
            "schema_version": "2.0",
            "paper_basic_info": {},
            "global_constants": {},
            "experiment_series": [],
            "process_steps": [],
            "evidence_objects": [],
            "multimodal_extractions": [],
            "cross_modal_links": [],
            "data_provenance": {},
        },
        summary_payload={"data_point_count": 0, "process_steps_count": 0, "evidence_object_count": 0, "experiment_series_count": 0},
    )
    manifest_path = tmp_path / "data" / "batch_manifest" / "source_manifest.csv"
    _make_manifest(
        manifest_path,
        [
            {
                "source_id": "fiber_process__paper_empty",
                "category": "fiber_process",
                "paper_id_guess": "paper_empty",
                "resolved_output_dir": str(paper_dir),
            }
        ],
    )
    output_dir = tmp_path / "analysis_outputs_stage3"
    module.build_analysis_outputs(
        manifest_path=manifest_path,
        outputs_dir=tmp_path / "data" / "outputs",
        output_dir=output_dir,
        stage3_subdir="stage3_twopass",
        top_n=10,
        report_path=tmp_path / "report.md",
    )
    assert (output_dir / "figures" / "parameter_cooccurrence_network.png").exists()
    assert (output_dir / "figures" / "stage3_pipeline_funnel.svg").exists()


def test_range_list_text_values_are_safe(tmp_path: Path) -> None:
    module = _load_module()
    rows = module.extract_parameter_rows(
        category="fiber_process",
        paper_id="paper_values",
        data_points=[
            {
                "sample_id": "sample-1",
                "sample_label": "Sample 1",
                "process_parameters": {},
                "results": {},
                "additional_parameter_records": [
                    {"canonical_key": "particle_size_nm", "raw_name": "particle size", "value": [10, 20], "unit": "nm"},
                    {"canonical_key": "holding_time_h", "raw_name": "holding time", "value": None, "min_value": 1, "max_value": 2, "unit": "h"},
                    {"canonical_key": "spinnability", "raw_name": "spinnability", "value": "good", "unit": ""},
                ],
                "evidence_refs": [{"quote_or_context": "support"}],
            }
        ],
    )
    by_key = {row["canonical_key"]: row for row in rows}
    assert by_key["particle_size_nm"]["value"] is None
    assert "10 | 20" in by_key["particle_size_nm"]["value_text"]
    assert by_key["holding_time_h"]["value"] is None
    assert "1 ~ 2" in by_key["holding_time_h"]["value_text"]
    assert by_key["spinnability"]["value_text"] == "good"
