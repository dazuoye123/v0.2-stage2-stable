from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import normalize_text, read_csv, read_json, read_jsonl, schema_report_from_frame


STAGE3_KEY_FILES = [
    "analysis_outputs_stage3_summary.json",
    "stage3_analysis_summary.json",
    "parameter_distribution.csv",
    "sample_parameter_long.csv",
    "paper_stage3_summary.csv",
    "canonical_key_category_summary.csv",
    "canonical_key_by_category.csv",
    "time_condition_distribution_by_type.csv",
    "process_condition_distribution.csv",
]

STAGE3_PUBLICATION_FILES = [
    "fig3_coverage_matrix_plotting_data.csv",
    "fig3_paper_metadata_plotting_data.csv",
    "label_mapping.csv",
]

STAGE4_KEY_FILES = [
    "stage4a_summary.json",
    "stage4_summary.json",
    "spectra_extractions.jsonl",
    "failed_records.jsonl",
    "spectra_failed_records.jsonl",
    "stage4_quality_review.json",
]

STAGE5_KEY_FILES = [
    "paper.json",
    "parameters.jsonl",
    "samples.jsonl",
    "process_steps.jsonl",
    "evidence.jsonl",
    "spectra.jsonl",
    "quality_summary.json",
    "fusion_report.md",
    "linking/links.jsonl",
    "linking/linking_summary.json",
    "link_aware_exports/final_parameters_linked.csv",
    "link_aware_exports/sample_parameter_matrix.csv",
    "link_aware_exports/evidence_parameter_links.csv",
    "link_aware_exports/process_step_parameter_links.csv",
    "link_aware_exports/spectra_parameter_links.csv",
    "link_aware_exports/process_steps_table.csv",
    "link_aware_exports/link_aware_export_summary.json",
]

BATCH_EXPORT_FILES = [
    "all_papers_final_parameters_linked.csv",
    "all_papers_evidence_parameter_links.csv",
    "all_papers_process_step_parameter_links.csv",
    "all_papers_spectra_parameter_links.csv",
    "all_papers_process_steps_table.csv",
    "all_papers_sample_parameter_matrix.csv",
    "all_papers_final_showcase_table.csv",
    "all_papers_link_aware_summary.json",
    "all_papers_export_report.md",
]


def discover_inputs(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
) -> dict[str, Any]:
    stage3_dirs = [
        project_root / "data" / "analysis_outputs_stage3_v2",
        project_root / "data" / "analysis_outputs_stage3",
    ]
    if stage3_analysis_dir:
        stage3_dirs.insert(0, stage3_analysis_dir)
    stage3_dirs = _dedupe_existing_dirs(stage3_dirs)

    stage3_publication_dirs = [project_root / "data" / "analysis_outputs_stage3_publication"]
    if stage3_publication_dir:
        stage3_publication_dirs.insert(0, stage3_publication_dir)
    stage3_publication_dirs = _dedupe_existing_dirs(stage3_publication_dirs)

    stage4_papers = _discover_paper_dirs(outputs_dir, target_subdir_names=("stage4_vision_spectra_universal", "stage4_vision_spectra"))
    stage5_papers = _discover_final_dataset_dirs(outputs_dir)

    availability_rows: list[dict[str, Any]] = []
    schema_reports: list[dict[str, Any]] = []
    warnings: list[str] = []

    for directory in stage3_dirs:
        for filename in STAGE3_KEY_FILES:
            _collect_file_report(
                availability_rows,
                schema_reports,
                data_source="stage3",
                file_path=directory / filename,
                key_columns=_guess_key_columns(filename),
            )
    for directory in stage3_publication_dirs:
        for filename in STAGE3_PUBLICATION_FILES:
            _collect_file_report(
                availability_rows,
                schema_reports,
                data_source="stage3_publication",
                file_path=directory / filename,
                key_columns=_guess_key_columns(filename),
            )
    for paper in stage4_papers[:]:
        for filename in STAGE4_KEY_FILES:
            _collect_file_report(
                availability_rows,
                schema_reports,
                data_source="stage4",
                file_path=paper["stage4_dir"] / filename,
                key_columns=_guess_key_columns(filename),
                paper_id=paper["paper_id"],
                category=paper["category"],
            )
    for paper in stage5_papers[:]:
        for filename in STAGE5_KEY_FILES:
            _collect_file_report(
                availability_rows,
                schema_reports,
                data_source="stage5",
                file_path=paper["final_dataset_dir"] / filename,
                key_columns=_guess_key_columns(filename),
                paper_id=paper["paper_id"],
                category=paper["category"],
            )
    for filename in BATCH_EXPORT_FILES:
        _collect_file_report(
            availability_rows,
            schema_reports,
            data_source="stage5_batch_export",
            file_path=batch_final_export_dir / filename,
            key_columns=_guess_key_columns(filename),
        )

    core_inputs = {
        filename: (batch_final_export_dir / filename).exists()
        for filename in (
            "all_papers_final_parameters_linked.csv",
            "all_papers_process_steps_table.csv",
            "all_papers_spectra_parameter_links.csv",
            "all_papers_link_aware_summary.json",
        )
    }
    if not all(core_inputs.values()):
        warnings.append("missing_core_batch_export_inputs")

    return {
        "project_root": str(project_root),
        "outputs_dir": str(outputs_dir),
        "batch_final_export_dir": str(batch_final_export_dir),
        "stage3_dirs_found": [str(path) for path in stage3_dirs],
        "stage3_publication_dirs_found": [str(path) for path in stage3_publication_dirs],
        "stage4_paper_count": len(stage4_papers),
        "stage5_paper_count": len(stage5_papers),
        "stage4_papers": stage4_papers,
        "stage5_papers": stage5_papers,
        "batch_export_files_found": [filename for filename, exists in core_inputs.items() if exists],
        "core_input_availability": core_inputs,
        "availability_rows": availability_rows,
        "schema_reports": schema_reports,
        "warnings": warnings,
    }


