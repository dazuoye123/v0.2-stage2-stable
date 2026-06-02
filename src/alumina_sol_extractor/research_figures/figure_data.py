from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import normalize_text
from .stage3_inputs import build_stage3_numeric_parameter_distribution, build_stage3_parameter_coverage, build_stage3_paper_lookup, build_stage3_sample_parameter_heatmap, classify_parameter_family


def build_research_figure_data(stage3_payload: dict[str, Any], stage4_payload: dict[str, Any]) -> dict[str, Any]:
    stage3_parameter_coverage = build_stage3_parameter_coverage(stage3_payload)
    stage3_sample_parameter_heatmap = build_stage3_sample_parameter_heatmap(stage3_payload)
    stage3_numeric_parameter_distribution = build_stage3_numeric_parameter_distribution(stage3_payload)
    stage4_extraction_overview = stage4_payload["extraction_overview"]
    stage4_figure_type_distribution = stage4_payload["figure_type_distribution"]
    stage4_spectra_type_distribution = stage4_payload["spectra_type_distribution"]
    stage4_peak_summary = stage4_payload["peak_summary"]
    stage3_stage4_link_overview = build_stage3_stage4_link_overview(stage3_payload, stage4_payload)

    return {
        "stage3_parameter_coverage": stage3_parameter_coverage,
        "stage3_sample_parameter_heatmap": stage3_sample_parameter_heatmap,
        "stage3_numeric_parameter_distribution": stage3_numeric_parameter_distribution,
        "stage4_extraction_overview": stage4_extraction_overview,
        "stage4_figure_type_distribution": stage4_figure_type_distribution,
        "stage4_spectra_type_distribution": stage4_spectra_type_distribution,
        "stage4_peak_summary": stage4_peak_summary,
        "stage3_stage4_link_overview": stage3_stage4_link_overview,
        "stage4_statistics": pd.DataFrame(stage4_payload["per_paper_rows"]),
        "stage4_peak_rows": pd.DataFrame(stage4_payload["peak_rows"]),
    }


def build_stage3_stage4_link_overview(stage3_payload: dict[str, Any], stage4_payload: dict[str, Any]) -> pd.DataFrame:
    stage3_lookup = build_stage3_paper_lookup(stage3_payload)
    stage4_rows = pd.DataFrame(stage4_payload["per_paper_rows"])
    if not stage4_rows.empty and not stage3_lookup.empty:
        merged = stage4_rows.merge(stage3_lookup[["paper_id", "sample_count"]], on="paper_id", how="left")
    else:
        merged = stage4_rows.copy()
        if "sample_count" not in merged.columns:
            merged["sample_count"] = 0

    links = stage4_payload["link_rows"]
    parameters = pd.DataFrame(stage4_payload["parameter_rows"])
    spectra = pd.DataFrame(stage4_payload["spectra_rows"])
    link_heatmap_rows: list[dict[str, Any]] = []
    if links and not parameters.empty and not spectra.empty:
        parameter_family = {row["parameter_id"]: classify_parameter_family(row.get("canonical_key")) for _, row in parameters.iterrows() if normalize_text(row.get("parameter_id"))}
        spectra_type = {f"spectra-{normalize_text(row.get('figure_id'))}": normalize_text(row.get("technique")) or normalize_text(row.get("figure_type")) for _, row in spectra.iterrows() if normalize_text(row.get("figure_id"))}
        counter: dict[tuple[str, str], int] = {}
        for row in links:
            if normalize_text(row.get("target_type")) != "parameter":
                continue
            source_type = normalize_text(row.get("source_type"))
            if source_type not in {"spectra_record", "spectra_peak"}:
                continue
            family = parameter_family.get(normalize_text(row.get("target_id")), "other")
            spec_type = spectra_type.get(normalize_text(row.get("source_id")), "Unknown")
            key = (spec_type or "Unknown", family or "other")
            counter[key] = counter.get(key, 0) + 1
        link_heatmap_rows = [
            {"spectra_type": spec_type, "parameter_family": family, "count": count}
            for (spec_type, family), count in sorted(counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        ]

    scatter_rows = []
    if not merged.empty:
        for _, row in merged.iterrows():
            scatter_rows.append(
                {
                    "paper_id": row.get("paper_id"),
                    "category": row.get("category"),
                    "sample_count": row.get("sample_count", 0),
                    "stage4_success_count": row.get("success_count", 0),
                    "stage4_candidate_count": row.get("candidate_count", 0),
                    "coverage_rate": row.get("coverage_rate", 0),
                    "row_type": "paper_scatter",
                }
            )
    for row in link_heatmap_rows:
        enriched = dict(row)
        enriched["row_type"] = "spectra_parameter_link"
        scatter_rows.append(enriched)
    return pd.DataFrame(scatter_rows)


def build_stage3_stage4_figure_index(figure_tables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {"figure_name": "stage3_parameter_coverage", "primary_csv": "tables/stage3_parameter_coverage.csv", "description": "Stage3 parameter coverage rates by key/family"},
        {"figure_name": "stage3_sample_parameter_heatmap", "primary_csv": "tables/stage3_sample_parameter_heatmap.csv", "description": "Stage3 sample-parameter matrix used for heatmap"},
        {"figure_name": "stage3_numeric_parameter_distribution", "primary_csv": "tables/stage3_numeric_parameter_distribution.csv", "description": "Numeric Stage3 parameter values for distribution plots"},
        {"figure_name": "stage4_extraction_overview", "primary_csv": "tables/stage4_extraction_overview.csv", "description": "Batch-level Stage4 candidate/success/fail/validated counts"},
        {"figure_name": "stage4_figure_type_distribution", "primary_csv": "tables/stage4_figure_type_distribution.csv", "description": "Batch-level Stage4 figure_class distribution"},
        {"figure_name": "stage4_spectra_type_distribution", "primary_csv": "tables/stage4_spectra_type_distribution.csv", "description": "Batch-level Stage4 spectra type distribution"},
        {"figure_name": "stage4_peak_summary", "primary_csv": "tables/stage4_peak_summary.csv", "description": "Peak-row counts grouped by spectra type and peak source field"},
        {"figure_name": "stage3_stage4_link_overview", "primary_csv": "tables/stage3_stage4_link_overview.csv", "description": "Stage3 sample counts vs Stage4 success and spectra-parameter link rows"},
        {"figure_name": "stage3_stage4_research_overview", "primary_csv": "stage3_stage4_figure_data.csv", "description": "Combined publication-style multi-panel overview"},
    ]
    if not figure_tables:
        return rows
    row_counts = {
        name: int(len(frame))
        for name, frame in figure_tables.items()
        if isinstance(frame, pd.DataFrame)
    }
    if "stage3_stage4_research_overview" not in row_counts and "stage3_stage4_link_overview" in row_counts:
        row_counts["stage3_stage4_research_overview"] = row_counts["stage3_stage4_link_overview"]
    for row in rows:
        row["json_path"] = f"figure_data/{row['figure_name']}.json"
        row["row_count"] = row_counts.get(row["figure_name"], 0)
    return rows
