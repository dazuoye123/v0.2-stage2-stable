from __future__ import annotations

import csv
import json
from pathlib import Path

from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor, validate_universal_extraction_payload


def test_band_assignments_string_normalizes_to_list() -> None:
    normalized, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"band_assignments": "Si-O stretching"},
        figure_type="ftir_spectrum",
        schema_name="VibrationalSpectrumExtraction",
        use_universal_adapter=True,
    )
    assert normalized["band_assignments"] == ["Si-O stretching"]


def test_band_assignments_dict_list_normalizes_to_strings() -> None:
    normalized, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "band_assignments": [
                {"wavenumber": "1000-1100 cm^-1", "assignment": "Si-O stretching"},
                {"position": 780, "assignment": "Al-O"},
            ]
        },
        figure_type="ftir_spectrum",
        schema_name="VibrationalSpectrumExtraction",
        use_universal_adapter=True,
    )
    assert normalized["band_assignments"] == ["1000-1100 cm^-1: Si-O stretching", "780: Al-O"]


def test_vibrational_sample_name_list_normalizes_to_joined_string() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"sample_name": ["A-Si", "A-Si+1.5wt%PEO"]},
        figure_type="ftir_spectrum",
        schema_name="VibrationalSpectrumExtraction",
        use_universal_adapter=True,
    )
    assert normalized["sample_name"] == "A-Si; A-Si+1.5wt%PEO"
    assert "sample_name_joined_from_list" in warnings


def test_phase_assignments_string_and_dict_list_normalize_to_strings() -> None:
    normalized, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "phase_assignments": [
                "mullite",
                {"peak_position": 26.2, "phase": "corundum"},
            ]
        },
        figure_type="xrd_pattern",
        schema_name="XRDExtraction",
        use_universal_adapter=True,
    )
    assert normalized["phase_assignments"] == ["mullite", "26.2: corundum"]


def test_diameter_range_dict_and_list_normalize_to_string() -> None:
    normalized_dict, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"diameter_range": {"min": 10, "max": 15, "unit": "um"}},
        figure_type="sem_image",
        schema_name="MicroscopyExtraction",
        use_universal_adapter=True,
    )
    assert normalized_dict["diameter_range"] == "10-15 um"

    normalized_list, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"diameter_range": [3, 4], "diameter_unit": "μm"},
        figure_type="sem_image",
        schema_name="MicroscopyExtraction",
        use_universal_adapter=True,
    )
    assert normalized_list["diameter_range"] == "3-4 μm"


def test_thermal_peak_scalars_and_dicts_normalize_to_peak_records() -> None:
    normalized, _ = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "thermal_events": {"temperature": 234, "type": "endothermic", "description": "small dip"},
            "endothermic_peaks": [234, {"temperature": 933, "description": "dip"}],
            "exothermic_peaks": [365],
        },
        figure_type="dsc_curve",
        schema_name="ThermalAnalysisExtraction",
        use_universal_adapter=True,
    )
    assert normalized["thermal_events"][0]["temperature_peak"] == 234.0
    assert normalized["thermal_events"][0]["event_type"] == "endothermic"
    assert normalized["endothermic_peaks"][0]["position"] == 234.0
    assert normalized["exothermic_peaks"][0]["position"] == 365.0


def test_thermal_peak_string_does_not_crash_validation() -> None:
    payload = {
        "actual_figure_type": "dsc_curve",
        "type_confidence": 0.8,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "endothermic_peaks": "broad dip near 200 C",
            "thermal_events": ["broad dip near 200 C"],
        },
    }
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-thermal",
        "caption": "DSC curve",
        "source_image_path": "thermal.jpg",
        "stage2_figure_class": "thermal_analysis_plot",
        "stage3_figure_type": "thermal_analysis_plot",
        "initial_figure_type": "dsc_curve",
        "technique": None,
        "context_source": {},
    }
    result = validate_universal_extraction_payload(payload, candidate)
    assert result["ok"] is True
    assert result["record"]["endothermic_peaks"] == []


def test_unknown_actual_figure_type_uses_unknown_schema() -> None:
    payload = {
        "actual_figure_type": "unknown",
        "type_confidence": 0.2,
        "type_reason": "unclear",
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {"safe_observations": ["contains one plotted line"]},
    }
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-unknown",
        "caption": "unclear figure",
        "source_image_path": "unknown.jpg",
        "stage2_figure_class": "generic_chart_or_plot",
        "stage3_figure_type": None,
        "initial_figure_type": "unknown",
        "technique": None,
        "context_source": {},
    }
    result = validate_universal_extraction_payload(payload, candidate)
    assert result["ok"] is True
    assert result["schema_name"] == "UnknownFigureExtraction"


