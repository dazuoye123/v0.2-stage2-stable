"""Batch export helpers for link-aware final dataset tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.exporters import write_json, write_markdown
from alumina_sol_extractor.dataset_fusion.link_aware_export import (
    EVIDENCE_PARAMETER_LINK_FIELDS,
    FINAL_PARAMETERS_LINKED_FIELDS,
    FINAL_SHOWCASE_FIELDS,
    SAMPLE_PARAMETER_MATRIX_FIELDS,
    SPECTRA_PARAMETER_LINK_FIELDS,
)
from alumina_sol_extractor.dataset_fusion.loaders import read_json


def export_batch_link_aware_dataset(
    outputs_dir: Path | str,
    *,
    output_dir: Path | str,
    paper_ids: list[str] | None = None,
) -> dict[str, Any]:
    outputs_dir = Path(outputs_dir)
    output_dir = Path(output_dir)
    discovered = discover_link_aware_export_dirs(outputs_dir, paper_ids=paper_ids)

    aggregate_rows = {
        "final_parameters": [],
        "sample_matrix": [],
        "evidence_links": [],
        "spectra_links": [],
        "showcase": [],
    }
    summary_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for item in discovered:
        paper_id = item["paper_id"]
        export_dir = item["export_dir"]
        if not item["has_link_aware_exports"]:
            warnings.append(f"{paper_id}:missing_link_aware_exports")
            continue
        missing = [name for name, exists in item["file_presence"].items() if not exists]
        if missing:
            warnings.append(f"{paper_id}:missing_files={','.join(missing)}")
        summary_payload = read_json(export_dir / "link_aware_export_summary.json", default={}) or {}
        if summary_payload:
            summary_rows.append({"paper_id": paper_id, **summary_payload})

        aggregate_rows["final_parameters"].extend(_read_csv_rows(export_dir / "final_parameters_linked.csv", paper_id))
        aggregate_rows["sample_matrix"].extend(_read_csv_rows(export_dir / "sample_parameter_matrix.csv", paper_id))
        aggregate_rows["evidence_links"].extend(_read_csv_rows(export_dir / "evidence_parameter_links.csv", paper_id))
        aggregate_rows["spectra_links"].extend(_read_csv_rows(export_dir / "spectra_parameter_links.csv", paper_id))
        aggregate_rows["showcase"].extend(_read_csv_rows(export_dir / "final_showcase_table.csv", paper_id))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv_with_fields(
        output_dir / "all_papers_final_parameters_linked.csv",
        aggregate_rows["final_parameters"],
        FINAL_PARAMETERS_LINKED_FIELDS,
    )
    _write_csv_with_fields(
        output_dir / "all_papers_sample_parameter_matrix.csv",
        aggregate_rows["sample_matrix"],
        SAMPLE_PARAMETER_MATRIX_FIELDS,
    )
    _write_csv_with_fields(
        output_dir / "all_papers_evidence_parameter_links.csv",
        aggregate_rows["evidence_links"],
        EVIDENCE_PARAMETER_LINK_FIELDS,
    )
    _write_csv_with_fields(
        output_dir / "all_papers_spectra_parameter_links.csv",
        aggregate_rows["spectra_links"],
        SPECTRA_PARAMETER_LINK_FIELDS,
    )
    _write_csv_with_fields(
        output_dir / "all_papers_final_showcase_table.csv",
        aggregate_rows["showcase"],
        FINAL_SHOWCASE_FIELDS,
    )

    summary = {
        "paper_count": len([item for item in discovered if item["has_link_aware_exports"]]),
        "discovered_papers": len(discovered),
        "warnings": warnings,
        "per_paper": summary_rows,
        "total_parameters": sum(int(row.get("total_parameters") or 0) for row in summary_rows),
        "parameters_with_any_link": sum(int(row.get("parameters_with_any_link") or 0) for row in summary_rows),
        "parameters_with_sample_link": sum(int(row.get("parameters_with_sample_link") or 0) for row in summary_rows),
        "parameters_with_evidence_link": sum(int(row.get("parameters_with_evidence_link") or 0) for row in summary_rows),
        "parameters_with_spectra_link": sum(int(row.get("parameters_with_spectra_link") or 0) for row in summary_rows),
        "parameters_missing_all_links": sum(int(row.get("parameters_missing_all_links") or 0) for row in summary_rows),
        "total_evidence_parameter_links": sum(int(row.get("total_evidence_parameter_links") or 0) for row in summary_rows),
        "total_spectra_parameter_links": sum(int(row.get("total_spectra_parameter_links") or 0) for row in summary_rows),
        "total_samples": sum(int(row.get("total_samples") or 0) for row in summary_rows),
        "showcase_rows": len(aggregate_rows["showcase"]),
        "sample_matrix_rows": len(aggregate_rows["sample_matrix"]),
    }
    report = _build_batch_export_report(summary)
    write_json(output_dir / "all_papers_link_aware_summary.json", summary)
    write_markdown(output_dir / "all_papers_export_report.md", report)
    return {
        "output_dir": str(output_dir),
        "summary": summary,
    }


def discover_link_aware_export_dirs(outputs_dir: Path | str, *, paper_ids: list[str] | None = None) -> list[dict[str, Any]]:
    outputs_dir = Path(outputs_dir)
    allowed = set(paper_ids or [])
    export_files = {
        "final_parameters_linked.csv": "final_parameters_linked.csv",
        "sample_parameter_matrix.csv": "sample_parameter_matrix.csv",
        "evidence_parameter_links.csv": "evidence_parameter_links.csv",
        "spectra_parameter_links.csv": "spectra_parameter_links.csv",
        "final_showcase_table.csv": "final_showcase_table.csv",
        "link_aware_export_summary.json": "link_aware_export_summary.json",
        "link_aware_export_readme.md": "link_aware_export_readme.md",
    }
    rows: list[dict[str, Any]] = []
    for paper_dir in sorted(outputs_dir.iterdir(), key=lambda path: path.name):
        if not paper_dir.is_dir():
            continue
        if allowed and paper_dir.name not in allowed:
            continue
        final_dataset_dir = paper_dir / "final_dataset"
        if not final_dataset_dir.exists():
            continue
        export_dir = final_dataset_dir / "link_aware_exports"
        file_presence = {name: (export_dir / rel_path).exists() for name, rel_path in export_files.items()}
        rows.append(
            {
                "paper_id": paper_dir.name,
                "export_dir": export_dir,
                "has_link_aware_exports": export_dir.exists() and all(file_presence.values()),
                "file_presence": file_presence,
            }
        )
    return rows


def _read_csv_rows(path: Path, paper_id: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            payload = dict(row)
            if not payload.get("paper_id"):
                payload["paper_id"] = paper_id
            rows.append(payload)
    return rows


def _write_csv_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    full_fieldnames = list(dict.fromkeys(["paper_id", *fieldnames]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=full_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in full_fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _build_batch_export_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Batch Link-aware Export Report",
        "",
        "## Overview",
        f"- discovered_papers: {summary['discovered_papers']}",
        f"- exported_papers: {summary['paper_count']}",
        f"- total_parameters: {summary['total_parameters']}",
        f"- parameters_with_any_link: {summary['parameters_with_any_link']}",
        f"- parameters_with_sample_link: {summary['parameters_with_sample_link']}",
        f"- parameters_with_evidence_link: {summary['parameters_with_evidence_link']}",
        f"- parameters_with_spectra_link: {summary['parameters_with_spectra_link']}",
        f"- parameters_missing_all_links: {summary['parameters_missing_all_links']}",
        f"- total_evidence_parameter_links: {summary['total_evidence_parameter_links']}",
        f"- total_spectra_parameter_links: {summary['total_spectra_parameter_links']}",
        f"- total_samples: {summary['total_samples']}",
        f"- showcase_rows: {summary['showcase_rows']}",
        "",
        "## Warnings",
    ]
    if summary["warnings"]:
        lines.extend([f"- {item}" for item in summary["warnings"]])
    else:
        lines.append("- none")
    lines.extend(["", "## Per Paper"])
    for row in summary["per_paper"]:
        lines.extend(
            [
                "",
                f"### {row['paper_id']}",
                f"- total_parameters: {row.get('total_parameters', 0)}",
                f"- parameters_with_any_link: {row.get('parameters_with_any_link', 0)}",
                f"- parameters_with_sample_link: {row.get('parameters_with_sample_link', 0)}",
                f"- parameters_with_evidence_link: {row.get('parameters_with_evidence_link', 0)}",
                f"- parameters_with_spectra_link: {row.get('parameters_with_spectra_link', 0)}",
                f"- showcase_rows: {row.get('showcase_rows', 0)}",
            ]
        )
    return "\n".join(lines)
