"""Link-aware final dataset exports built from Stage 5 and Stage 5.5 outputs."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.exporters import write_json, write_markdown
from alumina_sol_extractor.dataset_fusion.loaders import read_json, read_jsonl
from alumina_sol_extractor.ontology.ontology_loader import get_ontology_entry_map

CORE_SAMPLE_MATRIX_KEYS = [
    "aluminum_source",
    "peptizing_agent",
    "pH",
    "hydrolysis_temperature_C",
    "hydrolysis_time_h",
    "peptization_temperature_C",
    "peptization_time_h",
    "concentration_temperature_C",
    "concentration_time_h",
    "spinning_channel_temperature_C",
    "spinneret_hole_diameter_mm",
    "take_up_speed_m_min",
    "drying_temperature_C",
    "calcination_temperature_C",
    "sintering_temperature_C",
    "holding_time_h",
    "average_fiber_diameter_um",
    "tensile_strength_MPa",
    "Al13_fraction_percent",
    "nmr_27Al_peak_position_ppm",
    "ftir_peak_position_cm_1",
    "xrd_peak_position_2theta_deg",
]

FINAL_PARAMETERS_LINKED_FIELDS = [
    "paper_id",
    "title",
    "parameter_id",
    "canonical_key",
    "zh_name",
    "en_name",
    "category",
    "sample_id_original",
    "linked_sample_ids",
    "resolved_sample_id",
    "sample_resolution_source",
    "value_raw",
    "value_num",
    "value_text",
    "unit",
    "value_type",
    "source_scope",
    "evidence_refs_original",
    "linked_evidence_ids",
    "linked_figure_ids",
    "linked_spectra_ids",
    "linked_peak_positions",
    "link_types",
    "link_confidences",
    "link_reasoning_preview",
    "evidence_text_preview",
    "link_count",
    "strong_link_count",
    "weak_link_count",
    "evidence_status",
    "quality_flags",
    "normalization_note",
]

SAMPLE_PARAMETER_MATRIX_FIELDS = [
    "paper_id",
    "title",
    "sample_id",
    "sample_name",
    "material_system",
    "process_route",
    "parameter_count",
    "linked_parameter_count",
    "evidence_count",
    "spectra_count",
    *CORE_SAMPLE_MATRIX_KEYS,
    "multi_value_flags",
]

EVIDENCE_PARAMETER_LINK_FIELDS = [
    "paper_id",
    "evidence_id",
    "evidence_type",
    "figure_id",
    "table_id",
    "figure_type",
    "caption",
    "evidence_text_preview",
    "parameter_id",
    "canonical_key",
    "parameter_value",
    "unit",
    "sample_id",
    "link_type",
    "confidence",
    "reasoning",
    "created_by",
    "validation_status",
]

SPECTRA_PARAMETER_LINK_FIELDS = [
    "paper_id",
    "spectra_id",
    "figure_id",
    "figure_type",
    "technique",
    "peak_position",
    "peak_unit",
    "assignment",
    "source",
    "parameter_id",
    "canonical_key",
    "parameter_value",
    "unit",
    "sample_id",
    "link_type",
    "confidence",
    "reasoning",
    "created_by",
]

FINAL_SHOWCASE_FIELDS = [
    "paper_short",
    "sample",
    "parameter_zh",
    "canonical_key",
    "value_display",
    "evidence_display",
    "spectra_display",
    "link_status",
    "confidence",
    "note",
]


def load_link_aware_inputs(final_dataset_dir: Path | str) -> dict[str, Any]:
    final_dataset_dir = Path(final_dataset_dir)
    linking_dir = final_dataset_dir / "linking"
    return {
        "final_dataset_dir": final_dataset_dir,
        "paper": read_json(final_dataset_dir / "paper.json", default={}) or {},
        "samples": read_jsonl(final_dataset_dir / "samples.jsonl"),
        "parameters": read_jsonl(final_dataset_dir / "parameters.jsonl"),
        "evidence": read_jsonl(final_dataset_dir / "evidence.jsonl"),
        "spectra": read_jsonl(final_dataset_dir / "spectra.jsonl"),
        "figures": read_jsonl(final_dataset_dir / "figures.jsonl"),
        "quality_summary": read_json(final_dataset_dir / "quality_summary.json", default={}) or {},
        "links": read_jsonl(linking_dir / "links.jsonl"),
        "linking_summary": read_json(linking_dir / "linking_summary.json", default={}) or {},
        "link_candidates": read_jsonl(linking_dir / "link_candidates.jsonl"),
    }


def generate_link_aware_exports(
    final_dataset_dir: Path | str,
    *,
    output_dir: Path | str | None = None,
    paper_id: str | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    inputs = load_link_aware_inputs(final_dataset_dir)
    ontology_map = get_ontology_entry_map(project_root)
    paper = inputs["paper"]
    paper_id = paper_id or paper.get("paper_id") or Path(final_dataset_dir).parent.name
    title = paper.get("title") or paper_id
    output_dir = Path(output_dir) if output_dir else Path(final_dataset_dir) / "link_aware_exports"

    parameters = inputs["parameters"]
    evidence = inputs["evidence"]
    spectra = inputs["spectra"]
    samples = inputs["samples"]
    links = inputs["links"]

    indexes = _build_indexes(parameters, evidence, spectra, samples, links)
    evidence_parameter_links = _build_evidence_parameter_links(
        paper_id=paper_id,
        parameters=parameters,
        evidence=evidence,
        links=links,
        indexes=indexes,
    )
    spectra_parameter_links = _build_spectra_parameter_links(
        paper_id=paper_id,
        parameters=parameters,
        evidence_parameter_links=evidence_parameter_links,
        spectra=spectra,
        links=links,
        indexes=indexes,
    )
    final_parameters_linked = _build_final_parameters_linked(
        paper_id=paper_id,
        title=title,
        paper=paper,
        parameters=parameters,
        evidence=evidence,
        spectra=spectra,
        links=links,
        ontology_map=ontology_map,
        indexes=indexes,
        evidence_parameter_links=evidence_parameter_links,
        spectra_parameter_links=spectra_parameter_links,
    )
    sample_parameter_matrix = _build_sample_parameter_matrix(
        paper_id=paper_id,
        title=title,
        paper=paper,
        samples=samples,
        final_parameters_linked=final_parameters_linked,
    )
    final_showcase_table = _build_final_showcase_table(
        paper_id=paper_id,
        title=title,
        final_parameters_linked=final_parameters_linked,
        samples=samples,
    )
    summary = _build_link_aware_summary(
        final_parameters_linked=final_parameters_linked,
        evidence_parameter_links=evidence_parameter_links,
        spectra_parameter_links=spectra_parameter_links,
        samples=samples,
        showcase_rows=final_showcase_table,
    )
    readme = _build_link_aware_readme()

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv_with_fields(output_dir / "final_parameters_linked.csv", final_parameters_linked, FINAL_PARAMETERS_LINKED_FIELDS)
    _write_parquet_with_fields(
        output_dir / "final_parameters_linked.parquet",
        final_parameters_linked,
        FINAL_PARAMETERS_LINKED_FIELDS,
    )
    _write_csv_with_fields(output_dir / "sample_parameter_matrix.csv", sample_parameter_matrix, SAMPLE_PARAMETER_MATRIX_FIELDS)
    _write_csv_with_fields(
        output_dir / "evidence_parameter_links.csv",
        evidence_parameter_links,
        EVIDENCE_PARAMETER_LINK_FIELDS,
    )
    _write_csv_with_fields(
        output_dir / "spectra_parameter_links.csv",
        spectra_parameter_links,
        SPECTRA_PARAMETER_LINK_FIELDS,
    )
    _write_csv_with_fields(output_dir / "final_showcase_table.csv", final_showcase_table, FINAL_SHOWCASE_FIELDS)
    write_json(output_dir / "link_aware_export_summary.json", summary)
    write_markdown(output_dir / "link_aware_export_readme.md", readme)

    return {
        "paper_id": paper_id,
        "title": title,
        "output_dir": str(output_dir),
        "summary": summary,
        "final_parameters_linked": final_parameters_linked,
        "sample_parameter_matrix": sample_parameter_matrix,
        "evidence_parameter_links": evidence_parameter_links,
        "spectra_parameter_links": spectra_parameter_links,
        "final_showcase_table": final_showcase_table,
    }


def _build_indexes(
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_by_id = {row.get("evidence_id"): row for row in evidence if row.get("evidence_id")}
    evidence_by_figure = defaultdict(list)
    for row in evidence:
        if row.get("figure_id"):
            evidence_by_figure[row["figure_id"]].append(row)
    spectra_by_id = {}
    spectra_by_figure = {}
    for row in spectra:
        figure_id = row.get("figure_id")
        spectra_id = _spectra_id_for_figure(figure_id) if figure_id else None
        if spectra_id:
            spectra_by_id[spectra_id] = row
        if figure_id:
            spectra_by_figure[figure_id] = row
    samples_by_id = {row.get("sample_id"): row for row in samples if row.get("sample_id")}
    parameters_by_id = {row.get("parameter_id"): row for row in parameters if row.get("parameter_id")}
    links_by_parameter = defaultdict(list)
    links_by_evidence = defaultdict(list)
    links_by_sample = defaultdict(list)
    links_by_spectra = defaultdict(list)
    for link in links:
        for kind, key, bucket in (
            ("parameter", link.get("source_id") if link.get("source_type") == "parameter" else None, links_by_parameter),
            ("parameter", link.get("target_id") if link.get("target_type") == "parameter" else None, links_by_parameter),
            ("evidence_object", link.get("source_id") if link.get("source_type") == "evidence_object" else None, links_by_evidence),
            ("evidence_object", link.get("target_id") if link.get("target_type") == "evidence_object" else None, links_by_evidence),
            ("sample", link.get("source_id") if link.get("source_type") == "sample" else None, links_by_sample),
            ("sample", link.get("target_id") if link.get("target_type") == "sample" else None, links_by_sample),
            ("spectra_record", link.get("source_id") if link.get("source_type") == "spectra_record" else None, links_by_spectra),
            ("spectra_record", link.get("target_id") if link.get("target_type") == "spectra_record" else None, links_by_spectra),
        ):
            if key:
                bucket[key].append(link)
        if link.get("source_type") == "spectra_peak" and link.get("source_id"):
            links_by_spectra[link["source_id"]].append(link)
    return {
        "evidence_by_id": evidence_by_id,
        "evidence_by_figure": evidence_by_figure,
        "spectra_by_id": spectra_by_id,
        "spectra_by_figure": spectra_by_figure,
        "samples_by_id": samples_by_id,
        "parameters_by_id": parameters_by_id,
        "links_by_parameter": links_by_parameter,
        "links_by_evidence": links_by_evidence,
        "links_by_sample": links_by_sample,
        "links_by_spectra": links_by_spectra,
    }


def _build_final_parameters_linked(
    *,
    paper_id: str,
    title: str,
    paper: dict[str, Any],
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    links: list[dict[str, Any]],
    ontology_map: dict[str, dict[str, Any]],
    indexes: dict[str, Any],
    evidence_parameter_links: list[dict[str, Any]],
    spectra_parameter_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_link_rows_by_parameter = defaultdict(list)
    for row in evidence_parameter_links:
        evidence_link_rows_by_parameter[row.get("parameter_id")].append(row)
    spectra_link_rows_by_parameter = defaultdict(list)
    for row in spectra_parameter_links:
        spectra_link_rows_by_parameter[row.get("parameter_id")].append(row)

    rows: list[dict[str, Any]] = []
    for parameter in parameters:
        parameter_id = parameter.get("parameter_id")
        canonical_key = parameter.get("canonical_key")
        ontology_entry = ontology_map.get(str(canonical_key), {}) if canonical_key else {}
        parameter_links = indexes["links_by_parameter"].get(parameter_id, [])
        sample_links = [
            link
            for link in parameter_links
            if {link.get("source_type"), link.get("target_type")} == {"parameter", "sample"}
        ]
        linked_sample_ids = _sorted_unique(
            [
                link.get("target_id") if link.get("target_type") == "sample" else link.get("source_id")
                for link in sample_links
            ]
        )
        sample_id_original = parameter.get("sample_id")
        resolved_sample_id, resolution_source = _resolve_sample_id(sample_id_original, sample_links)

        explicit_evidence_ids = _extract_explicit_evidence_ids(
            parameter.get("evidence_refs"),
            indexes["evidence_by_id"],
            indexes["evidence_by_figure"],
        )
        evidence_rows = evidence_link_rows_by_parameter.get(parameter_id, [])
        spectra_rows = spectra_link_rows_by_parameter.get(parameter_id, [])
        linked_evidence_ids = _sorted_unique(explicit_evidence_ids + [row.get("evidence_id") for row in evidence_rows])
        linked_figure_ids = _sorted_unique(
            _coerce_str_list(parameter.get("linked_figure_ids"))
            + [row.get("figure_id") for row in evidence_rows]
            + [row.get("figure_id") for row in spectra_rows]
        )
        linked_spectra_ids = _sorted_unique(
            _coerce_str_list(parameter.get("linked_spectra_ids"))
            + [row.get("spectra_id") for row in spectra_rows]
        )
        linked_peak_positions = _sorted_unique([_stringify(row.get("peak_position")) for row in spectra_rows if row.get("peak_position") is not None])
        link_types = _sorted_unique([link.get("link_type") for link in parameter_links])
        link_confidences = _sorted_unique([link.get("confidence") for link in parameter_links])
        link_reasoning_preview = _sorted_unique(
            [_truncate(str(link.get("reasoning") or ""), 120) for link in parameter_links if link.get("reasoning")]
        )
        evidence_text_preview = _sorted_unique([row.get("evidence_text_preview") for row in evidence_rows if row.get("evidence_text_preview")])

        value_meta = _normalize_parameter_value(parameter.get("value"), parameter.get("unit"))
        evidence_status = _resolve_evidence_status(explicit_evidence_ids, evidence_rows, spectra_rows, linked_sample_ids)
        quality_flags = list(parameter.get("quality_flags") or [])
        if len(linked_sample_ids) > 1:
            quality_flags.append("multiple_sample_links")

        strong_link_count = sum(
            1
            for link in parameter_links
            if (link.get("confidence") in {"high", "medium"} and link.get("link_type") != "weak_supports")
        ) + len([row for row in evidence_rows if row.get("created_by") == "direct_evidence_refs"])
        weak_link_count = sum(
            1
            for link in parameter_links
            if link.get("confidence") == "low" or link.get("link_type") == "weak_supports"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "parameter_id": parameter_id,
                "canonical_key": canonical_key,
                "zh_name": ontology_entry.get("zh_name") or canonical_key,
                "en_name": ontology_entry.get("en_name") or canonical_key,
                "category": ontology_entry.get("category"),
                "sample_id_original": sample_id_original,
                "linked_sample_ids": "; ".join(linked_sample_ids),
                "resolved_sample_id": resolved_sample_id,
                "sample_resolution_source": resolution_source,
                "value_raw": value_meta["value_raw"],
                "value_num": value_meta["value_num"],
                "value_text": value_meta["value_text"],
                "unit": value_meta["unit"],
                "value_type": value_meta["value_type"],
                "source_scope": parameter.get("source_scope"),
                "evidence_refs_original": _json_or_none(parameter.get("evidence_refs")),
                "linked_evidence_ids": "; ".join(linked_evidence_ids),
                "linked_figure_ids": "; ".join(linked_figure_ids),
                "linked_spectra_ids": "; ".join(linked_spectra_ids),
                "linked_peak_positions": "; ".join(linked_peak_positions),
                "link_types": "; ".join(link_types),
                "link_confidences": "; ".join(link_confidences),
                "link_reasoning_preview": " | ".join(link_reasoning_preview),
                "evidence_text_preview": " | ".join(evidence_text_preview),
                "link_count": len(parameter_links) + len(explicit_evidence_ids),
                "strong_link_count": strong_link_count,
                "weak_link_count": weak_link_count,
                "evidence_status": evidence_status,
                "quality_flags": "; ".join(_sorted_unique(quality_flags)),
                "normalization_note": parameter.get("normalization_note"),
            }
        )
    return rows


def _build_sample_parameter_matrix(
    *,
    paper_id: str,
    title: str,
    paper: dict[str, Any],
    samples: list[dict[str, Any]],
    final_parameters_linked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    parameters_by_sample = defaultdict(list)
    for row in final_parameters_linked:
        if row.get("resolved_sample_id"):
            parameters_by_sample[row["resolved_sample_id"]].append(row)
    for sample in samples:
        sample_id = sample.get("sample_id")
        sample_parameters = parameters_by_sample.get(sample_id, [])
        row: dict[str, Any] = {
            "paper_id": paper_id,
            "title": title,
            "sample_id": sample_id,
            "sample_name": sample.get("sample_name"),
            "material_system": paper.get("material_system"),
            "process_route": paper.get("process_route"),
            "parameter_count": len(sample.get("linked_parameters") or []),
            "linked_parameter_count": len(sample_parameters),
            "evidence_count": len(
                _sorted_unique(
                    [
                        evidence_id
                        for item in sample_parameters
                        for evidence_id in str(item.get("linked_evidence_ids") or "").split("; ")
                        if evidence_id
                    ]
                )
            ),
            "spectra_count": len(
                _sorted_unique(
                    [
                        spectra_id
                        for item in sample_parameters
                        for spectra_id in str(item.get("linked_spectra_ids") or "").split("; ")
                        if spectra_id
                    ]
                )
            ),
        }
        multi_value_keys: list[str] = []
        for canonical_key in CORE_SAMPLE_MATRIX_KEYS:
            values = [_display_value(item) for item in sample_parameters if item.get("canonical_key") == canonical_key and _display_value(item)]
            unique_values = _sorted_unique(values)
            if len(unique_values) > 1:
                multi_value_keys.append(canonical_key)
            row[canonical_key] = "; ".join(unique_values)
        row["multi_value_flags"] = "; ".join(multi_value_keys)
        rows.append(row)
    return rows


def _build_evidence_parameter_links(
    *,
    paper_id: str,
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    links: list[dict[str, Any]],
    indexes: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_id = indexes["evidence_by_id"]
    parameter_by_id = indexes["parameters_by_id"]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_row(
        evidence_row: dict[str, Any],
        parameter_row: dict[str, Any],
        *,
        link_type: str,
        confidence: str,
        reasoning: str | None,
        created_by: str,
        validation_status: str = "accepted",
    ) -> None:
        key = (str(evidence_row.get("evidence_id")), str(parameter_row.get("parameter_id")))
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "paper_id": paper_id,
                "evidence_id": evidence_row.get("evidence_id"),
                "evidence_type": evidence_row.get("evidence_type"),
                "figure_id": evidence_row.get("figure_id"),
                "table_id": evidence_row.get("table_id"),
                "figure_type": evidence_row.get("figure_type"),
                "caption": evidence_row.get("caption"),
                "evidence_text_preview": _evidence_preview(evidence_row, limit=120),
                "parameter_id": parameter_row.get("parameter_id"),
                "canonical_key": parameter_row.get("canonical_key"),
                "parameter_value": parameter_row.get("value"),
                "unit": None if parameter_row.get("unit") == "text" else parameter_row.get("unit"),
                "sample_id": parameter_row.get("sample_id"),
                "link_type": link_type,
                "confidence": confidence,
                "reasoning": reasoning,
                "created_by": created_by,
                "validation_status": validation_status,
            }
        )

    for link in links:
        source_type = link.get("source_type")
        target_type = link.get("target_type")
        if {source_type, target_type} != {"evidence_object", "parameter"}:
            continue
        evidence_id = link.get("source_id") if source_type == "evidence_object" else link.get("target_id")
        parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
        evidence_row = evidence_by_id.get(evidence_id)
        parameter_row = parameter_by_id.get(parameter_id)
        if evidence_row and parameter_row:
            add_row(
                evidence_row,
                parameter_row,
                link_type=link.get("link_type") or "supports",
                confidence=link.get("confidence") or "medium",
                reasoning=link.get("reasoning"),
                created_by=link.get("created_by") or "llm",
                validation_status=link.get("validation_status") or "accepted",
            )

    evidence_by_figure = indexes["evidence_by_figure"]
    for parameter_row in parameters:
        explicit_ids = _extract_explicit_evidence_ids(parameter_row.get("evidence_refs"), evidence_by_id, evidence_by_figure)
        for evidence_id in explicit_ids:
            evidence_row = evidence_by_id.get(evidence_id)
            if evidence_row:
                add_row(
                    evidence_row,
                    parameter_row,
                    link_type="supports",
                    confidence="high",
                    reasoning="parameter.evidence_refs contains evidence reference",
                    created_by="direct_evidence_refs",
                )

    return rows


def _build_spectra_parameter_links(
    *,
    paper_id: str,
    parameters: list[dict[str, Any]],
    evidence_parameter_links: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    links: list[dict[str, Any]],
    indexes: dict[str, Any],
) -> list[dict[str, Any]]:
    parameter_by_id = indexes["parameters_by_id"]
    spectra_by_id = indexes["spectra_by_id"]
    evidence_by_id = indexes["evidence_by_id"]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_row(
        *,
        spectra_id: str,
        figure_id: str | None,
        figure_type: str | None,
        technique: str | None,
        peak_position: Any,
        peak_unit: str | None,
        assignment: str | None,
        source: str | None,
        parameter_id: str,
        canonical_key: str | None,
        parameter_value: Any,
        unit: str | None,
        sample_id: str | None,
        link_type: str,
        confidence: str,
        reasoning: str | None,
        created_by: str,
    ) -> None:
        key = (spectra_id, parameter_id, f"{peak_position}|{link_type}")
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "paper_id": paper_id,
                "spectra_id": spectra_id,
                "figure_id": figure_id,
                "figure_type": figure_type,
                "technique": technique,
                "peak_position": peak_position,
                "peak_unit": peak_unit,
                "assignment": assignment,
                "source": source,
                "parameter_id": parameter_id,
                "canonical_key": canonical_key,
                "parameter_value": parameter_value,
                "unit": None if unit == "text" else unit,
                "sample_id": sample_id,
                "link_type": link_type,
                "confidence": confidence,
                "reasoning": reasoning,
                "created_by": created_by,
            }
        )

    for link in links:
        source_type = link.get("source_type")
        target_type = link.get("target_type")
        if {source_type, target_type} != {"spectra_peak", "parameter"}:
            continue
        spectra_peak_id = link.get("source_id") if source_type == "spectra_peak" else link.get("target_id")
        parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
        peak_info = _parse_peak_source_id(spectra_peak_id)
        parameter_row = parameter_by_id.get(parameter_id)
        spectra_row = spectra_by_id.get(peak_info["spectra_id"]) if peak_info else None
        peak = _get_peak_by_index(spectra_row, peak_info["peak_index"]) if spectra_row and peak_info else None
        if not (parameter_row and spectra_row and peak):
            continue
        add_row(
            spectra_id=peak_info["spectra_id"],
            figure_id=spectra_row.get("figure_id"),
            figure_type=spectra_row.get("figure_type"),
            technique=spectra_row.get("technique"),
            peak_position=peak.get("position"),
            peak_unit=peak.get("unit"),
            assignment=peak.get("assignment"),
            source=peak.get("source"),
            parameter_id=parameter_id,
            canonical_key=parameter_row.get("canonical_key"),
            parameter_value=parameter_row.get("value"),
            unit=parameter_row.get("unit"),
            sample_id=parameter_row.get("sample_id"),
            link_type=link.get("link_type") or "supports",
            confidence=link.get("confidence") or "medium",
            reasoning=link.get("reasoning"),
            created_by=link.get("created_by") or "deterministic",
        )

    same_figure_links = {
        link.get("target_id"): link
        for link in links
        if link.get("source_type") == "spectra_record"
        and link.get("target_type") == "evidence_object"
        and link.get("link_type") == "same_figure"
    }
    evidence_parameter_by_evidence = defaultdict(list)
    for row in evidence_parameter_links:
        evidence_parameter_by_evidence[row.get("evidence_id")].append(row)
    for evidence_id, evidence_links in evidence_parameter_by_evidence.items():
        same_figure_link = same_figure_links.get(evidence_id)
        if not same_figure_link:
            continue
        spectra_id = same_figure_link.get("source_id")
        spectra_row = spectra_by_id.get(spectra_id)
        if not spectra_row:
            continue
        all_positions = "; ".join(_sorted_unique([_stringify(peak.get("position")) for peak in spectra_row.get("peaks", []) if peak.get("position") is not None]))
        all_units = "; ".join(_sorted_unique([peak.get("unit") for peak in spectra_row.get("peaks", []) if peak.get("unit")]))
        all_assignments = "; ".join(_sorted_unique([peak.get("assignment") for peak in spectra_row.get("peaks", []) if peak.get("assignment")]))
        all_sources = "; ".join(_sorted_unique([peak.get("source") for peak in spectra_row.get("peaks", []) if peak.get("source")]))
        for row in evidence_links:
            parameter_row = parameter_by_id.get(row.get("parameter_id"))
            if not parameter_row:
                continue
            add_row(
                spectra_id=spectra_id,
                figure_id=spectra_row.get("figure_id"),
                figure_type=spectra_row.get("figure_type"),
                technique=spectra_row.get("technique"),
                peak_position=all_positions or None,
                peak_unit=all_units or None,
                assignment=all_assignments or None,
                source=all_sources or None,
                parameter_id=row.get("parameter_id"),
                canonical_key=parameter_row.get("canonical_key"),
                parameter_value=parameter_row.get("value"),
                unit=parameter_row.get("unit"),
                sample_id=parameter_row.get("sample_id"),
                link_type="indirect_spectra_evidence_parameter",
                confidence=row.get("confidence") or "medium",
                reasoning=f"same_figure + evidence link: {row.get('reasoning') or ''}".strip(),
                created_by="indirect",
            )
    return rows


def _build_final_showcase_table(
    *,
    paper_id: str,
    title: str,
    final_parameters_linked: list[dict[str, Any]],
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sample_names = {row.get("sample_id"): row.get("sample_name") for row in samples if row.get("sample_id")}
    priority = {
        "strong_evidence": 0,
        "linked_evidence": 1,
        "linked_spectra": 2,
        "sample_link_only": 3,
        "missing": 4,
    }
    role_priority = {
        "aluminum_source": 0,
        "peptizing_agent": 1,
        "Al_to_nitrate_molar_ratio": 2,
        "pH": 3,
        "nmr_27Al_peak_position_ppm": 4,
        "ftir_peak_position_cm_1": 5,
        "xrd_peak_position_2theta_deg": 6,
        "Al13_fraction_percent": 7,
        "tensile_strength_MPa": 8,
    }
    ranked = sorted(
        final_parameters_linked,
        key=lambda row: (
            priority.get(row.get("evidence_status"), 9),
            role_priority.get(row.get("canonical_key"), 99),
            row.get("canonical_key") or "",
        ),
    )
    rows: list[dict[str, Any]] = []
    for row in ranked:
        if len(rows) >= 30:
            break
        resolved_sample = row.get("resolved_sample_id")
        sample_display = sample_names.get(resolved_sample) or resolved_sample or "paper-level"
        evidence_display = row.get("linked_figure_ids") or row.get("linked_evidence_ids") or ""
        spectra_display = ""
        if row.get("linked_spectra_ids"):
            spectra_display = row.get("linked_spectra_ids")
            if row.get("linked_peak_positions"):
                spectra_display = f"{spectra_display} | {row.get('linked_peak_positions')}"
        link_status_map = {
            "strong_evidence": "evidence-linked",
            "linked_evidence": "evidence-linked",
            "linked_spectra": "spectra-linked",
            "sample_link_only": "sample-linked",
            "missing": "missing",
        }
        rows.append(
            {
                "paper_short": _truncate(title, 28),
                "sample": sample_display,
                "parameter_zh": row.get("zh_name") or row.get("canonical_key"),
                "canonical_key": row.get("canonical_key"),
                "value_display": _display_value(row),
                "evidence_display": evidence_display,
                "spectra_display": spectra_display,
                "link_status": link_status_map.get(row.get("evidence_status"), "missing"),
                "confidence": _showcase_confidence(row.get("link_confidences")),
                "note": row.get("quality_flags") or row.get("normalization_note") or "",
            }
        )
    return rows


def _build_link_aware_summary(
    *,
    final_parameters_linked: list[dict[str, Any]],
    evidence_parameter_links: list[dict[str, Any]],
    spectra_parameter_links: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    showcase_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "total_parameters": len(final_parameters_linked),
        "parameters_with_any_link": sum(
            1
            for row in final_parameters_linked
            if row.get("linked_sample_ids") or row.get("linked_evidence_ids") or row.get("linked_spectra_ids")
        ),
        "parameters_with_sample_link": sum(1 for row in final_parameters_linked if row.get("linked_sample_ids")),
        "parameters_with_evidence_link": sum(1 for row in final_parameters_linked if row.get("linked_evidence_ids")),
        "parameters_with_spectra_link": sum(1 for row in final_parameters_linked if row.get("linked_spectra_ids")),
        "parameters_missing_all_links": sum(
            1
            for row in final_parameters_linked
            if not row.get("linked_sample_ids") and not row.get("linked_evidence_ids") and not row.get("linked_spectra_ids")
        ),
        "total_evidence_parameter_links": len(evidence_parameter_links),
        "total_spectra_parameter_links": len(spectra_parameter_links),
        "total_samples": len(samples),
        "sample_matrix_rows": len(samples),
        "showcase_rows": len(showcase_rows),
        "warning_count": sum(
            1
            for row in final_parameters_linked
            if row.get("evidence_status") == "missing" or "multi" in str(row.get("quality_flags") or "")
        ),
    }


def _build_link_aware_readme() -> str:
    return """# Link-aware Final Dataset Exports

