"""Batch export helpers for link-aware final dataset tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.exporters import write_json, write_markdown
from alumina_sol_extractor.dataset_fusion.link_aware_fields import (
    EVIDENCE_PARAMETER_LINK_FIELDS,
    FINAL_PARAMETERS_LINKED_FIELDS,
    FINAL_SHOWCASE_FIELDS,
    PROCESS_STEPS_TABLE_FIELDS,
    SAMPLE_PARAMETER_MATRIX_FIELDS,
    SPECTRA_PARAMETER_LINK_FIELDS,
    build_sample_parameter_matrix_fields,
)
from alumina_sol_extractor.dataset_fusion.loaders import read_json
from alumina_sol_extractor.stage5.dataset_fusion.link_aware_export import generate_link_aware_exports
from alumina_sol_extractor.stage5.dataset_fusion.semantics import resolve_paper_identity_from_dir

REQUIRED_EXPORT_FILES = {
    "final_parameters_linked.csv": "final_parameters_linked.csv",
    "sample_parameter_matrix.csv": "sample_parameter_matrix.csv",
    "evidence_parameter_links.csv": "evidence_parameter_links.csv",
    "process_step_parameter_links.csv": "process_step_parameter_links.csv",
    "spectra_parameter_links.csv": "spectra_parameter_links.csv",
    "process_steps_table.csv": "process_steps_table.csv",
    "link_aware_export_summary.json": "link_aware_export_summary.json",
}

OPTIONAL_EXPORT_FILES = {
    "final_showcase_table.csv": "final_showcase_table.csv",
    "sample_parameter_matrix_long.csv": "sample_parameter_matrix_long.csv",
    "sample_matrix_missing_diagnosis.csv": "sample_matrix_missing_diagnosis.csv",
    "link_aware_export_readme.md": "link_aware_export_readme.md",
}

REBUILD_REQUIRED_FILES = [
    "paper.json",
    "samples.jsonl",
    "parameters.jsonl",
    "process_steps.jsonl",
    "evidence.jsonl",
    "spectra.jsonl",
    "linking/links.jsonl",
]


def export_batch_link_aware_dataset(
    outputs_dir: Path | str,
    *,
    output_dir: Path | str,
    paper_ids: list[str] | None = None,
    rebuild_from_final_dataset: bool = True,
) -> dict[str, Any]:
    outputs_dir = Path(outputs_dir)
    output_dir = Path(output_dir)
    discovered = discover_link_aware_export_dirs(outputs_dir, paper_ids=paper_ids)

    aggregate_rows = {
        "final_parameters": [],
        "sample_matrix": [],
        "evidence_links": [],
        "process_step_links": [],
        "spectra_links": [],
        "process_steps_table": [],
        "showcase": [],
        "excluded_parameters": [],
        "parameter_semantic_qa": [],
    }
    summary_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    exported_flat_paper_count = 0
    exported_category_paper_count = 0
    rebuilt_paper_count = 0
    reused_existing_export_count = 0
    missing_required_file_count = 0
    missing_optional_file_count = 0
    by_category: dict[str, dict[str, int]] = {}

    for item in discovered:
        paper_id = item["paper_id"]
        qualified_paper_id = item["qualified_paper_id"]
        export_payload: dict[str, Any] | None = None
        summary_payload: dict[str, Any] = {}

        if rebuild_from_final_dataset and _can_rebuild_from_final_dataset(item["final_dataset_dir"]):
            try:
                export_payload = generate_link_aware_exports(
                    item["final_dataset_dir"],
                    output_dir=output_dir / "_semantic_tmp" / paper_id,
                    paper_id=paper_id,
                    write_outputs=False,
                )
                summary_payload = dict(export_payload.get("summary") or {})
                rebuilt_paper_count += 1
            except Exception as exc:
                warnings.append(f"{qualified_paper_id}:semantic_rebuild_failed={type(exc).__name__}:{exc}")

        if export_payload is None:
            missing_required = [name for name in REQUIRED_EXPORT_FILES if not item["file_presence"].get(name)]
            missing_optional = [name for name in OPTIONAL_EXPORT_FILES if not item["file_presence"].get(name)]
            if missing_required:
                warnings.append(f"{qualified_paper_id}:missing_required={','.join(missing_required)}")
                missing_required_file_count += len(missing_required)
                continue
            if missing_optional:
                warnings.append(f"{qualified_paper_id}:missing_optional={','.join(missing_optional)}")
                missing_optional_file_count += len(missing_optional)
            export_payload = _read_existing_export_payload(item)
            summary_payload = dict(export_payload.get("summary") or {})
            reused_existing_export_count += 1

        paper_identity = dict(export_payload.get("paper_identity") or {}) or dict(item.get("paper_identity") or {})
        paper_category = paper_identity.get("paper_category") or item.get("paper_category") or "uncategorized"
        summary_payload.setdefault("paper_category", paper_category if paper_category != "uncategorized" else "")
        summary_payload.setdefault("paper_category_status", paper_identity.get("paper_category_status") or item.get("paper_category_status"))
        summary_rows.append(
            {
                "paper_id": paper_id,
                "paper_category": paper_category if paper_category != "uncategorized" else "",
                "paper_category_status": paper_identity.get("paper_category_status") or item.get("paper_category_status"),
                "qualified_paper_id": qualified_paper_id,
                **summary_payload,
            }
        )

        if item["layout_type"] == "flat":
            exported_flat_paper_count += 1
        else:
            exported_category_paper_count += 1

        aggregate_rows["final_parameters"].extend(export_payload.get("final_parameters_linked") or [])
        aggregate_rows["sample_matrix"].extend(export_payload.get("sample_parameter_matrix") or [])
        aggregate_rows["evidence_links"].extend(export_payload.get("evidence_parameter_links") or [])
        aggregate_rows["process_step_links"].extend(export_payload.get("process_step_parameter_links") or [])
        aggregate_rows["spectra_links"].extend(export_payload.get("spectra_parameter_links") or [])
        aggregate_rows["process_steps_table"].extend(export_payload.get("process_steps_table") or [])
        aggregate_rows["showcase"].extend(export_payload.get("final_showcase_table") or [])
        aggregate_rows["excluded_parameters"].extend(export_payload.get("excluded_parameters") or [])
        aggregate_rows["parameter_semantic_qa"].extend(export_payload.get("parameter_semantic_qa") or [])

        category_summary = by_category.setdefault(
            paper_category or "uncategorized",
            {
                "paper_count": 0,
                "total_parameters": 0,
                "excluded_parameters": 0,
                "metadata_or_bookkeeping_count": 0,
                "characterization_output_parameter_count": 0,
                "total_evidence_parameter_links": 0,
                "total_process_step_parameter_links": 0,
                "total_spectra_parameter_links": 0,
                "sample_matrix_rows": 0,
            },
        )
        category_summary["paper_count"] += 1
        category_summary["total_parameters"] += int(summary_payload.get("total_parameters") or 0)
        category_summary["excluded_parameters"] += int(summary_payload.get("excluded_parameter_count") or 0)
        category_summary["metadata_or_bookkeeping_count"] += int(summary_payload.get("metadata_or_bookkeeping_count") or 0)
        category_summary["characterization_output_parameter_count"] += int(summary_payload.get("characterization_output_parameter_count") or 0)
        category_summary["total_evidence_parameter_links"] += int(summary_payload.get("total_evidence_parameter_links") or 0)
        category_summary["total_process_step_parameter_links"] += int(summary_payload.get("process_step_parameter_links") or 0)
        category_summary["total_spectra_parameter_links"] += int(summary_payload.get("total_spectra_parameter_links") or 0)
        category_summary["sample_matrix_rows"] += int(summary_payload.get("sample_matrix_rows") or 0)

    output_dir.mkdir(parents=True, exist_ok=True)
    sample_matrix_fields = build_sample_parameter_matrix_fields(_collect_dynamic_sample_matrix_keys(aggregate_rows["sample_matrix"]))
    _write_csv_with_fields(output_dir / "all_papers_final_parameters_linked.csv", aggregate_rows["final_parameters"], FINAL_PARAMETERS_LINKED_FIELDS)
    _write_csv_with_fields(output_dir / "all_papers_sample_parameter_matrix.csv", aggregate_rows["sample_matrix"], sample_matrix_fields)
    _write_csv_with_fields(output_dir / "all_papers_evidence_parameter_links.csv", aggregate_rows["evidence_links"], EVIDENCE_PARAMETER_LINK_FIELDS)
    _write_csv_with_fields(output_dir / "all_papers_process_step_parameter_links.csv", aggregate_rows["process_step_links"], EVIDENCE_PARAMETER_LINK_FIELDS)
    _write_csv_with_fields(output_dir / "all_papers_spectra_parameter_links.csv", aggregate_rows["spectra_links"], SPECTRA_PARAMETER_LINK_FIELDS)
    _write_csv_with_fields(output_dir / "all_papers_process_steps_table.csv", aggregate_rows["process_steps_table"], PROCESS_STEPS_TABLE_FIELDS)
    _write_csv_with_fields(output_dir / "all_papers_final_showcase_table.csv", aggregate_rows["showcase"], FINAL_SHOWCASE_FIELDS)
    _write_csv_with_dynamic_fields(output_dir / "all_papers_excluded_parameters.csv", aggregate_rows["excluded_parameters"])
    _write_csv_with_dynamic_fields(output_dir / "all_papers_parameter_semantic_qa.csv", aggregate_rows["parameter_semantic_qa"])

    summary = {
        "paper_count": len(summary_rows),
        "discovered_papers": len(discovered),
        "warnings": warnings,
        "per_paper": summary_rows,
        "total_parameters": sum(int(row.get("total_parameters") or 0) for row in summary_rows),
        "parameters_with_any_link": sum(int(row.get("parameters_with_any_link") or 0) for row in summary_rows),
        "parameters_with_sample_link": sum(int(row.get("parameters_with_sample_link") or 0) for row in summary_rows),
        "parameters_with_evidence_link": sum(int(row.get("parameters_with_evidence_link") or 0) for row in summary_rows),
        "parameters_with_spectra_link": sum(int(row.get("parameters_with_spectra_link") or 0) for row in summary_rows),
        "parameters_missing_all_links": sum(int(row.get("parameters_missing_all_links") or 0) for row in summary_rows),
        "excluded_parameter_count": sum(int(row.get("excluded_parameter_count") or 0) for row in summary_rows),
        "metadata_or_bookkeeping_count": sum(int(row.get("metadata_or_bookkeeping_count") or 0) for row in summary_rows),
        "characterization_output_parameter_count": sum(int(row.get("characterization_output_parameter_count") or 0) for row in summary_rows),
        "total_evidence_parameter_links": sum(int(row.get("total_evidence_parameter_links") or 0) for row in summary_rows),
        "total_process_step_parameter_links": sum(int(row.get("process_step_parameter_links") or 0) for row in summary_rows),
        "total_spectra_parameter_links": sum(int(row.get("total_spectra_parameter_links") or 0) for row in summary_rows),
        "total_samples": sum(int(row.get("total_samples") or 0) for row in summary_rows),
        "showcase_rows": len(aggregate_rows["showcase"]),
        "sample_matrix_rows": len(aggregate_rows["sample_matrix"]),
        "process_steps_table_rows": len(aggregate_rows["process_steps_table"]),
        "exported_flat_paper_count": exported_flat_paper_count,
        "exported_category_paper_count": exported_category_paper_count,
        "rebuilt_paper_count": rebuilt_paper_count,
        "reused_existing_export_count": reused_existing_export_count,
        "official_paper_count": sum(1 for row in summary_rows if row.get("paper_category_status") == "official"),
        "non_primary_paper_count": sum(1 for row in summary_rows if row.get("paper_category_status") != "official"),
        "missing_identity_row_count": _count_missing_identity_rows(aggregate_rows),
        "by_category": by_category,
        "missing_required_file_count": missing_required_file_count,
        "missing_optional_file_count": missing_optional_file_count,
        "rebuild_from_final_dataset": rebuild_from_final_dataset,
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
    normalized_filters = {_normalize_paper_selector(item) for item in (paper_ids or []) if item}
    discovered: list[dict[str, Any]] = []

    for child in sorted(outputs_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or _is_ignored_dir(child.name):
            continue
        if _is_paper_dir(child):
            _add_discovered_paper(discovered, child, category=None, normalized_filters=normalized_filters)
            continue
        if _looks_like_category_dir(child):
            for grandchild in sorted(child.iterdir(), key=lambda path: path.name):
                if not grandchild.is_dir() or _is_ignored_dir(grandchild.name):
                    continue
                if _is_paper_dir(grandchild):
                    _add_discovered_paper(discovered, grandchild, category=child.name, normalized_filters=normalized_filters)

    deduped: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for row in discovered:
        paper_id = row["paper_id"]
        current = deduped.get(paper_id)
        if current is None:
            deduped[paper_id] = row
            continue
        if current["layout_type"] == "flat" and row["layout_type"] == "category":
            warnings.append(f"{paper_id}:duplicate_flat_and_category_prefer_category")
            deduped[paper_id] = row
        elif current["layout_type"] == "category" and row["layout_type"] == "flat":
            warnings.append(f"{paper_id}:duplicate_flat_and_category_prefer_category")
        else:
            warnings.append(f"{row['qualified_paper_id']}:duplicate_paper_id")

    rows = sorted(deduped.values(), key=lambda item: (item.get("paper_category") or "uncategorized", item["paper_id"]))
    for row in rows:
        if warnings:
            row.setdefault("discovery_warnings", [])
    if warnings and rows:
        rows[0]["discovery_warnings"] = warnings
    return rows


def _add_discovered_paper(
    rows: list[dict[str, Any]],
    paper_dir: Path,
    *,
    category: str | None,
    normalized_filters: set[str],
) -> None:
    paper_id = paper_dir.name
    qualified = f"{category}/{paper_id}" if category else paper_id
    if normalized_filters and not _matches_paper_filters(normalized_filters, category, paper_id):
        return
    final_dataset_dir = paper_dir / "final_dataset"
    export_dir = final_dataset_dir / "link_aware_exports"
    paper_identity = resolve_paper_identity_from_dir(paper_dir)
    file_presence = {
        **{name: (export_dir / rel_path).exists() for name, rel_path in REQUIRED_EXPORT_FILES.items()},
        **{name: (export_dir / rel_path).exists() for name, rel_path in OPTIONAL_EXPORT_FILES.items()},
    }
    required_present = all(file_presence[name] for name in REQUIRED_EXPORT_FILES)
    rows.append(
        {
            "category": paper_identity.get("paper_category") or "",
            "paper_category": paper_identity.get("paper_category") or "",
            "paper_category_status": paper_identity.get("paper_category_status"),
            "paper_id": paper_id,
            "qualified_paper_id": qualified,
            "paper_dir": paper_dir,
            "paper_identity": paper_identity,
            "final_dataset_dir": final_dataset_dir,
            "export_dir": export_dir,
            "layout_type": "category" if category else "flat",
            "has_link_aware_exports": export_dir.exists() and required_present,
            "file_presence": file_presence,
        }
    )


def _read_existing_export_payload(item: dict[str, Any]) -> dict[str, Any]:
    paper_id = item["paper_id"]
    export_dir = item["export_dir"]
    paper_identity = dict(item.get("paper_identity") or {})
    summary = read_json(export_dir / "link_aware_export_summary.json", default={}) or {}
    return {
        "paper_id": paper_id,
        "paper_identity": paper_identity,
        "summary": summary,
        "final_parameters_linked": _read_csv_rows(export_dir / "final_parameters_linked.csv", paper_id, paper_identity),
        "sample_parameter_matrix": _read_csv_rows(export_dir / "sample_parameter_matrix.csv", paper_id, paper_identity),
        "evidence_parameter_links": _read_csv_rows(export_dir / "evidence_parameter_links.csv", paper_id, paper_identity),
        "process_step_parameter_links": _read_csv_rows(export_dir / "process_step_parameter_links.csv", paper_id, paper_identity),
        "spectra_parameter_links": _read_csv_rows(export_dir / "spectra_parameter_links.csv", paper_id, paper_identity),
        "process_steps_table": _read_csv_rows(export_dir / "process_steps_table.csv", paper_id, paper_identity),
        "final_showcase_table": _read_csv_rows(export_dir / "final_showcase_table.csv", paper_id, paper_identity),
        "excluded_parameters": _read_csv_rows(export_dir / "excluded_parameters.csv", paper_id, paper_identity),
        "parameter_semantic_qa": _read_csv_rows(export_dir / "parameter_semantic_qa.csv", paper_id, paper_identity),
    }


def _matches_paper_filters(normalized_filters: set[str], category: str | None, paper_id: str) -> bool:
    selectors = {
        _normalize_paper_selector(paper_id),
        _normalize_paper_selector(f"{category}/{paper_id}") if category else None,
    }
    selectors.discard(None)
    return any(selector in normalized_filters for selector in selectors)


def _normalize_paper_selector(value: str) -> str:
    return str(value).replace("\\", "/").strip()


def _is_paper_dir(path: Path) -> bool:
    return (path / "final_dataset").exists()


def _looks_like_category_dir(path: Path) -> bool:
    return not _is_ignored_dir(path.name)


def _is_ignored_dir(name: str) -> bool:
    return name.startswith(".") or name.startswith("_batch") or name.startswith("_")


def _can_rebuild_from_final_dataset(final_dataset_dir: Path) -> bool:
    return all((final_dataset_dir / rel_path).exists() for rel_path in REBUILD_REQUIRED_FILES)


def _read_csv_rows(path: Path, paper_id: str, paper_identity: dict[str, Any]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            payload = dict(row)
            payload.setdefault("paper_id", paper_id)
            payload.setdefault("paper_category", paper_identity.get("paper_category") or "")
            payload.setdefault("paper_category_status", paper_identity.get("paper_category_status") or "")
            payload.setdefault("paper_dir", paper_identity.get("paper_dir") or "")
            if not payload.get("category"):
                payload["category"] = payload.get("paper_category") or ""
            rows.append(payload)
    return rows


def _collect_dynamic_sample_matrix_keys(rows: list[dict[str, Any]]) -> list[str]:
    reserved = set(SAMPLE_PARAMETER_MATRIX_FIELDS)
    dynamic: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if not key or key in reserved or key in seen:
                continue
            seen.add(key)
            dynamic.append(key)
    return dynamic


def _write_csv_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _write_csv_with_dynamic_fields(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)
    _write_csv_with_fields(path, rows, fieldnames)


def _count_missing_identity_rows(aggregate_rows: dict[str, list[dict[str, Any]]]) -> int:
    count = 0
    for table_name, rows in aggregate_rows.items():
        if table_name == "showcase":
            continue
        for row in rows:
            if not row.get("paper_id") or ("paper_category" in row and row.get("paper_category_status") == "official" and not row.get("paper_category")):
                count += 1
    return count


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
        f"- rebuilt_papers: {summary['rebuilt_paper_count']}",
        f"- reused_existing_export_count: {summary['reused_existing_export_count']}",
        f"- official_paper_count: {summary['official_paper_count']}",
        f"- non_primary_paper_count: {summary['non_primary_paper_count']}",
        f"- missing_identity_row_count: {summary['missing_identity_row_count']}",
        f"- flat_papers: {summary['exported_flat_paper_count']}",
        f"- categorized_papers: {summary['exported_category_paper_count']}",
        f"- total_parameters: {summary['total_parameters']}",
        f"- excluded_parameter_count: {summary['excluded_parameter_count']}",
        f"- metadata_or_bookkeeping_count: {summary['metadata_or_bookkeeping_count']}",
        f"- characterization_output_parameter_count: {summary['characterization_output_parameter_count']}",
        f"- parameters_with_any_link: {summary['parameters_with_any_link']}",
        f"- parameters_with_sample_link: {summary['parameters_with_sample_link']}",
        f"- parameters_with_evidence_link: {summary['parameters_with_evidence_link']}",
        f"- parameters_with_spectra_link: {summary['parameters_with_spectra_link']}",
        f"- parameters_missing_all_links: {summary['parameters_missing_all_links']}",
        f"- total_evidence_parameter_links: {summary['total_evidence_parameter_links']}",
        f"- total_process_step_parameter_links: {summary['total_process_step_parameter_links']}",
        f"- total_spectra_parameter_links: {summary['total_spectra_parameter_links']}",
        f"- total_samples: {summary['total_samples']}",
        f"- sample_matrix_rows: {summary['sample_matrix_rows']}",
        f"- process_steps_table_rows: {summary['process_steps_table_rows']}",
        f"- missing_required_file_count: {summary['missing_required_file_count']}",
        f"- missing_optional_file_count: {summary['missing_optional_file_count']}",
        "",
        "## By Category",
    ]
    if summary["by_category"]:
        for category, payload in sorted(summary["by_category"].items()):
            lines.append(
                f"- {category}: papers={payload['paper_count']}, parameters={payload['total_parameters']}, "
                f"excluded={payload['excluded_parameters']}, metadata={payload['metadata_or_bookkeeping_count']}, "
                f"characterization={payload['characterization_output_parameter_count']}, "
                f"evidence_links={payload['total_evidence_parameter_links']}, "
                f"process_step_links={payload['total_process_step_parameter_links']}, "
                f"spectra_links={payload['total_spectra_parameter_links']}, sample_matrix_rows={payload['sample_matrix_rows']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings"])
    if summary["warnings"]:
        lines.extend([f"- {item}" for item in summary["warnings"]])
    else:
        lines.append("- none")
    lines.extend(["", "## Per Paper"])
    for row in summary["per_paper"]:
        lines.extend(
            [
                "",
                f"### {row['qualified_paper_id']}",
                f"- paper_category: {row.get('paper_category', '')}",
                f"- paper_category_status: {row.get('paper_category_status', '')}",
                f"- total_parameters: {row.get('total_parameters', 0)}",
                f"- excluded_parameter_count: {row.get('excluded_parameter_count', 0)}",
                f"- parameters_with_any_link: {row.get('parameters_with_any_link', 0)}",
                f"- parameters_with_sample_link: {row.get('parameters_with_sample_link', 0)}",
                f"- parameters_with_evidence_link: {row.get('parameters_with_evidence_link', 0)}",
                f"- parameters_with_spectra_link: {row.get('parameters_with_spectra_link', 0)}",
                f"- process_step_parameter_links: {row.get('process_step_parameter_links', 0)}",
                f"- showcase_rows: {row.get('showcase_rows', 0)}",
            ]
        )
    return "\n".join(lines)
