from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""), encoding="utf-8")


def _build_fixture(output_dir: Path) -> None:
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage4_dir = output_dir / "stage4_vision_spectra"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "paper_basic_info.json").write_text(
        json.dumps({"title": "paper", "authors": ["A"], "material_system": "alumina_sol"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage3_dir / "global_constants.json").write_text(
        json.dumps(
            {
                "additional_parameter_records": [
                    {
                        "canonical_key": "nmr_27Al_peak_position_ppm",
                        "raw_name": "NMR peak",
                        "value": 62.5,
                        "unit": "ppm",
                        "evidence_refs": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [
            {
                "sample_id": "sample-1",
                "sample_label": "sample 1",
                "independent_variable_values": [
                    {
                        "canonical_key": "aluminum_source",
                        "raw_name": "aluminum_source",
                        "value": "Al powder",
                        "unit": "text",
                        "evidence_refs": [{"source_id": "图2.2", "figure_id": "图2.2"}],
                    }
                ],
                "process_parameters": {"precursor_solution": {"stirring_speed_rpm": 500}},
                "results": {},
                "additional_parameter_records": [],
                "extended_data": {},
            }
        ],
    )
    _write_jsonl(
        stage3_dir / "experiment_series.jsonl",
        [
            {
                "series_id": "series-1",
                "series_name": "NMR study",
                "variables": {"start_temperature_C": 50},
            }
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [
            {
                "evidence_id": "图2.2__ev01",
                "figure_id": "图2.2",
                "figure_type": "nmr_spectrum",
                "caption": "27Al NMR",
                "fact_summary": ["62.5 ppm peak"],
            }
        ],
    )
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")
    (stage3_dir / "stage3_smoke_summary.json").write_text(
        json.dumps({"schema_valid": True, "canonical_key_errors_count": 0, "core_parameter_without_evidence_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage3_dir / "stage3_validation_report.md").write_text("ok", encoding="utf-8")
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.2",
                "figure_type": "nmr_spectrum",
                "schema_name": "NMRExtraction",
                "technique": "27Al NMR",
                "extraction_mode": "live",
                "confidence": 0.9,
                "peaks": [{"position": 62.5, "unit": "ppm", "source": "image_and_text"}],
                "quantitative_values": {},
            }
        ],
    )
    (stage4_dir / "stage4_summary.json").write_text(
        json.dumps({"total_candidates": 1, "failed_record_count": 0, "validation_error_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage4_dir / "stage4_quality_review.json").write_text(
        json.dumps(
            {
                "summary": {"overall_status": "warning"},
                "figures": [
                    {
                        "figure_id": "图2.2",
                        "source_distribution": {"image_and_text": 1},
                        "warning_codes": [],
                        "assessment": "usable",
                        "conflict_warnings": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stage4_dir / "stage4_quality_review.md").write_text("review", encoding="utf-8")


def test_fusion_links_spectra_to_evidence_and_expands_parameters(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    _build_fixture(output_dir)
    bundle = run_stage5_dataset_fusion(paper_id="paper-1", output_dir=output_dir)
    assert bundle["spectra"][0]["figure_id"] == "图2.2"
    assert bundle["evidence"][0]["figure_id"] == "图2.2"
    linked_parameter = next(item for item in bundle["parameters"] if item["canonical_key"] == "aluminum_source")
    assert linked_parameter["linked_evidence_ids"] == ["图2.2__ev01"]
    weak_link_parameter = next(item for item in bundle["parameters"] if item["canonical_key"] == "nmr_27Al_peak_position_ppm")
    assert "weak_link_from_spectra" in weak_link_parameter["quality_flags"]
    assert bundle["samples"][0]["linked_spectra"] == ["图2.2"]