## Files
- `final_parameters_linked.csv`: parameter-long table enriched with sample/evidence/spectra links.
- `final_parameters_linked.parquet`: parquet version of the linked parameter table.
- `sample_parameter_matrix.csv`: sample-centric matrix for comparison and presentation.
- `evidence_parameter_links.csv`: evidence-to-parameter relationships.
- `spectra_parameter_links.csv`: spectra/peak-to-parameter relationships, including indirect spectra→evidence→parameter paths.
- `final_showcase_table.csv`: compact display table for meetings and quick review.
- `link_aware_export_summary.json`: export statistics.

## Notes
- Original `parameters.jsonl`, `evidence.jsonl`, `spectra.jsonl`, and `samples.jsonl` are not modified.
- Missing links are preserved as missing rather than fabricated.
- Sample resolution prefers direct `sample_id`, then accepted parameter→sample links.
"""


def _normalize_parameter_value(value: Any, unit: Any) -> dict[str, Any]:
    unit_text = _string_or_none(unit)
    value_raw = value
    value_num = None
    value_text = None
    value_type = "unknown"

    if unit_text == "text":
        value_text = _stringify(value)
        unit_text = None
        value_type = "text"
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        value_num = float(value)
        value_type = "numeric"
    elif isinstance(value, str):
        stripped = value.strip()
        range_match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[-~–]\s*(-?\d+(?:\.\d+)?)\s*$", stripped)
        if range_match:
            value_type = "range"
            return {
                "value_raw": value_raw,
                "value_num": None,
                "value_text": None,
                "value_min": float(range_match.group(1)),
                "value_max": float(range_match.group(2)),
                "unit": unit_text,
                "value_type": "range",
            }
        try:
            value_num = float(stripped)
            value_type = "numeric"
        except ValueError:
            value_text = stripped
            value_type = "text" if unit_text is None else "categorical"
    else:
        value_text = _stringify(value)
        value_type = "text" if value_text else "unknown"

    return {
        "value_raw": value_raw,
        "value_num": value_num,
        "value_text": value_text,
        "value_min": None,
        "value_max": None,
        "unit": unit_text,
        "value_type": value_type,
    }


def _resolve_sample_id(sample_id_original: Any, sample_links: list[dict[str, Any]]) -> tuple[str | None, str]:
    if sample_id_original:
        return str(sample_id_original), "direct_sample_id"
    for link in sample_links:
        if link.get("confidence") == "high":
            sample_id = link.get("target_id") if link.get("target_type") == "sample" else link.get("source_id")
            if sample_id:
                return str(sample_id), "parameter_sample_link"
    return None, "unresolved"


def _resolve_evidence_status(
    explicit_evidence_ids: list[str],
    evidence_rows: list[dict[str, Any]],
    spectra_rows: list[dict[str, Any]],
    linked_sample_ids: list[str],
) -> str:
    if explicit_evidence_ids:
        return "strong_evidence"
    if evidence_rows:
        return "linked_evidence"
    if spectra_rows:
        return "linked_spectra"
    if linked_sample_ids:
        return "sample_link_only"
    return "missing"


def _extract_explicit_evidence_ids(
    evidence_refs: Any,
    evidence_by_id: dict[str, dict[str, Any]],
    evidence_by_figure: dict[str, list[dict[str, Any]]],
) -> list[str]:
    resolved: list[str] = []
    for ref in evidence_refs or []:
        if isinstance(ref, str):
            if ref in evidence_by_id:
                resolved.append(ref)
            continue
        if not isinstance(ref, dict):
            continue
        for key in ("evidence_id", "source_id"):
            value = ref.get(key)
            if isinstance(value, str) and value in evidence_by_id:
                resolved.append(value)
        figure_id = ref.get("figure_id")
        if figure_id and figure_id in evidence_by_figure:
            resolved.extend(item.get("evidence_id") for item in evidence_by_figure[figure_id] if item.get("evidence_id"))
    return _sorted_unique(resolved)


def _parse_peak_source_id(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    match = re.match(r"^(spectra-.+)-peak-(\d+)$", str(source_id))
    if not match:
        return None
    return {"spectra_id": match.group(1), "peak_index": int(match.group(2))}


def _get_peak_by_index(spectra_row: dict[str, Any] | None, peak_index: int | None) -> dict[str, Any] | None:
    if not spectra_row or not peak_index:
        return None
    peaks = spectra_row.get("peaks") or []
    zero_index = peak_index - 1
    if 0 <= zero_index < len(peaks):
        peak = peaks[zero_index]
        return peak if isinstance(peak, dict) else None
    return None


def _spectra_id_for_figure(figure_id: Any) -> str | None:
    if not figure_id:
        return None
    return f"spectra-{figure_id}"


def _evidence_preview(evidence_row: dict[str, Any], *, limit: int = 80) -> str:
    text = (
        evidence_row.get("detailed_observation")
        or _join_text(evidence_row.get("fact_summary"))
        or evidence_row.get("caption")
        or ""
    )
    return _truncate(str(text), limit)


def _join_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if value is None:
        return ""
    return str(value)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value)]


def _sorted_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _string_or_none(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _json_or_none(value: Any) -> str | None:
    if value in (None, [], {}):
        return None
    return json.dumps(value, ensure_ascii=False)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _display_value(row: dict[str, Any]) -> str:
    if row.get("value_text"):
        return str(row["value_text"])
    if row.get("value_num") is not None:
        value = row["value_num"]
        unit = row.get("unit")
        if float(value).is_integer():
            text = str(int(value))
        else:
            text = str(value)
        return f"{text} {unit}".strip()
    if row.get("value_min") is not None and row.get("value_max") is not None:
        unit = row.get("unit") or ""
        return f"{row['value_min']}-{row['value_max']} {unit}".strip()
    return _stringify(row.get("value_raw"))


def _showcase_confidence(link_confidences: Any) -> str:
    text = _string_or_none(link_confidences) or ""
    for item in ("high", "medium", "low"):
        if item in text:
            return item
    return ""


def _write_csv_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _write_parquet_with_fields(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=fieldnames)
    for column in frame.columns:
        if str(frame[column].dtype) == "object":
            frame[column] = frame[column].apply(_parquet_value).astype("string")
    frame.to_parquet(path, index=False)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _parquet_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