def _discover_paper_dirs(outputs_dir: Path, *, target_subdir_names: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        if category_dir.name.startswith("_"):
            continue
        for paper_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            stage4_dir = None
            for name in target_subdir_names:
                candidate = paper_dir / name
                if candidate.exists():
                    stage4_dir = candidate
                    break
            if stage4_dir is None:
                continue
            rows.append(
                {
                    "category": category_dir.name,
                    "paper_id": paper_dir.name,
                    "paper_dir": str(paper_dir),
                    "stage4_dir": stage4_dir,
                }
            )
    return rows


def _discover_final_dataset_dirs(outputs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category_dir in sorted(path for path in outputs_dir.iterdir() if path.is_dir()):
        if category_dir.name.startswith("_"):
            continue
        for paper_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            final_dataset_dir = paper_dir / "final_dataset"
            if not final_dataset_dir.exists():
                continue
            rows.append(
                {
                    "category": category_dir.name,
                    "paper_id": paper_dir.name,
                    "paper_dir": str(paper_dir),
                    "final_dataset_dir": final_dataset_dir,
                }
            )
    return rows


def _collect_file_report(
    availability_rows: list[dict[str, Any]],
    schema_reports: list[dict[str, Any]],
    *,
    data_source: str,
    file_path: Path,
    key_columns: list[str],
    category: str | None = None,
    paper_id: str | None = None,
) -> None:
    exists = file_path.exists()
    row_count = 0
    column_count = 0
    columns: list[str] = []
    notes = ""
    if exists and file_path.suffix == ".csv":
        frame = read_csv(file_path)
        row_count = int(len(frame))
        column_count = int(len(frame.columns))
        columns = frame.columns.tolist()
        schema_reports.append(schema_report_from_frame(str(file_path), frame))
    elif exists and file_path.suffix == ".jsonl":
        rows = read_jsonl(file_path)
        row_count = len(rows)
        if rows:
            columns = sorted({key for row in rows for key in row.keys()})
            column_count = len(columns)
        schema_reports.append(
            {
                "name": str(file_path),
                "row_count": row_count,
                "column_count": column_count,
                "columns": columns,
                "dtypes": {},
            }
        )
    elif exists and file_path.suffix == ".json":
        payload = read_json(file_path, default={}) or {}
        if isinstance(payload, dict):
            columns = list(payload.keys())
            column_count = len(columns)
        notes = "json_object"
    missing_keys = [column for column in key_columns if column and column not in columns]
    availability_rows.append(
        {
            "data_source": data_source,
            "category": category,
            "paper_id": paper_id,
            "file_path": str(file_path),
            "exists": exists,
            "row_count": row_count,
            "column_count": column_count,
            "key_columns_present": "; ".join(column for column in key_columns if column in columns),
            "missing_key_columns": "; ".join(missing_keys),
            "usable_for_figures": bool(exists and not missing_keys),
            "notes": notes,
        }
    )


def _guess_key_columns(filename: str) -> list[str]:
    lookup = {
        "parameter_distribution.csv": ["canonical_key", "paper_count"],
        "sample_parameter_long.csv": ["paper_id", "sample_id", "canonical_key", "value"],
        "paper_stage3_summary.csv": ["paper_id", "sample_count"],
        "all_papers_final_parameters_linked.csv": ["paper_id", "category", "parameter_id", "canonical_key"],
        "all_papers_process_steps_table.csv": ["paper_id", "step_id", "action"],
        "all_papers_spectra_parameter_links.csv": ["paper_id", "figure_id", "parameter_id", "canonical_key"],
        "all_papers_sample_parameter_matrix.csv": ["paper_id", "sample_id", "parameter_count"],
        "spectra_extractions.jsonl": ["figure_id", "figure_type"],
        "parameters.jsonl": ["parameter_id", "canonical_key"],
        "process_steps.jsonl": ["step_id", "action"],
        "linking/links.jsonl": ["source_id", "target_id", "link_type"],
    }
    return lookup.get(filename, [])


def _dedupe_existing_dirs(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    existing: list[Path] = []
    for path in paths:
        resolved = str(path)
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        existing.append(path)
    return existing
