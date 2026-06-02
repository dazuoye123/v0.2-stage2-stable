from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .io import normalize_text, read_json, read_jsonl, safe_int
from .normalization import normalize_category, normalize_spectra_type


def load_stage4_inputs(outputs_dir: Path) -> dict[str, Any]:
    summary_rows: list[dict[str, Any]] = []
    spectra_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    peak_rows: list[dict[str, Any]] = []

    for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        if category_dir.name.startswith("_"):
            continue
        for paper_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            stage4_dir = _resolve_stage4_dir(paper_dir)
            if stage4_dir is None:
                continue
            summary = read_json(stage4_dir / "stage4a_summary.json", default=None)
            if summary is None:
                summary = read_json(stage4_dir / "stage4_summary.json", default={}) or {}
            spectra = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
            failed = read_jsonl(stage4_dir / "failed_records.jsonl") or read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
            quality = read_json(stage4_dir / "stage4_quality_review.json", default={}) or {}

            success_count = len({_figure_identity(row) for row in spectra if _figure_identity(row)})
            failed_count = len({_figure_identity(row) for row in failed if _figure_identity(row)})
            raw_candidate_count = safe_int(summary.get("total_candidates"), 0)
            candidate_count = max(raw_candidate_count, success_count + failed_count, success_count)
            validation_errors = sum(len(row.get("validation_errors") or []) for row in spectra if isinstance(row, dict))
            summary_rows.append(
                {
                    "category": normalize_category(category_dir.name),
                    "paper_id": paper_dir.name,
                    "raw_candidate_count": raw_candidate_count,
                    "candidate_count": candidate_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "validation_error_count": validation_errors,
                    "validated_count": max(success_count - validation_errors, 0),
                    "coverage_rate": round(success_count / candidate_count, 4) if candidate_count else 0.0,
                    "figure_class_distribution": summary.get("by_stage2_figure_class") or {},
                }
            )
            if quality:
                quality_rows.append({"category": normalize_category(category_dir.name), "paper_id": paper_dir.name, **quality})
            for index, row in enumerate(spectra, start=1):
                enriched = {
                    "category": normalize_category(category_dir.name),
                    "paper_id": paper_dir.name,
                    "figure_id": normalize_text(row.get("figure_id")) or f"{paper_dir.name}-figure-{index}",
                    "spectra_id": normalize_text(row.get("spectra_id")) or f"{paper_dir.name}-spectra-{index}",
                    "raw_spectra_type": normalize_text(row.get("technique") or row.get("actual_figure_type") or row.get("figure_type")),
                    "normalized_spectra_type": normalize_spectra_type(row.get("technique"), row.get("actual_figure_type"), row.get("figure_type")),
                    "figure_class": normalize_text(row.get("stage2_figure_class") or row.get("figure_class") or row.get("figure_type")),
                    "technique": normalize_text(row.get("technique")),
                    "caption": normalize_text(row.get("caption") or row.get("safe_observations")),
                    "source_table": str(stage4_dir / "spectra_extractions.jsonl"),
                }
                spectra_rows.append({**row, **enriched})
                peak_rows.extend(_extract_peak_rows(enriched, row))
            for row in failed:
                failed_rows.append({"category": normalize_category(category_dir.name), "paper_id": paper_dir.name, **row})

    return {
        "paper_summary": pd.DataFrame(summary_rows),
        "spectra": pd.DataFrame(spectra_rows),
        "failed": pd.DataFrame(failed_rows),
        "quality": pd.DataFrame(quality_rows),
        "peaks": pd.DataFrame(peak_rows),
    }


def _resolve_stage4_dir(paper_dir: Path) -> Path | None:
    for name in ("stage4_vision_spectra_universal", "stage4_vision_spectra"):
        candidate = paper_dir / name
        if candidate.exists():
            return candidate
    return None


def _figure_identity(row: dict[str, Any]) -> str:
    for key in ("figure_id", "figure_key", "figure_path", "source_id"):
        value = normalize_text(row.get(key))
        if value:
            return value
    return ""


def _extract_peak_rows(base: dict[str, Any], raw_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_name in (
        "peaks",
        "characteristic_peaks",
        "ftir_peaks",
        "xrd_peaks",
        "nmr_peaks",
        "raman_peaks",
        "mass_loss_steps",
        "thermal_events",
        "endothermic_peaks",
        "exothermic_peaks",
        "transition_temperatures",
    ):
        payload = raw_row.get(field_name)
        if not payload:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for index, entry in enumerate(entries, start=1):
            if isinstance(entry, dict):
                rows.append(
                    {
                        **base,
                        "peak_source_field": field_name,
                        "peak_index": index,
                        "peak_value": entry.get("position") or entry.get("peak_position") or entry.get("value") or entry.get("temperature") or entry.get("ppm") or entry.get("two_theta"),
                        "peak_unit": normalize_text(entry.get("unit")),
                        "peak_label": normalize_text(entry.get("assignment") or entry.get("label") or entry.get("event") or entry.get("name")),
                        "source_table": base["source_table"],
                    }
                )
            else:
                rows.append(
                    {
                        **base,
                        "peak_source_field": field_name,
                        "peak_index": index,
                        "peak_value": entry,
                        "peak_unit": "",
                        "peak_label": "",
                        "source_table": base["source_table"],
                    }
                )
    return rows
