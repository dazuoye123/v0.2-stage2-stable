"""Markdown report generation for Stage 5 dataset fusion."""

from __future__ import annotations

import json
from typing import Any


def render_fusion_report(bundle: dict[str, Any]) -> str:
    presence = bundle["inputs"]["file_presence"]
    quality_summary = bundle["quality_summary"]
    weak_links = bundle.get("weak_links", [])
    ontology_gaps = bundle.get("ontology_gaps", [])
    rejected_parameters = bundle.get("rejected_parameters", [])
    spectra_warnings = [
        {
            "figure_id": item.get("figure_id"),
            "warning_codes": item.get("warning_codes", []),
            "assessment": item.get("quality_review_assessment"),
        }
        for item in bundle["spectra"]
        if item.get("warning_codes") or item.get("quality_review_assessment") == "usable_with_warning"
    ]
    parameters_without_evidence = [
        {
            "parameter_id": item.get("parameter_id"),
            "canonical_key": item.get("canonical_key"),
            "sample_id": item.get("sample_id"),
            "quality_flags": item.get("quality_flags", []),
        }
        for item in bundle["parameters"]
        if not item.get("linked_evidence_ids") and "weak_link_from_spectra" not in set(item.get("quality_flags", []))
    ]
    paper_level_parameters = [
        {
            "parameter_id": item.get("parameter_id"),
            "canonical_key": item.get("canonical_key"),
            "quality_flags": item.get("quality_flags", []),
        }
        for item in bundle["parameters"]
        if not item.get("linked_evidence_ids") and not item.get("sample_id")
    ]
    recommend_batch = (
        bool(quality_summary.get("stage3_schema_valid"))
        and quality_summary.get("stage4_overall_status") != "fail"
        and quality_summary.get("fusion_warning_count", 0) < max(10, len(bundle["parameters"]))
    )
    lines = [
        "# Stage 5 Fusion Report",
        "",
        "## Input Files",
        f"- Stage 3 presence: {json.dumps(presence['stage3'], ensure_ascii=False)}",
        f"- Stage 4 presence: {json.dumps(presence['stage4'], ensure_ascii=False)}",
        "",
        "## Fusion Counts",
        f"- parameters: {len(bundle['parameters'])}",
        f"- evidence: {len(bundle['evidence'])}",
        f"- spectra: {len(bundle['spectra'])}",
        f"- samples: {len(bundle['samples'])}",
        f"- rejected invalid canonical keys: {len(rejected_parameters)}",
        "",
        "## Parameters Without Strong Evidence",
        f"- count: {len(parameters_without_evidence)}",
    ]
    if parameters_without_evidence:
        for item in parameters_without_evidence[:10]:
            lines.append(
                f"- {item['parameter_id']}: canonical_key={item['canonical_key']} sample_id={item['sample_id']} flags={json.dumps(item['quality_flags'], ensure_ascii=False)}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Paper-level Parameters Without Direct Evidence",
            f"- count: {len(paper_level_parameters)}",
        ]
    )
    if paper_level_parameters:
        for item in paper_level_parameters[:10]:
            lines.append(
                f"- {item['parameter_id']}: canonical_key={item['canonical_key']} flags={json.dumps(item['quality_flags'], ensure_ascii=False)}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Spectra Warnings",
            f"- count: {len(spectra_warnings)}",
        ]
    )
    if spectra_warnings:
        for item in spectra_warnings[:10]:
            lines.append(
                f"- {item['figure_id']}: assessment={item['assessment']} warnings={json.dumps(item['warning_codes'], ensure_ascii=False)}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Weak Links", f"- count: {len(weak_links)}"])
    if weak_links:
        for item in weak_links[:10]:
            lines.append(
                f"- {item['parameter_id']}: canonical_key={item['canonical_key']} figure_id={item['figure_id']} reason={item['reason']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Invalid Canonical Keys", f"- count: {len(rejected_parameters)}"])
    if rejected_parameters:
        for item in rejected_parameters[:10]:
            lines.append(
                f"- {item.get('parameter_id')}: raw_name={item.get('raw_name')} canonical_key={item.get('canonical_key')} reason={item.get('reason')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Ontology Gaps", f"- count: {len(ontology_gaps)}"])
    if ontology_gaps:
        for item in ontology_gaps[:10]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Recommendation",
            f"- {'suggest_batch_processing' if recommend_batch else 'hold_for_manual_review'}",
            "",
        ]
    )
    return "\n".join(lines)
