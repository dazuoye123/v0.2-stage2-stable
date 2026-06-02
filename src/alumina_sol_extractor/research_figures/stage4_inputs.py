from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from .io import normalize_text, read_json, read_jsonl, safe_float, safe_int


DEFAULT_STAGE4_SUBDIRS = ("stage4_vision_spectra_universal", "stage4_vision_spectra")
IGNORED_NON_PAPER_DIR_NAMES = {
    "figures",
    "figures_all",
    "figures_for_vision",
    "figures_merged",
    "figures_recropped",
    "final_dataset",
    "markdown",
    "stage3",
    "stage3_dspy_smoke",
    "stage3_text",
    "stage4_vision_spectra",
    "tables",
}


def load_stage4_batch_data(
    outputs_dir: Path,
    *,
    selected_pairs: set[tuple[str, str]] | None = None,
    selected_paper_ids: set[str] | None = None,
) -> dict[str, Any]:
    per_paper_rows: list[dict[str, Any]] = []
    spectra_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        if category_dir.name.startswith("_"):
            continue
        for paper_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            if not _is_selected(category_dir.name, paper_dir.name, selected_pairs=selected_pairs, selected_paper_ids=selected_paper_ids):
                continue
            stage4_dir = _resolve_stage4_dir(paper_dir)
            if stage4_dir is None:
                if paper_dir.name in IGNORED_NON_PAPER_DIR_NAMES:
                    continue
                warnings.append(f"missing_stage4:{paper_dir.name}")
                continue
            summary = read_json(stage4_dir / "stage4a_summary.json", default=None)
            if summary is None:
                summary = read_json(stage4_dir / "stage4_summary.json", default={}) or {}
            spectra = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
            failed = read_jsonl(stage4_dir / "failed_records.jsonl") or read_jsonl(stage4_dir / "spectra_failed_records.jsonl")
            summary_row = _build_per_paper_row(category_dir.name, paper_dir.name, summary, spectra, failed)
            per_paper_rows.append(summary_row)
            for row in spectra:
                enriched = dict(row)
                enriched.setdefault("paper_id", paper_dir.name)
                enriched.setdefault("category", category_dir.name)
                spectra_rows.append(enriched)
            for row in failed:
                enriched = dict(row)
                enriched.setdefault("paper_id", paper_dir.name)
                enriched.setdefault("category", category_dir.name)
                failed_rows.append(enriched)

            final_dataset_dir = paper_dir / "final_dataset"
            if final_dataset_dir.exists():
                link_rows.extend(_read_enriched_jsonl(final_dataset_dir / "linking" / "links.jsonl", paper_dir.name, category_dir.name))
                parameter_rows.extend(_read_enriched_jsonl(final_dataset_dir / "parameters.jsonl", paper_dir.name, category_dir.name))
                sample_rows.extend(_read_enriched_jsonl(final_dataset_dir / "samples.jsonl", paper_dir.name, category_dir.name))

    extraction_overview = _build_extraction_overview(per_paper_rows)
    figure_type_distribution = _build_figure_type_distribution(per_paper_rows, spectra_rows)
    spectra_type_distribution = _build_spectra_type_distribution(spectra_rows)
    peak_summary, peak_rows = _build_peak_summary(spectra_rows)
    return {
        "outputs_dir": str(outputs_dir),
        "per_paper_rows": per_paper_rows,
        "spectra_rows": spectra_rows,
        "failed_rows": failed_rows,
        "link_rows": link_rows,
        "parameter_rows": parameter_rows,
        "sample_rows": sample_rows,
        "extraction_overview": extraction_overview,
        "figure_type_distribution": figure_type_distribution,
        "spectra_type_distribution": spectra_type_distribution,
        "peak_summary": peak_summary,
        "peak_rows": peak_rows,
        "warnings": warnings,
    }


def _is_selected(
    category: str,
    paper_id: str,
    *,
    selected_pairs: set[tuple[str, str]] | None,
    selected_paper_ids: set[str] | None,
) -> bool:
    normalized_pair = (normalize_text(category), normalize_text(paper_id))
    if selected_pairs:
        return normalized_pair in selected_pairs
    if selected_paper_ids:
        return normalize_text(paper_id) in selected_paper_ids
    return True


def _resolve_stage4_dir(paper_dir: Path) -> Path | None:
    for name in DEFAULT_STAGE4_SUBDIRS:
        candidate = paper_dir / name
        if candidate.exists():
            return candidate
    return None


