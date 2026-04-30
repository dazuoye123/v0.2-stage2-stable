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
    PaperExtractionRecordList,
)
from alumina_sol_extractor.ontology import get_canonical_keys, get_ontology_entry_map
from alumina_sol_extractor.stage3.merge import merge_stage_outputs_to_paper_record
from alumina_sol_extractor.stage3.normalization import (
    collect_parameter_records,
    normalize_parameter_records,
    reject_noncanonical_records,
    validate_canonical_keys,
)
from alumina_sol_extractor.stage3.report import build_stage3_validation_report
from alumina_sol_extractor.stage3.validators import (
    build_quality_flags,
    validate_evidence_refs,
    validate_id_uniqueness,
    validate_no_core_keys_in_extended_data,
    validate_units_against_ontology,
)
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
    """Run optional Stage 3 DSPy schema extraction or dry-run validator."""
    dspy_settings = load_dspy_settings(Path(project_root), settings)
    stage3_settings = settings.get("stage3", {})
    if not dspy_settings.get("enabled", False):
        if stage3_settings.get("dry_run_validator", False):
            return _run_dry_run_validator(project_root, settings, paper_id, output_dir)
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

    paper_record = merge_stage_outputs_to_paper_record(
        paper_basic_info=paper_basic_info_result.payload or {},
        global_constants=global_constants_result.payload or {},
        experiment_series=experiment_series_payload if isinstance(experiment_series_payload, list) else [],
        data_points=data_point_records,
        evidence_objects=_coerce_list_payload(evidence_objects_result.payload, "evidence_objects"),
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
    validated = _validate_stage3_record(paper_record, project_root, stage3_dir)

    outputs = dspy_settings.get("outputs", {})
    _write_json(stage3_dir / outputs.get("paper_basic_info", "paper_basic_info.json"), validated.paper_basic_info.model_dump() if validated.paper_basic_info else {})
    _write_json(stage3_dir / outputs.get("global_constants", "global_constants.json"), validated.global_constants.model_dump() if validated.global_constants else {})
    write_jsonl(
        [series.model_dump() for series in validated.experiment_series],
        stage3_dir / outputs.get("experiment_series", "experiment_series.jsonl"),
    )
    write_jsonl(
        data_point_records,
        stage3_dir / outputs.get("data_points", "data_points.jsonl"),
    )
    write_jsonl(
        [item.model_dump() for item in validated.evidence_objects],
        stage3_dir / outputs.get("evidence_objects", "evidence_objects.jsonl"),
    )
    _write_json(
        stage3_dir / outputs.get("paper_extraction", "paper_extraction.schema_v2.json"),
        validated.model_dump(),
    )

    judge_payload: dict[str, Any] = {"stage3_judge": "disabled"}
    if dspy_settings.get("run_judge", False):
        schema_hint_path = Path(project_root) / "configs" / "schema_v2.json"
        schema_hint = json.loads(schema_hint_path.read_text(encoding="utf-8"))
        judge_result = run_judge(
            paper_text=paper_text,
            extraction_json=validated.model_dump(),
            ontology_keys=ontology_keys,
            schema_hint=schema_hint,
        )
        judge_payload = judge_result.payload if isinstance(judge_result.payload, dict) else {"raw_output": judge_result.raw_output}
    _write_json(stage3_dir / outputs.get("judge", "dspy_judge.json"), judge_payload)

    summary = {
        "stage3_dspy": "enabled",
        "paper_id": paper_id,
        "paper_basic_info_ok": validated.paper_basic_info is not None,
        "experiment_series_count": len(validated.experiment_series),
        "data_point_count": sum(len(series.data_points) for series in validated.experiment_series),
        "evidence_object_count": len(validated.evidence_objects),
        "run_judge": bool(dspy_settings.get("run_judge", False)),
        "stage3_dir": str(stage3_dir),
    }
    _write_json(stage3_dir / outputs.get("summary", "stage3_summary.json"), summary)
    return summary


def _run_dry_run_validator(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    stage3_settings = settings.get("stage3", {})
    fixture_path = Path(project_root) / stage3_settings.get(
        "fixture_path",
        "resources/stage3_seed/extraction_lijianjun_full.schema_v2.json",
    )
    stage3_dir = Path(output_dir) / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)

    records = PaperExtractionRecordList.model_validate_json(fixture_path.read_text(encoding="utf-8")).root
    record = records[0] if records else PaperExtractionRecord()
    validated_record = _validate_stage3_record(record, project_root, stage3_dir)
    _write_json(stage3_dir / "paper_extraction.schema_v2.json", validated_record.model_dump())

    report_name = stage3_settings.get("validation_report", "stage3_validation_report.md")
    summary_name = settings.get("dspy", {}).get("outputs", {}).get("summary", "stage3_summary.json")
    summary = _build_validation_summary(validated_record, project_root, stage3_dir / report_name, schema_valid=True)
    summary.update(
        {
            "stage3_dspy": "disabled",
            "stage3_mode": "dry_run_validator",
            "paper_id": paper_id,
            "fixture_path": str(fixture_path),
            "stage3_dir": str(stage3_dir),
        }
    )
    _write_json(stage3_dir / summary_name, summary)
    return summary


def _validate_stage3_record(record: PaperExtractionRecord, project_root: Path, stage3_dir: Path) -> PaperExtractionRecord:
    ontology = get_ontology_entry_map(project_root)
    parameter_records = collect_parameter_records(record)
    accepted_records, rejected_records = reject_noncanonical_records(parameter_records, ontology)
    normalized_records, normalization_log = normalize_parameter_records(accepted_records, ontology)
    canonical_key_errors = [
        {**issue, "type": "canonical_key_error"}
        for issue in validate_canonical_keys(parameter_records, ontology)
    ]
    duplicate_ids = validate_id_uniqueness(record)
    evidence_ref_warnings = validate_evidence_refs(record)
    extended_data_core_keys = validate_no_core_keys_in_extended_data(record, ontology)
    unit_warnings = validate_units_against_ontology(record, ontology)
    combined_issues = canonical_key_errors + duplicate_ids + evidence_ref_warnings + extended_data_core_keys + unit_warnings
    combined_issues.extend({**issue, "type": "rejected_parameter_record"} for issue in rejected_records)
    quality_flags = build_quality_flags(record, combined_issues)

    provenance = record.data_provenance or DataProvenance()
    record = record.model_copy(
        update={
            "data_provenance": provenance.model_copy(
                update={
                    "normalization_log": list(provenance.normalization_log) + normalization_log,
                    "quality_flags": quality_flags,
                }
            )
        }
    )
    report_path = stage3_dir / "stage3_validation_report.md"
    build_stage3_validation_report(
        output_path=report_path,
        schema_valid=True,
        canonical_key_errors=canonical_key_errors,
        unit_warnings=unit_warnings,
        duplicate_ids=duplicate_ids,
        evidence_ref_warnings=evidence_ref_warnings,
        extended_data_core_keys=extended_data_core_keys,
        rejected_parameter_records=rejected_records,
        quality_flags=quality_flags,
    )
    return record


def _build_validation_summary(
    record: PaperExtractionRecord,
    project_root: Path,
    report_path: Path,
    *,
    schema_valid: bool,
) -> dict[str, Any]:
    ontology = get_ontology_entry_map(project_root)
    parameter_records = collect_parameter_records(record)
    _, rejected_records = reject_noncanonical_records(parameter_records, ontology)
    canonical_key_errors = validate_canonical_keys(parameter_records, ontology)
    duplicate_ids = validate_id_uniqueness(record)
    evidence_ref_warnings = validate_evidence_refs(record)
    extended_data_core_keys = validate_no_core_keys_in_extended_data(record, ontology)
    unit_warnings = validate_units_against_ontology(record, ontology)
    return {
        "schema_valid": schema_valid,
        "canonical_key_errors_count": len(canonical_key_errors),
        "unit_warning_count": len(unit_warnings),
        "duplicate_id_count": len(duplicate_ids),
        "evidence_ref_warning_count": len(evidence_ref_warnings),
        "extended_data_core_key_count": len(extended_data_core_keys),
        "rejected_parameter_records_count": len(rejected_records),
        "quality_flags": list(record.data_provenance.quality_flags if record.data_provenance else []),
        "validation_report_path": str(report_path),
    }


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