def test_range_peak_position_does_not_convert_to_midpoint() -> None:
    payload = {
        "actual_figure_type": "ftir_spectrum",
        "type_confidence": 0.9,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "peaks": [{"position": "1000-1100", "source_text": "1000-1100 cm^-1", "assignment": "Si-O stretching"}],
            "band_assignments": [],
        },
    }
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-ftir",
        "caption": "FTIR spectrum",
        "source_image_path": "ftir.jpg",
        "stage2_figure_class": "ftir_spectrum",
        "stage3_figure_type": "ftir_spectrum",
        "initial_figure_type": "ftir_spectrum",
        "technique": None,
        "context_source": {},
    }
    result = validate_universal_extraction_payload(payload, candidate)
    assert result["ok"] is True
    peak = result["record"]["peaks"][0]
    assert peak["position"] is None
    assert "1000-1100" in peak["source_text"]
    assert any(str(item).startswith("range_peak_position_not_numeric:") for item in peak["warnings"])


def test_en_dash_range_peak_position_does_not_convert_to_midpoint() -> None:
    payload = {
        "actual_figure_type": "ftir_spectrum",
        "type_confidence": 0.9,
        "warnings": [],
        "conflict_warnings": [],
        "extraction": {
            "peaks": [{"position": 1050, "source_text": "1000–1100 cm^-1", "assignment": "Si-O stretching"}],
            "band_assignments": [],
        },
    }
    candidate = {
        "paper_id": "paper-1",
        "figure_id": "fig-ftir",
        "caption": "FTIR spectrum",
        "source_image_path": "ftir.jpg",
        "stage2_figure_class": "ftir_spectrum",
        "stage3_figure_type": "ftir_spectrum",
        "initial_figure_type": "ftir_spectrum",
        "technique": None,
        "context_source": {},
    }
    result = validate_universal_extraction_payload(payload, candidate)
    assert result["ok"] is True
    peak = result["record"]["peaks"][0]
    assert peak["position"] is None
    assert "1000–1100" in peak["source_text"]
    assert any(str(item).startswith("range_peak_position_not_numeric:") for item in peak["warnings"])


def test_approximate_xrd_peak_source_text_nullifies_position() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {
            "peaks": [
                {
                    "position": 18.0,
                    "source_text": "~18",
                }
            ]
        },
        figure_type="xrd_pattern",
        schema_name="XRDExtraction",
        use_universal_adapter=True,
    )
    peak = normalized["peaks"][0]
    assert peak["position"] is None
    assert any(str(item).startswith("range_peak_position_not_numeric:") for item in peak["warnings"])
    assert any(str(item).startswith("range_peak_position_not_numeric:") for item in warnings)


def test_sem_without_scale_bar_does_not_invent_diameter() -> None:
    result = validate_universal_extraction_payload(
        {
            "actual_figure_type": "sem_image",
            "type_confidence": 0.9,
            "warnings": [],
            "conflict_warnings": [],
            "extraction": {"morphology_summary": "fibers visible"},
        },
        {
            "paper_id": "paper-1",
            "figure_id": "fig-sem",
            "caption": "SEM",
            "source_image_path": "sem.jpg",
            "stage2_figure_class": "microscopy_image",
            "stage3_figure_type": "microscopy_image",
            "initial_figure_type": "sem_image",
            "technique": None,
            "context_source": {},
        },
    )
    assert result["ok"] is True
    assert result["record"]["diameter_estimate"] is None
    assert result["record"]["diameter_basis"] == "not_measurable"


def test_limit5_schema_failures_replay_recovers_at_least_ten_when_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    report = root / "data" / "batch_validation_reports" / "stage4a_universal_limit5_live" / "stage4a_batch_report.csv"
    if not report.exists():
        return
    with report.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    recovered = 0
    failures = 0
    for row in rows:
        raw_path = root / row["stage4_dir"] / "raw_vlm_outputs.jsonl"
        if not raw_path.exists():
            continue
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("error_type") != "schema_validation_failed":
                continue
            universal_payload = payload.get("raw_universal_payload") or {}
            candidate = {
                "paper_id": universal_payload.get("paper_id"),
                "figure_id": universal_payload.get("figure_id"),
                "caption": universal_payload.get("caption"),
                "source_image_path": universal_payload.get("source_image_path"),
                "stage2_figure_class": universal_payload.get("stage2_figure_class"),
                "stage3_figure_type": universal_payload.get("stage3_figure_type"),
                "initial_figure_type": universal_payload.get("initial_figure_type") or universal_payload.get("figure_type"),
                "technique": (universal_payload.get("extraction") or {}).get("technique"),
                "context_source": {},
            }
            result = validate_universal_extraction_payload(universal_payload, candidate)
            if result["ok"]:
                recovered += 1
            else:
                failures += 1
    assert recovered >= 10
    assert failures <= 4
