from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.vision_spectra.quality_review import (
    load_stage4_outputs,
    review_stage4_extractions,
    write_stage4_quality_review,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""), encoding="utf-8")


def test_stage4_quality_review_generates_md_and_json_with_expected_peak_matching(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.18",
                "figure_type": "ftir_spectrum",
                "schema_name": "VibrationalSpectrumExtraction",
                "extraction_mode": "live",
                "technique": "FTIR",
                "confidence": 0.9,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [
                    {"position": 3400, "unit": "cm^-1", "source": "image_and_text", "source_text": "text", "confidence": 0.9},
                    {"position": 1645, "unit": "cm^-1", "source": "image_and_text", "source_text": "text", "confidence": 0.9},
                    {"position": 761, "unit": "cm^-1", "source": "text", "source_text": "text", "confidence": 0.6},
                    {"position": 615, "unit": "cm^-1", "source": "text", "source_text": "text", "confidence": 0.6},
                ],
            },
            {
                "figure_id": "图2.19",
                "figure_type": "xrd_pattern",
                "schema_name": "XRDExtraction",
                "extraction_mode": "live",
                "technique": "XRD",
                "confidence": 0.9,
                "warnings": ["image-vs-text tension"],
                "conflict_warnings": [],
                "peaks": [
                    {"position": 7, "unit": "2theta_deg", "source": "text", "source_text": "text", "confidence": 0.9},
                ],
            },
            {
                "figure_id": "图2.20",
                "figure_type": "nmr_spectrum",
                "schema_name": "NMRExtraction",
                "extraction_mode": "live",
                "technique": "27Al NMR",
                "confidence": None,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [
                    {"position": 62.5, "unit": "ppm", "source": "inferred", "source_text": None, "evidence_note": None, "confidence": 0.9},
                ],
            },
        ],
    )
    _write_jsonl(stage4_dir / "raw_vlm_outputs.jsonl", [{"figure_id": "图2.18", "raw_response": "{}"}])
    _write_jsonl(stage4_dir / "failed_records.jsonl", [{"figure_id": "图2.21", "error": "json parse failed"}])
    (stage4_dir / "stage4_summary.json").write_text(
        json.dumps(
            {
                "total_candidates": 4,
                "processed_count": 3,
                "live_count": 3,
                "validation_error_count": 0,
                "failed_record_count": 1,
                "by_figure_type": {"ftir_spectrum": 1, "xrd_pattern": 1, "nmr_spectrum": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(stage4_dir / "stage4_prompts.jsonl", [{"figure_id": "图2.18"}])

    outputs = load_stage4_outputs(stage4_dir)
    review_payload = review_stage4_extractions(
        outputs,
        expected_peaks={
            "图2.18": {"figure_type": "ftir_spectrum", "unit": "cm^-1", "tolerance": 10, "expected_positions": [3400, 1645, 761, 615]},
            "图2.19": {"figure_type": "xrd_pattern", "unit": "2theta_deg", "tolerance": 0.5, "expected_positions": [7]},
        },
    )

    assert review_payload["summary"]["total_records"] == 3
    assert review_payload["summary"]["failed_record_count"] == 1
    assert review_payload["summary"]["source_distribution"]["image_and_text"] == 2
    assert review_payload["summary"]["source_distribution"]["text"] == 3
    assert review_payload["summary"]["source_distribution"]["inferred"] == 1
    figure_218 = next(item for item in review_payload["figures"] if item["figure_id"] == "图2.18")
    assert figure_218["peak_count"] == 4
    assert not figure_218["expected_peak_review"]["missing_expected_peaks"]
    figure_219 = next(item for item in review_payload["figures"] if item["figure_id"] == "图2.19")
    assert figure_219["expected_peak_review"]["matched_peaks"][0]["actual_position"] == 7
    figure_220 = next(item for item in review_payload["figures"] if item["figure_id"] == "图2.20")
    assert "inferred_without_support" in figure_220["warning_codes"]

    md_path = stage4_dir / "stage4_quality_review.md"
    json_path = stage4_dir / "stage4_quality_review.json"
    write_stage4_quality_review(review_payload, output_md=md_path, output_json=json_path)
    assert md_path.exists()
    assert json_path.exists()
    md_text = md_path.read_text(encoding="utf-8")
    assert "overall_status: fail" in md_text
    assert "图2.18" in md_text
    assert "图2.19" in md_text


def test_stage4_quality_review_without_expected_peaks_still_generates_review(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.18",
                "figure_type": "ftir_spectrum",
                "schema_name": "VibrationalSpectrumExtraction",
                "extraction_mode": "live",
                "technique": "FTIR",
                "confidence": 0.9,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [{"position": 3400, "unit": "cm^-1", "source": "text", "source_text": "caption", "confidence": 0.9}],
            }
        ],
    )
    _write_jsonl(stage4_dir / "raw_vlm_outputs.jsonl", [])
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({"validation_error_count": 0}, ensure_ascii=False), encoding="utf-8")

    outputs = load_stage4_outputs(stage4_dir)
    review_payload = review_stage4_extractions(outputs)
    assert review_payload["summary"]["overall_status"] in {"pass", "warning"}
    assert review_payload["figures"][0]["expected_peak_review"] is None


def test_ferron_with_standard_curve_only_is_warning_not_fail(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.12",
                "figure_type": "ferron_curve",
                "schema_name": "FerronCurveExtraction",
                "extraction_mode": "live",
                "technique": "Al-Ferron比色法",
                "confidence": 0.9,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [],
                "equation": "y = 200.38571x + 0.28589",
                "fitted_parameters": {"slope": 200.38571, "intercept": 0.28589},
                "species_quantification": {"Ala": None, "Alb": None, "Alc": None, "Al13": None},
            }
        ],
    )
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({"validation_error_count": 0}, ensure_ascii=False), encoding="utf-8")

    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))
    figure = review_payload["figures"][0]
    assert "ferron_standard_curve_only" in figure["warning_codes"]
    assert "ferron_insufficient_structured_content" not in figure["warning_codes"]
    assert figure["assessment"] == "usable_with_warning"
    assert review_payload["summary"]["overall_status"] == "warning"


