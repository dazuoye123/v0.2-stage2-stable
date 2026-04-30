"""Deterministic Stage 3 merge utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from alumina_sol_extractor.models.schema_v2 import (
    DataPoint,
    DataProvenance,
    EvidenceObject,
    ExperimentSeries,
    GlobalConstants,
    PaperBasicInfo,
    PaperExtractionRecord,
    SchemaBaseModel,
)


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
    evidence_objects: list[dict[str, Any] | EvidenceObject] | None = None,
    multimodal_extractions: list[dict[str, Any]] | None = None,
    cross_modal_links: list[dict[str, Any]] | None = None,
    data_provenance: dict[str, Any] | DataProvenance | None = None,
    schema_version: str = "2.0",
) -> PaperExtractionRecord:
    """Merge intermediate stage outputs into a validated paper extraction record."""

    series_models = [_coerce_model(item, ExperimentSeries) for item in (experiment_series or [])]
    data_point_models = [_coerce_model(item, DataPoint) for item in (data_points or [])]
    series_models = _attach_data_points_to_series(series_models, data_point_models)

    payload = ensure_required_top_level_sections(
        ensure_schema_version(
            {
                "paper_basic_info": _dump_or_none(paper_basic_info),
                "global_constants": _dump_or_none(global_constants),
                "experiment_series": [series.model_dump() for series in series_models],
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


def _fill_nested_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    if result["paper_basic_info"] is None:
        result["paper_basic_info"] = {}
    if result["global_constants"] is None:
        result["global_constants"] = {}
    if result["data_provenance"] is None:
        result["data_provenance"] = {}
    return result


def _coerce_model(item: dict[str, Any] | SchemaBaseModel, model_cls: type[SchemaBaseModel]):
    if isinstance(item, model_cls):
        return item
    return model_cls.model_validate(item or {})


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
