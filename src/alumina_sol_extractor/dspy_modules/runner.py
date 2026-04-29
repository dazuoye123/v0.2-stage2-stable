"""Runner for optional Stage 3 schema_v2 DSPy extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.models.schema_v2 import (
    DataProvenance,
    EvidenceObject,
    ExperimentSeries,
    GlobalConstants,
    PaperBasicInfo,
    PaperExtractionRecord,
)
from alumina_sol_extractor.ontology import get_canonical_keys
from alumina_sol_extractor.utils.jsonl import write_jsonl

from .judge import run_judge
from .modules import (
    ExtractDataPointsModule,
    ExtractEvidenceObjectsModule,
    ExtractExperimentSeriesModule,
    ExtractGlobalConstantsModule,
    ExtractPaperBasicInfoModule,
    to_json_text,
)
from .settings import configure_dspy_lm, load_dspy_settings


def run_stage3_dspy_schema_extraction(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Run optional Stage 3 DSPy schema extraction."""
    dspy_settings = load_dspy_settings(Path(project_root), settings)
    if not dspy_settings.get("enabled", False):
        return {"stage3_dspy": "disabled"}

    configure_dspy_lm(dspy_settings)

    paper_text = Path(cleaned_markdown_path).read_text(encoding="utf-8")
    stage2_output_dir = Path(output_dir)
    figures_jsonl_path = stage2_output_dir / "figures.jsonl"
    vision_inputs_path = stage2_output_dir / "vision_inputs.jsonl"
    tables_dir = stage2_output_dir / "tables"
    stage3_dir = stage2_output_dir / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)

    figures = _read_jsonl(figures_jsonl_path)
    vision_inputs = _read_jsonl(vision_inputs_path)
    tables_summary = _summarize_tables(tables_dir)
    figure_summaries = _summarize_figures(figures)
    captions_and_references = [
        {
            "figure_id": item.get("figure_id"),
            "caption": item.get("caption"),
            "reference_sentences": item.get("reference_sentences"),
        }
        for item in figures
    ]
    ontology_keys = get_canonical_keys(project_root)

    paper_basic_info_result = ExtractPaperBasicInfoModule().run(
        paper_text_head=paper_text[: max(2000, int(dspy_settings.get("chunk_size", 4000)))],
        source_file=str(cleaned_markdown_path),
    )
    global_constants_result = ExtractGlobalConstantsModule().run(
        paper_text=paper_text,
        ontology_keys=to_json_text(ontology_keys),
        paper_basic_info_json=to_json_text(paper_basic_info_result.payload or {}),
    )
    experiment_series_result = ExtractExperimentSeriesModule().run(
        paper_text=paper_text,
        figure_summaries=to_json_text(figure_summaries),
        table_summaries=to_json_text(tables_summary),
        ontology_keys=to_json_text(ontology_keys),
        paper_basic_info_json=to_json_text(paper_basic_info_result.payload or {}),
        global_constants_json=to_json_text(global_constants_result.payload or {}),
    )

    experiment_series_payload = experiment_series_result.payload or []
    if isinstance(experiment_series_payload, dict):
        experiment_series_payload = experiment_series_payload.get("experiment_series", [])

    data_point_records: list[dict[str, Any]] = []
    for series in experiment_series_payload if isinstance(experiment_series_payload, list) else []:
        data_points_result = ExtractDataPointsModule().run(
            one_series_json=to_json_text(series),
            relevant_text=paper_text,
            table_summaries=to_json_text(tables_summary),
            figure_summaries=to_json_text(figure_summaries),
            ontology_keys=to_json_text(ontology_keys),
        )
        payload = data_points_result.payload or []
        if isinstance(payload, dict):
            payload = payload.get("data_points", [])
        if isinstance(payload, list):
            data_point_records.extend(item for item in payload if isinstance(item, dict))

    evidence_objects_result = ExtractEvidenceObjectsModule().run(
        figures_jsonl_summary=to_json_text(vision_inputs or figure_summaries),
        tables_summary=to_json_text(tables_summary),
        captions_and_references=to_json_text(captions_and_references),
    )

    paper_record = PaperExtractionRecord(
        schema_version="2.0",
        paper_basic_info=PaperBasicInfo.model_validate(paper_basic_info_result.payload or {}),
        global_constants=GlobalConstants.model_validate(global_constants_result.payload or {}),
        experiment_series=[
            ExperimentSeries.model_validate(series)
            for series in experiment_series_payload
            if isinstance(series, dict)
        ],
        evidence_objects=[
            EvidenceObject.model_validate(item)
            for item in _coerce_list_payload(evidence_objects_result.payload, "evidence_objects")
            if isinstance(item, dict)
        ],
        data_provenance=DataProvenance(
            source_pipeline="stage3_dspy_schema_extraction",
            quality_flags=[
                flag
                for flag in [
                    _error_flag("paper_basic_info_json_error", paper_basic_info_result.error),
                    _error_flag("global_constants_json_error", global_constants_result.error),
                    _error_flag("experiment_series_json_error", experiment_series_result.error),
                    _error_flag("evidence_objects_json_error", evidence_objects_result.error),
                ]
                if flag
            ],
            notes=[],
        ),
    )
    paper_record = PaperExtractionRecord.model_validate(paper_record.model_dump())

    outputs = dspy_settings.get("outputs", {})
    _write_json(stage3_dir / outputs.get("paper_basic_info", "paper_basic_info.json"), paper_record.paper_basic_info.model_dump() if paper_record.paper_basic_info else {})
    _write_json(stage3_dir / outputs.get("global_constants", "global_constants.json"), paper_record.global_constants.model_dump() if paper_record.global_constants else {})
    write_jsonl(
        [series.model_dump() for series in paper_record.experiment_series],
        stage3_dir / outputs.get("experiment_series", "experiment_series.jsonl"),
    )
    write_jsonl(
        data_point_records,
        stage3_dir / outputs.get("data_points", "data_points.jsonl"),
    )
    write_jsonl(
        [item.model_dump() for item in paper_record.evidence_objects],
        stage3_dir / outputs.get("evidence_objects", "evidence_objects.jsonl"),
    )
    _write_json(
        stage3_dir / outputs.get("paper_extraction", "paper_extraction.schema_v2.json"),
        paper_record.model_dump(),
    )

    judge_payload: dict[str, Any] = {"stage3_judge": "disabled"}
    if dspy_settings.get("run_judge", False):
        schema_hint_path = Path(project_root) / "configs" / "schema_v2.json"
        schema_hint = json.loads(schema_hint_path.read_text(encoding="utf-8"))
        judge_result = run_judge(
            paper_text=paper_text,
            extraction_json=paper_record.model_dump(),
            ontology_keys=ontology_keys,
            schema_hint=schema_hint,
        )
        judge_payload = judge_result.payload if isinstance(judge_result.payload, dict) else {"raw_output": judge_result.raw_output}
    _write_json(stage3_dir / outputs.get("judge", "dspy_judge.json"), judge_payload)

    summary = {
        "stage3_dspy": "enabled",
        "paper_id": paper_id,
        "paper_basic_info_ok": paper_record.paper_basic_info is not None,
        "experiment_series_count": len(paper_record.experiment_series),
        "data_point_count": len(data_point_records),
        "evidence_object_count": len(paper_record.evidence_objects),
        "run_judge": bool(dspy_settings.get("run_judge", False)),
        "stage3_dir": str(stage3_dir),
    }
    _write_json(stage3_dir / outputs.get("summary", "stage3_summary.json"), summary)
    return summary


def _coerce_list_payload(payload: object | None, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _error_flag(flag_name: str, error: str | None) -> str | None:
    return flag_name if error else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _summarize_tables(tables_dir: Path) -> list[dict[str, Any]]:
    if not tables_dir.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for json_path in sorted(tables_dir.glob("table_*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        summaries.append({"table_id": json_path.stem, "rows": payload})
    return summaries


def _summarize_figures(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "figure_id": item.get("figure_id"),
            "caption": item.get("caption"),
            "description_text": item.get("description_text"),
            "figure_class": item.get("figure_class"),
        }
        for item in figures
    ]