def test_ferron_without_curve_or_quantification_is_insufficient(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.13",
                "figure_type": "ferron_curve",
                "schema_name": "FerronCurveExtraction",
                "extraction_mode": "live",
                "technique": "Al-Ferron比色法",
                "confidence": 0.9,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [],
            }
        ],
    )
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({"validation_error_count": 0}, ensure_ascii=False), encoding="utf-8")

    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))
    figure = review_payload["figures"][0]
    assert "ferron_insufficient_structured_content" in figure["warning_codes"]
    assert figure["assessment"] == "insufficient_structured_content"


def test_nmr_low_confidence_peak_is_kept_as_warning_but_supported_main_peak_is_usable(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra"
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "图2.2",
                "figure_type": "nmr_spectrum",
                "schema_name": "NMRExtraction",
                "extraction_mode": "live",
                "technique": "27Al NMR",
                "confidence": 0.9,
                "warnings": [],
                "conflict_warnings": [],
                "peaks": [
                    {"position": 62.5, "unit": "ppm", "source": "image_and_text", "source_text": "62.5 ppm 主峰", "confidence": 0.9},
                    {"position": -10.0, "unit": "ppm", "source": "image", "source_text": "微小峰", "confidence": 0.3},
                ],
            }
        ],
    )
    (stage4_dir / "stage4_summary.json").write_text(json.dumps({"validation_error_count": 0}, ensure_ascii=False), encoding="utf-8")

    review_payload = review_stage4_extractions(load_stage4_outputs(stage4_dir))
    figure = review_payload["figures"][0]
    assert figure["assessment"] == "usable_with_warning"
    assert "low_confidence_peak" in figure["warning_codes"]
    low_conf_peak = next(item for item in figure["peak_reviews"] if item["position"] == -10.0)
    assert "low_confidence_peak" in low_conf_peak["warnings"]
