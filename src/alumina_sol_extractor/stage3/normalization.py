"""Stage 3 canonical-key and unit normalization helpers."""

from __future__ import annotations

from typing import Any

from alumina_sol_extractor.models.schema_v2 import DataPoint, ExperimentSeries, GlobalConstants, PaperExtractionRecord, ParameterRecord
from alumina_sol_extractor.ontology import get_ontology_entry_map, normalize_unit_value


OntologyMap = dict[str, dict[str, Any]]


def _coerce_ontology_map(ontology: OntologyMap | None) -> OntologyMap:
    return ontology or {}


def collect_parameter_records(record: PaperExtractionRecord) -> list[ParameterRecord]:
    """Collect all ParameterRecord objects from a validated paper record."""

    records: list[ParameterRecord] = []

    def _append_from_global_constants(global_constants: GlobalConstants | None) -> None:
        if not global_constants:
            return
        records.extend(global_constants.additional_parameter_records)

    def _append_from_data_point(data_point: DataPoint) -> None:
        records.extend(data_point.independent_variable_values)
        records.extend(data_point.additional_parameter_records)

    _append_from_global_constants(record.global_constants)
    for series in record.experiment_series:
        if series.series_constants:
            records.extend(series.series_constants.parameter_records)
        for data_point in series.data_points:
            _append_from_data_point(data_point)
    return records


def validate_canonical_keys(
    records: list[ParameterRecord],
    ontology: OntologyMap | None,
) -> list[dict[str, Any]]:
    """Return validation issues for records that do not match ontology keys."""

    ontology_map = _coerce_ontology_map(ontology)
    errors: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        needs_extension = bool(getattr(record, "needs_ontology_extension", False))
        if not record.canonical_key:
            if needs_extension:
                continue
            errors.append(
                {
                    "index": index,
                    "canonical_key": None,
                    "raw_name": record.raw_name,
                    "reason": "missing_canonical_key",
                }
            )
            continue
        if record.canonical_key not in ontology_map:
            errors.append(
                {
                    "index": index,
                    "canonical_key": record.canonical_key,
                    "raw_name": record.raw_name,
                    "reason": "unknown_canonical_key",
                }
            )
    return errors


def reject_noncanonical_records(
    records: list[ParameterRecord],
    ontology: OntologyMap | None,
) -> tuple[list[ParameterRecord], list[dict[str, Any]]]:
    """Split records into accepted and rejected buckets based on ontology membership."""

    ontology_map = _coerce_ontology_map(ontology)
    accepted: list[ParameterRecord] = []
    rejected: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if record.canonical_key and record.canonical_key in ontology_map:
            accepted.append(record)
        else:
            rejected.append(
                {
                    "index": index,
                    "canonical_key": record.canonical_key,
                    "raw_name": record.raw_name,
                    "raw_text": record.raw_text,
                    "reason": "noncanonical_parameter_record",
                    "needs_manual_review": True,
                }
            )
    return accepted, rejected


def prune_rejected_parameter_records(
    record: PaperExtractionRecord,
    ontology: OntologyMap | None,
) -> PaperExtractionRecord:
    """Drop noncanonical parameter records from the output record.

    Rejected records are still surfaced in validation summaries/reports, but they
    should not remain inside accepted `data_points` / `global_constants` payloads.
    """

    ontology_map = _coerce_ontology_map(ontology)

    def _keep(items: list[ParameterRecord]) -> list[ParameterRecord]:
        accepted, _ = reject_noncanonical_records(items, ontology_map)
        return accepted

    updated_global = None
    if record.global_constants:
        updated_global = record.global_constants.model_copy(
            update={
                "additional_parameter_records": _keep(list(record.global_constants.additional_parameter_records or []))
            }
        )

    updated_series: list[ExperimentSeries] = []
    for series in record.experiment_series:
        updated_constants = None
        if series.series_constants:
            updated_constants = series.series_constants.model_copy(
                update={
                    "parameter_records": _keep(list(series.series_constants.parameter_records or []))
                }
            )
        updated_data_points: list[DataPoint] = []
        for data_point in series.data_points:
            updated_data_points.append(
                data_point.model_copy(
                    update={
                        "independent_variable_values": _keep(list(data_point.independent_variable_values or [])),
                        "additional_parameter_records": _keep(list(data_point.additional_parameter_records or [])),
                    }
                )
            )
        updated_series.append(
            series.model_copy(
                update={
                    "series_constants": updated_constants,
                    "data_points": updated_data_points,
                }
            )
        )

    return record.model_copy(
        update={
            "global_constants": updated_global,
            "experiment_series": updated_series,
        }
    )


def normalize_parameter_records(
    records: list[ParameterRecord],
    ontology: OntologyMap | None,
) -> tuple[list[ParameterRecord], list[dict[str, Any]]]:
    """Normalize record units against ontology standard units conservatively."""

    ontology_map = _coerce_ontology_map(ontology)
    normalized: list[ParameterRecord] = []
    logs: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        target_unit = None
        if record.canonical_key and record.canonical_key in ontology_map:
            target_unit = ontology_map[record.canonical_key].get("standard_unit")
        if not target_unit or record.unit is None:
            normalized.append(record)
            continue

        result = normalize_unit_value(record.value, record.unit, target_unit)
        min_result = normalize_unit_value(record.min_value, record.unit, target_unit)
        max_result = normalize_unit_value(record.max_value, record.unit, target_unit)
        updated = record.model_copy(
            update={
                "value": result["value"],
                "min_value": min_result["value"],
                "max_value": max_result["value"],
                "unit": result["unit"],
                "normalization_note": _merge_notes(
                    record.normalization_note,
                    result.get("normalization_note"),
                    min_result.get("normalization_note"),
                    max_result.get("normalization_note"),
                ),
            }
        )
        normalized.append(updated)
        if updated.normalization_note:
            logs.append(
                {
                    "index": index,
                    "canonical_key": updated.canonical_key,
                    "source_unit": record.unit,
                    "target_unit": updated.unit,
                    "note": updated.normalization_note,
                }
            )
    return normalized, logs


def _merge_notes(*notes: str | None) -> str | None:
    parts = []
    seen = set()
    for note in notes:
        if not note:
            continue
        if note in seen:
            continue
        seen.add(note)
        parts.append(note)
    if not parts:
        return None
    return "; ".join(parts)


def load_default_ontology_map(project_root: Any) -> OntologyMap:
    """Convenience helper for callers that want the default ontology mapping."""

    return get_ontology_entry_map(project_root)
