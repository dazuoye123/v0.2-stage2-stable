"""Reusable quality review helpers for Stage 4 vision spectra outputs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl, write_json


_ALLOWED_SOURCES = {"image", "text", "image_and_text", "inferred", "unknown"}


def load_stage4_outputs(stage4_dir: Path | str) -> dict[str, Any]:
    stage4_dir = Path(stage4_dir)
    return {
        "stage4_dir": stage4_dir,
        "spectra_extractions": read_jsonl(stage4_dir / "spectra_extractions.jsonl"),
        "raw_vlm_outputs": read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl"),
        "stage4_summary": read_json(stage4_dir / "stage4_summary.json", default={}) or {},
        "failed_records": read_jsonl(stage4_dir / "failed_records.jsonl"),
        "stage4_prompts": read_jsonl(stage4_dir / "stage4_prompts.jsonl"),
    }


def review_stage4_extractions(
    outputs: dict[str, Any],
    *,
    expected_peaks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extractions = list(outputs.get("spectra_extractions") or [])
    summary = dict(outputs.get("stage4_summary") or {})
    failed_records = list(outputs.get("failed_records") or [])

    by_figure_reviews: list[dict[str, Any]] = []
    source_distribution = Counter()
    global_warnings: list[dict[str, Any]] = []

    for record in extractions:
        figure_id = str(record.get("figure_id") or "")
        figure_expected = (expected_peaks or {}).get(figure_id)
        review = _review_single_figure(record, expected_config=figure_expected)
        by_figure_reviews.append(review)
        source_distribution.update(review["source_distribution"])
        for warning_code in review["warning_codes"]:
            global_warnings.append({"figure_id": figure_id, "warning": warning_code})
        for warning_text in review["conflict_warnings"]:
            global_warnings.append({"figure_id": figure_id, "warning": "image_text_conflict", "detail": warning_text})

    if failed_records:
        for item in failed_records:
            global_warnings.append(
                {
                    "figure_id": item.get("figure_id"),
                    "warning": "failed_record",
                    "detail": item.get("error"),
                }
            )

    total_validation_errors = int(summary.get("validation_error_count", 0))
    overall_status = _determine_overall_status(
        failed_record_count=len(failed_records),
        validation_error_count=total_validation_errors,
        figure_reviews=by_figure_reviews,
    )

    review_payload = {
        "summary": {
            "total_records": len(extractions),
            "live_count": sum(1 for item in extractions if item.get("extraction_mode") == "live"),
            "failed_record_count": len(failed_records),
            "validation_error_count": total_validation_errors,
            "by_figure_type": dict(Counter(str(item.get("figure_type") or "unknown") for item in extractions)),
            "source_distribution": dict(source_distribution),
            "overall_status": overall_status,
        },
        "figures": by_figure_reviews,
        "global_warnings": global_warnings,
    }
    return review_payload


def write_stage4_quality_review(
    review_payload: dict[str, Any],
    *,
    output_md: Path | str,
    output_json: Path | str,
) -> tuple[Path, Path]:
    output_md = Path(output_md)
    output_json = Path(output_json)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_render_markdown_review(review_payload), encoding="utf-8")
    write_json(output_json, review_payload)
    return output_md, output_json


def _review_single_figure(record: dict[str, Any], *, expected_config: dict[str, Any] | None) -> dict[str, Any]:
    figure_type = str(record.get("figure_type") or "unknown")
    peaks = [item for item in (record.get("peaks") or []) if isinstance(item, dict)]
    warnings = list(record.get("warnings") or [])
    conflict_warnings = list(record.get("conflict_warnings") or [])
    source_distribution = Counter()
    warning_codes: list[str] = []
    peak_reviews: list[dict[str, Any]] = []

    for peak in peaks:
        source = str(peak.get("source") or "unknown")
        source_distribution[source] += 1
        peak_warning_codes: list[str] = []
        source_text = peak.get("source_text")
        evidence_note = peak.get("evidence_note")
        peak_conflict = peak.get("conflict_warning")
        confidence = peak.get("confidence")

        if source == "inferred" and not source_text and not evidence_note:
            peak_warning_codes.append("inferred_without_support")
            warning_codes.append("inferred_without_support")
        if source == "unknown" and isinstance(confidence, (int, float)) and confidence >= 0.8:
            peak_warning_codes.append("high_confidence_unknown_source")
            warning_codes.append("high_confidence_unknown_source")
        if source == "text":
            peak_warning_codes.append("text_supported_peak")
        if peak_conflict:
            conflict_warnings.append(str(peak_conflict))
        if confidence is None:
            peak_warning_codes.append("missing_peak_confidence")
            warning_codes.append("missing_peak_confidence")
        elif not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            peak_warning_codes.append("invalid_peak_confidence")
            warning_codes.append("invalid_peak_confidence")
        elif confidence < 0.5:
            peak_warning_codes.append("low_confidence_peak")
            warning_codes.append("low_confidence_peak")
        elif confidence >= 0.8 and source in {"inferred", "unknown"}:
            peak_warning_codes.append("high_confidence_unknown_source")
            warning_codes.append("high_confidence_unknown_source")

        peak_reviews.append(
            {
                "position": peak.get("position"),
                "unit": peak.get("unit"),
                "source": source,
                "source_text": source_text,
                "confidence": confidence,
                "warnings": peak_warning_codes,
            }
        )

    record_confidence = record.get("confidence")
    if record_confidence is None:
        warning_codes.append("missing_record_confidence")
    elif not isinstance(record_confidence, (int, float)) or record_confidence < 0 or record_confidence > 1:
        warning_codes.append("invalid_record_confidence")
    elif record_confidence < 0.5:
        warning_codes.append("low_confidence_warning")

    conflict_warnings.extend(_extract_conflict_warnings(warnings))
    conflict_warnings = list(dict.fromkeys(str(item) for item in conflict_warnings if item))

    expected_review = _review_expected_peaks(peaks, expected_config) if expected_config else None
    if expected_review:
        if expected_review["missing_expected_peaks"]:
            warning_codes.append("missing_expected_peaks")
        if expected_review["extra_peaks"]:
            warning_codes.append("extra_peaks_detected")

    ferron_summary = _review_ferron_content(record) if figure_type == "ferron_curve" else None
    if ferron_summary:
        warning_codes.extend(ferron_summary["warning_codes"])

    assessment = _determine_figure_assessment(
        figure_type=figure_type,
        peaks=peaks,
        peak_reviews=peak_reviews,
        warning_codes=warning_codes,
        ferron_summary=ferron_summary,
    )

    return {
        "figure_id": record.get("figure_id"),
        "figure_type": figure_type,
        "schema_name": record.get("schema_name"),
        "extraction_mode": record.get("extraction_mode"),
        "technique": record.get("technique"),
        "confidence": record_confidence,
        "peak_count": len(peaks),
        "source_distribution": dict(source_distribution),
        "warnings": warnings,
        "conflict_warnings": conflict_warnings,
        "failed_or_not": False,
        "warning_codes": list(dict.fromkeys(warning_codes)),
        "peak_reviews": peak_reviews,
        "expected_peak_review": expected_review,
        "assessment": assessment,
        "curve_type": ferron_summary["curve_type"] if ferron_summary else record.get("curve_type"),
        "fitted_parameters_summary": ferron_summary["fitted_parameters_summary"] if ferron_summary else None,
        "species_quantification_summary": ferron_summary["species_quantification_summary"] if ferron_summary else None,
        "method_summary": ferron_summary["method_summary"] if ferron_summary else None,
    }


def _review_expected_peaks(peaks: list[dict[str, Any]], expected_config: dict[str, Any]) -> dict[str, Any]:
    expected_positions = list(expected_config.get("expected_positions") or [])
    tolerance = float(expected_config.get("tolerance") or 0)
    expected_unit = str(expected_config.get("unit") or "")
    unmatched_peaks = [peak for peak in peaks if isinstance(peak.get("position"), (int, float))]
    matched_peaks: list[dict[str, Any]] = []
    missing_expected_peaks: list[float] = []

    for expected_position in expected_positions:
        matched = None
        for peak in list(unmatched_peaks):
            if not _units_match(expected_unit, str(peak.get("unit") or "")):
                continue
            actual_position = peak.get("position")
            if isinstance(actual_position, (int, float)) and abs(float(actual_position) - float(expected_position)) <= tolerance:
                matched = {
                    "expected_position": expected_position,
                    "actual_position": actual_position,
                    "unit": peak.get("unit"),
                    "source": peak.get("source"),
                }
                unmatched_peaks.remove(peak)
                break
        if matched:
            matched_peaks.append(matched)
        else:
            missing_expected_peaks.append(expected_position)

    extra_peaks = [
        {
            "position": peak.get("position"),
            "unit": peak.get("unit"),
            "source": peak.get("source"),
        }
        for peak in unmatched_peaks
        if _units_match(expected_unit, str(peak.get("unit") or ""))
    ]
    return {
        "figure_type": expected_config.get("figure_type"),
        "unit": expected_unit,
        "match_tolerance": tolerance,
        "matched_peaks": matched_peaks,
        "missing_expected_peaks": missing_expected_peaks,
        "extra_peaks": extra_peaks,
    }


def _units_match(expected_unit: str, actual_unit: str) -> bool:
    norm_expected = _normalize_unit(expected_unit)
    norm_actual = _normalize_unit(actual_unit)
    return not norm_expected or norm_expected == norm_actual


def _normalize_unit(unit: str) -> str:
    normalized = (unit or "").strip().lower()
    aliases = {
        "cm^-1": "cm-1",
        "cm−1": "cm-1",
        "cm-1": "cm-1",
        "2theta": "2theta_deg",
        "2θ": "2theta_deg",
        "2theta_deg": "2theta_deg",
    }
    return aliases.get(normalized, normalized)


def _extract_conflict_warnings(warnings: list[str]) -> list[str]:
    collected: list[str] = []
    for warning in warnings:
        lower = str(warning).lower()
        if any(token in lower for token in ("conflict", "tension", "image-vs-text", "image_text_conflict")):
            collected.append(str(warning))
    return collected


def _determine_overall_status(
    *,
    failed_record_count: int,
    validation_error_count: int,
    figure_reviews: list[dict[str, Any]],
) -> str:
    if failed_record_count > 0 or validation_error_count > 0:
        return "fail"
    if any(review.get("warning_codes") or review.get("conflict_warnings") for review in figure_reviews):
        return "warning"
    return "pass"


def _review_ferron_content(record: dict[str, Any]) -> dict[str, Any]:
    warning_codes: list[str] = []
    curve_type = record.get("curve_type")
    fitted_parameters = record.get("fitted_parameters") or {}
    equation = record.get("equation")
    quantification_method = record.get("quantification_method")
    species_quantification = record.get("species_quantification") or {}
    ferron_fraction_keys = (
        "Ala_fraction_percent",
        "Alb_fraction_percent",
        "Alc_fraction_percent",
        "Al13_fraction_percent",
    )
    scalar_quantification = {key: record.get(key) for key in ferron_fraction_keys if record.get(key) is not None}
    dict_quantification = {key: value for key, value in species_quantification.items() if value is not None}
    has_curve_signal = bool(curve_type or fitted_parameters or equation or quantification_method)
    has_species_quantification = bool(scalar_quantification or dict_quantification)

    if not has_curve_signal and not has_species_quantification:
        warning_codes.append("ferron_insufficient_structured_content")
    elif has_curve_signal and not has_species_quantification:
        if equation or fitted_parameters:
            warning_codes.append("ferron_standard_curve_only")
        else:
            warning_codes.append("ferron_no_species_quantification")

    fitted_summary = {
        key: value
        for key, value in {
            "equation": equation,
            "r_squared": record.get("r_squared"),
            "wavelength_nm": record.get("wavelength_nm"),
            **(fitted_parameters if isinstance(fitted_parameters, dict) else {}),
        }.items()
        if value is not None and value != {}
    }
    species_summary = {
        "scalar_quantification": scalar_quantification,
        "species_quantification": dict_quantification,
    }
    method_parts = [
        value
        for value in (
            record.get("technique"),
            quantification_method,
            record.get("sample_name"),
        )
        if value
    ]
    return {
        "warning_codes": warning_codes,
        "curve_type": curve_type,
        "fitted_parameters_summary": fitted_summary or None,
        "species_quantification_summary": species_summary if (scalar_quantification or dict_quantification) else None,
        "method_summary": "; ".join(str(item) for item in method_parts) if method_parts else None,
    }


def _determine_figure_assessment(
    *,
    figure_type: str,
    peaks: list[dict[str, Any]],
    peak_reviews: list[dict[str, Any]],
    warning_codes: list[str],
    ferron_summary: dict[str, Any] | None,
) -> str:
    unique_warnings = set(warning_codes)
    if figure_type == "ferron_curve":
        if "ferron_insufficient_structured_content" in unique_warnings:
            return "insufficient_structured_content"
        if ferron_summary and (
            ferron_summary.get("fitted_parameters_summary")
            or ferron_summary.get("species_quantification_summary")
            or ferron_summary.get("method_summary")
        ):
            return "usable_with_warning" if unique_warnings else "usable"
        return "warning"

    if figure_type == "nmr_spectrum":
        supported_primary_peak = any(
            review.get("source") == "image_and_text"
            and isinstance(review.get("confidence"), (int, float))
            and float(review["confidence"]) >= 0.8
            for review in peak_reviews
        )
        if supported_primary_peak:
            return "usable_with_warning" if unique_warnings else "usable"
        if peaks:
            return "warning" if unique_warnings else "usable"
        return "insufficient_structured_content"

    if peaks:
        return "warning" if unique_warnings else "usable"
    return "warning" if unique_warnings else "insufficient_structured_content"


def _render_markdown_review(review_payload: dict[str, Any]) -> str:
    summary = review_payload["summary"]
    figures = review_payload["figures"]
    global_warnings = review_payload["global_warnings"]

    lines = [
        "# Stage 4 Vision Spectra Quality Review",
        "",
        "## Summary",
        f"- total_records: {summary['total_records']}",
        f"- failed_record_count: {summary['failed_record_count']}",
        f"- validation_error_count: {summary['validation_error_count']}",
        f"- source_distribution: {json.dumps(summary['source_distribution'], ensure_ascii=False)}",
        f"- overall_status: {summary['overall_status']}",
        "",
        "## Per Figure Review",
        "",
    ]

    for figure in figures:
        lines.extend(
            [
                f"### {figure['figure_id']}",
                f"- figure_type: {figure['figure_type']}",
                f"- schema_name: {figure['schema_name']}",
                f"- technique: {figure['technique']}",
                f"- extraction_mode: {figure['extraction_mode']}",
                f"- confidence: {figure['confidence']}",
                f"- peak_count: {figure['peak_count']}",
                f"- source_distribution: {json.dumps(figure['source_distribution'], ensure_ascii=False)}",
                f"- assessment: {figure['assessment']}",
            ]
        )
        if figure.get("figure_type") == "ferron_curve":
            lines.append(f"- curve_type: {json.dumps(figure.get('curve_type'), ensure_ascii=False)}")
            lines.append(f"- fitted_parameters_summary: {json.dumps(figure.get('fitted_parameters_summary'), ensure_ascii=False)}")
            lines.append(f"- species_quantification_summary: {json.dumps(figure.get('species_quantification_summary'), ensure_ascii=False)}")
            lines.append(f"- method_summary: {json.dumps(figure.get('method_summary'), ensure_ascii=False)}")
        expected_review = figure.get("expected_peak_review")
        if expected_review:
            lines.append(f"- matched_expected_peaks: {json.dumps(expected_review['matched_peaks'], ensure_ascii=False)}")
            lines.append(f"- missing_expected_peaks: {json.dumps(expected_review['missing_expected_peaks'], ensure_ascii=False)}")
            lines.append(f"- extra_peaks: {json.dumps(expected_review['extra_peaks'], ensure_ascii=False)}")
        lines.append(f"- warnings: {json.dumps(figure['warning_codes'], ensure_ascii=False)}")
        lines.append(f"- conflict_warnings: {json.dumps(figure['conflict_warnings'], ensure_ascii=False)}")
        lines.append("")

    lines.extend(["## Global Warnings"])
    if global_warnings:
        for item in global_warnings:
            detail = f": {item.get('detail')}" if item.get("detail") else ""
            lines.append(f"- {item.get('figure_id')}: {item.get('warning')}{detail}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Recommendation",
            f"- {summary['overall_status']}: "
            + {
                "pass": "可进入下一张图 live-smoke",
                "warning": "需要人工复核",
                "fail": "不建议继续扩大 live 批量",
            }[summary["overall_status"]],
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "load_stage4_outputs",
    "review_stage4_extractions",
    "write_stage4_quality_review",
]