def _build_per_paper_row(
    category: str,
    paper_id: str,
    summary: dict[str, Any],
    spectra_rows: list[dict[str, Any]],
    failed_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_candidate_count = safe_int(summary.get("total_candidates"), 0)
    success_count = _count_unique_figures(spectra_rows)
    failed_count = _count_unique_figures(failed_rows)
    candidate_count = max(raw_candidate_count, success_count + failed_count, success_count)
    validation_error_count = _count_validation_error_figures(spectra_rows, failed_rows)
    by_figure_type = summary.get("by_stage2_figure_class") or Counter(normalize_text(row.get("stage2_figure_class")) for row in spectra_rows if normalize_text(row.get("stage2_figure_class")))
    spectra_types = Counter(normalize_spectra_type(row) for row in spectra_rows if normalize_spectra_type(row))
    return {
        "category": category,
        "paper_id": paper_id,
        "raw_candidate_count": raw_candidate_count,
        "candidate_count": candidate_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "validated_count": max(success_count - validation_error_count, 0),
        "validation_error_count": validation_error_count,
        "coverage_rate": round(success_count / candidate_count, 4) if candidate_count else 0.0,
        "figure_type_distribution": dict(by_figure_type),
        "spectra_type_distribution": dict(spectra_types),
    }


def _build_extraction_overview(per_paper_rows: list[dict[str, Any]]) -> pd.DataFrame:
    total_candidates = sum(row["candidate_count"] for row in per_paper_rows)
    total_success = sum(row["success_count"] for row in per_paper_rows)
    total_failed = sum(row["failed_count"] for row in per_paper_rows)
    total_validated = sum(row["validated_count"] for row in per_paper_rows)
    total_validation_errors = sum(row["validation_error_count"] for row in per_paper_rows)
    return pd.DataFrame(
        [
            {"metric": "candidates", "count": total_candidates},
            {"metric": "successful_extractions", "count": total_success},
            {"metric": "failed_records", "count": total_failed},
            {"metric": "validated", "count": total_validated},
            {"metric": "validation_errors", "count": total_validation_errors},
            {"metric": "papers_with_stage4", "count": len(per_paper_rows)},
        ]
    )


def _build_figure_type_distribution(per_paper_rows: list[dict[str, Any]], spectra_rows: list[dict[str, Any]]) -> pd.DataFrame:
    counter = Counter()
    for row in per_paper_rows:
        counter.update(row["figure_type_distribution"])
    if not counter and spectra_rows:
        counter.update(normalize_text(row.get("stage2_figure_class") or row.get("figure_type")) for row in spectra_rows if normalize_text(row.get("stage2_figure_class") or row.get("figure_type")))
    return pd.DataFrame(
        [{"figure_class": key or "unknown", "count": value} for key, value in counter.most_common()]
    )


def _build_spectra_type_distribution(spectra_rows: list[dict[str, Any]]) -> pd.DataFrame:
    counter = Counter(normalize_spectra_type(row) for row in spectra_rows if normalize_spectra_type(row))
    return pd.DataFrame([{"spectra_type": key, "count": value} for key, value in counter.most_common()])


def _build_peak_summary(spectra_rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    peak_rows: list[dict[str, Any]] = []
    for row in spectra_rows:
        paper_id = row.get("paper_id")
        figure_id = normalize_text(row.get("figure_id"))
        spectra_type = normalize_spectra_type(row)
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
            value = row.get(field_name)
            if not value:
                continue
            peak_rows.extend(_extract_peak_rows(value, paper_id=paper_id, figure_id=figure_id, spectra_type=spectra_type, source_field=field_name))
    frame = pd.DataFrame(peak_rows)
    if frame.empty:
        return pd.DataFrame(columns=["spectra_type", "source_field", "peak_row_count"]), peak_rows
    summary = (
        frame.groupby(["spectra_type", "source_field"]).size().reset_index(name="peak_row_count").sort_values("peak_row_count", ascending=False)
    )
    return summary, peak_rows


def normalize_spectra_type(record: dict[str, Any]) -> str:
    raw = normalize_text(record.get("technique") or record.get("actual_figure_type") or record.get("figure_type"))
    lowered = raw.lower().replace("-", " ").replace("_", " ")
    compact = " ".join(lowered.split())
    padded = f" {compact} "
    if not compact or compact in {"unknown", "non extractable", "non_extractable"}:
        return "Unknown"
    if any(token in compact for token in ("xrd", "x ray diffraction", "xray diffraction", "diffraction pattern")):
        return "XRD"
    if any(token in compact for token in ("ftir", "ft ir", "infrared", "ir spectrum")):
        return "FTIR"
    if "raman" in compact:
        return "Raman"
    if "nmr" in compact:
        return "NMR"
    if any(token in compact for token in ("tg dsc", "tga dsc", "simultaneous thermal", "sta")):
        return "TG-DSC"
    if any(token in compact for token in ("thermogravimetric", "tga", "mass loss")) or (" tg " in padded and "dsc" not in compact):
        return "TG"
    if any(token in compact for token in ("differential scanning calorimetry", "dsc", "dta")) and " tg " not in padded:
        return "DSC"
    if any(token in compact for token in ("rheology", "viscosity", "viscometry")):
        return "Rheology"
    if any(token in compact for token in ("particle size", "dynamic light scattering", "dls")):
        return "Particle size"
    if "zeta" in compact:
        return "Zeta"
    if any(token in compact for token in ("fesem", "scanning electron microscopy")) or " sem " in padded:
        return "SEM"
    if any(token in compact for token in ("hrtem", "transmission electron microscopy", "haadf", "saed")) or " tem " in padded or " stem " in padded:
        return "TEM"
    if any(token in compact for token in ("optical microscopy", "microscopy", "afm")):
        return "Microscopy"
    if "xps" in compact:
        return "XPS"
    if any(token in compact for token in ("n2 adsorption", "nitrogen adsorption", "bet", "surface area")):
        return "BET"
    if any(token in compact for token in ("ferron", "spectrophotometry")):
        return "Ferron"
    if any(token in compact for token in ("tensile", "compression", "mechanical")):
        return "Mechanical"
    if any(token in compact for token in ("photography", "photo")):
        return "Photography"
    if "simulation" in compact or "molecular dynamics" in compact:
        return "Simulation"
    return raw or "Unknown"


def _extract_peak_rows(
    value: Any,
    *,
    paper_id: str,
    figure_id: str,
    spectra_type: str,
    source_field: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                peak_value = _pick_numeric(item, "position", "peak_position", "value", "temperature", "ppm", "two_theta", "x")
                peak_label = normalize_text(item.get("assignment") or item.get("label") or item.get("event") or item.get("name"))
            else:
                peak_value = safe_float(item)
                peak_label = ""
            rows.append(
                {
                    "paper_id": paper_id,
                    "figure_id": figure_id,
                    "spectra_type": spectra_type or "Unknown",
                    "source_field": source_field,
                    "peak_index": index,
                    "peak_value": peak_value,
                    "peak_label": peak_label,
                }
            )
        return rows
    if isinstance(value, dict):
        for index, (key, item) in enumerate(value.items(), start=1):
            rows.append(
                {
                    "paper_id": paper_id,
                    "figure_id": figure_id,
                    "spectra_type": spectra_type or "Unknown",
                    "source_field": source_field,
                    "peak_index": index,
                    "peak_value": safe_float(item),
                    "peak_label": str(key),
                }
            )
        return rows
    rows.append(
        {
            "paper_id": paper_id,
            "figure_id": figure_id,
            "spectra_type": spectra_type or "Unknown",
            "source_field": source_field,
            "peak_index": 1,
            "peak_value": safe_float(value),
            "peak_label": "",
        }
    )
    return rows


def _pick_numeric(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = safe_float(payload.get(key))
        if value is not None:
            return value
    return None


def _count_validation_error_figures(*row_sets: list[dict[str, Any]]) -> int:
    figure_ids: set[str] = set()
    for rows in row_sets:
        for row in rows:
            if row.get("validation_errors"):
                figure_ids.add(_figure_identity(row))
    return len(figure_ids)


def _read_enriched_jsonl(path: Path, paper_id: str, category: str) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        new_row.setdefault("paper_id", paper_id)
        new_row.setdefault("category", category)
        enriched.append(new_row)
    return enriched


def _count_unique_figures(rows: list[dict[str, Any]]) -> int:
    return len({_figure_identity(row) for row in rows if _figure_identity(row)})


def _figure_identity(row: dict[str, Any]) -> str:
    for key in ("figure_id", "figure_key", "figure_path", "source_id"):
        value = normalize_text(row.get(key))
        if value:
            return value
    return ""
