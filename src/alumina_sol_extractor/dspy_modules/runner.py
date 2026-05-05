"""Runner for optional Stage 3 schema_v2 DSPy extraction."""

from __future__ import annotations

import json
import re
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
from alumina_sol_extractor.stage3.merge import (
    merge_stage_outputs_to_paper_record,
    move_top_level_core_keys_from_global_constants,
)
from alumina_sol_extractor.stage3.normalization import (
    collect_parameter_records,
    normalize_parameter_records,
    reject_noncanonical_records,
    validate_canonical_keys,
)
from alumina_sol_extractor.stage3.report import build_stage3_validation_report
from alumina_sol_extractor.stage3.validators import (
    build_quality_flags,
    validate_core_parameter_without_evidence,
    validate_duplicate_evidence_ids,
    validate_evidence_figure_id_alignment,
    validate_evidence_refs,
    validate_id_uniqueness,
    validate_no_core_keys_in_extended_data,
    validate_no_top_level_core_keys_in_global_constants,
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

    return _run_live_stage3_extraction(
        project_root=Path(project_root),
        dspy_settings=dspy_settings,
        paper_id=paper_id,
        cleaned_markdown_path=Path(cleaned_markdown_path),
        output_dir=Path(output_dir),
        stage3_dir_name="stage3",
        summary_filename=dspy_settings.get("outputs", {}).get("summary", "stage3_summary.json"),
        raw_outputs_filename=None,
    )


def run_stage3_dspy_smoke_test(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
    *,
    paper_text_limit_chars: int = 4000,
    max_experiment_series: int = 1,
) -> dict[str, Any]:
    """Run a single-paper Stage 3 DSPy smoke test with raw output capture."""
    dspy_settings = load_dspy_settings(Path(project_root), settings)
    dspy_settings["enabled"] = True
    return _run_live_stage3_extraction(
        project_root=Path(project_root),
        dspy_settings=dspy_settings,
        paper_id=paper_id,
        cleaned_markdown_path=Path(cleaned_markdown_path),
        output_dir=Path(output_dir),
        stage3_dir_name="stage3_dspy_smoke",
        summary_filename="stage3_smoke_summary.json",
        raw_outputs_filename="raw_dspy_outputs.jsonl",
        paper_text_limit_chars=paper_text_limit_chars,
        max_experiment_series=max_experiment_series,
    )


def _run_live_stage3_extraction(
    *,
    project_root: Path,
    dspy_settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
    stage3_dir_name: str,
    summary_filename: str,
    raw_outputs_filename: str | None,
    paper_text_limit_chars: int | None = None,
    max_experiment_series: int | None = None,
) -> dict[str, Any]:
    configure_dspy_lm(dspy_settings)

    paper_text = _read_text_best_effort(cleaned_markdown_path)
    if paper_text_limit_chars and paper_text_limit_chars > 0:
        paper_text = paper_text[:paper_text_limit_chars]
    stage2_output_dir = output_dir
    figures_jsonl_path = stage2_output_dir / "figures.jsonl"
    vision_inputs_path = stage2_output_dir / "vision_inputs.jsonl"
    tables_dir = stage2_output_dir / "tables"
    stage3_dir = stage2_output_dir / stage3_dir_name
    stage3_dir.mkdir(parents=True, exist_ok=True)
    raw_outputs: list[dict[str, Any]] = []

    figures = _read_jsonl(figures_jsonl_path)
    vision_inputs = _read_jsonl(vision_inputs_path)
    tables_summary = _summarize_tables(tables_dir)
    figure_summaries = _summarize_figures(figures)
    figure_metadata_map = _build_figure_metadata_map(figures, vision_inputs)
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
    _append_raw_output(
        raw_outputs,
        step_name="paper_basic_info",
        module_name="ExtractPaperBasicInfoModule",
        result=paper_basic_info_result,
    )
    global_constants_result = ExtractGlobalConstantsModule().run(
        paper_text=paper_text,
        ontology_keys=to_json_text(ontology_keys),
        paper_basic_info_json=to_json_text(paper_basic_info_result.payload or {}),
    )
    _append_raw_output(
        raw_outputs,
        step_name="global_constants",
        module_name="ExtractGlobalConstantsModule",
        result=global_constants_result,
    )
    experiment_series_result = ExtractExperimentSeriesModule().run(
        paper_text=paper_text,
        figure_summaries=to_json_text(figure_summaries),
        table_summaries=to_json_text(tables_summary),
        ontology_keys=to_json_text(ontology_keys),
        paper_basic_info_json=to_json_text(paper_basic_info_result.payload or {}),
        global_constants_json=to_json_text(global_constants_result.payload or {}),
    )
    _append_raw_output(
        raw_outputs,
        step_name="experiment_series",
        module_name="ExtractExperimentSeriesModule",
        result=experiment_series_result,
    )

    experiment_series_payload = experiment_series_result.payload or []
    if isinstance(experiment_series_payload, dict):
        experiment_series_payload = experiment_series_payload.get("experiment_series", [])
    if isinstance(experiment_series_payload, list) and max_experiment_series and max_experiment_series > 0:
        experiment_series_payload = experiment_series_payload[:max_experiment_series]

    data_point_records: list[dict[str, Any]] = []
    for index, series in enumerate(experiment_series_payload if isinstance(experiment_series_payload, list) else []):
        data_points_result = ExtractDataPointsModule().run(
            one_series_json=to_json_text(series),
            relevant_text=paper_text,
            table_summaries=to_json_text(tables_summary),
            figure_summaries=to_json_text(figure_summaries),
            ontology_keys=to_json_text(ontology_keys),
        )
        _append_raw_output(
            raw_outputs,
            step_name=f"data_points:{index}",
            module_name="ExtractDataPointsModule",
            result=data_points_result,
            extra={"series_id": series.get("series_id") if isinstance(series, dict) else None},
        )
        series_data_points, parse_issue = _coerce_data_points_payload(
            payload=data_points_result.payload,
            series=series if isinstance(series, dict) else {},
            ontology=get_ontology_entry_map(project_root),
            series_index=index,
        )
        if parse_issue:
            raw_outputs.append(parse_issue)
        data_point_records.extend(series_data_points)

    evidence_objects_result = ExtractEvidenceObjectsModule().run(
        figures_jsonl_summary=to_json_text(vision_inputs or figure_summaries),
        tables_summary=to_json_text(tables_summary),
        captions_and_references=to_json_text(captions_and_references),
    )
    _append_raw_output(
        raw_outputs,
        step_name="evidence_objects",
        module_name="ExtractEvidenceObjectsModule",
        result=evidence_objects_result,
    )

    cleaned_paper_basic_info = _postprocess_paper_basic_info(
        payload=paper_basic_info_result.payload,
        paper_text=paper_text,
        source_file=cleaned_markdown_path,
    )
    ontology_map = get_ontology_entry_map(project_root)
    cleaned_global_constants, moved_top_level_logs = move_top_level_core_keys_from_global_constants(
        global_constants_result.payload,
        ontology_map,
    )
    evidence_payload = _split_evidence_objects_payload(
        payload=_coerce_list_payload(evidence_objects_result.payload, "evidence_objects"),
        figure_metadata_map=figure_metadata_map,
        tables_summary=tables_summary,
    )

    quality_flags = []
    if _detect_mojibake(paper_text):
        quality_flags.append("source_text_mojibake_suspected")
    if any(_detect_mojibake(item.get("raw_output")) for item in raw_outputs):
        quality_flags.append("dspy_output_mojibake_suspected")

    paper_record = merge_stage_outputs_to_paper_record(
        paper_basic_info=cleaned_paper_basic_info,
        global_constants=cleaned_global_constants,
        experiment_series=experiment_series_payload if isinstance(experiment_series_payload, list) else [],
        data_points=data_point_records,
        evidence_objects=evidence_payload,
        data_provenance=DataProvenance(
            source_pipeline="stage3_dspy_schema_extraction",
            quality_flags=quality_flags
            + [
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
            normalization_log=moved_top_level_logs,
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
        [data_point.model_dump() for series in validated.experiment_series for data_point in series.data_points],
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
    if raw_outputs_filename:
        write_jsonl(raw_outputs, stage3_dir / raw_outputs_filename)

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

    validation_summary = _build_validation_summary(
        validated,
        project_root,
        stage3_dir / "stage3_validation_report.md",
        schema_valid=True,
    )
    summary = {
        "stage3_dspy": "enabled",
        "stage3_mode": "live_smoke_test" if raw_outputs_filename else "live_pipeline",
        "paper_id": paper_id,
        "paper_basic_info_ok": validated.paper_basic_info is not None,
        "experiment_series_count": len(validated.experiment_series),
        "data_point_count": sum(len(series.data_points) for series in validated.experiment_series),
        "evidence_object_count": len(validated.evidence_objects),
        "run_judge": bool(dspy_settings.get("run_judge", False)),
        "stage3_dir": str(stage3_dir),
        "raw_dspy_outputs_path": str(stage3_dir / raw_outputs_filename) if raw_outputs_filename else None,
        "paper_text_limit_chars": paper_text_limit_chars,
        "max_experiment_series": max_experiment_series,
    }
    summary.update(validation_summary)
    _write_json(stage3_dir / summary_filename, summary)
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
    duplicate_evidence_ids = validate_duplicate_evidence_ids(record)
    evidence_ref_warnings = validate_evidence_refs(record)
    evidence_figure_id_mismatches = validate_evidence_figure_id_alignment(record)
    core_parameter_without_evidence = validate_core_parameter_without_evidence(record, ontology)
    extended_data_core_keys = validate_no_core_keys_in_extended_data(record, ontology)
    top_level_core_keys = validate_no_top_level_core_keys_in_global_constants(record, ontology)
    unit_warnings = validate_units_against_ontology(record, ontology)
    combined_issues = (
        canonical_key_errors
        + duplicate_ids
        + duplicate_evidence_ids
        + evidence_ref_warnings
        + evidence_figure_id_mismatches
        + core_parameter_without_evidence
        + extended_data_core_keys
        + top_level_core_keys
        + unit_warnings
    )
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
        duplicate_evidence_ids=duplicate_evidence_ids,
        evidence_ref_warnings=evidence_ref_warnings,
        evidence_figure_id_mismatches=evidence_figure_id_mismatches,
        core_parameter_without_evidence=core_parameter_without_evidence,
        extended_data_core_keys=extended_data_core_keys,
        top_level_core_keys=top_level_core_keys,
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
    duplicate_evidence_ids = validate_duplicate_evidence_ids(record)
    evidence_ref_warnings = validate_evidence_refs(record)
    evidence_figure_id_mismatches = validate_evidence_figure_id_alignment(record)
    core_parameter_without_evidence = validate_core_parameter_without_evidence(record, ontology)
    extended_data_core_keys = validate_no_core_keys_in_extended_data(record, ontology)
    top_level_core_keys = validate_no_top_level_core_keys_in_global_constants(record, ontology)
    unit_warnings = validate_units_against_ontology(record, ontology)
    return {
        "schema_valid": schema_valid,
        "canonical_key_errors_count": len(canonical_key_errors),
        "unit_warning_count": len(unit_warnings),
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_evidence_id_count": len(duplicate_evidence_ids),
        "evidence_ref_warning_count": len(evidence_ref_warnings),
        "evidence_figure_id_mismatch_count": len(evidence_figure_id_mismatches),
        "core_parameter_without_evidence_count": len(core_parameter_without_evidence),
        "extended_data_core_key_count": len(extended_data_core_keys),
        "top_level_core_key_count": len(top_level_core_keys),
        "top_level_core_key_warnings": top_level_core_keys,
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


def _append_raw_output(
    target: list[dict[str, Any]],
    *,
    step_name: str,
    module_name: str,
    result: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "step_name": step_name,
        "module_name": module_name,
        "json_parse_ok": result.error is None,
        "json_parse_error": result.error,
        "raw_output": result.raw_output,
    }
    if extra:
        payload.update(extra)
    target.append(payload)


def _error_flag(flag_name: str, error: str | None) -> str | None:
    return flag_name if error else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_text_best_effort(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


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


def _build_figure_metadata_map(
    figures: list[dict[str, Any]],
    vision_inputs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for item in figures + vision_inputs:
        figure_id = item.get("figure_id")
        if figure_id and figure_id not in metadata:
            metadata[str(figure_id)] = item
    return metadata


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


def _postprocess_paper_basic_info(
    *,
    payload: object | None,
    paper_text: str,
    source_file: Path,
) -> dict[str, Any]:
    result = payload if isinstance(payload, dict) else {}
    result = dict(result)

    head_lines = [line.strip().lstrip("#").strip() for line in paper_text[:5000].splitlines() if line.strip()]
    title_candidate = next((line for line in head_lines if _looks_like_title_line(line)), None)
    if not result.get("title"):
        result["title"] = title_candidate or source_file.stem
    if not result.get("source_file"):
        result["source_file"] = str(source_file)

    authors = result.get("authors")
    if authors is None:
        result["authors"] = []
    elif not isinstance(authors, list):
        result["authors"] = [str(authors)]

    year = result.get("year")
    if year is None:
        year_match = re.search(r"(19|20)\d{2}", source_file.stem)
        if year_match:
            result["year"] = int(year_match.group(0))

    inferred: dict[str, Any] = {}
    abstract_blob = " ".join(
        str(result.get(key) or "")
        for key in ("abstract_summary", "abstract_zh", "abstract_en")
    )
    title_blob = str(result.get("title") or "")
    keywords = [str(item) for item in result.get("keywords", []) if item]
    keyword_blob = " ".join(keywords)
    combined = f"{title_blob} {abstract_blob} {keyword_blob} {source_file.stem}"
    if not result.get("authors"):
        inferred_authors = _infer_authors_from_head_lines(head_lines)
        if inferred_authors:
            result["authors"] = inferred_authors
    if not result.get("material_system"):
        material_system = _infer_material_system(combined)
        if material_system:
            result["material_system"] = material_system
            inferred["material_system_evidence"] = "inferred_from_abstract_or_keywords"
            inferred["material_system_confidence"] = 0.45
    if not result.get("process_route"):
        process_route = _infer_process_route(combined)
        if process_route:
            result["process_route"] = process_route
            inferred["process_route_evidence"] = "inferred_from_abstract_or_keywords"
            inferred["process_route_confidence"] = 0.4
    result.update(inferred)
    return result


def _infer_material_system(text: str) -> str | None:
    lowered = text.lower()
    if (
        'alumina' in lowered
        or '\u6c27\u5316\u94dd' in text
        or '\u94dd\u6eb6\u80f6' in text
        or 'mullite' in lowered
    ):
        return 'alumina-based ceramic fiber'
    return None


def _infer_process_route(text: str) -> str | None:
    lowered = text.lower()
    if (
        'sol-gel' in lowered
        or 'sol gel' in lowered
        or '\u6eb6\u80f6-\u51dd\u80f6' in text
        or ('dry spinning' in lowered and 'sol' in lowered)
        or '\u5e72\u6cd5\u7eba\u4e1d' in text
        or '\u7eba\u4e1d' in text
    ):
        return 'sol-gel dry spinning'
    return None


def _infer_authors_from_head_lines(lines: list[str]) -> list[str]:
    separators = [',', '\uFF0C', '\u3001', ';', '\uFF1B']
    split_pattern = '[,\uFF0C\u3001;\uFF1B]'
    for line in lines[:8]:
        lowered = line.lower()
        if (
            len(line) > 60
            or '\u6458\u8981' in line
            or '\u5173\u952e\u8bcd' in line
            or 'abstract' in lowered
            or 'keyword' in lowered
            or re.match(r"^\d+(\.\d+)*", line)
        ):
            continue
        if any(token in line for token in separators):
            candidates = [part.strip() for part in re.split(split_pattern, line) if part.strip()]
            if candidates and all(1 <= len(part) <= 20 and not re.search(r"\d", part) for part in candidates):
                return candidates
    return []


def _looks_like_title_line(line: str) -> bool:
    lowered = line.lower()
    if not 4 <= len(line) <= 120:
        return False
    if re.match(r"^(abstract|摘要|关键词|keywords)\b", line, flags=re.IGNORECASE):
        return False
    if re.match(r"^\d+(\.\d+)*[\s\.、]", line):
        return False
    if re.match(r"^[ivxlcdm]+\.", lowered):
        return False
    if len(re.findall(r"[。！？!?]", line)) > 0:
        return False
    if len(line.split()) > 20:
        return False
    return True


def _coerce_data_points_payload(
    *,
    payload: object | None,
    series: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    series_index: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    datapoint_items: list[object] = []
    parse_issue: dict[str, Any] | None = None
    if isinstance(payload, list):
        datapoint_items = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("data_points"), list):
            datapoint_items = payload.get("data_points") or []
        elif _looks_like_datapoint_dict(payload):
            datapoint_items = _explode_flat_datapoint_dict(payload)
        else:
            datapoint_items = [payload]
    elif payload is not None:
        parse_issue = {
            "step_name": f"data_points_postprocess:{series_index}",
            "module_name": "ExtractDataPointsPostprocess",
            "json_parse_ok": False,
            "json_parse_error": "non_list_non_dict_data_points_payload",
            "raw_output": json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload,
        }
        return [], parse_issue

    normalized = [
        _normalize_datapoint_item(item, series=series, ontology=ontology, item_index=index)
        for index, item in enumerate(datapoint_items)
        if isinstance(item, dict)
    ]
    return normalized, parse_issue


def _looks_like_datapoint_dict(payload: dict[str, Any]) -> bool:
    known = {
        "sample_id",
        "sample_label",
        "independent_variable_values",
        "process_parameters",
        "results",
        "evidence_refs",
        "additional_parameter_records",
        "extended_data",
    }
    if known.intersection(payload.keys()):
        return True
    return any(not str(key).startswith("_") for key in payload.keys())


def _explode_flat_datapoint_dict(payload: dict[str, Any]) -> list[dict[str, Any]]:
    list_lengths = [len(value) for value in payload.values() if isinstance(value, list) and value]
    count = max(list_lengths) if list_lengths else 1
    exploded: list[dict[str, Any]] = []
    for index in range(count):
        item: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                if not value:
                    item[key] = None
                elif index < len(value):
                    item[key] = value[index]
                else:
                    item[key] = value[-1]
            else:
                item[key] = value
        exploded.append(item)
    return exploded


def _normalize_datapoint_item(
    item: dict[str, Any],
    *,
    series: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    item_index: int,
) -> dict[str, Any]:
    if any(
        key in item
        for key in (
            "independent_variable_values",
            "process_parameters",
            "results",
            "additional_parameter_records",
            "extended_data",
        )
    ):
        normalized = dict(item)
        normalized.setdefault("sample_id", f"{series.get('series_id') or 'series'}-dp-{item_index + 1}")
        normalized.setdefault("sample_label", normalized["sample_id"])
        normalized["independent_variable_values"] = _coerce_parameter_record_list(
            normalized.get("independent_variable_values"),
            ontology,
        )
        normalized.setdefault("process_parameters", {})
        normalized.setdefault("results", {})
        normalized["process_parameters"] = dict(normalized.get("process_parameters") or {})
        normalized["results"] = dict(normalized.get("results") or {})
        normalized["evidence_refs"] = list(normalized.get("evidence_refs") or [])
        normalized["additional_parameter_records"] = _coerce_parameter_record_list(
            normalized.get("additional_parameter_records"),
            ontology,
        )
        normalized.setdefault("extended_data", {})
        normalized["extended_data"] = dict(normalized.get("extended_data") or {})
        normalized["extended_data"].setdefault("parent_series_id", series.get("series_id"))
        return _structure_data_point_sections(normalized, ontology)

    sample_id = item.get("sample_id") or f"{series.get('series_id') or 'series'}-dp-{item_index + 1}"
    process_parameters: dict[str, Any] = {}
    results: dict[str, Any] = {}
    additional_parameter_records: list[dict[str, Any]] = []
    independent_variable_values: list[dict[str, Any]] = []

    for key, value in item.items():
        if key in {"sample_id", "sample_label", "evidence_refs", "extended_data"}:
            continue
        entry = ontology.get(key)
        parameter_record = {
            "canonical_key": key if entry else None,
            "raw_name": key,
            "value": value,
            "unit": entry.get("standard_unit") if entry else None,
            "raw_text": str(value) if value is not None else None,
        }
        category = str(entry.get("category", "")).lower() if entry else ""
        if key in _formability_keys():
            results[key] = value
        elif category in {
            "processing",
            "composition",
            "solution",
            "sol_process",
            "sol_property",
            "precursor_solution",
            "forming",
            "heat_treatment",
        }:
            process_parameters[key] = value
        else:
            results[key] = value
        additional_parameter_records.append(parameter_record)

    normalized = {
        "sample_id": sample_id,
        "sample_label": item.get("sample_label") or sample_id,
        "independent_variable_values": independent_variable_values,
        "process_parameters": process_parameters,
        "results": results,
        "evidence_refs": item.get("evidence_refs") or [],
        "additional_parameter_records": additional_parameter_records,
        "extended_data": {
            **dict(item.get("extended_data") or {}),
            "parent_series_id": series.get("series_id"),
        },
    }
    return _structure_data_point_sections(normalized, ontology)


def _structure_data_point_sections(
    item: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    normalized = dict(item)
    extended_data = dict(normalized.get("extended_data") or {})
    normalized["process_parameters"] = _structure_process_parameters(
        dict(normalized.get("process_parameters") or {}),
        ontology,
        extended_data,
    )
    normalized["results"] = _structure_result_sections(
        dict(normalized.get("results") or {}),
        ontology,
        extended_data,
    )
    normalized["extended_data"] = extended_data
    return normalized


def _structure_process_parameters(
    process_parameters: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    extended_data: dict[str, Any],
) -> dict[str, Any]:
    sections = {
        "precursor_solution": dict(process_parameters.get("precursor_solution") or {}),
        "forming": dict(process_parameters.get("forming") or {}),
        "heat_treatment": dict(process_parameters.get("heat_treatment") or {}),
    }
    section_names = set(sections)
    leftovers: dict[str, Any] = {}
    for key, value in process_parameters.items():
        if key in section_names:
            continue
        section_name = _map_process_parameter_section(key, ontology)
        if section_name:
            sections[section_name][key] = value
        else:
            leftovers[key] = value
    if leftovers:
        existing = dict(extended_data.get("unclassified_process_parameters") or {})
        existing.update(leftovers)
        extended_data["unclassified_process_parameters"] = existing
    return sections


def _map_process_parameter_section(
    canonical_key: str,
    ontology: dict[str, dict[str, Any]],
) -> str | None:
    category = str((ontology.get(canonical_key) or {}).get("category") or "").lower()
    if category in {"precursor_solution", "composition", "solution", "sol_process", "sol_property"}:
        return "precursor_solution"
    if category in {"forming", "processing"}:
        return "forming"
    if category == "heat_treatment":
        return "heat_treatment"
    return None


def _structure_result_sections(
    results: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    extended_data: dict[str, Any],
) -> dict[str, Any]:
    sections = {
        "formability": dict(results.get("formability") or {}),
        "phase_and_chemistry": dict(results.get("phase_and_chemistry") or {}),
        "microstructure_and_pores": dict(results.get("microstructure_and_pores") or {}),
        "mechanical_properties": dict(results.get("mechanical_properties") or {}),
        "thermal_properties": dict(results.get("thermal_properties") or {}),
        "mechanism_and_evidence": dict(results.get("mechanism_and_evidence") or {}),
    }
    section_names = set(sections)
    leftovers: dict[str, Any] = {}
    for key, value in results.items():
        if key in section_names:
            continue
        section_name = _map_result_section(key, ontology)
        if section_name:
            sections[section_name][key] = value
        else:
            leftovers[key] = value
    if leftovers:
        existing = dict(extended_data.get("unclassified_results") or {})
        existing.update(leftovers)
        extended_data["unclassified_results"] = existing
    return sections


def _map_result_section(
    canonical_key: str,
    ontology: dict[str, dict[str, Any]],
) -> str | None:
    category = str((ontology.get(canonical_key) or {}).get("category") or "").lower()
    if category == "structure":
        return "microstructure_and_pores"
    if category == "mechanical":
        return "mechanical_properties"
    if category in {"production", "forming"}:
        return "formability"
    formability_keys = _formability_keys()
    if canonical_key in formability_keys:
        return "formability"
    return None


def _formability_keys() -> set[str]:
    return {
        "spinnability",
        "fiber_forming_ability",
        "continuous_length_m",
        "spinnability_description",
        "continuous_spinning",
        "surface_quality_description",
    }


def _coerce_parameter_record_list(
    value: object | None,
    ontology: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if {"canonical_key", "raw_name", "value"} & set(value.keys()):
            return [value]
        coerced: list[dict[str, Any]] = []
        for key, item_value in value.items():
            entry = ontology.get(key)
            coerced.append(
                {
                    "canonical_key": key if entry else None,
                    "raw_name": key,
                    "value": item_value,
                    "unit": entry.get("standard_unit") if entry else None,
                    "raw_text": str(item_value) if item_value is not None else None,
                }
            )
        return coerced
    return []


def _split_evidence_objects_payload(
    *,
    payload: list[Any],
    figure_metadata_map: dict[str, dict[str, Any]],
    tables_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    table_ids = {item.get("table_id") for item in tables_summary if item.get("table_id")}
    split_payload: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ids = _extract_evidence_targets(item, figure_metadata_map, table_ids)
        if not ids:
            split_payload.append(item)
            continue
        for target in ids:
            split_payload.append(_apply_single_evidence_target(item, target, figure_metadata_map))
    return _ensure_unique_evidence_ids(split_payload)


def _extract_evidence_targets(
    item: dict[str, Any],
    figure_metadata_map: dict[str, dict[str, Any]],
    table_ids: set[str],
) -> list[dict[str, str]]:
    evidence_id_text = str(item.get("evidence_id") or "")
    caption_text = str(item.get("caption") or "")
    reference_sentences = [
        str(text)
        for text in item.get("reference_sentences", [])
        if text
    ]
    allowed_sources = [evidence_id_text, caption_text, *reference_sentences]
    targets: list[dict[str, str]] = []
    for figure_id in sorted(figure_metadata_map.keys(), key=len, reverse=True):
        if any(_contains_explicit_reference(text, figure_id) for text in allowed_sources):
            targets.append({"kind": "figure", "id": figure_id})
    for table_id in sorted(table_ids):
        if any(_contains_explicit_reference(text, table_id) for text in allowed_sources):
            targets.append({"kind": "table", "id": table_id})
    deduped: list[dict[str, str]] = []
    seen = set()
    for target in targets:
        marker = (target["kind"], target["id"])
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(target)
    return deduped


def _apply_single_evidence_target(
    item: dict[str, Any],
    target: dict[str, str],
    figure_metadata_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = dict(item)
    result["object_id"] = None
    if target["kind"] == "figure":
        metadata = figure_metadata_map.get(target["id"], {})
        result["evidence_id"] = target["id"]
        result["figure_id"] = target["id"]
        result["figure_type"] = _map_figure_type(metadata)
        result["caption"] = metadata.get("caption") or result.get("caption")
        result["object_type"] = "figure"
    else:
        result["evidence_id"] = target["id"]
        result["figure_id"] = None
        result["figure_type"] = "table"
        result["table_id"] = target["id"]
        result["object_type"] = "table"
    return result


def _contains_explicit_reference(text: str, target_id: str) -> bool:
    if not text or not target_id:
        return False
    start = text.find(target_id)
    while start != -1:
        end = start + len(target_id)
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if not before.isdigit() and not after.isdigit():
            return True
        start = text.find(target_id, start + 1)
    return False


def _ensure_unique_evidence_ids(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    grouped: dict[str, list[int]] = {}
    for index, item in enumerate(payload):
        base_id = str(item.get("evidence_id") or "").strip() or f"evidence_{index + 1}"
        item["evidence_id"] = base_id
        grouped.setdefault(base_id, []).append(index)

    for base_id, indices in grouped.items():
        if len(indices) == 1:
            continue
        for offset, item_index in enumerate(indices, start=1):
            payload[item_index]["evidence_id"] = f"{base_id}__ev{offset:02d}"

    for item in payload:
        evidence_id = str(item.get("evidence_id") or "").strip()
        if not evidence_id:
            counts["anonymous"] = counts.get("anonymous", 0) + 1
            item["evidence_id"] = f"evidence__ev{counts['anonymous']:02d}"
    return payload


def _map_figure_type(metadata: dict[str, Any]) -> str | None:
    figure_class = str(metadata.get("figure_class") or "").lower()
    caption = str(metadata.get("caption") or "")
    description = str(metadata.get("description_text") or "")
    text = f"{caption} {description}"
    if "tem" in text.lower():
        return "TEM"
    if "sem" in text.lower():
        return "SEM"
    mapping = {
        "xrd_pattern": "XRD",
        "ftir_spectrum": "FTIR",
        "raman_spectrum": "Raman",
        "mass_spectrum": "mass_spectrum",
        "rheology_curve": "rheology_curve",
        "photo_image": "photo",
        "microscopy_image": "microscopy_image",
        "elemental_mapping": "EDS",
        "thermal_analysis_plot": "TG_DSC",
    }
    return mapping.get(figure_class, metadata.get("figure_class"))


def _detect_mojibake(text: str | None) -> bool:
    if not text:
        return False
    suspicious = [
        '\u9225',
        '\u9286',
        '\u9365',
        '\u59d8',
        '\u7f01',
        '\u95c4',
        '\u95be',
        '\u6fe7',
        '\ufffd',
    ]
    hits = sum(text.count(token) for token in suspicious)
    return hits >= 3
