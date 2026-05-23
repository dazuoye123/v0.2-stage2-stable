"""Deterministic Stage 3 merge utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic.fields import FieldInfo

from alumina_sol_extractor.models.schema_v2 import (
    DataPoint,
    DataProvenance,
    EvidenceObject,
    ExperimentSeries,
    GlobalConstants,
    ParameterRecord,
    PaperBasicInfo,
    PaperExtractionRecord,
    ProcessStepRecord,
    SchemaBaseModel,
)


SPECTRAL_LIST_CANONICAL_KEYS = {
    "nmr_27Al_peak_position_ppm",
    "raman_peak_position_cm_1",
    "ftir_peak_position_cm_1",
    "xrd_peak_position_2theta_deg",
    "peak_positions",
    "peak_position",
    "spectral_peak_positions",
}


def fill_missing_with_none(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Return a copy of ``payload`` with missing scalar keys set to ``None``."""

    result = deepcopy(payload)
    for key in keys:
        result.setdefault(key, None)
    return result


def ensure_schema_version(payload: dict[str, Any], schema_version: str = "2.0") -> dict[str, Any]:
    result = deepcopy(payload)
    result["schema_version"] = result.get("schema_version") or schema_version
    return result


def ensure_required_top_level_sections(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    result.setdefault("paper_basic_info", None)
    result.setdefault("global_constants", None)
    result.setdefault("experiment_series", [])
    result.setdefault("process_steps", [])
    result.setdefault("evidence_objects", [])
    result.setdefault("multimodal_extractions", [])
    result.setdefault("cross_modal_links", [])
    result.setdefault("data_provenance", None)
    return result


def merge_stage_outputs_to_paper_record(
    *,
    paper_basic_info: dict[str, Any] | PaperBasicInfo | None = None,
    global_constants: dict[str, Any] | GlobalConstants | None = None,
    experiment_series: list[dict[str, Any] | ExperimentSeries] | None = None,
    data_points: list[dict[str, Any] | DataPoint] | None = None,
    process_steps: list[dict[str, Any] | ProcessStepRecord] | None = None,
    evidence_objects: list[dict[str, Any] | EvidenceObject] | None = None,
    multimodal_extractions: list[dict[str, Any]] | None = None,
    cross_modal_links: list[dict[str, Any]] | None = None,
    data_provenance: dict[str, Any] | DataProvenance | None = None,
    schema_version: str = "2.0",
) -> PaperExtractionRecord:
    """Merge intermediate stage outputs into a validated paper extraction record."""

    series_models = [_coerce_model(item, ExperimentSeries) for item in (experiment_series or [])]
    data_point_models = [_coerce_model(item, DataPoint) for item in (data_points or [])]
    process_step_models = [_coerce_model(item, ProcessStepRecord) for item in (process_steps or [])]
    if not series_models and data_point_models:
        series_models = _synthesize_series_from_data_points(data_point_models)
    series_models = _attach_data_points_to_series(series_models, data_point_models)

    payload = ensure_required_top_level_sections(
        ensure_schema_version(
            {
                "paper_basic_info": _dump_or_none(paper_basic_info),
                "global_constants": _dump_or_none(global_constants),
                "experiment_series": [series.model_dump() for series in series_models],
                "process_steps": [step.model_dump() for step in process_step_models],
                "evidence_objects": [_dump_or_none(item) for item in (evidence_objects or [])],
                "multimodal_extractions": [deepcopy(item) for item in (multimodal_extractions or [])],
                "cross_modal_links": [deepcopy(item) for item in (cross_modal_links or [])],
                "data_provenance": _dump_or_none(data_provenance),
            },
            schema_version=schema_version,
        )
    )
    payload = _fill_nested_defaults(payload)
    return PaperExtractionRecord.model_validate(payload)


def move_top_level_core_keys_from_global_constants(
    global_constants: dict[str, Any] | GlobalConstants | None,
    ontology: dict[str, dict[str, Any]] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Move stray top-level core canonical keys into additional_parameter_records."""

    ontology_map = ontology or {}
    payload = _dump_or_none(global_constants) or {}
    if not isinstance(payload, dict):
        return {}, []

    result = deepcopy(payload)
    additional_records = result.setdefault("additional_parameter_records", [])
    if not isinstance(additional_records, list):
        additional_records = []
        result["additional_parameter_records"] = additional_records

    shared_parameters = result.setdefault("shared_parameters", {})
    if not isinstance(shared_parameters, dict):
        shared_parameters = {}
        result["shared_parameters"] = shared_parameters

    moved_logs: list[dict[str, Any]] = []
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
    for key in list(result.keys()):
        if key in known_nested_keys:
            continue
        entry = ontology_map.get(key)
        if not entry or not entry.get("is_core_statistical_field"):
            continue
        value = result.pop(key)
        additional_records.extend(
            _build_parameter_records_for_global_constant(
                canonical_key=key,
                value=value,
                unit=entry.get("standard_unit"),
                raw_name=entry.get("zh_name") or entry.get("en_name") or key,
            )
        )
        moved_logs.append(
            {
                "type": "moved_top_level_core_key",
                "canonical_key": key,
                "target": "global_constants.additional_parameter_records",
            }
        )
    return result, moved_logs


def _build_parameter_records_for_global_constant(
    *,
    canonical_key: str,
    value: Any,
    unit: str | None,
    raw_name: str,
) -> list[dict[str, Any]]:
    base_note = "moved_from_global_constants_top_level"
    if isinstance(value, list) and _is_list_valued_spectral_key(canonical_key):
        records: list[dict[str, Any]] = []
        for index, scalar_value in enumerate(value):
            if isinstance(scalar_value, (dict, list)):
                continue
            records.append(
                ParameterRecord(
                    canonical_key=canonical_key,
                    raw_name=raw_name,
                    value=scalar_value,
                    unit=unit,
                    raw_text=str(value),
                    normalization_note=f"{base_note}; split_list_valued_parameter:index={index};original_length={len(value)}",
                ).model_dump()
            )
        return records
    if isinstance(value, list):
        return [
            ParameterRecord(
                canonical_key=canonical_key,
                raw_name=raw_name,
                value=None,
                unit=unit,
                raw_text=str(value),
                normalization_note=f"{base_note}; raw_list_value_preserved_unmaterialized",
            ).model_dump()
        ]
    if isinstance(value, dict):
        return [
            ParameterRecord(
                canonical_key=canonical_key,
                raw_name=raw_name,
                value=None,
                unit=unit,
                raw_text=str(value),
                normalization_note=f"{base_note}; raw_dict_value_preserved_unmaterialized",
            ).model_dump()
        ]
    return [
        ParameterRecord(
            canonical_key=canonical_key,
            raw_name=raw_name,
            value=value,
            unit=unit,
            raw_text=str(value) if value is not None else None,
            normalization_note=base_note,
        ).model_dump()
    ]


def _is_list_valued_spectral_key(canonical_key: str) -> bool:
    normalized = str(canonical_key or "").strip()
    if normalized in SPECTRAL_LIST_CANONICAL_KEYS:
        return True
    lowered = normalized.lower()
    return "peak_position" in lowered or lowered.endswith("peak_positions")


def _fill_nested_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    if result["paper_basic_info"] is None:
        result["paper_basic_info"] = {}
    if result["global_constants"] is None:
        result["global_constants"] = {}
    if result["data_provenance"] is None:
        result["data_provenance"] = {}
    return _sanitize_model_payload(result, PaperExtractionRecord)


def _coerce_model(item: dict[str, Any] | SchemaBaseModel, model_cls: type[SchemaBaseModel]):
    if isinstance(item, model_cls):
        return item
    payload = _sanitize_model_payload(_normalize_identifier_fields(item or {}, model_cls), model_cls)
    return model_cls.model_validate(payload)


def _normalize_identifier_fields(
    payload: dict[str, Any],
    model_cls: type[SchemaBaseModel],
) -> dict[str, Any]:
    result = deepcopy(payload)
    if model_cls is ExperimentSeries and result.get("series_id") is not None:
        result["series_id"] = str(result["series_id"])
    if model_cls is DataPoint and result.get("sample_id") is not None:
        result["sample_id"] = str(result["sample_id"])
    return result


def _dump_or_none(item: Any) -> Any:
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return deepcopy(item)


def _attach_data_points_to_series(
    series_models: list[ExperimentSeries],
    data_points: list[DataPoint],
) -> list[ExperimentSeries]:
    if not data_points:
        return series_models
    if len(series_models) == 1:
        series = series_models[0]
        return [series.model_copy(update={"data_points": list(series.data_points) + data_points})]

    series_by_id = {series.series_id: series for series in series_models if series.series_id}
    leftovers: list[DataPoint] = []
    updated: dict[str, list[DataPoint]] = {series.series_id or f"__idx_{idx}": list(series.data_points) for idx, series in enumerate(series_models)}
    for data_point in data_points:
        series_id = getattr(data_point, "series_id", None) or data_point.extended_data.get("series_id")
        parent_series_id = data_point.extended_data.get("parent_series_id")
        target = series_id or parent_series_id
        if target and target in series_by_id:
            updated[target].append(data_point)
        else:
            leftovers.append(data_point)

    rebuilt: list[ExperimentSeries] = []
    for idx, series in enumerate(series_models):
        key = series.series_id or f"__idx_{idx}"
        merged_points = updated.get(key, list(series.data_points))
        if leftovers and idx == len(series_models) - 1:
            merged_points = merged_points + leftovers
        rebuilt.append(series.model_copy(update={"data_points": merged_points}))
    return rebuilt


def _synthesize_series_from_data_points(
    data_points: list[DataPoint],
) -> list[ExperimentSeries]:
    grouped: dict[str, list[DataPoint]] = {}
    series_names: dict[str, str] = {}
    fallback_counter = 1
    for data_point in data_points:
        extended = dict(data_point.extended_data or {})
        series_id = (
            getattr(data_point, "series_id", None)
            or extended.get("series_id")
            or extended.get("parent_series_id")
        )
        if not series_id:
            series_id = f"series-{fallback_counter}"
            fallback_counter += 1
        series_id = str(series_id)
        grouped.setdefault(series_id, []).append(data_point)
        series_name = extended.get("series_name")
        if series_name:
            series_names.setdefault(series_id, str(series_name))

    synthesized: list[ExperimentSeries] = []
    for index, (series_id, points) in enumerate(grouped.items(), start=1):
        synthesized.append(
            ExperimentSeries(
                series_id=series_id,
                series_name=series_names.get(series_id) or f"Series {index}",
                extended_data={"synthetic_series_from_data_points": True},
            )
        )
    return synthesized


def _sanitize_model_payload(payload: Any, model_cls: type[SchemaBaseModel] | None = None) -> Any:
    if not isinstance(payload, dict) or model_cls is None:
        return payload

    result = deepcopy(payload)
    for field_name, field_info in model_cls.model_fields.items():
        if field_name not in result:
            continue
        result[field_name] = _sanitize_field_value(result[field_name], field_info)
    return result


def _sanitize_field_value(value: Any, field_info: FieldInfo) -> Any:
    if value is None:
        if field_info.default_factory is list:
            return []
        if field_info.default_factory is dict:
            return {}
        return value

    annotation = field_info.annotation
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    if isinstance(value, dict):
        nested_model = _find_schema_model(annotation, args)
        if nested_model is not None:
            return _sanitize_model_payload(value, nested_model)
        return value

    if isinstance(value, list):
        item_model = _find_list_item_schema_model(annotation, args)
        if item_model is None:
            return value
        return [
            _sanitize_model_payload(item, item_model) if isinstance(item, dict) else item
            for item in value
        ]

    return value


def _find_schema_model(annotation: Any, args: tuple[Any, ...]) -> type[SchemaBaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, SchemaBaseModel):
        return annotation
    for arg in args:
        if isinstance(arg, type) and issubclass(arg, SchemaBaseModel):
            return arg
    return None


def _find_list_item_schema_model(annotation: Any, args: tuple[Any, ...]) -> type[SchemaBaseModel] | None:
    origin = getattr(annotation, "__origin__", None)
    if origin is list and args:
        item_type = args[0]
        if isinstance(item_type, type) and issubclass(item_type, SchemaBaseModel):
            return item_type
    for arg in args:
        nested_origin = getattr(arg, "__origin__", None)
        nested_args = getattr(arg, "__args__", ())
        if nested_origin is list and nested_args:
            item_type = nested_args[0]
            if isinstance(item_type, type) and issubclass(item_type, SchemaBaseModel):
                return item_type
    return None
