"""Validation helpers for deterministic Stage 3 outputs."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord, ParameterRecord

from .normalization import collect_parameter_records


OntologyMap = dict[str, dict[str, Any]]


def validate_id_uniqueness(record: PaperExtractionRecord) -> list[dict[str, Any]]:
    """Find duplicate identifiers across top-level Stage 3 entities."""

    buckets: dict[str, list[str]] = {
        "paper_id": [record.paper_basic_info.paper_id] if record.paper_basic_info and record.paper_basic_info.paper_id else [],
        "series_id": [series.series_id for series in record.experiment_series if series.series_id],
        "sample_id": [dp.sample_id for series in record.experiment_series for dp in series.data_points if dp.sample_id],
        "figure_id": [obj.figure_id for obj in record.evidence_objects if obj.figure_id],
        "table_id": [ref.table_id for ref in _iter_evidence_refs(record) if getattr(ref, "table_id", None)],
        "link_id": [link.link_id for link in record.cross_modal_links if link.link_id],
    }
    issues: list[dict[str, Any]] = []
    for bucket_name, values in buckets.items():
        for value, count in Counter(values).items():
            if count > 1:
                issues.append({"type": "duplicate_id", "id_type": bucket_name, "id_value": value, "count": count})
    return issues


def validate_evidence_refs(record: PaperExtractionRecord) -> list[dict[str, Any]]:
    """Check that evidence references point to known figure/table/evidence ids."""

    evidence_ids = {obj.evidence_id for obj in record.evidence_objects if obj.evidence_id}
    figure_ids = {obj.figure_id for obj in record.evidence_objects if obj.figure_id}
    issues: list[dict[str, Any]] = []
    for ref in _iter_evidence_refs(record):
        source_id = getattr(ref, "source_id", None)
        figure_id = getattr(ref, "figure_id", None)
        table_id = getattr(ref, "table_id", None)
        if source_id and source_id not in evidence_ids and source_id not in figure_ids:
            issues.append({"type": "evidence_ref_warning", "reason": "unknown_source_id", "source_id": source_id})
        if figure_id and figure_id not in figure_ids:
            issues.append({"type": "evidence_ref_warning", "reason": "unknown_figure_id", "figure_id": figure_id})
        if table_id and not str(table_id).strip():
            issues.append({"type": "evidence_ref_warning", "reason": "blank_table_id"})
    return issues


def validate_no_core_keys_in_extended_data(
    record: PaperExtractionRecord,
    ontology: OntologyMap,
) -> list[dict[str, Any]]:
    """Ensure core statistical fields do not hide inside extended_data blobs."""

    core_keys = {key for key, entry in ontology.items() if entry.get("is_core_statistical_field")}
    issues: list[dict[str, Any]] = []
    payloads = []
    if record.global_constants:
        payloads.append(("global_constants", record.global_constants.extended_data))
    for series in record.experiment_series:
        payloads.append((f"series:{series.series_id}", series.extended_data))
        if series.series_constants:
            payloads.append((f"series_constants:{series.series_id}", series.series_constants.extended_data))
        for data_point in series.data_points:
            payloads.append((f"data_point:{data_point.sample_id}", data_point.extended_data))
    for scope, payload in payloads:
        for key in (payload or {}).keys():
            if key in core_keys:
                issues.append({"type": "extended_data_core_key", "scope": scope, "canonical_key": key})
    return issues


def validate_units_against_ontology(
    record: PaperExtractionRecord,
    ontology: OntologyMap,
) -> list[dict[str, Any]]:
    """Warn when record units differ from ontology standard units."""

    issues: list[dict[str, Any]] = []
    for parameter_record in collect_parameter_records(record):
        canonical_key = parameter_record.canonical_key
        if not canonical_key or canonical_key not in ontology:
            continue
        standard_unit = ontology[canonical_key].get("standard_unit")
        if parameter_record.unit and standard_unit and parameter_record.unit != standard_unit:
            issues.append(
                {
                    "type": "unit_warning",
                    "canonical_key": canonical_key,
                    "record_unit": parameter_record.unit,
                    "standard_unit": standard_unit,
                }
            )
    return issues


def validate_no_top_level_core_keys_in_global_constants(
    record: PaperExtractionRecord,
    ontology: OntologyMap,
) -> list[dict[str, Any]]:
    """Warn when core canonical keys remain at global_constants top level."""

    if not record.global_constants:
        return []

    known_nested_keys = {
        "scope_note",
        "raw_materials",
        "nominal_composition",
        "shared_process_summary",
        "shared_parameters",
        "heat_treatment_programs",
        "characterization_methods",
        "global_observations",
        "additional_parameter_records",
        "extended_data",
    }
    payload = record.global_constants.model_dump()
    issues: list[dict[str, Any]] = []
    for key in payload.keys():
        if key in known_nested_keys:
            continue
        entry = ontology.get(key)
        if entry and entry.get("is_core_statistical_field"):
            issues.append(
                {
                    "type": "top_level_core_key_warning",
                    "scope": "global_constants",
                    "canonical_key": key,
                }
            )
    return issues


def build_quality_flags(record: PaperExtractionRecord, validation_errors: Iterable[dict[str, Any]]) -> list[str]:
    """Build a concise list of quality flags from validation output."""

    flags: list[str] = list(record.data_provenance.quality_flags if record.data_provenance else [])
    flag_map = {
        "duplicate_id": "duplicate_ids_detected",
        "evidence_ref_warning": "evidence_reference_warnings",
        "extended_data_core_key": "core_keys_in_extended_data",
        "top_level_core_key_warning": "top_level_core_keys_review_needed",
        "unit_warning": "unit_normalization_review_needed",
        "canonical_key_error": "canonical_key_review_needed",
        "rejected_parameter_record": "rejected_parameter_records_present",
    }
    for issue in validation_errors:
        key = issue.get("type")
        mapped = flag_map.get(str(key))
        if mapped and mapped not in flags:
            flags.append(mapped)
    return flags


def _iter_evidence_refs(record: PaperExtractionRecord):
    for parameter_record in collect_parameter_records(record):
        for ref in parameter_record.evidence_refs:
            if hasattr(ref, "model_dump"):
                yield ref
