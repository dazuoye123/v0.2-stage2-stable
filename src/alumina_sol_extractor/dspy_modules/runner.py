"""Runner for optional Stage 3 schema_v2 DSPy extraction."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from alumina_sol_extractor.models.schema_v2 import (
    DataProvenance,
    DataPoint,
    EvidenceObject,
    ExperimentSeries,
    GlobalConstants,
    EvidenceRef,
    JsonScalar,
    ParameterRecord,
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
    prune_rejected_parameter_records,
    reject_noncanonical_records,
    validate_canonical_keys,
)
from alumina_sol_extractor.stage3.document_trim import generate_cleaned_body_markdown
from alumina_sol_extractor.stage3.procedure_sections import select_procedure_sections
from alumina_sol_extractor.stage3.report import build_stage3_validation_report
from alumina_sol_extractor.stage3.sections import (
    build_selected_sections_markdown,
    infer_selected_chapter_numbers,
    parse_markdown_sections,
    score_sections,
    select_sections,
)
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
    ExtractProcessStepsModule,
    ExtractTwoPassCoreModule,
    ExtractTwoPassDataEvidenceModule,
    ExtractUnifiedStage3Module,
    to_json_text,
)
from .settings import configure_dspy_lm, load_dspy_settings


SPECTRAL_LIST_CANONICAL_KEYS = {
    "nmr_27Al_peak_position_ppm",
    "raman_peak_position_cm_1",
    "ftir_peak_position_cm_1",
    "xrd_peak_position_2theta_deg",
    "peak_positions",
    "peak_position",
    "spectral_peak_positions",
}

PROCESS_STEP_SECTION_KEYWORDS = (
    "实验过程",
    "实验部分",
    "制备过程",
    "制备",
    "实验",
    "synthesis",
    "experimental procedure",
    "preparation",
    "fabrication",
)

SCIENTIFIC_EVIDENCE_FIGURE_CLASSES = {
    "xrd_pattern",
    "ftir_spectrum",
    "raman_spectrum",
    "thermal_analysis_plot",
    "microscopy_image",
    "mechanical_property_plot",
    "ferron_curve",
    "rheology_curve",
}

FLAT_PARAMETER_BUNDLE_KEYS = {
    "key",
    "value",
    "unit",
    "context",
    "source_text",
    "evidence_id",
    "evidence_ref",
    "series_id",
    "series_name",
    "sample",
    "sample_id",
    "sample_label",
    "parameters",
}

MANUAL_PARAMETER_KEY_ALIASES = {
    "spinning pressure": "feed_pressure_MPa",
    "spinning pressure mpa": "feed_pressure_MPa",
    "feed pressure": "feed_pressure_MPa",
    "calcination temperature": "calcination_temperature_C",
    "calcination temp": "calcination_temperature_C",
    "calcined temperature": "calcination_temperature_C",
    "peo content": "peo_content_wt_percent",
    "polyethylene oxide content": "peo_content_wt_percent",
    "pva content": "pva_content_wt_percent",
    "polyvinyl alcohol content": "pva_content_wt_percent",
    "mg/al ratio": "Mg_to_Al_molar_ratio",
    "mg:al ratio": "Mg_to_Al_molar_ratio",
    "mg to al molar ratio": "Mg_to_Al_molar_ratio",
    "magnesium to aluminum molar ratio": "Mg_to_Al_molar_ratio",
    "mg_to_al_molar_ratio": "Mg_to_Al_molar_ratio",
}

COMPACT_STAGE3_PROMPT_LIMITS = {
    "pass1_total_chars": 180000,
    "pass2_total_chars": 180000,
    "paper_text_chars": 18000,
    "procedure_sections_chars": 12000,
    "figure_summaries_chars": 12000,
    "table_summaries_chars": 8000,
    "captions_and_references_chars": 12000,
    "ontology_keys_chars": 6000,
    "stage3_core_json_chars": 24000,
}


def run_stage3_dspy_schema_extraction(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
    *,
    mode: str = "full",
    max_experiment_series: int | None = None,
    stage3_subdir: str = "stage3",
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
        stage3_dir_name=stage3_subdir,
        summary_filename=dspy_settings.get("outputs", {}).get("summary", "stage3_summary.json"),
        raw_outputs_filename=None,
        extraction_mode=mode,
        max_experiment_series=max_experiment_series,
    )


def run_stage3_dspy_smoke_test(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
    *,
    paper_text_limit_chars: int | None = None,
    max_experiment_series: int = 1,
    section_aware: bool = False,
    section_method: str = "rule",
    max_sections: int = 6,
    section_keywords: list[str] | None = None,
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
        section_aware=section_aware,
        section_method=section_method,
        max_sections=max_sections,
        section_keywords=section_keywords or [],
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
    section_aware: bool = False,
    section_method: str = "rule",
    max_sections: int = 6,
    section_keywords: list[str] | None = None,
    extraction_mode: str = "full",
) -> dict[str, Any]:
    configure_dspy_lm(dspy_settings)

    stage2_output_dir = output_dir
    figures_jsonl_path = stage2_output_dir / "figures.jsonl"
    vision_inputs_path = stage2_output_dir / "vision_inputs.jsonl"
    tables_dir = stage2_output_dir / "tables"
    stage3_dir = stage2_output_dir / stage3_dir_name
    stage3_dir.mkdir(parents=True, exist_ok=True)
    raw_outputs: list[dict[str, Any]] = []
    stage3_warnings: list[str] = []

    original_markdown_text = _read_text_best_effort(cleaned_markdown_path)
    cleaned_body_path = stage2_output_dir / "stage3_text" / "cleaned_body.md"
    try:
        trimmed = generate_cleaned_body_markdown(
            markdown_path=cleaned_markdown_path,
            paper_output_dir=stage2_output_dir,
        )
        full_paper_text = trimmed.cleaned_text or original_markdown_text
    except Exception as exc:  # noqa: BLE001
        full_paper_text = original_markdown_text
        stage3_warnings.append(f"cleaned_body_generation_failed:{type(exc).__name__}")
    effective_markdown_path = cleaned_body_path if cleaned_body_path.exists() else cleaned_markdown_path

    figures = _read_jsonl(figures_jsonl_path)
    vision_inputs = _read_jsonl(vision_inputs_path)
    tables_summary = _summarize_tables(tables_dir)
    figure_metadata_map = _build_figure_metadata_map(figures, vision_inputs)
    captions_and_references = _build_captions_and_references(figures)
    ontology_keys = get_canonical_keys(project_root)

    section_keywords = list(section_keywords or [])
    paper_text = full_paper_text
    selected_sections_text: str | None = None
    selected_section_titles: list[str] = []
    selected_chapter_numbers: set[str] = set()
    selected_section_map: list[dict[str, Any]] = []
    full_text_max_chars = _read_int_env("STAGE3_FULL_TEXT_MAX_CHARS", 30000, stage3_warnings)
    max_input_chars = _read_int_env("STAGE3_MAX_INPUT_CHARS", 60000, stage3_warnings)
    actual_section_aware = bool(section_aware or (paper_text_limit_chars is None and len(full_paper_text) > full_text_max_chars))
    if actual_section_aware:
        if section_method != "rule":
            raise RuntimeError(f"Unsupported section-aware method: {section_method}")
        parsed_sections = parse_markdown_sections(full_paper_text)
        scored_sections = score_sections(parsed_sections, custom_keywords=section_keywords)
        selected_section_map = select_sections(scored_sections, max_sections=max_sections)
        selected_section_map = _limit_selected_sections_by_chars(selected_section_map, max_chars=max_input_chars)
        selected_sections_text = build_selected_sections_markdown(selected_section_map)
        if selected_sections_text.strip():
            paper_text = selected_sections_text
        selected_section_titles = [str(item.get("title") or "") for item in selected_section_map if item.get("title")]
        selected_chapter_numbers = infer_selected_chapter_numbers(selected_section_map)
        (stage3_dir / "stage3_sections.json").write_text(
            json.dumps(parsed_sections, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (stage3_dir / "stage3_section_scores.json").write_text(
            json.dumps(scored_sections, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (stage3_dir / "stage3_selected_sections.md").write_text(
            selected_sections_text,
            encoding="utf-8",
        )

    if paper_text_limit_chars and paper_text_limit_chars > 0:
        paper_text = paper_text[:paper_text_limit_chars]

    procedure_sections, procedure_text = select_procedure_sections(full_paper_text)
    (stage3_dir / "stage3_procedure_sections.json").write_text(
        json.dumps(procedure_sections, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    scoped_inputs = _scope_stage2_evidence_inputs(
        figures=figures,
        vision_inputs=vision_inputs,
        tables_summary=tables_summary,
        selected_sections_text=selected_sections_text if actual_section_aware else None,
        selected_section_titles=selected_section_titles,
        selected_chapter_numbers=selected_chapter_numbers,
        section_keywords=section_keywords,
    )
    figures = scoped_inputs["figures"]
    vision_inputs = scoped_inputs["vision_inputs"]
    tables_summary = scoped_inputs["tables_summary"]
    figure_metadata_map = _build_figure_metadata_map(figures, vision_inputs)
    figure_summaries = _summarize_figures(figures)
    captions_and_references = _build_captions_and_references(figures)
    if actual_section_aware:
        (stage3_dir / "stage3_evidence_scope.json").write_text(
            json.dumps(scoped_inputs["scope"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (stage3_dir / "stage3_evidence_scope_review.json").write_text(
            json.dumps(scoped_inputs["review"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if extraction_mode in {"unified", "two-pass", "lite"}:
        compact_mode = "two-pass" if extraction_mode == "lite" else extraction_mode
        return _run_compact_stage3_extraction(
            extraction_mode=compact_mode,
            project_root=project_root,
            dspy_settings=dspy_settings,
            paper_id=paper_id,
            paper_text=paper_text,
            full_paper_text=full_paper_text,
            effective_markdown_path=effective_markdown_path,
            cleaned_body_path=cleaned_body_path,
            stage3_dir=stage3_dir,
            raw_outputs_filename=raw_outputs_filename,
            summary_filename=summary_filename,
            figures=figures,
            figure_summaries=figure_summaries,
            figure_metadata_map=figure_metadata_map,
            vision_inputs=vision_inputs,
            tables_summary=tables_summary,
            captions_and_references=captions_and_references,
            ontology_keys=ontology_keys,
            procedure_sections=procedure_sections,
            procedure_text=procedure_text,
            max_experiment_series=max_experiment_series,
            actual_section_aware=actual_section_aware,
            stage3_warnings=stage3_warnings,
        )

    paper_basic_info_result = ExtractPaperBasicInfoModule().run(
        paper_text_head=paper_text[: max(2000, int(dspy_settings.get("chunk_size", 4000)))],
        source_file=str(effective_markdown_path),
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
    process_steps_payload: list[dict[str, Any]] = []
    if procedure_text.strip():
        process_steps_result = ExtractProcessStepsModule().run(
            procedure_text=procedure_text[:12000],
            paper_basic_info_json=to_json_text(paper_basic_info_result.payload or {}),
        )
        _append_raw_output(
            raw_outputs,
            step_name="process_steps",
            module_name="ExtractProcessStepsModule",
            result=process_steps_result,
        )
        process_steps_payload = _normalize_process_steps_payload(
            _coerce_list_payload(process_steps_result.payload, "process_steps")
        )
        if not process_steps_payload:
            process_steps_payload = _build_rule_based_process_steps_v2(procedure_text)
            if process_steps_payload:
                raw_outputs.append(
                    {
                        "step_name": "process_steps",
                        "module_name": "rule_based_procedure_fallback",
                        "json_parse_ok": True,
                        "json_parse_error": None,
                        "raw_output": json.dumps(process_steps_payload, ensure_ascii=False),
                        "warning": "llm_process_steps_empty_used_rule_based_fallback",
                    }
                )
    else:
        stage3_warnings.append("procedure_text_not_found")
        raw_outputs.append(
            {
                "step_name": "process_steps",
                "module_name": "ExtractProcessStepsModule",
                "json_parse_ok": True,
                "json_parse_error": None,
                "raw_output": "[]",
                "warning": "procedure_text_not_found",
            }
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
        source_file=effective_markdown_path,
    )
    ontology_map = get_ontology_entry_map(project_root)
    cleaned_global_constants, moved_top_level_logs = move_top_level_core_keys_from_global_constants(
        global_constants_result.payload,
        ontology_map,
    )
    evidence_payload = _split_evidence_objects_payload(
        payload=evidence_objects_result.payload,
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
        process_steps=process_steps_payload,
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
    paper_record = _backfill_core_parameter_evidence(
        record=paper_record,
        ontology=ontology_map,
        tables_summary=tables_summary,
        cleaned_markdown_text=full_paper_text,
    )
    validated = _validate_stage3_record(paper_record, project_root, stage3_dir)
    llm_call_count = _estimate_stage3_llm_call_count(
        mode="full",
        experiment_series_count=len(experiment_series_payload if isinstance(experiment_series_payload, list) else []),
        process_steps_called=bool(procedure_text.strip()),
        run_judge=bool(dspy_settings.get("run_judge", False)),
    )
    return _finalize_stage3_outputs(
        validated=validated,
        project_root=project_root,
        dspy_settings=dspy_settings,
        stage3_dir=stage3_dir,
        summary_filename=summary_filename,
        raw_outputs=raw_outputs,
        raw_outputs_filename=raw_outputs_filename,
        paper_text=paper_text,
        full_paper_text=full_paper_text,
        cleaned_body_path=cleaned_body_path,
        paper_id=paper_id,
        paper_text_limit_chars=paper_text_limit_chars,
        max_experiment_series=max_experiment_series,
        actual_section_aware=actual_section_aware,
        stage3_warnings=stage3_warnings,
        stage3_mode="live_smoke_test" if raw_outputs_filename else "full",
        llm_call_count=llm_call_count,
        ontology_keys=ontology_keys,
        extra_summary_fields=None,
    )


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


def _run_compact_stage3_extraction(
    *,
    extraction_mode: str,
    project_root: Path,
    dspy_settings: dict[str, Any],
    paper_id: str,
    paper_text: str,
    full_paper_text: str,
    effective_markdown_path: Path,
    cleaned_body_path: Path,
    stage3_dir: Path,
    raw_outputs_filename: str | None,
    summary_filename: str,
    figures: list[dict[str, Any]],
    figure_summaries: list[dict[str, Any]],
    figure_metadata_map: dict[str, dict[str, Any]],
    vision_inputs: list[dict[str, Any]],
    tables_summary: list[dict[str, Any]],
    captions_and_references: list[dict[str, Any]],
    ontology_keys: list[str],
    procedure_sections: list[dict[str, Any]],
    procedure_text: str,
    max_experiment_series: int | None,
    actual_section_aware: bool,
    stage3_warnings: list[str],
) -> dict[str, Any]:
    raw_outputs: list[dict[str, Any]] = []
    ontology_map = get_ontology_entry_map(project_root)
    pass1_inputs = _build_compact_stage3_prompt_inputs(
        paper_text=paper_text,
        procedure_sections=procedure_sections,
        figures=figures,
        figure_summaries=vision_inputs or figure_summaries,
        tables_summary=tables_summary,
        captions_and_references=captions_and_references,
        ontology_keys=ontology_keys,
        stage3_core_payload=None,
        pass_name="pass1",
    )

    if extraction_mode == "unified":
        unified_result = ExtractUnifiedStage3Module().run(
            paper_text=pass1_inputs["paper_text"],
            procedure_sections_json=pass1_inputs["procedure_sections_json"],
            figure_summaries=pass1_inputs["figure_summaries_json"],
            table_summaries=pass1_inputs["table_summaries_json"],
            captions_and_references=pass1_inputs["captions_and_references_json"],
            ontology_keys=pass1_inputs["ontology_keys_json"],
            source_file=str(effective_markdown_path),
        )
        _append_raw_output(
            raw_outputs,
            step_name="unified_stage3",
            module_name="ExtractUnifiedStage3Module",
            result=unified_result,
        )
        core_payload = unified_result.payload if isinstance(unified_result.payload, dict) else {}
        secondary_payload: dict[str, Any] = {}
        llm_call_count = 1
    else:
        core_result = ExtractTwoPassCoreModule().run(
            paper_text=pass1_inputs["paper_text"],
            procedure_text=pass1_inputs["procedure_text"],
            figure_summaries=pass1_inputs["figure_summaries_json"],
            table_summaries=pass1_inputs["table_summaries_json"],
            ontology_keys=pass1_inputs["ontology_keys_json"],
            source_file=str(effective_markdown_path),
        )
        _append_raw_output(
            raw_outputs,
            step_name="two_pass_core",
            module_name="ExtractTwoPassCoreModule",
            result=core_result,
        )
        core_payload = core_result.payload if isinstance(core_result.payload, dict) else {}

        if max_experiment_series and max_experiment_series > 0 and isinstance(core_payload.get("experiment_series"), list):
            core_payload = dict(core_payload)
            core_payload["experiment_series"] = core_payload.get("experiment_series", [])[:max_experiment_series]

        pass2_inputs = _build_compact_stage3_prompt_inputs(
            paper_text=paper_text,
            procedure_sections=procedure_sections,
            figures=figures,
            figure_summaries=vision_inputs or figure_summaries,
            tables_summary=tables_summary,
            captions_and_references=captions_and_references,
            ontology_keys=ontology_keys,
            stage3_core_payload=core_payload,
            pass_name="pass2",
        )

        secondary_result = ExtractTwoPassDataEvidenceModule().run(
            paper_text=pass2_inputs["paper_text"],
            stage3_core_json=pass2_inputs["stage3_core_json"],
            figure_summaries=pass2_inputs["figure_summaries_json"],
            table_summaries=pass2_inputs["table_summaries_json"],
            captions_and_references=pass2_inputs["captions_and_references_json"],
            ontology_keys=pass2_inputs["ontology_keys_json"],
        )
        _append_raw_output(
            raw_outputs,
            step_name="two_pass_data_evidence",
            module_name="ExtractTwoPassDataEvidenceModule",
            result=secondary_result,
        )
        secondary_payload = secondary_result.payload if isinstance(secondary_result.payload, dict) else {}
        llm_call_count = 2
    if extraction_mode == "unified":
        pass2_inputs = None

    experiment_series_payload = _coerce_list_payload(core_payload, "experiment_series")
    if max_experiment_series and max_experiment_series > 0:
        experiment_series_payload = experiment_series_payload[:max_experiment_series]

    data_points_payload = _coerce_list_payload(core_payload, "data_points") or _coerce_list_payload(secondary_payload, "data_points")
    data_point_records: list[dict[str, Any]] = []
    if experiment_series_payload:
        for index, series in enumerate(experiment_series_payload):
            series_payload = _select_compact_series_data_points(
                data_points_payload,
                series if isinstance(series, dict) else {},
                series_index=index,
                series_count=len(experiment_series_payload),
            )
            series_data_points, parse_issue = _coerce_data_points_payload(
                payload=series_payload,
                series=series if isinstance(series, dict) else {},
                ontology=ontology_map,
                series_index=index,
            )
            if parse_issue:
                raw_outputs.append(parse_issue)
            data_point_records.extend(series_data_points)
    elif data_points_payload:
        series_data_points, parse_issue = _coerce_data_points_payload(
            payload=data_points_payload,
            series={"series_id": "series-1"},
            ontology=ontology_map,
            series_index=0,
        )
        if parse_issue:
            raw_outputs.append(parse_issue)
        data_point_records.extend(series_data_points)

    procedure_text_for_steps = procedure_text.strip() or _extract_procedure_text(full_paper_text)
    process_steps_payload = _normalize_process_steps_payload(_coerce_list_payload(core_payload, "process_steps"))
    if (_process_steps_are_too_generic(process_steps_payload) or not process_steps_payload) and procedure_text_for_steps:
        fallback_steps = _build_rule_based_process_steps_v2(procedure_text_for_steps)
        if _fallback_process_steps_are_better(process_steps_payload, fallback_steps):
            process_steps_payload = fallback_steps
            raw_outputs.append(
                {
                    "step_name": "process_steps",
                    "module_name": "rule_based_procedure_fallback",
                    "json_parse_ok": True,
                    "json_parse_error": None,
                    "raw_output": json.dumps(process_steps_payload, ensure_ascii=False),
                    "warning": "compact_process_steps_generic_used_rule_based_fallback",
                }
            )
    elif not process_steps_payload and procedure_text_for_steps:
        process_steps_payload = _build_rule_based_process_steps_v2(procedure_text_for_steps)
        if process_steps_payload:
            raw_outputs.append(
                {
                    "step_name": "process_steps",
                    "module_name": "rule_based_procedure_fallback",
                    "json_parse_ok": True,
                    "json_parse_error": None,
                    "raw_output": json.dumps(process_steps_payload, ensure_ascii=False),
                    "warning": "compact_process_steps_empty_used_rule_based_fallback",
                }
            )
    if not process_steps_payload and not procedure_text_for_steps:
        stage3_warnings.append("procedure_text_not_found")

    evidence_source_payload: object | None
    if "evidence_objects" in secondary_payload:
        evidence_source_payload = secondary_payload.get("evidence_objects")
    else:
        evidence_source_payload = core_payload.get("evidence_objects")
    evidence_payload = _split_evidence_objects_payload(
        payload=evidence_source_payload,
        figure_metadata_map=figure_metadata_map,
        tables_summary=tables_summary,
    )
    evidence_payload = _ensure_scientific_figure_evidence_candidates(
        evidence_payload,
        figures=figures,
    )

    cleaned_paper_basic_info = _postprocess_paper_basic_info(
        payload=core_payload.get("paper_basic_info"),
        paper_text=paper_text,
        source_file=effective_markdown_path,
    )
    compact_global_constants_payload = _coerce_compact_global_constants_payload(
        core_payload.get("global_constants"),
        ontology_map,
    )
    cleaned_global_constants, moved_top_level_logs = move_top_level_core_keys_from_global_constants(
        compact_global_constants_payload,
        ontology_map,
    )

    quality_flags: list[str] = []
    if _detect_mojibake(paper_text):
        quality_flags.append("source_text_mojibake_suspected")
    if any(_detect_mojibake(item.get("raw_output")) for item in raw_outputs):
        quality_flags.append("dspy_output_mojibake_suspected")

    paper_record = merge_stage_outputs_to_paper_record(
        paper_basic_info=cleaned_paper_basic_info,
        global_constants=cleaned_global_constants,
        experiment_series=experiment_series_payload,
        data_points=data_point_records,
        process_steps=process_steps_payload,
        evidence_objects=evidence_payload,
        data_provenance=DataProvenance(
            source_pipeline=f"stage3_dspy_{extraction_mode}",
            quality_flags=quality_flags,
            notes=[],
            normalization_log=moved_top_level_logs,
        ),
    )
    paper_record = _backfill_core_parameter_evidence(
        record=paper_record,
        ontology=ontology_map,
        tables_summary=tables_summary,
        cleaned_markdown_text=full_paper_text,
    )
    validated = _validate_stage3_record(paper_record, project_root, stage3_dir)
    return _finalize_stage3_outputs(
        validated=validated,
        project_root=project_root,
        dspy_settings=dspy_settings,
        stage3_dir=stage3_dir,
        summary_filename=summary_filename,
        raw_outputs=raw_outputs,
        raw_outputs_filename=raw_outputs_filename,
        paper_text=paper_text,
        full_paper_text=full_paper_text,
        cleaned_body_path=cleaned_body_path,
        paper_id=paper_id,
        paper_text_limit_chars=None,
        max_experiment_series=max_experiment_series,
        actual_section_aware=actual_section_aware,
        stage3_warnings=stage3_warnings,
        stage3_mode=extraction_mode,
        llm_call_count=llm_call_count + (1 if dspy_settings.get("run_judge", False) else 0),
        ontology_keys=ontology_keys,
        extra_summary_fields={
            "pass1_input_chars": int(pass1_inputs["total_chars"]),
            "pass2_input_chars": int((pass2_inputs or {}).get("total_chars") or 0),
            "input_truncated": bool(pass1_inputs["input_truncated"] or ((pass2_inputs or {}).get("input_truncated") or False)),
            "truncation_reason": "; ".join(
                part
                for part in [
                    pass1_inputs.get("truncation_reason") or "",
                    (pass2_inputs or {}).get("truncation_reason") or "",
                ]
                if part
            ) or None,
        },
    )


def _finalize_stage3_outputs(
    *,
    validated: PaperExtractionRecord,
    project_root: Path,
    dspy_settings: dict[str, Any],
    stage3_dir: Path,
    summary_filename: str,
    raw_outputs: list[dict[str, Any]],
    raw_outputs_filename: str | None,
    paper_text: str,
    full_paper_text: str,
    cleaned_body_path: Path,
    paper_id: str,
    paper_text_limit_chars: int | None,
    max_experiment_series: int | None,
    actual_section_aware: bool,
    stage3_warnings: list[str],
    stage3_mode: str,
    llm_call_count: int,
    ontology_keys: list[str],
    extra_summary_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        [item.model_dump() for item in validated.process_steps],
        stage3_dir / outputs.get("process_steps", "process_steps.jsonl"),
    )
    write_jsonl(
        [item.model_dump() for item in validated.evidence_objects],
        stage3_dir / outputs.get("evidence_objects", "evidence_objects.jsonl"),
    )
    _write_json(stage3_dir / outputs.get("paper_extraction", "paper_extraction.schema_v2.json"), validated.model_dump())
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
        "stage3_mode": stage3_mode,
        "paper_id": paper_id,
        "paper_basic_info_ok": validated.paper_basic_info is not None,
        "experiment_series_count": len(validated.experiment_series),
        "data_point_count": sum(len(series.data_points) for series in validated.experiment_series),
        "process_steps_count": len(validated.process_steps),
        "evidence_object_count": len(validated.evidence_objects),
        "run_judge": bool(dspy_settings.get("run_judge", False)),
        "llm_call_count": llm_call_count,
        "stage3_dir": str(stage3_dir),
        "raw_dspy_outputs_path": str(stage3_dir / raw_outputs_filename) if raw_outputs_filename else None,
        "paper_text_limit_chars": paper_text_limit_chars,
        "max_experiment_series": max_experiment_series,
        "stage3_input_mode": "section_aware" if actual_section_aware else "full_cleaned_body",
        "cleaned_body_char_count": len(full_paper_text),
        "paper_text_char_count": len(paper_text),
        "cleaned_body_path": str(cleaned_body_path) if cleaned_body_path.exists() else None,
        "warnings": stage3_warnings,
    }
    summary.update(validation_summary)
    if extra_summary_fields:
        summary.update(extra_summary_fields)
    _write_json(stage3_dir / summary_filename, summary)
    return summary


def _estimate_stage3_llm_call_count(
    *,
    mode: str,
    experiment_series_count: int,
    process_steps_called: bool,
    run_judge: bool,
) -> int:
    if mode == "full":
        base = 5 if process_steps_called else 4
        count = base + max(0, experiment_series_count)
    elif mode == "unified":
        count = 1
    else:
        count = 2
    if run_judge:
        count += 1
    return count


def _validate_stage3_record(record: PaperExtractionRecord, project_root: Path, stage3_dir: Path) -> PaperExtractionRecord:
    ontology = get_ontology_entry_map(project_root)
    parameter_records = collect_parameter_records(record)
    accepted_records, rejected_records = reject_noncanonical_records(parameter_records, ontology)
    record = prune_rejected_parameter_records(record, ontology)
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


def _build_captions_and_references(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "figure_id": item.get("figure_id"),
            "caption": item.get("caption"),
            "reference_sentences": item.get("reference_sentences"),
        }
        for item in figures
    ]


def _scope_stage2_evidence_inputs(
    *,
    figures: list[dict[str, Any]],
    vision_inputs: list[dict[str, Any]],
    tables_summary: list[dict[str, Any]],
    selected_sections_text: str | None,
    selected_section_titles: list[str],
    selected_chapter_numbers: set[str],
    section_keywords: list[str],
) -> dict[str, Any]:
    if not selected_sections_text:
        return {
            "figures": figures,
            "vision_inputs": vision_inputs,
            "tables_summary": tables_summary,
            "scope": {
                "mode": "full_text",
                "included_figure_ids": [item.get("figure_id") for item in figures if item.get("figure_id")],
                "included_table_ids": [item.get("table_id") for item in tables_summary if item.get("table_id")],
            },
            "review": [],
        }

    normalized_selected_text = _normalize_evidence_text(selected_sections_text)
    normalized_titles = [_normalize_evidence_text(title) for title in selected_section_titles if title]
    normalized_keywords = [_normalize_evidence_text(keyword) for keyword in section_keywords if keyword]

    scoped_figures: list[dict[str, Any]] = []
    included_figure_ids: list[str] = []
    review_entries: list[dict[str, Any]] = []
    reviewed_figure_ids: list[str] = []
    figure_ids_in_scope = set()
    scoped_figure_ids = set()

    for figure in figures:
        figure_id = str(figure.get("figure_id") or "").strip()
        if not figure_id:
            continue
        scoped_figure_ids.add(figure_id)
        scientific_class = str(figure.get("figure_class") or "").strip()
        in_scope = _figure_is_in_selected_scope(
            figure,
            normalized_selected_text=normalized_selected_text,
            normalized_titles=normalized_titles,
            normalized_keywords=normalized_keywords,
            selected_chapter_numbers=selected_chapter_numbers,
        )
        if in_scope or scientific_class in SCIENTIFIC_EVIDENCE_FIGURE_CLASSES:
            scoped_figures.append(figure)
            included_figure_ids.append(figure_id)
            figure_ids_in_scope.add(figure_id)
            if not in_scope and scientific_class in SCIENTIFIC_EVIDENCE_FIGURE_CLASSES:
                review_entries.append(
                    {
                        "source_type": "figure",
                        "source_id": figure_id,
                        "reason": "force_keep_scientific_figure_candidate",
                        "figure_class": scientific_class,
                    }
                )
            continue
        review_entries.append(
            {
                "source_type": "figure",
                "source_id": figure_id,
                "reason": "outside_selected_section_scope",
                "caption": figure.get("caption"),
            }
        )
        reviewed_figure_ids.append(figure_id)

    scoped_vision_inputs = []
    for item in vision_inputs:
        figure_id = str(item.get("figure_id") or "").strip()
        if not figure_id or figure_id in figure_ids_in_scope:
            scoped_vision_inputs.append(item)
        elif figure_id:
            review_entries.append(
                {
                    "source_type": "vision_input",
                    "source_id": figure_id,
                    "reason": "vision_input_not_in_selected_scope",
                }
            )

    scoped_tables: list[dict[str, Any]] = []
    included_table_ids: list[str] = []
    reviewed_table_ids: list[str] = []
    for table in tables_summary:
        table_id = str(table.get("table_id") or "").strip()
        if not table_id:
            continue
        decision = _table_is_in_selected_scope(
            table,
            normalized_selected_text=normalized_selected_text,
            normalized_titles=normalized_titles,
            normalized_keywords=normalized_keywords,
        )
        if decision == "include":
            scoped_tables.append(table)
            included_table_ids.append(table_id)
        else:
            review_entries.append(
                {
                    "source_type": "table",
                    "source_id": table_id,
                    "reason": "table_scope_uncertain" if decision == "review" else "outside_selected_section_scope",
                }
            )
            reviewed_table_ids.append(table_id)

    return {
        "figures": scoped_figures,
        "vision_inputs": scoped_vision_inputs,
        "tables_summary": scoped_tables,
        "scope": {
            "mode": "section_aware",
            "selected_chapter_numbers": sorted(selected_chapter_numbers),
            "selected_section_titles": selected_section_titles,
            "included_figure_ids": included_figure_ids,
            "included_table_ids": included_table_ids,
            "reviewed_figure_ids": reviewed_figure_ids,
            "reviewed_table_ids": reviewed_table_ids,
        },
        "review": review_entries,
    }


def _figure_is_in_selected_scope(
    figure: dict[str, Any],
    *,
    normalized_selected_text: str,
    normalized_titles: list[str],
    normalized_keywords: list[str],
    selected_chapter_numbers: set[str],
) -> bool:
    figure_id = str(figure.get("figure_id") or "").strip()
    caption = str(figure.get("caption") or "")
    description = str(figure.get("description_text") or "")
    reference_sentences = " ".join(str(text) for text in (figure.get("reference_sentences") or []) if text)
    combined = _normalize_evidence_text(" ".join([figure_id, caption, description, reference_sentences]))
    if figure_id and _contains_explicit_reference(normalized_selected_text, _normalize_evidence_text(figure_id)):
        return True
    chapter_number = _extract_source_chapter_number(figure_id)
    if selected_chapter_numbers and chapter_number and chapter_number not in selected_chapter_numbers:
        return False
    if any(title and title in combined for title in normalized_titles):
        return True
    keyword_hits = sum(1 for keyword in normalized_keywords if keyword and keyword in combined)
    if keyword_hits >= 1:
        return True
    return not selected_chapter_numbers and bool(combined)


def _table_is_in_selected_scope(
    table: dict[str, Any],
    *,
    normalized_selected_text: str,
    normalized_titles: list[str],
    normalized_keywords: list[str],
) -> str:
    table_id = str(table.get("table_id") or "").strip()
    if table_id and _contains_explicit_reference(normalized_selected_text, _normalize_evidence_text(table_id)):
        return "include"
    row_preview = " ".join(_table_row_to_text(row) for row in (table.get("rows") or [])[:3])
    combined = _normalize_evidence_text(f"{table_id} {row_preview}")
    if any(title and title in combined for title in normalized_titles):
        return "include"
    keyword_hits = sum(1 for keyword in normalized_keywords if keyword and keyword in combined)
    if keyword_hits >= 2:
        return "include"
    return "review"


def _extract_source_chapter_number(source_id: str) -> str | None:
    text = str(source_id or "").strip()
    if not text:
        return None
    match = re.search(r"(?:图|鍥?|fig(?:ure)?\.?)\s*([1-9]\d*)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _postprocess_paper_basic_info(
    *,
    payload: object | None,
    paper_text: str,
    source_file: Path,
) -> dict[str, Any]:
    result = payload if isinstance(payload, dict) else {}
    result = dict(result)
    normalization_warnings: list[str] = []

    head_lines = [line.strip().lstrip("#").strip() for line in paper_text[:5000].splitlines() if line.strip()]
    title_candidate = next((line for line in head_lines if _looks_like_title_line(line)), None)
    if not result.get("title") and title_candidate:
        result["title"] = title_candidate
    result["title"] = (
        result.get("title_zh")
        or result.get("title_en")
        or result.get("title")
        or source_file.stem
    )
    if not result.get("source_file"):
        result["source_file"] = str(source_file)

    authors = result.get("authors")
    if authors is None:
        result["authors"] = []
        normalization_warnings.append("authors:normalized_none_to_empty_list")
    elif not isinstance(authors, list):
        result["authors"] = [str(authors)]
    if not result.get("authors") and result.get("author"):
        result["authors"] = [str(result.get("author")).strip()]

    year = result.get("year")
    if isinstance(year, str):
        year_text = year.strip()
        if not year_text:
            result["year"] = None
        elif re.fullmatch(r"(19|20)\d{2}", year_text):
            result["year"] = int(year_text)
    if year is None:
        date_text = str(result.get("date") or "").strip()
        date_match = re.match(r"((?:19|20)\d{2})", date_text)
        if date_match:
            result["year"] = int(date_match.group(1))
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
    keywords = [str(item) for item in _ensure_list(result.get("keywords"), "keywords", normalization_warnings) if item]
    result["keywords"] = keywords
    keyword_blob = " ".join(keywords)
    combined = f"{title_blob} {abstract_blob} {keyword_blob} {source_file.stem}"
    if not result.get("authors"):
        inferred_authors = _infer_authors_from_head_lines(head_lines)
        if inferred_authors:
            result["authors"] = inferred_authors
    material_system = str(result.get("material_system") or "").strip()
    if not material_system or material_system == "alumina-based ceramic fiber":
        material_system = _infer_material_system(combined)
        if material_system:
            result["material_system"] = material_system
            inferred["material_system_evidence"] = "inferred_from_abstract_or_keywords"
            inferred["material_system_confidence"] = 0.45
    process_route = str(result.get("process_route") or "").strip()
    if not process_route or process_route == "sol-gel dry spinning":
        process_route = _infer_process_route(combined)
        if process_route:
            result["process_route"] = process_route
            inferred["process_route_evidence"] = "inferred_from_abstract_or_keywords"
            inferred["process_route_confidence"] = 0.4
    if normalization_warnings:
        existing_warnings = _ensure_list(result.get("normalization_warnings"), "normalization_warnings", [])
        result["normalization_warnings"] = [*existing_warnings, *normalization_warnings]
    result.update(inferred)
    return result


def _coerce_compact_global_constants_payload(
    payload: object | None,
    ontology: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = dict(payload) if isinstance(payload, dict) else {}
    raw_materials = result.get("raw_materials")
    if isinstance(raw_materials, dict):
        result["raw_materials"] = [
            {
                "material_id": f"raw-material-{index + 1}",
                "role": str(key),
                "name": str(value) if value not in (None, "") else str(key),
                "note": None if value in (None, "") else f"{key}: {value}",
            }
            for index, (key, value) in enumerate(raw_materials.items())
        ]
    elif isinstance(raw_materials, list):
        normalized_raw_materials = []
        for index, item in enumerate(raw_materials, start=1):
            if isinstance(item, dict):
                normalized_raw_materials.append(item)
            elif item not in (None, ""):
                normalized_raw_materials.append({"material_id": f"raw-material-{index}", "name": str(item)})
        result["raw_materials"] = normalized_raw_materials

    characterization_methods = result.get("characterization_methods")
    if isinstance(characterization_methods, list):
        normalized_methods = []
        for item in characterization_methods:
            if isinstance(item, dict):
                normalized_methods.append(item)
            elif item not in (None, ""):
                normalized_methods.append({"method": str(item)})
        result["characterization_methods"] = normalized_methods

    nominal_composition = result.get("nominal_composition")
    if isinstance(nominal_composition, dict):
        result["nominal_composition"] = [
            {"component": str(key), "value": value}
            for key, value in nominal_composition.items()
        ]

    result["additional_parameter_records"] = _coerce_parameter_record_list(
        result.get("additional_parameter_records"),
        ontology,
    )
    return result


def _ensure_list(value: Any, field_name: str, warnings: list[str]) -> list[Any]:
    if value is None:
        warnings.append(f"{field_name}:normalized_none_to_empty_list")
        return []
    if isinstance(value, list):
        return value
    return [value]


def _infer_material_system(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ["fiber precursor", "fibre precursor"]) or "前驱体" in text:
        return "alumina_fiber_precursor"
    if "alumina sol" in lowered or "铝溶胶" in text or "al13" in lowered or "高 al13" in lowered:
        return "alumina_sol"
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
        "alumina sol" in lowered
        or "铝溶胶" in text
        or "al13" in lowered
        or "ferron" in lowered
        or "27al nmr" in lowered
    ) and not (
        "dry spinning" in lowered
        or "干法纺丝" in text
        or "纺丝" in text
    ):
        return "alumina sol synthesis and characterization"
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
    """Coerce two-pass/full data point payloads into legal DataPoint dicts.

    Accepted compact shapes:
    A. Standard parameter record dicts with canonical_key/raw_name/value/unit/source_text/evidence_refs
    B. Flat compact bundles: key/value/unit/context/evidence_id
    C. Dicts with ``parameters=[...]`` containing compact bundles

    This helper must never materialize pseudo records such as
    raw_name=key/value/unit/context/evidence_ref.
    """
    datapoint_items: list[object] = []
    parse_issue: dict[str, Any] | None = None
    if isinstance(payload, list):
        datapoint_items = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("data_points"), list):
            datapoint_items = payload.get("data_points") or []
        elif isinstance(payload.get("parameters"), list):
            datapoint_items = _expand_compact_parameter_bundle_list(payload)
        elif _is_structured_datapoint_payload(payload):
            datapoint_items = [payload]
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


def _select_compact_series_data_points(
    payload: list[Any],
    series: dict[str, Any],
    *,
    series_index: int,
    series_count: int,
) -> list[Any]:
    if not isinstance(payload, list) or not payload:
        return []
    series_id = str(series.get("series_id") or "").strip()
    if series_id:
        matched = [
            item
            for item in payload
            if isinstance(item, dict)
            and (
                str(item.get("series_id") or "").strip() == series_id
                or str((item.get("extended_data") or {}).get("series_id") or "").strip() == series_id
                or str((item.get("extended_data") or {}).get("parent_series_id") or "").strip() == series_id
            )
        ]
        if matched:
            return matched
    if series_count == 1 or series_index == 0:
        return payload
    return []


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


def _is_structured_datapoint_payload(payload: dict[str, Any]) -> bool:
    structured_keys = {
        "independent_variable_values",
        "process_parameters",
        "results",
        "additional_parameter_records",
        "extended_data",
    }
    return any(key in payload for key in structured_keys)


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


def _expand_compact_parameter_bundle_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    shared_fields = {
        key: deepcopy(value)
        for key, value in payload.items()
        if key not in {"parameters"} and not str(key).startswith("_")
    }
    expanded: list[dict[str, Any]] = []
    for item in payload.get("parameters") or []:
        if not isinstance(item, dict):
            continue
        merged = dict(shared_fields)
        merged.update(item)
        expanded.append(merged)
    return expanded


def _normalize_datapoint_item(
    item: dict[str, Any],
    *,
    series: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    item_index: int,
) -> dict[str, Any]:
    if _looks_like_flat_parameter_bundle_dict(item):
        return _build_datapoint_from_flat_parameter_bundle(
            item,
            series=series,
            ontology=ontology,
            item_index=item_index,
        )
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
        additional_parameter_records.extend(_split_parameter_record_dict(parameter_record, ontology))

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
        merged = _merge_split_parameter_record_rows(value, ontology)
        if merged is not None:
            return merged
        records: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            records.extend(_split_parameter_record_dict(item, ontology))
        return records
    if isinstance(value, dict):
        if _looks_like_flat_parameter_bundle_dict(value):
            return [_coerce_flat_parameter_bundle_to_record(value, ontology)]
        if {"canonical_key", "raw_name", "value"} & set(value.keys()):
            return _split_parameter_record_dict(value, ontology)
        coerced: list[dict[str, Any]] = []
        for key, item_value in value.items():
            coerced.extend(
                _split_parameter_record_dict(
                    {
                        "canonical_key": key if ontology.get(key) else None,
                        "raw_name": key,
                        "value": item_value,
                        "unit": (ontology.get(key) or {}).get("standard_unit"),
                        "raw_text": str(item_value) if item_value is not None else None,
                    },
                    ontology,
                )
            )
        return coerced
    return []


def _extract_procedure_text(markdown_text: str) -> str:
    sections = parse_markdown_sections(markdown_text)
    selected_blocks: list[str] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        normalized_title = title.lower()
        if any(keyword.lower() in normalized_title for keyword in PROCESS_STEP_SECTION_KEYWORDS):
            text = str(section.get("text") or "").strip()
            if text:
                selected_blocks.append(text)
    if selected_blocks:
        return "\n\n".join(selected_blocks).strip()

    lowered = markdown_text.lower()
    fallback_markers = ["实验过程", "experimental procedure", "preparation", "fabrication"]
    marker_index = next((lowered.find(marker.lower()) for marker in fallback_markers if lowered.find(marker.lower()) >= 0), -1)
    if marker_index >= 0:
        return markdown_text[marker_index : marker_index + 6000].strip()
    return ""


def _looks_like_flat_parameter_bundle_dict(item: dict[str, Any]) -> bool:
    keys = {str(key).strip().lower() for key in item.keys()}
    return "key" in keys and "value" in keys and keys.issubset(FLAT_PARAMETER_BUNDLE_KEYS | {"extended_data"})


def _normalize_alias_token(value: str) -> str:
    text = re.sub(r"[\s_\-]+", " ", str(value or "").strip().casefold())
    text = re.sub(r"[^\w/%:+\. ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _resolve_canonical_key(raw_key: str | None, ontology: dict[str, dict[str, Any]]) -> str | None:
    candidate = str(raw_key or "").strip()
    if not candidate:
        return None
    if candidate in ontology:
        return candidate

    normalized_candidate = _normalize_alias_token(candidate)
    manual = MANUAL_PARAMETER_KEY_ALIASES.get(normalized_candidate)
    if manual and manual in ontology:
        return manual

    for canonical_key, entry in ontology.items():
        if normalized_candidate == _normalize_alias_token(canonical_key):
            return canonical_key
        aliases: list[str] = [canonical_key]
        for field_name in ("aliases_en", "aliases_zh", "en_aliases", "zh_aliases"):
            aliases.extend(str(alias) for alias in (entry.get(field_name) or []) if alias)
        for field_name in ("zh_name", "en_name"):
            alias = entry.get(field_name)
            if alias:
                aliases.append(str(alias))
        if any(normalized_candidate == _normalize_alias_token(alias) for alias in aliases):
            return canonical_key
    return None


def _normalize_bundle_scalar_value(
    *,
    canonical_key: str | None,
    value: Any,
    source_text: str | None,
) -> tuple[JsonScalar, str | None, str | None]:
    if isinstance(value, list) and _is_list_valued_spectral_key(str(canonical_key or "")):
        return None, json.dumps(value, ensure_ascii=False), "raw_list_value_preserved_unmaterialized; split_required_for_spectral_series"
    if isinstance(value, list):
        return None, json.dumps(value, ensure_ascii=False), "raw_list_value_preserved_unmaterialized; needs_manual_review"
    if isinstance(value, dict):
        return None, json.dumps(value, ensure_ascii=False, sort_keys=True), "raw_dict_value_preserved_unmaterialized; needs_manual_review"
    if source_text:
        return value, source_text, None
    return value, (str(value) if value is not None else None), None


def _coerce_flat_parameter_bundle_to_record(
    item: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    raw_key = str(item.get("key") or "").strip()
    canonical_key = _resolve_canonical_key(raw_key, ontology)
    source_text = str(item.get("context") or item.get("source_text") or "").strip() or None
    evidence_id = str(item.get("evidence_id") or item.get("evidence_ref") or "").strip() or None
    normalized_value, normalized_raw_text, normalization_note = _normalize_bundle_scalar_value(
        canonical_key=canonical_key,
        value=item.get("value"),
        source_text=source_text,
    )
    record: dict[str, Any] = {
        "canonical_key": canonical_key,
        "raw_name": raw_key or None,
        "value": normalized_value,
        "unit": item.get("unit") or ((ontology.get(canonical_key or raw_key) or {}).get("standard_unit") if (canonical_key or raw_key) else None),
        "raw_text": normalized_raw_text,
        "evidence_refs": _build_evidence_refs_from_flat_bundle(evidence_id, source_text),
    }
    if normalization_note:
        record["normalization_note"] = normalization_note
    if raw_key and canonical_key is None:
        record["needs_ontology_extension"] = True
        record["normalization_note"] = _append_normalization_note(
            record.get("normalization_note"),
            "two_pass_flat_bundle_unknown_key",
        )
    return record


def _build_evidence_refs_from_flat_bundle(
    evidence_id: str | None,
    source_text: str | None,
) -> list[dict[str, Any]]:
    if not evidence_id and not source_text:
        return []
    ref: dict[str, Any] = {}
    if evidence_id:
        ref["source_id"] = evidence_id
        lowered = evidence_id.lower()
        if lowered.startswith("fig") or "图" in evidence_id:
            ref["figure_id"] = evidence_id
        elif lowered.startswith("table") or "表" in evidence_id:
            ref["table_id"] = evidence_id
    if source_text:
        ref["quote_or_context"] = source_text
    return [ref]


def _merge_split_parameter_record_rows(
    value: list[Any],
    ontology: dict[str, dict[str, Any]],
) -> list[dict[str, Any]] | None:
    rows = [item for item in value if isinstance(item, dict)]
    if not rows:
        return None
    raw_names = [str(item.get("raw_name") or "").strip().lower() for item in rows]
    if not raw_names or not any(name == "key" for name in raw_names):
        return None
    if not all(name in FLAT_PARAMETER_BUNDLE_KEYS for name in raw_names):
        return None

    merged_records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for item in rows:
        raw_name = str(item.get("raw_name") or "").strip().lower()
        if raw_name == "key" and current.get("key"):
            merged_records.append(_coerce_flat_parameter_bundle_to_record(current, ontology))
            current = {}
        current[raw_name] = item.get("value")
    if current.get("key"):
        merged_records.append(_coerce_flat_parameter_bundle_to_record(current, ontology))
    return merged_records


def _build_datapoint_from_flat_parameter_bundle(
    item: dict[str, Any],
    *,
    series: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
    item_index: int,
) -> dict[str, Any]:
    sample_id = item.get("sample_id") or f"{series.get('series_id') or 'series'}-dp-{item_index + 1}"
    sample_label = item.get("sample_label") or item.get("sample") or sample_id
    parameter_record = _coerce_flat_parameter_bundle_to_record(item, ontology)
    canonical_key = str(parameter_record.get("canonical_key") or parameter_record.get("raw_name") or "").strip()
    value = parameter_record.get("value")
    process_parameters: dict[str, Any] = {}
    results: dict[str, Any] = {}
    entry = ontology.get(canonical_key) if canonical_key else None
    category = str((entry or {}).get("category") or "").lower()
    if canonical_key in _formability_keys():
        results[canonical_key] = value
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
        process_parameters[canonical_key or str(parameter_record.get("raw_name") or "unknown_parameter")] = value
    else:
        results[canonical_key or str(parameter_record.get("raw_name") or "unknown_parameter")] = value

    normalized = {
        "sample_id": sample_id,
        "sample_label": sample_label,
        "independent_variable_values": [],
        "process_parameters": process_parameters,
        "results": results,
        "evidence_refs": parameter_record.get("evidence_refs") or [],
        "additional_parameter_records": [parameter_record],
        "extended_data": {
            **dict(item.get("extended_data") or {}),
            "parent_series_id": series.get("series_id"),
            **({"series_name": item.get("series_name")} if item.get("series_name") else {}),
        },
    }
    return _structure_data_point_sections(normalized, ontology)


def _build_compact_stage3_prompt_inputs(
    *,
    paper_text: str,
    procedure_sections: list[dict[str, Any]],
    figures: list[dict[str, Any]],
    figure_summaries: list[dict[str, Any]],
    tables_summary: list[dict[str, Any]],
    captions_and_references: list[dict[str, Any]],
    ontology_keys: list[str],
    stage3_core_payload: dict[str, Any] | None,
    pass_name: str,
) -> dict[str, Any]:
    limits = COMPACT_STAGE3_PROMPT_LIMITS
    reasons: list[str] = []

    paper_text_limited, paper_trimmed = _truncate_prompt_text(paper_text, limits["paper_text_chars"])
    if paper_trimmed:
        reasons.append("paper_text")

    procedure_sections_json, procedure_trimmed = _serialize_trimmed_json(
        _compact_procedure_sections_for_prompt(procedure_sections),
        limits["procedure_sections_chars"],
    )
    if procedure_trimmed:
        reasons.append("procedure_sections")

    figure_summaries_json, figures_trimmed = _serialize_trimmed_json(
        _compact_figure_summaries_for_prompt(figures or figure_summaries),
        limits["figure_summaries_chars"],
    )
    if figures_trimmed:
        reasons.append("figure_summaries")

    table_summaries_json, tables_trimmed = _serialize_trimmed_json(
        _compact_tables_for_prompt(tables_summary),
        limits["table_summaries_chars"],
    )
    if tables_trimmed:
        reasons.append("table_summaries")

    captions_and_references_json, captions_trimmed = _serialize_trimmed_json(
        _compact_captions_for_prompt(captions_and_references),
        limits["captions_and_references_chars"],
    )
    if captions_trimmed:
        reasons.append("captions_and_references")

    ontology_keys_json, ontology_trimmed = _serialize_trimmed_json(
        _compact_ontology_keys_for_prompt(ontology_keys),
        limits["ontology_keys_chars"],
    )
    if ontology_trimmed:
        reasons.append("ontology_keys")

    stage3_core_json = ""
    core_trimmed = False
    if stage3_core_payload is not None:
        stage3_core_json, core_trimmed = _serialize_trimmed_json(
            _compact_stage3_core_payload_for_prompt(stage3_core_payload),
            limits["stage3_core_json_chars"],
        )
        if core_trimmed:
            reasons.append("stage3_core_json")

    total_chars = sum(
        len(value)
        for value in [
            paper_text_limited,
            procedure_sections_json,
            figure_summaries_json,
            table_summaries_json,
            captions_and_references_json,
            ontology_keys_json,
            stage3_core_json,
        ]
    )
    total_limit = limits["pass1_total_chars"] if pass_name == "pass1" else limits["pass2_total_chars"]
    if total_chars > total_limit:
        overflow = total_chars - total_limit
        # Prefer trimming evidence context first, then figures, then core json.
        fields = {
            "captions_and_references": captions_and_references_json,
            "figure_summaries": figure_summaries_json,
            "stage3_core_json": stage3_core_json,
            "table_summaries": table_summaries_json,
            "procedure_sections": procedure_sections_json,
        }
        for field_name in ("captions_and_references", "figure_summaries", "stage3_core_json", "table_summaries", "procedure_sections"):
            value = fields[field_name]
            if not value:
                continue
            shrink_by = min(len(value) // 2, overflow)
            if shrink_by <= 0:
                continue
            trimmed_value, _ = _truncate_prompt_text(value, max(2000, len(value) - shrink_by))
            fields[field_name] = trimmed_value
            overflow -= len(value) - len(trimmed_value)
            if field_name not in reasons:
                reasons.append(field_name)
            if overflow <= 0:
                break
        procedure_sections_json = fields["procedure_sections"]
        figure_summaries_json = fields["figure_summaries"]
        table_summaries_json = fields["table_summaries"]
        captions_and_references_json = fields["captions_and_references"]
        stage3_core_json = fields["stage3_core_json"]
        total_chars = sum(
            len(value)
            for value in [
                paper_text_limited,
                procedure_sections_json,
                figure_summaries_json,
                table_summaries_json,
                captions_and_references_json,
                ontology_keys_json,
                stage3_core_json,
            ]
        )

    procedure_text = _truncate_prompt_text(_compact_procedure_text_for_prompt(procedure_sections), limits["procedure_sections_chars"])[0]
    return {
        "paper_text": paper_text_limited,
        "procedure_text": procedure_text,
        "procedure_sections_json": procedure_sections_json,
        "figure_summaries_json": figure_summaries_json,
        "table_summaries_json": table_summaries_json,
        "captions_and_references_json": captions_and_references_json,
        "ontology_keys_json": ontology_keys_json,
        "stage3_core_json": stage3_core_json,
        "total_chars": total_chars,
        "input_truncated": bool(reasons),
        "truncation_reason": ",".join(reasons),
    }


def _compact_procedure_sections_for_prompt(procedure_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in procedure_sections:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "title": item.get("title"),
                "score": item.get("score"),
                "selected_for_process_steps": item.get("selected_for_process_steps"),
                "text_preview": str(item.get("text_preview") or item.get("text") or "")[:400],
            }
        )
    return compact


def _compact_procedure_text_for_prompt(procedure_sections: list[dict[str, Any]]) -> str:
    selected = []
    for item in procedure_sections:
        if not isinstance(item, dict):
            continue
        if item.get("selected_for_process_steps"):
            text = str(item.get("text") or item.get("text_preview") or "").strip()
            if text:
                selected.append(text[:1200])
    return "\n\n".join(selected).strip()


def _compact_figure_summaries_for_prompt(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in figures:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "figure_id": item.get("figure_id"),
                "figure_class": item.get("figure_class"),
                "caption": str(item.get("caption") or "")[:220],
                "reference_sentences": [str(text)[:180] for text in (item.get("reference_sentences") or [])[:1] if text],
            }
        )
    return compact


def _compact_tables_for_prompt(tables_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in tables_summary:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "table_id": item.get("table_id"),
                "row_preview": " ".join(_table_row_to_text(row) for row in (item.get("rows") or [])[:2])[:240],
            }
        )
    return compact


def _compact_captions_for_prompt(captions_and_references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in captions_and_references:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "figure_id": item.get("figure_id"),
                "caption": str(item.get("caption") or "")[:220],
                "reference_sentences": [str(text)[:180] for text in (item.get("reference_sentences") or [])[:2] if text],
            }
        )
    return compact


def _compact_ontology_keys_for_prompt(ontology_keys: list[str]) -> list[str]:
    return [str(key)[:80] for key in ontology_keys[:400]]


def _compact_stage3_core_payload_for_prompt(core_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(core_payload or {})
    experiment_series = []
    for item in _coerce_list_payload(payload, "experiment_series")[:12]:
        if not isinstance(item, dict):
            continue
        experiment_series.append(
            {
                "series_id": item.get("series_id"),
                "series_name": item.get("series_name"),
                "relevant_source_sections": (item.get("relevant_source_sections") or [])[:4],
                "relevant_figure_ids": (item.get("relevant_figure_ids") or [])[:8],
            }
        )
    process_steps = []
    for item in _coerce_list_payload(payload, "process_steps")[:12]:
        if not isinstance(item, dict):
            continue
        process_steps.append(
            {
                "step_id": item.get("step_id"),
                "action": item.get("action"),
                "action_zh": item.get("action_zh"),
                "evidence_text": str(item.get("evidence_text") or item.get("source_text") or "")[:180],
            }
        )
    return {
        "paper_basic_info": payload.get("paper_basic_info"),
        "global_constants": payload.get("global_constants"),
        "experiment_series": experiment_series,
        "process_steps": process_steps,
    }


def _serialize_trimmed_json(payload: Any, max_chars: int) -> tuple[str, bool]:
    text = to_json_text(payload)
    if len(text) <= max_chars:
        return text, False
    if isinstance(payload, list):
        working = list(payload)
        while len(working) > 1:
            candidate = to_json_text(working)
            if len(candidate) <= max_chars:
                return candidate, True
            working = working[:-1]
        text = to_json_text(working[:1])
        return _truncate_prompt_text(text, max_chars)[0], True
    return _truncate_prompt_text(text, max_chars)[0], True


def _truncate_prompt_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _read_int_env(name: str, default: int, warnings: list[str]) -> int:
    raw_value = os.environ.get(name)
    if raw_value in (None, ""):
        return default
    try:
        value = int(raw_value)
    except ValueError:
        warnings.append(f"invalid_env_{name}_using_default")
        return default
    if value <= 0:
        warnings.append(f"non_positive_env_{name}_using_default")
        return default
    return value


def _limit_selected_sections_by_chars(
    selected_sections: list[dict[str, Any]],
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    if max_chars <= 0:
        return selected_sections
    limited: list[dict[str, Any]] = []
    total_chars = 0
    for section in selected_sections:
        text = str(section.get("text") or "")
        if not text:
            continue
        if limited and total_chars + len(text) > max_chars:
            continue
        limited.append(section)
        total_chars += len(text)
        if total_chars >= max_chars:
            break
    return limited or selected_sections[:1]


def _build_rule_based_process_steps(procedure_text: str) -> list[dict[str, Any]]:
    action_verbs = (
        "称取",
        "加入",
        "滴加",
        "搅拌",
        "加热",
        "升温",
        "保温",
        "冷却",
        "过滤",
        "洗涤",
        "干燥",
        "煅烧",
        "研磨",
        "溶解",
        "配制",
        "注入",
        "纺丝",
        "收集",
    )
    fragments = re.split(r"[。\n；;]+", procedure_text)
    steps: list[dict[str, Any]] = []
    for fragment in fragments:
        sentence = fragment.strip()
        if not sentence:
            continue
        action_zh = next((verb for verb in action_verbs if verb in sentence), None)
        if not action_zh:
            continue
        steps.append(
            {
                "step_id": f"fallback-step-{len(steps) + 1:02d}",
                "step_order": len(steps) + 1,
                "action": "other",
                "action_zh": action_zh,
                "evidence_text": sentence,
                "confidence": "low",
                "needs_manual_review": True,
                "linked_parameter_keys": [],
                "created_by": "rule_based_procedure_fallback",
                "normalization_note": "rule_based_procedure_fallback",
            }
        )
    return _normalize_process_steps_payload(steps) if steps else []


def _build_rule_based_process_steps_v2(procedure_text: str) -> list[dict[str, Any]]:
    action_hints = (
        "称取",
        "加入",
        "滴加",
        "搅拌",
        "加热",
        "升温",
        "保温",
        "冷却",
        "过滤",
        "洗涤",
        "干燥",
        "煅烧",
        "烧结",
        "研磨",
        "溶解",
        "配制",
        "注入",
        "纺丝",
        "静电纺丝",
        "收集",
        "绉板彇",
        "鍔犲叆",
        "婊村姞",
        "鎼呮媽",
        "鍔犵儹",
        "鍗囨俯",
        "淇濇俯",
        "鍐峰嵈",
        "杩囨护",
        "娲楁钉",
        "骞茬嚗",
        "鐓呯儳",
        "鐑х粨",
        "鐮旂（",
        "婧惰В",
        "閰嶅埗",
        "娉ㄥ叆",
        "绾轰笣",
        "闈欑數绾轰笣",
        "鏀堕泦",
        "add",
        "added",
        "mix",
        "mixed",
        "stir",
        "stirred",
        "dissolve",
        "dissolved",
        "dropwise",
        "age",
        "aged",
        "dry",
        "dried",
        "calcine",
        "calcined",
        "heat",
        "heated",
        "sinter",
        "sintered",
        "electrospin",
        "electrospun",
        "inject",
        "injected",
        "prepare",
        "prepared",
        "synthes",
        "reflux",
        "wash",
        "washed",
        "filter",
        "filtered",
        "cool",
        "cooled",
        "collect",
        "collected",
    )
    reject_markers = (
        "研究了性能",
        "分析了结构",
        "研究意义",
        "研究进展",
        "结果与讨论",
        "性能研究",
        "研究了性能",
        "分析了结构",
        "研究意义",
        "thermal evolution",
        "results and discussion",
        "characterization was performed",
        "the results show",
        "it was observed",
        "研究进展",
        "结果与讨论",
        "性能研究",
    )
    fragments = re.split(r"[。；;]+|(?<=[.!?])\s+|\n+", procedure_text)
    steps: list[dict[str, Any]] = []
    for fragment in fragments:
        sentence = fragment.strip()
        if not sentence:
            continue
        lowered = sentence.lower()
        if any(marker.lower() in lowered for marker in reject_markers):
            continue
        if not any(hint in sentence or hint in lowered for hint in action_hints):
            continue
        inferred_action = _infer_process_action_v2(sentence)
        steps.append(
            {
                "step_id": f"fallback-step-{len(steps) + 1:02d}",
                "step_order": len(steps) + 1,
                "action": inferred_action[0] if inferred_action else "other",
                "action_zh": inferred_action[1] if inferred_action else "鍏朵粬",
                "reagent_name": _extract_reagent_name_v2(sentence),
                "condition_value": _extract_numeric_value(sentence, r"([0-9]+(?:\.[0-9]+)?)\s*(?:wt%|mol/L|M|%)"),
                "condition_unit": _extract_unit_value_v2(sentence, r"(wt%|mol/L|M|%)"),
                "duration_value": _extract_numeric_value(sentence, r"([0-9]+(?:\.[0-9]+)?)\s*(?:h|hr|hrs|hour|hours|min|mins|minutes)"),
                "duration_unit": _extract_unit_value_v2(sentence, r"(h|hr|hrs|hour|hours|min|mins|minutes)"),
                "temperature_value": _extract_numeric_value(sentence, r"([0-9]+(?:\.[0-9]+)?)\s*(?:℃|°C|C)"),
                "temperature_unit": _extract_unit_value_v2(sentence, r"(℃|°C|C)"),
                "heating_rate_value": _extract_heating_rate_value_v2(sentence),
                "heating_rate_unit": "℃/min" if _extract_heating_rate_value_v2(sentence) is not None else None,
                "evidence_text": sentence,
                "confidence": "low",
                "needs_manual_review": True,
                "linked_parameter_keys": [],
                "created_by": "rule_based_procedure_fallback_v2",
                "normalization_note": "rule_based_procedure_fallback_v2",
            }
        )
    return _normalize_process_steps_payload(steps) if steps else []


def _normalize_process_steps_payload(payload: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            normalized.append(
                {
                    "step_id": f"step-{index:02d}",
                    "step_order": index,
                    "action": "other",
                    "action_zh": "其他",
                    "evidence_text": str(item),
                    "confidence": "low",
                    "needs_manual_review": True,
                    "linked_parameter_keys": [],
                    "normalization_note": "coerced_non_object_process_step",
                }
            )
            continue
        evidence_text = (
            item.get("evidence_text")
            or item.get("source_text")
            or item.get("evidence")
            or item.get("text")
        )
        linked_parameter_keys = item.get("linked_parameter_keys")
        if linked_parameter_keys is None:
            linked_parameter_keys = []
            normalization_note = "linked_parameter_keys:normalized_none_to_empty_list"
        elif isinstance(linked_parameter_keys, list):
            normalization_note = item.get("normalization_note")
        else:
            linked_parameter_keys = [str(linked_parameter_keys)]
            normalization_note = _append_normalization_note(
                item.get("normalization_note"),
                "linked_parameter_keys:coerced_scalar_to_list",
            )
        normalized.append(
            {
                **item,
                "step_id": item.get("step_id") or f"step-{index:02d}",
                "step_order": item.get("step_order") or index,
                "action": item.get("action") or "other",
                "action_zh": item.get("action_zh") or item.get("action") or "其他",
                "reagent_formula": item.get("reagent_formula") or item.get("formula"),
                "reagent_amount": item.get("reagent_amount", item.get("amount")),
                "condition_value": item.get("condition_value", item.get("value")),
                "duration_value": item.get("duration_value", item.get("duration")),
                "temperature_value": item.get("temperature_value", item.get("temperature")),
                "heating_rate_value": item.get("heating_rate_value", item.get("heating_rate")),
                "evidence_text": str(evidence_text or "").strip() or None,
                "evidence_section": item.get("evidence_section") or item.get("section"),
                "confidence": _normalize_step_confidence(item.get("confidence")),
                "linked_parameter_keys": [str(value) for value in linked_parameter_keys if value not in (None, "")],
                "needs_manual_review": bool(item.get("needs_manual_review")) if item.get("needs_manual_review") is not None else False,
                "normalization_note": normalization_note,
            }
        )
    return _enrich_process_steps(normalized)


def _enrich_process_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for step in steps:
        expanded.extend(_expand_process_step(step))
    for index, step in enumerate(expanded, start=1):
        step["step_order"] = index
        step["step_id"] = f"step-{index:02d}"
    return expanded


def _expand_process_step(step: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(step.get("evidence_text") or step.get("description") or "").strip()
    if not text:
        return [step]
    normalized_text = _normalize_step_text(text)
    lowered = normalized_text.lower()

    if "alcl3" in lowered and ("去离子水" in normalized_text or "deionized water" in lowered):
        records = [
            _make_process_step_variant(
                step,
                action="dissolve",
                action_zh="溶解",
                reagent_name="AlCl3·6H2O",
                reagent_formula="AlCl3·6H2O",
                reagent_amount=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*mol\s*AlCl3"),
                reagent_unit="mol",
                reagent_role="aluminum_source",
                linked_parameter_keys=["aluminum_source"],
            ),
            _make_process_step_variant(
                step,
                action="dissolve",
                action_zh="溶解",
                reagent_name="去离子水",
                reagent_amount="一定量",
                reagent_role="solvent",
                linked_parameter_keys=["solvent_type"],
                needs_manual_review=True,
                note="solvent_amount_not_explicit",
            ),
        ]
        return records

    if "异丙醇铝" in normalized_text and "无水乙醇" in normalized_text:
        records = [
            _make_process_step_variant(
                step,
                action="add",
                action_zh="加入",
                reagent_name="异丙醇铝",
                reagent_formula="C9H21AlO3",
                reagent_amount=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*mol\s*异丙醇铝"),
                reagent_unit="mol",
                reagent_role="aluminum_source",
                linked_parameter_keys=["aluminum_source"],
            ),
            _make_process_step_variant(
                step,
                action="add",
                action_zh="加入",
                reagent_name="无水乙醇",
                reagent_role="solvent",
                linked_parameter_keys=["solvent_type"],
                needs_manual_review=True,
                note="solvent_amount_not_explicit",
            ),
        ]
        return records

    if "冰醋酸" in normalized_text and "盐酸" in normalized_text:
        duration = _extract_numeric_value(normalized_text, r"搅拌\s*([0-9]+(?:\.[0-9]+)?)\s*h")
        records = [
            _make_process_step_variant(
                step,
                action="add",
                action_zh="加入",
                reagent_name="冰醋酸",
                reagent_amount=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*mL\s*冰醋酸"),
                reagent_unit="mL",
                reagent_role="acid",
                linked_parameter_keys=["acid_type"],
            ),
            _make_process_step_variant(
                step,
                action="add",
                action_zh="加入",
                reagent_name="盐酸",
                reagent_amount=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*mL\s*盐酸"),
                reagent_unit="mL",
                reagent_role="acid",
                linked_parameter_keys=["acid_type"],
            ),
            _make_process_step_variant(
                step,
                action="stir",
                action_zh="搅拌",
                duration_value=duration,
                duration_unit="h" if duration is not None else None,
                product_or_outcome="透明溶胶" if "透明" in normalized_text else None,
                linked_parameter_keys=["stirring_time_h"],
            ),
        ]
        return records

    if "PVP" in normalized_text:
        return [
            _make_process_step_variant(
                step,
                action="add_polymer",
                action_zh="加入聚合物",
                reagent_name="PVP",
                reagent_amount="一定量" if "一定量" in normalized_text else None,
                reagent_role="polymer_additive",
                product_or_outcome="透明澄清的可纺性溶胶" if "可纺性溶胶" in normalized_text else None,
                linked_parameter_keys=["polymer_additive"],
                needs_manual_review="一定量" in normalized_text,
            )
        ]

    if "注射器" in normalized_text and ("静电纺丝" in normalized_text or "电纺" in normalized_text):
        records = [
            _make_process_step_variant(
                step,
                action="inject",
                action_zh="注入",
                equipment=_extract_equipment_with_volume(normalized_text, "塑料注射器"),
                linked_parameter_keys=[],
            ),
            _make_process_step_variant(
                step,
                action="electrospin",
                action_zh="静电纺丝",
                equipment="静电纺丝机",
                condition_key="applied_voltage_kV",
                condition_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*kV"),
                condition_unit="kV",
                linked_parameter_keys=["applied_voltage_kV", "collector_distance_cm", "feed_rate_ml_h"],
                note="electrospin_conditions_embedded_in_evidence_text",
            ),
            _make_process_step_variant(
                step,
                action="electrospin",
                action_zh="静电纺丝",
                equipment="静电纺丝机",
                condition_key="collector_distance_cm",
                condition_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*cm"),
                condition_unit="cm",
                linked_parameter_keys=["collector_distance_cm"],
            ),
            _make_process_step_variant(
                step,
                action="electrospin",
                action_zh="静电纺丝",
                equipment="静电纺丝机",
                condition_key="feed_rate_ml_h",
                condition_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*mL\s*/\s*h"),
                condition_unit="mL/h",
                linked_parameter_keys=["feed_rate_ml_h"],
            ),
        ]
        return records

    if "接收器" in normalized_text and ("干凝胶纤维" in normalized_text or "凝胶纤维" in normalized_text):
        return [
            _make_process_step_variant(
                step,
                action="collect",
                action_zh="收集",
                equipment="齿形接收器" if "齿形接收器" in normalized_text else "接收器",
                product_or_outcome="氧化铝干凝胶纤维" if "氧化铝干凝胶纤维" in normalized_text else "凝胶纤维",
                linked_parameter_keys=[],
            )
        ]

    if "600" in normalized_text and ("℃" in normalized_text or "°c" in lowered):
        return [
            _make_process_step_variant(
                step,
                action="heat",
                action_zh="升温保温",
                heating_rate_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*[℃°cC]+\s*/\s*min"),
                heating_rate_unit="℃/min",
                temperature_value=600.0,
                temperature_unit="℃",
                duration_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*h"),
                duration_unit="h",
                linked_parameter_keys=["heating_rate_C_min", "target_temperature_C", "holding_time_h"],
            )
        ]

    if "800" in normalized_text and ("℃" in normalized_text or "°c" in lowered):
        return [
            _make_process_step_variant(
                step,
                action="heat",
                action_zh="升温保温",
                heating_rate_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*[℃°cC]+\s*/\s*min"),
                heating_rate_unit="℃/min",
                temperature_value=800.0,
                temperature_unit="℃",
                duration_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*h"),
                duration_unit="h",
                product_or_outcome="γ-Al2O3 纤维" if ("γ-Al2O3" in normalized_text or "γ-Al2O3" in lowered) else None,
                linked_parameter_keys=["heating_rate_C_min", "target_temperature_C", "holding_time_h"],
            )
        ]

    if "1200" in normalized_text and ("煅烧" in normalized_text or "calcine" in lowered):
        return [
            _make_process_step_variant(
                step,
                action="calcine",
                action_zh="煅烧",
                temperature_value=1200.0,
                temperature_unit="℃",
                duration_value=_extract_numeric_value(normalized_text, r"([0-9]+(?:\.[0-9]+)?)\s*h"),
                duration_unit="h",
                heating_rate_value=_extract_heating_rate_value_v2(normalized_text),
                heating_rate_unit="℃/min" if _extract_heating_rate_value_v2(normalized_text) is not None else None,
                linked_parameter_keys=["target_temperature_C", "holding_time_h", "heating_rate_C_min"],
            )
        ]

    if "室温" in normalized_text and ("α-Al2O3" in normalized_text or "纳米结构纤维" in normalized_text):
        return [
            _make_process_step_variant(
                step,
                action="obtain_product",
                action_zh="冷却得到产物",
                condition_key="cooling_condition",
                condition_value="自然降至室温",
                product_or_outcome="α-Al2O3 纳米结构纤维",
                linked_parameter_keys=[],
            )
        ]

    inferred_action = _infer_process_action(normalized_text)
    if inferred_action and step.get("action") in (None, "", "other"):
        step = dict(step)
        step["action"] = inferred_action[0]
        step["action_zh"] = inferred_action[1]
    return [step]


def _make_process_step_variant(
    base_step: dict[str, Any],
    *,
    action: str,
    action_zh: str,
    reagent_name: str | None = None,
    reagent_formula: str | None = None,
    reagent_amount: Any = None,
    reagent_unit: str | None = None,
    reagent_role: str | None = None,
    condition_key: str | None = None,
    condition_value: Any = None,
    condition_unit: str | None = None,
    equipment: str | None = None,
    duration_value: Any = None,
    duration_unit: str | None = None,
    temperature_value: Any = None,
    temperature_unit: str | None = None,
    heating_rate_value: Any = None,
    heating_rate_unit: str | None = None,
    product_or_outcome: str | None = None,
    linked_parameter_keys: list[str] | None = None,
    needs_manual_review: bool | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    step = dict(base_step)
    step.update(
        {
            "action": action,
            "action_zh": action_zh,
            "reagent_name": reagent_name,
            "reagent_formula": reagent_formula,
            "reagent_amount": reagent_amount,
            "reagent_unit": reagent_unit,
            "reagent_role": reagent_role,
            "condition_key": condition_key,
            "condition_value": condition_value,
            "condition_unit": condition_unit,
            "equipment": equipment,
            "duration_value": duration_value,
            "duration_unit": duration_unit,
            "temperature_value": temperature_value,
            "temperature_unit": temperature_unit,
            "heating_rate_value": heating_rate_value,
            "heating_rate_unit": heating_rate_unit,
            "product_or_outcome": product_or_outcome,
            "linked_parameter_keys": linked_parameter_keys or [],
        }
    )
    if needs_manual_review is not None:
        step["needs_manual_review"] = needs_manual_review
    if note:
        step["normalization_note"] = _append_normalization_note(step.get("normalization_note"), note)
    return step


def _normalize_step_text(text: str) -> str:
    normalized = text.replace("~", " ")
    normalized = normalized.replace("路", "·")
    normalized = normalized.replace("掳", "℃")
    normalized = normalized.replace("伪", "α")
    normalized = normalized.replace("纬", "γ")
    normalized = normalized.replace("鈫?", "→")
    normalized = normalized.replace("  ", " ")
    return normalized


def _extract_numeric_value(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _extract_equipment_with_volume(text: str, equipment_name: str) -> str:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*mL\s*" + re.escape(equipment_name), text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} mL {equipment_name}"
    return equipment_name


def _infer_process_action(text: str) -> tuple[str, str] | None:
    if "搅拌" in text:
        return ("stir", "搅拌")
    if "静电纺丝" in text or "电纺" in text:
        return ("electrospin", "静电纺丝")
    if "煅烧" in text:
        return ("calcine", "煅烧")
    if "升温" in text:
        return ("heat", "升温保温")
    if "收集" in text:
        return ("collect", "收集")
    if "注入" in text or "注射器" in text:
        return ("inject", "注入")
    if "加入" in text:
        return ("add", "加入")
    if "溶于" in text or "溶解" in text:
        return ("dissolve", "溶解")
    if "室温" in text:
        return ("cool", "冷却")
    return None


def _infer_process_action_v2(text: str) -> tuple[str, str] | None:
    inferred = _infer_process_action(text)
    if inferred:
        return inferred
    if "称取" in text:
        return ("weigh", "称取")
    if "加入" in text:
        return ("add", "加入")
    if "滴加" in text:
        return ("add", "滴加")
    if "搅拌" in text:
        return ("stir", "搅拌")
    if "静电纺丝" in text or "纺丝" in text:
        return ("electrospin", "静电纺丝")
    if "煅烧" in text:
        return ("calcine", "煅烧")
    if "烧结" in text:
        return ("sinter", "烧结")
    if "加热" in text or "升温" in text or "保温" in text:
        return ("heat", "升温保温")
    if "过滤" in text:
        return ("filter", "过滤")
    if "洗涤" in text:
        return ("wash", "洗涤")
    if "冷却" in text:
        return ("cool", "冷却")
    if "溶解" in text:
        return ("dissolve", "溶解")
    if "配制" in text:
        return ("prepare", "制备")
    lowered = text.lower()
    if "dropwise" in lowered:
        return ("add", "婊村姞")
    if "electrospin" in lowered or "electrospun" in lowered:
        return ("electrospin", "闈欑數绾轰笣")
    if "calcine" in lowered or "calcined" in lowered:
        return ("calcine", "鐓呯儳")
    if "sinter" in lowered or "sintered" in lowered:
        return ("sinter", "鐑х粨")
    if "dissolve" in lowered or "dissolved" in lowered:
        return ("dissolve", "婧惰В")
    if "stir" in lowered or "mixed" in lowered or "mix " in lowered:
        return ("stir", "鎼呮媽")
    if "add " in lowered or "added" in lowered:
        return ("add", "鍔犲叆")
    if "dry" in lowered or "dried" in lowered:
        return ("dry", "骞茬嚗")
    if "heat" in lowered or "heated" in lowered or "reflux" in lowered:
        return ("heat", "鍗囨俯淇濇俯")
    if "filter" in lowered or "filtered" in lowered:
        return ("filter", "杩囨护")
    if "wash" in lowered or "washed" in lowered:
        return ("wash", "娲楁钉")
    if "cool" in lowered or "cooled" in lowered:
        return ("cool", "鍐峰嵈")
    if "prepare" in lowered or "prepared" in lowered or "synthes" in lowered:
        return ("prepare", "鍒跺")
    return None


def _extract_reagent_name_v2(text: str) -> str | None:
    patterns = [
        r"(PVA|PEO|PVP|TEOS|DMF|HNO3|HCl|AlCl3(?:·6H2O)?|polyvinyl alcohol|polyethylene oxide|nitric acid|hydrochloric acid)",
        r"(拟薄水铝石|硝酸铝|氯化铝|铝溶胶|氧化铝溶胶|去离子水|无水乙醇|乙醇|液体石蜡|Span 80|Tween 80)",
        r"(拟薄水铝石|硝酸铝|氯化铝|铝溶胶|氧化铝溶胶|去离子水|无水乙醇|乙醇|液体石蜡|Span 80|Tween 80)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_unit_value_v2(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def _extract_heating_rate_value_v2(text: str) -> float | None:
    normalized = (
        str(text or "")
        .replace("℃", " C ")
        .replace("°C", " C ")
        .replace("?C", " C ")
        .replace("鈩?", " C ")
        .lower()
    )
    patterns = (
        r"heating rate of\s*([0-9]+(?:\.[0-9]+)?)",
        r"([0-9]+(?:\.[0-9]+)?)\s*c\s*/\s*min",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                continue
    return None


def _process_steps_are_too_generic(steps: list[dict[str, Any]]) -> bool:
    if not steps:
        return True
    generic_count = 0
    empty_evidence_count = 0
    for step in steps:
        action = str(step.get("action") or "").strip().lower()
        if action in {"", "other", "analyze", "study", "test", "characterize", "measure"}:
            generic_count += 1
        if not str(step.get("evidence_text") or "").strip():
            empty_evidence_count += 1
    return generic_count == len(steps) or empty_evidence_count == len(steps)


def _fallback_process_steps_are_better(
    current_steps: list[dict[str, Any]],
    fallback_steps: list[dict[str, Any]],
) -> bool:
    if not fallback_steps:
        return False
    if not current_steps:
        return True
    if _process_steps_are_too_generic(current_steps):
        return True
    current_meaningful = sum(
        1 for step in current_steps if str(step.get("action") or "").strip().lower() not in {"", "other"}
    )
    fallback_meaningful = sum(
        1 for step in fallback_steps if str(step.get("action") or "").strip().lower() not in {"", "other"}
    )
    return fallback_meaningful > current_meaningful


def _normalize_step_confidence(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return None


def _append_normalization_note(existing: Any, note: str) -> str:
    base = str(existing or "").strip()
    if not base:
        return note
    if note in base:
        return base
    return f"{base}; {note}"


def _split_parameter_record_dict(
    item: dict[str, Any],
    ontology: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    record = dict(item)
    resolved_key = _resolve_canonical_key(
        str(record.get("canonical_key") or record.get("raw_name") or "").strip(),
        ontology,
    )
    if resolved_key:
        record["canonical_key"] = resolved_key
    canonical_key = str(record.get("canonical_key") or record.get("raw_name") or "").strip()
    value = record.get("value")
    if isinstance(value, list) and _is_list_valued_spectral_key(canonical_key):
        total = len(value)
        split_records: list[dict[str, Any]] = []
        for index, scalar_value in enumerate(value):
            if isinstance(scalar_value, (list, dict)):
                continue
            split_record = dict(record)
            split_record["value"] = scalar_value
            split_record["raw_text"] = json.dumps(value, ensure_ascii=False)
            split_record["normalization_note"] = _append_normalization_note(
                split_record.get("normalization_note"),
                f"split_list_valued_parameter:index={index};original_length={total}",
            )
            split_records.append(split_record)
        return split_records
    if isinstance(value, list):
        fallback = dict(record)
        fallback["value"] = None
        fallback["raw_text"] = json.dumps(value, ensure_ascii=False)
        fallback["normalization_note"] = _append_normalization_note(
            fallback.get("normalization_note"),
            "raw_list_value_preserved_unmaterialized",
        )
        return [fallback]
    if isinstance(value, dict):
        fallback = dict(record)
        fallback["value"] = None
        fallback["raw_text"] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        fallback["normalization_note"] = _append_normalization_note(
            fallback.get("normalization_note"),
            "raw_dict_value_preserved_unmaterialized",
        )
        return [fallback]
    if canonical_key == "peptization_time_h" and _looks_like_reaction_time_context(record):
        record["normalization_note"] = _append_normalization_note(
            record.get("normalization_note"),
            "possible_misclassified_reaction_time_from_peptization_time",
        )
    return [record]


def _is_list_valued_spectral_key(canonical_key: str) -> bool:
    normalized = str(canonical_key or "").strip()
    if normalized in SPECTRAL_LIST_CANONICAL_KEYS:
        return True
    lowered = normalized.lower()
    return "peak_position" in lowered or lowered.endswith("peak_positions")


def _split_evidence_objects_payload(
    *,
    payload: object | None,
    figure_metadata_map: dict[str, dict[str, Any]],
    tables_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_items = _flatten_raw_evidence_payload(payload)
    table_ids = {item.get("table_id") for item in tables_summary if item.get("table_id")}
    split_payload: list[dict[str, Any]] = []
    for raw_item in raw_items:
        item = _materialize_evidence_leaf(raw_item)
        ids = _extract_evidence_targets(item, figure_metadata_map, table_ids)
        if not ids:
            split_payload.append(_finalize_evidence_item(item, None, figure_metadata_map))
            continue
        for target in ids:
            split_payload.append(_finalize_evidence_item(item, target, figure_metadata_map))
    return _ensure_unique_evidence_ids(split_payload)


def _ensure_scientific_figure_evidence_candidates(
    evidence_payload: list[dict[str, Any]],
    *,
    figures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_figure_ids = {str(item.get("figure_id") or "").strip() for item in evidence_payload if item.get("figure_id")}
    augmented = list(evidence_payload)
    for figure in figures:
        figure_id = str(figure.get("figure_id") or "").strip()
        figure_class = str(figure.get("figure_class") or "").strip()
        if not figure_id or figure_id in existing_figure_ids:
            continue
        if figure_class not in SCIENTIFIC_EVIDENCE_FIGURE_CLASSES:
            continue
        references = [str(text).strip() for text in (figure.get("reference_sentences") or []) if str(text).strip()]
        source_text = " ".join(references[:2]) or str(figure.get("description_text") or "").strip() or str(figure.get("caption") or "").strip()
        augmented.append(
            {
                "evidence_id": figure_id,
                "figure_id": figure_id,
                "figure_type": figure_class,
                "object_type": "figure",
                "caption": figure.get("caption"),
                "source_text": source_text or None,
                "note": "fallback_stage2_scientific_figure_candidate",
            }
        )
        existing_figure_ids.add(figure_id)
    return _ensure_unique_evidence_ids(augmented)


def _flatten_raw_evidence_payload(
    payload: object | None,
    *,
    source_path: list[str] | None = None,
) -> list[dict[str, Any]]:
    path = list(source_path or [])
    if payload is None:
        return []
    if isinstance(payload, list):
        flattened: list[dict[str, Any]] = []
        for index, item in enumerate(payload):
            flattened.extend(_flatten_raw_evidence_payload(item, source_path=[*path, str(index)]))
        return flattened
    if not isinstance(payload, dict):
        return []
    if _looks_like_evidence_leaf(payload):
        item = dict(payload)
        item.setdefault("_source_path", path)
        return [item]

    flattened: list[dict[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            child = dict(value)
            if _looks_like_evidence_leaf(child):
                child.setdefault("_source_path", [*path, str(key)])
                child.setdefault("_source_group", key)
                flattened.append(child)
                continue
            flattened.extend(_flatten_raw_evidence_payload(child, source_path=[*path, str(key)]))
            continue
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    child = dict(item)
                    child.setdefault("_source_path", [*path, str(key), str(index)])
                    child.setdefault("_source_group", key)
                    flattened.extend(_flatten_raw_evidence_payload(child, source_path=child["_source_path"]))
    return flattened


def _looks_like_evidence_leaf(payload: dict[str, Any]) -> bool:
    leaf_keys = {
        "fact",
        "fact_summary",
        "evidence_source",
        "reference_text",
        "reference_sentences",
        "caption",
        "figure_id",
        "table_id",
        "evidence_id",
        "linked_facts",
        "detailed_observation",
    }
    return bool(leaf_keys.intersection(payload.keys()))


def _materialize_evidence_leaf(payload: dict[str, Any]) -> dict[str, Any]:
    item = dict(payload)
    reference_sentences = item.get("reference_sentences")
    if isinstance(reference_sentences, str):
        reference_sentences = [reference_sentences]
    elif not isinstance(reference_sentences, list):
        reference_text = str(item.get("reference_text") or "").strip()
        reference_sentences = [reference_text] if reference_text else []
    item["reference_sentences"] = [str(text).strip() for text in reference_sentences if str(text).strip()]
    fact_summary = str(item.get("fact_summary") or item.get("fact") or "").strip()
    if fact_summary:
        item["fact_summary"] = fact_summary
    detailed_observation = str(item.get("detailed_observation") or item.get("fact") or "").strip()
    if detailed_observation:
        item["detailed_observation"] = detailed_observation
    linked_facts = item.get("linked_facts")
    if isinstance(linked_facts, str):
        linked_facts = [linked_facts]
    elif not isinstance(linked_facts, list):
        linked_facts = []
    if fact_summary and fact_summary not in linked_facts:
        linked_facts.append(fact_summary)
    item["linked_facts"] = [str(text).strip() for text in linked_facts if str(text).strip()]
    source_path = item.get("_source_path") or []
    if source_path:
        item.setdefault("normalization_note", f"flattened_evidence_path:{'/'.join(source_path)}")
    return item


def _finalize_evidence_item(
    item: dict[str, Any],
    target: dict[str, str] | None,
    figure_metadata_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = dict(item)
    metadata: dict[str, Any] = {}
    if target:
        result = _apply_single_evidence_target(result, target, figure_metadata_map)
        if target["kind"] == "figure":
            metadata = figure_metadata_map.get(target["id"], {})
    elif str(result.get("type") or "").strip().lower() == "figure":
        inferred_figure_id = str(result.get("figure_id") or result.get("id") or "").strip()
        if inferred_figure_id:
            result["figure_id"] = inferred_figure_id
            metadata = figure_metadata_map.get(inferred_figure_id, {})
            if metadata:
                result["caption"] = result.get("caption") or metadata.get("caption")
                result["object_type"] = result.get("object_type") or "figure"
    result.setdefault("evidence_type", result.get("object_type"))
    if not result.get("figure_type"):
        inherited_figure_type = _stage2_figure_type(metadata)
        if inherited_figure_type:
            result["figure_type"] = inherited_figure_type
            result["normalization_note"] = _append_normalization_note(
                result.get("normalization_note"),
                "inherited_figure_type_from_stage2",
            )
        else:
            fallback_figure_type = _map_figure_type({**metadata, **result})
            if fallback_figure_type:
                result["figure_type"] = fallback_figure_type
                result["normalization_note"] = _append_normalization_note(
                    result.get("normalization_note"),
                    "fallback_figure_type_from_caption",
                )
    if not result.get("evidence_id"):
        base_id = str(result.get("figure_id") or result.get("table_id") or result.get("object_id") or "").strip()
        if base_id:
            result["evidence_id"] = base_id
    return result


def _extract_evidence_targets(
    item: dict[str, Any],
    figure_metadata_map: dict[str, dict[str, Any]],
    table_ids: set[str],
) -> list[dict[str, str]]:
    evidence_id_text = str(item.get("evidence_id") or "")
    evidence_source_text = str(item.get("evidence_source") or "")
    caption_text = str(item.get("caption") or "")
    fact_summary_text = str(item.get("fact_summary") or "")
    detailed_observation_text = str(item.get("detailed_observation") or "")
    reference_sentences = [
        str(text)
        for text in _ensure_list(item.get("reference_sentences"), "reference_sentences", [])
        if text
    ]
    allowed_sources = [
        evidence_id_text,
        evidence_source_text,
        caption_text,
        fact_summary_text,
        detailed_observation_text,
        *reference_sentences,
    ]
    targets: list[dict[str, str]] = []
    for figure_id in sorted(figure_metadata_map.keys(), key=len, reverse=True):
        if any(_contains_explicit_reference(text, figure_id) for text in allowed_sources):
            targets.append({"kind": "figure", "id": figure_id})
    for table_id in sorted(table_ids):
        aliases = _table_aliases(table_id)
        if any(_contains_explicit_reference(text, alias) for text in allowed_sources for alias in aliases):
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
        inherited_figure_type = _stage2_figure_type(metadata)
        if inherited_figure_type:
            result["figure_type"] = inherited_figure_type
            result["normalization_note"] = _append_normalization_note(
                result.get("normalization_note"),
                "inherited_figure_type_from_stage2",
            )
        else:
            fallback_figure_type = _map_figure_type(metadata)
            if fallback_figure_type:
                result["figure_type"] = fallback_figure_type
                result["normalization_note"] = _append_normalization_note(
                    result.get("normalization_note"),
                    "fallback_figure_type_from_caption",
                )
        result["caption"] = metadata.get("caption") or result.get("caption")
        result["object_type"] = "figure"
    else:
        result["evidence_id"] = target["id"]
        result["figure_id"] = None
        result["figure_type"] = "table"
        result["table_id"] = target["id"]
        result["object_type"] = "table"
    result.setdefault("note", result.get("fact_summary") or result.get("detailed_observation"))
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


def _stage2_figure_type(metadata: dict[str, Any]) -> str | None:
    for key in ("figure_class", "technique"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return None


def _append_normalization_note(existing: Any, note: str) -> str:
    existing_text = str(existing or "").strip()
    if not existing_text:
        return note
    notes = [part.strip() for part in existing_text.split(";") if part.strip()]
    if note in notes:
        return "; ".join(notes)
    notes.append(note)
    return "; ".join(notes)


def _map_figure_type(metadata: dict[str, Any]) -> str | None:
    figure_class = str(metadata.get("figure_class") or "").lower()
    technique = str(metadata.get("technique") or "").lower()
    caption = str(metadata.get("caption") or "")
    description = str(metadata.get("description_text") or "")
    fact_summary = str(metadata.get("fact_summary") or metadata.get("fact") or "")
    text = f"{caption} {description} {fact_summary}"
    lowered = text.lower()
    if "nmr" in technique or "27al" in technique:
        return "nmr_spectrum"
    if "ferron" in technique:
        return "ferron_curve"
    if "ftir" in technique or "infrared" in technique or technique == "ir":
        return "ftir_spectrum"
    if "xrd" in technique or "diffraction" in technique:
        return "xrd_pattern"
    if "raman" in technique:
        return "raman_spectrum"
    if "sem" in technique or "tem" in technique or "microscopy" in technique:
        return "microscopy"
    if "27al" in lowered or " nmr" in lowered or "nmr" in lowered:
        return "nmr_spectrum"
    if "ferron" in lowered or "al-ferron" in lowered:
        return "ferron_curve"
    if (
        "ftir" in lowered
        or "infrared" in lowered
        or "ir谱图" in lowered
        or "红外" in text
        or "傅里叶红外" in text
    ):
        return "ftir_spectrum"
    if "xrd" in lowered or "diffraction" in lowered:
        return "xrd_pattern"
    if "raman" in lowered:
        return "raman_spectrum"
    if "tem" in lowered:
        return "microscopy"
    if "sem" in lowered:
        return "microscopy"
    if "显微" in text:
        return "microscopy"
    if "spinnability" in lowered or "可纺" in text:
        return "photo_image"
    mapping = {
        "xrd_pattern": "xrd_pattern",
        "ftir_spectrum": "ftir_spectrum",
        "raman_spectrum": "raman_spectrum",
        "mass_spectrum": "mass_spectrum",
        "rheology_curve": "rheology_curve",
        "photo_image": "photo_image",
        "microscopy_image": "microscopy",
        "microscopy": "microscopy",
        "elemental_mapping": "elemental_mapping",
        "thermal_analysis_plot": "thermal_analysis_plot",
        "nmr_spectrum": "nmr_spectrum",
        "ferron_curve": "ferron_curve",
    }
    return mapping.get(figure_class, metadata.get("figure_class"))


def _backfill_core_parameter_evidence(
    *,
    record: PaperExtractionRecord,
    ontology: dict[str, dict[str, Any]],
    tables_summary: list[dict[str, Any]] | None = None,
    cleaned_markdown_text: str | None = None,
) -> PaperExtractionRecord:
    evidence_index = _build_evidence_ref_index(record)
    updated_series: list[ExperimentSeries] = []
    data_point_candidates: list[tuple[str, Any, list[EvidenceRef], str]] = []

    for series in record.experiment_series:
        updated_points: list[DataPoint] = []
        for data_point in series.data_points:
            resolved_refs = _resolve_explicit_evidence_refs(data_point.evidence_refs, evidence_index)
            updated_independent_variables = [
                _backfill_parameter_record_from_refs(
                    parameter_record,
                    resolved_refs,
                    source_note=f"inherited_from_data_point:{data_point.sample_id or 'unknown'}",
                )
                for parameter_record in data_point.independent_variable_values
            ]
            updated_additional_records = [
                _backfill_parameter_record_from_refs(
                    parameter_record,
                    resolved_refs,
                    source_note=f"inherited_from_data_point:{data_point.sample_id or 'unknown'}",
                )
                for parameter_record in data_point.additional_parameter_records
            ]
            updated_point = data_point.model_copy(
                update={
                    "independent_variable_values": updated_independent_variables,
                    "additional_parameter_records": updated_additional_records,
                }
            )
            updated_points.append(updated_point)
            data_point_candidates.extend(
                _collect_data_point_evidence_candidates(
                    updated_point,
                    resolved_refs,
                )
            )
        updated_series.append(series.model_copy(update={"data_points": updated_points}))

    updated_global_constants = record.global_constants
    if updated_global_constants:
        updated_global_records: list[ParameterRecord] = []
        for parameter_record in updated_global_constants.additional_parameter_records:
            candidate_refs, source_note = _match_parameter_record_from_candidates(
                parameter_record,
                data_point_candidates,
            )
            if not candidate_refs:
                candidate_refs, source_note = _match_parameter_record_from_evidence_objects(
                    parameter_record,
                    record.evidence_objects,
                )
            if not candidate_refs:
                candidate_refs, source_note = _match_parameter_record_from_tables(
                    parameter_record,
                    tables_summary or [],
                    record.evidence_objects,
                )
            if not candidate_refs:
                candidate_refs, source_note = _match_parameter_record_from_full_text(
                    parameter_record,
                    cleaned_markdown_text or "",
                )
            updated_global_records.append(
                _backfill_parameter_record_from_refs(
                    parameter_record,
                    candidate_refs,
                    source_note=source_note,
                    missing_reason=_missing_evidence_reason(parameter_record, ontology),
                )
            )
        updated_global_constants = updated_global_constants.model_copy(
            update={"additional_parameter_records": updated_global_records}
        )

    updated_record = record.model_copy(
        update={
            "global_constants": updated_global_constants,
            "experiment_series": updated_series,
        }
    )
    return _annotate_missing_core_parameter_evidence_reasons(updated_record, ontology)


def _annotate_missing_core_parameter_evidence_reasons(
    record: PaperExtractionRecord,
    ontology: dict[str, dict[str, Any]],
) -> PaperExtractionRecord:
    updated_series: list[ExperimentSeries] = []
    for series in record.experiment_series:
        updated_points = [
            data_point.model_copy(
                update={
                    "independent_variable_values": [
                        _ensure_missing_evidence_reason(parameter_record, ontology)
                        for parameter_record in data_point.independent_variable_values
                    ],
                    "additional_parameter_records": [
                        _ensure_missing_evidence_reason(parameter_record, ontology)
                        for parameter_record in data_point.additional_parameter_records
                    ],
                }
            )
            for data_point in series.data_points
        ]
        updated_series.append(series.model_copy(update={"data_points": updated_points}))

    updated_global_constants = record.global_constants
    if updated_global_constants:
        updated_global_constants = updated_global_constants.model_copy(
            update={
                "additional_parameter_records": [
                    _ensure_missing_evidence_reason(parameter_record, ontology)
                    for parameter_record in updated_global_constants.additional_parameter_records
                ]
            }
        )

    return record.model_copy(
        update={
            "global_constants": updated_global_constants,
            "experiment_series": updated_series,
        }
    )


def _build_evidence_ref_index(record: PaperExtractionRecord) -> dict[str, EvidenceRef]:
    index: dict[str, EvidenceRef] = {}
    for obj in record.evidence_objects:
        payload = obj.model_dump()
        evidence_id = str(obj.evidence_id or "").strip()
        figure_id = str(obj.figure_id or "").strip()
        table_id = str(payload.get("table_id") or "").strip()
        if evidence_id and figure_id:
            ref = EvidenceRef(source_id=evidence_id, figure_id=figure_id)
            for alias in {evidence_id, figure_id}:
                index.setdefault(alias, ref)
        elif evidence_id and table_id:
            ref = EvidenceRef(source_id=evidence_id, table_id=table_id)
            for alias in _table_aliases(table_id):
                index.setdefault(alias, ref)
        elif evidence_id:
            ref = EvidenceRef(source_id=evidence_id)
            index.setdefault(evidence_id, ref)
    return index


def _resolve_explicit_evidence_refs(
    evidence_refs: list[EvidenceRef | str],
    evidence_index: dict[str, EvidenceRef],
) -> list[EvidenceRef]:
    resolved: list[EvidenceRef] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for item in evidence_refs:
        if isinstance(item, EvidenceRef):
            marker = (item.source_id, item.figure_id, item.table_id)
            if marker in seen:
                continue
            seen.add(marker)
            resolved.append(item)
            continue
        if not isinstance(item, str):
            continue
        for alias, ref in evidence_index.items():
            if _contains_explicit_reference(item, alias):
                marker = (ref.source_id, ref.figure_id, ref.table_id)
                if marker in seen:
                    continue
                seen.add(marker)
                resolved.append(ref)
    figure_refs = [ref for ref in resolved if ref.figure_id]
    if figure_refs:
        return figure_refs
    return resolved


def _collect_data_point_evidence_candidates(
    data_point: DataPoint,
    resolved_refs: list[EvidenceRef],
) -> list[tuple[str, Any, list[EvidenceRef], str]]:
    candidates: list[tuple[str, Any, list[EvidenceRef], str]] = []
    source_note = f"matched_data_point_parameter:{data_point.sample_id or 'unknown'}"
    for parameter_record in [*data_point.independent_variable_values, *data_point.additional_parameter_records]:
        refs = _coerce_evidence_ref_models(parameter_record.evidence_refs) or resolved_refs
        if not refs:
            continue
        candidates.append(
            (
                str(parameter_record.canonical_key or ""),
                parameter_record.value,
                refs,
                source_note,
            )
        )
    if not resolved_refs:
        return candidates
    for candidate_key, candidate_value in _iter_data_point_scalar_values(data_point):
        candidates.append((candidate_key, candidate_value, resolved_refs, source_note))
    return candidates


def _iter_data_point_scalar_values(data_point: DataPoint) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    for container in (data_point.process_parameters, data_point.results):
        values.extend(_flatten_nested_scalar_items(container))
    return values


def _flatten_nested_scalar_items(payload: dict[str, Any] | Any) -> list[tuple[str, Any]]:
    if not isinstance(payload, dict):
        return []
    values: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            values.extend(_flatten_nested_scalar_items(value))
            continue
        if isinstance(value, list):
            continue
        values.append((str(key), value))
    return values


def _table_aliases(table_id: str) -> set[str]:
    aliases = {table_id}
    match = re.match(r"table_(\d+)$", table_id)
    if not match:
        return aliases
    digits = match.group(1)
    aliases.add(f"table_{digits}")
    aliases.add(f"table{digits}")
    aliases.add(f"表{digits}")
    aliases.add(f"表{int(digits)}")
    return aliases


def _backfill_parameter_record_from_refs(
    parameter_record: ParameterRecord,
    refs: list[EvidenceRef],
    *,
    source_note: str | None = None,
    missing_reason: str | None = None,
) -> ParameterRecord:
    if parameter_record.evidence_refs:
        return _strip_missing_evidence_reason(parameter_record)
    if refs:
        note = parameter_record.normalization_note
        if source_note:
            note = _append_normalization_note(note, source_note)
        note = _remove_normalization_note_prefix(note, "missing_evidence_reason:")
        return parameter_record.model_copy(
            update={
                "evidence_refs": refs,
                "normalization_note": note,
            }
        )
    if source_note and source_note.startswith("possible_misclassified_"):
        return parameter_record.model_copy(
            update={
                "normalization_note": _append_normalization_note(
                    parameter_record.normalization_note,
                    source_note,
                )
            }
        )
    if missing_reason:
        return parameter_record.model_copy(
            update={
                "normalization_note": _append_normalization_note(
                    parameter_record.normalization_note,
                    f"missing_evidence_reason:{missing_reason}",
                )
            }
        )
    return parameter_record


def _ensure_missing_evidence_reason(
    parameter_record: ParameterRecord,
    ontology: dict[str, dict[str, Any]],
) -> ParameterRecord:
    if parameter_record.evidence_refs:
        return _strip_missing_evidence_reason(parameter_record)
    reason = _missing_evidence_reason(parameter_record, ontology)
    if not reason:
        return parameter_record
    if "missing_evidence_reason:" in str(parameter_record.normalization_note or ""):
        return parameter_record
    return parameter_record.model_copy(
        update={
            "normalization_note": _append_normalization_note(
                parameter_record.normalization_note,
                f"missing_evidence_reason:{reason}",
            )
        }
    )


def _strip_missing_evidence_reason(parameter_record: ParameterRecord) -> ParameterRecord:
    note = _remove_normalization_note_prefix(parameter_record.normalization_note, "missing_evidence_reason:")
    if note == parameter_record.normalization_note:
        return parameter_record
    return parameter_record.model_copy(update={"normalization_note": note})


def _append_normalization_note(note: str | None, addition: str) -> str:
    existing = [part.strip() for part in str(note or "").split("; ") if part.strip()]
    if addition not in existing:
        existing.append(addition)
    return "; ".join(existing)


def _remove_normalization_note_prefix(note: str | None, prefix: str) -> str | None:
    parts = [part.strip() for part in str(note or "").split("; ") if part.strip()]
    filtered = [part for part in parts if not part.startswith(prefix)]
    if not filtered:
        return None
    return "; ".join(filtered)


def _match_parameter_record_from_candidates(
    parameter_record: ParameterRecord,
    candidates: list[tuple[str, Any, list[EvidenceRef], str]],
) -> tuple[list[EvidenceRef], str | None]:
    canonical_key = str(parameter_record.canonical_key or "")
    for candidate_key, candidate_value, candidate_refs, source_note in candidates:
        normalized_value = _normalize_candidate_value_for_target(
            target_key=canonical_key,
            candidate_key=candidate_key,
            candidate_value=candidate_value,
        )
        if normalized_value is None:
            continue
        if _parameter_values_match(parameter_record.value, normalized_value):
            return candidate_refs, source_note
    return [], None


def _match_parameter_record_from_evidence_objects(
    parameter_record: ParameterRecord,
    evidence_objects: list[EvidenceObject],
) -> tuple[list[EvidenceRef], str | None]:
    for item in evidence_objects:
        payload = item.model_dump()
        source_id = str(payload.get("evidence_id") or "").strip()
        figure_id = str(payload.get("figure_id") or "").strip() or None
        caption = str(payload.get("caption") or "").strip()
        texts = [caption]
        texts.extend(str(text).strip() for text in (payload.get("linked_facts") or []) if text)
        for text in texts:
            if not text:
                continue
            if _text_matches_parameter_record(text, parameter_record):
                return (
                    [
                        EvidenceRef(
                            source_id=source_id or None,
                            figure_id=figure_id,
                            quote_or_context=text,
                        )
                    ],
                    f"matched_evidence_object:{source_id or figure_id or 'unknown'}",
                )
    return [], None


def _match_parameter_record_from_tables(
    parameter_record: ParameterRecord,
    tables_summary: list[dict[str, Any]],
    evidence_objects: list[EvidenceObject],
) -> tuple[list[EvidenceRef], str | None]:
    captions_by_table_id = _build_table_caption_map(evidence_objects)
    for table in tables_summary:
        table_id = str(table.get("table_id") or "").strip()
        if not table_id:
            continue
        rows = table.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        caption = captions_by_table_id.get(table_id, "")
        header_text = _table_row_to_text(rows[0]) if rows else ""
        for row in rows[1:]:
            row_text = _table_row_to_text(row)
            combined_text = " ".join(part for part in [caption, header_text, row_text] if part)
            if _text_matches_parameter_record(combined_text, parameter_record):
                return (
                    [
                        EvidenceRef(
                            source_id=table_id,
                            quote_or_context=row_text,
                        )
                    ],
                    f"matched_table_output:{table_id}",
                )
    return [], None


def _build_table_caption_map(evidence_objects: list[EvidenceObject]) -> dict[str, str]:
    captions: dict[str, str] = {}
    for item in evidence_objects:
        payload = item.model_dump()
        table_id = str(payload.get("table_id") or "").strip()
        if table_id:
            captions[table_id] = str(payload.get("caption") or "")
    return captions


def _table_row_to_text(row: Any) -> str:
    if isinstance(row, dict):
        ordered_values = [str(value).strip() for _, value in sorted(row.items(), key=lambda item: item[0]) if value is not None]
        return " ".join(value for value in ordered_values if value)
    if isinstance(row, list):
        return " ".join(str(value).strip() for value in row if value is not None)
    return str(row or "").strip()


def _match_parameter_record_from_full_text(
    parameter_record: ParameterRecord,
    cleaned_markdown_text: str,
) -> tuple[list[EvidenceRef], str | None]:
    if not cleaned_markdown_text.strip():
        return [], None
    best_score: int | None = None
    best_candidate: dict[str, Any] | None = None
    for candidate in _iter_full_text_evidence_candidates(cleaned_markdown_text):
        score = _score_full_text_evidence_candidate(candidate, parameter_record)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_candidate = candidate
    threshold = _full_text_match_threshold(parameter_record)
    if best_score is None or best_candidate is None or best_score < threshold:
        if _looks_like_reaction_time_misclassification(parameter_record, cleaned_markdown_text):
            return [], "possible_misclassified_reaction_time_from_peptization_time"
        return [], None
    source_id = str(best_candidate.get("source_id") or "").strip() or None
    section = str(best_candidate.get("section") or "").strip() or None
    table_id = str(best_candidate.get("table_id") or "").strip() or None
    return (
        [
            EvidenceRef(
                source_id=source_id,
                section=section,
                table_id=table_id,
                quote_or_context=str(best_candidate.get("text") or "").strip() or None,
                confidence=round(min(0.99, best_score / 10.0), 2),
            )
        ],
        f"matched_full_text:{source_id or section or 'text'}",
    )


def _iter_full_text_evidence_candidates(cleaned_markdown_text: str) -> list[dict[str, Any]]:
    base_candidates: list[dict[str, Any]] = []
    current_section = ""
    in_reference_section = False
    active_table_id: str | None = None
    for line_index, raw_line in enumerate(cleaned_markdown_text.splitlines(), start=1):
        stripped = str(raw_line or "").strip()
        if not stripped:
            active_table_id = None
            continue
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            in_reference_section = _looks_like_reference_section(current_section)
            active_table_id = None
            continue
        table_match = re.search(r"\[TableID:\s*([^\]]+)\]", stripped, flags=re.IGNORECASE)
        if table_match:
            active_table_id = table_match.group(1).strip()
            continue
        if _is_non_evidence_markdown_line(stripped):
            continue
        source_id = active_table_id or f"text:{_slugify_section(current_section)}:{line_index}"
        base_candidates.append(
            {
                "text": stripped,
                "section": current_section or "full_text",
                "source_id": source_id,
                "table_id": active_table_id,
                "line_index": line_index,
                "is_reference": in_reference_section or _looks_like_reference_entry(stripped),
                "anchor_score": 1 if active_table_id or _contains_figure_or_table_mention(stripped) else 0,
                "location_score": 1 if _is_preferred_evidence_context(current_section, stripped, active_table_id) else 0,
                "mojibake_penalty": 2 if _detect_mojibake(stripped) else 0,
            }
        )
    candidates = list(base_candidates)
    for index, candidate in enumerate(base_candidates[:-1]):
        nxt = base_candidates[index + 1]
        if nxt["line_index"] != candidate["line_index"] + 1 or nxt["section"] != candidate["section"]:
            continue
        candidates.append(
            {
                "text": f"{candidate['text']} {nxt['text']}".strip(),
                "section": candidate["section"],
                "source_id": candidate["source_id"],
                "table_id": candidate["table_id"] or nxt["table_id"],
                "line_index": candidate["line_index"],
                "is_reference": bool(candidate["is_reference"] or nxt["is_reference"]),
                "anchor_score": max(int(candidate["anchor_score"]), int(nxt["anchor_score"])),
                "location_score": max(int(candidate["location_score"]), int(nxt["location_score"])),
                "mojibake_penalty": max(int(candidate["mojibake_penalty"]), int(nxt["mojibake_penalty"])),
            }
        )
    return candidates


def _score_full_text_evidence_candidate(candidate: dict[str, Any], parameter_record: ParameterRecord) -> int | None:
    text = str(candidate.get("text") or "").strip()
    if not text:
        return None
    normalized_text = _normalize_evidence_text(text)
    if not normalized_text:
        return None
    if (
        str(parameter_record.canonical_key or "") == "peptization_time_h"
        and _candidate_looks_like_reaction_time_without_peptization(normalized_text)
    ):
        return None
    value_score = _parameter_value_match_score(normalized_text, parameter_record)
    keyword_score = _parameter_keyword_match_score(normalized_text, parameter_record)
    unit_score = _parameter_unit_match_score(normalized_text, parameter_record)
    if value_score <= 0 or keyword_score <= 0:
        return None
    if _parameter_requires_unit(parameter_record) and unit_score <= 0:
        return None
    return (
        value_score
        + keyword_score
        + unit_score
        + int(candidate.get("anchor_score") or 0)
        + int(candidate.get("location_score") or 0)
        - (5 if candidate.get("is_reference") else 0)
        - int(candidate.get("mojibake_penalty") or 0)
    )


def _text_matches_parameter_record(text: str, parameter_record: ParameterRecord) -> bool:
    score = _score_full_text_evidence_candidate(
        {
            "text": text,
            "section": "structured_source",
            "is_reference": False,
            "anchor_score": 0,
            "location_score": 1,
            "mojibake_penalty": 0,
        },
        parameter_record,
    )
    return score is not None and score >= _full_text_match_threshold(parameter_record)


def _contains_exact_value_token(text: str, token: str) -> bool:
    if not token:
        return False
    escaped = re.escape(token)
    pattern = rf"(?<![\dA-Za-z]){escaped}(?![\dA-Za-z])"
    return re.search(pattern, text) is not None


def _parameter_keywords(canonical_key: str) -> list[str]:
    mapping = {
        "viscosity_Pa_s": ["viscosity", "spinning viscosity"],
        "aluminum_source": ["aluminum source", "aluminium isopropanol", "aluminum isopropanol", "异丙醇铝"],
        "peptizing_agent": ["peptizing agent", "peptization", "nitric acid", "concentrated nitric acid", "硝酸", "浓硝酸"],
        "hydrolysis_temperature_C": ["hydrothermal", "hydrolysis", "reaction", "reacted", "加热反应", "反应釜", "水热"],
        "hydrolysis_time_h": ["hydrothermal", "hydrolysis", "reaction", "reacted", "加热反应", "反应釜", "水热"],
        "peptization_time_h": ["peptization", "peptizing", "alumina sol", "继续搅拌", "铝溶胶", "ph"],
        "concentration_temperature_C": ["concentration", "concentrated", "water bath", "减压浓缩", "浓缩", "水浴"],
        "concentration_time_h": ["concentration", "concentrated", "减压浓缩", "浓缩"],
        "spinning_channel_temperature_C": ["spinning channel temperature", "channel temperature", "甬道空气温度", "纺丝甬道", "channel air temperature"],
        "feed_pressure_MPa": ["feed pressure", "进料压力", "pressure", "一定压力"],
        "relative_humidity_percent": ["relative humidity", "环境湿度", "humidity"],
        "average_fiber_diameter_um": ["average fiber diameter", "fiber diameter", "diameter", "平均直径", "纤维直径", "直径"],
        "tensile_strength_MPa": ["tensile strength", "breaking strength", "fracture strength", "断裂强度", "拉伸强度", "强度"],
        "service_temperature_C": ["service temperature", "使用温度", "耐温"],
        "holding_time_h": ["holding time", "holding", "保温", "保温时间"],
        "strength_retention_percent": ["strength retention", "retained strength", "强度保留率", "保留率"],
        "sintering_temperature_C": ["sinter", "sintered", "烧结", "快速烧结", "高温烧结"],
        "take_up_speed_m_min": ["take-up speed", "line speed", "收丝辊线速度", "线速度"],
        "heating_rate_C_min": ["heating rate", "升温速度", "升温"],
        "target_temperature_C": ["heat to", "heated to", "升温至", "保温", "低温煅烧"],
    }
    return mapping.get(canonical_key, [canonical_key])


def _candidate_looks_like_reaction_time_without_peptization(normalized_text: str) -> bool:
    reaction_markers = ["reaction time", "reaction duration", "反应时间"]
    peptization_markers = ["peptization", "peptizing", "胶溶", "peptizing agent"]
    return any(marker in normalized_text for marker in reaction_markers) and not any(
        marker in normalized_text for marker in peptization_markers
    )


def _looks_like_reaction_time_context(record: dict[str, Any]) -> bool:
    context_blob = " ".join(
        str(record.get(key) or "")
        for key in ("raw_name", "raw_text", "source_section", "section_id", "normalization_note")
    )
    normalized_text = _normalize_evidence_text(context_blob)
    return _candidate_looks_like_reaction_time_without_peptization(normalized_text)


def _looks_like_reaction_time_misclassification(
    parameter_record: ParameterRecord,
    cleaned_markdown_text: str,
) -> bool:
    if str(parameter_record.canonical_key or "") != "peptization_time_h":
        return False
    if parameter_record.evidence_refs:
        return False
    context_blob = f"{parameter_record.raw_name or ''} {parameter_record.raw_text or ''} {parameter_record.normalization_note or ''}"
    if _looks_like_reaction_time_context({"raw_name": context_blob}):
        return True
    normalized_text = _normalize_evidence_text(cleaned_markdown_text)
    value_tokens = _parameter_value_tokens("peptization_time_h", parameter_record.value)
    return any(token in normalized_text for token in value_tokens) and "reaction time" in normalized_text and "peptization" not in normalized_text


def _parameter_value_tokens(canonical_key: str, value: Any) -> list[str]:
    range_tokens = _coerce_range_tokens(value)
    if range_tokens:
        tokens = set(range_tokens)
        if canonical_key == "heating_rate_C_min":
            tokens.update(_attach_unit_tokens(tokens, ["degc/min"]))
        return sorted(token for token in tokens if token)
    number = _coerce_float(value)
    if number is None:
        tokens = set(_parameter_text_value_tokens(canonical_key, value))
        normalized_value = _normalize_evidence_text(str(value).strip())
        if normalized_value:
            tokens.add(normalized_value)
        return sorted(token for token in tokens if token)
    tokens = {_format_number_token(number)}
    unit_tokens: list[str] = []
    time_keys = {"holding_time_h", "hydrolysis_time_h", "peptization_time_h", "concentration_time_h"}
    if canonical_key == "tensile_strength_MPa":
        tokens.add(_format_number_token(number / 1000.0))
        unit_tokens = ["mpa", "gpa"]
    elif canonical_key in {
        "hydrolysis_temperature_C",
        "concentration_temperature_C",
        "drying_temperature_C",
        "spinning_channel_temperature_C",
        "service_temperature_C",
        "sintering_temperature_C",
        "target_temperature_C",
    }:
        unit_tokens = ["degc"]
    elif canonical_key == "feed_pressure_MPa":
        unit_tokens = ["mpa"]
    elif canonical_key in {"relative_humidity_percent", "strength_retention_percent"}:
        unit_tokens = ["%"]
    elif canonical_key in time_keys:
        unit_tokens = ["h", "min"]
        minutes_value = number * 60.0
        if abs(minutes_value - round(minutes_value)) < 1e-9:
            tokens.add(_format_number_token(minutes_value))
    elif canonical_key == "average_fiber_diameter_um":
        unit_tokens = ["um"]
    elif canonical_key == "take_up_speed_m_min":
        unit_tokens = ["m/min"]
    elif canonical_key == "heating_rate_C_min":
        unit_tokens = ["degc/min"]
    if unit_tokens:
        tokens.update(_attach_unit_tokens(tokens, unit_tokens))
    return sorted(token for token in tokens if token)


def _parameter_text_value_tokens(canonical_key: str, value: Any) -> list[str]:
    mapping = {
        "aluminum_source": ["aluminium isopropanol", "aluminum isopropanol", "异丙醇铝"],
        "peptizing_agent": ["nitric acid", "concentrated nitric acid", "硝酸", "浓硝酸"],
    }
    tokens = [_normalize_evidence_text(token) for token in mapping.get(canonical_key, [])]
    raw_value = _normalize_evidence_text(str(value).strip())
    if raw_value:
        tokens.append(raw_value)
    return [token for token in tokens if token]


def _attach_unit_tokens(value_tokens: set[str], unit_tokens: list[str]) -> set[str]:
    combined: set[str] = set()
    for value_token in value_tokens:
        if not value_token:
            continue
        for unit_token in unit_tokens:
            combined.add(f"{value_token}{unit_token}")
            combined.add(f"{value_token} {unit_token}")
    return combined


def _coerce_range_tokens(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)\s*", value)
    if not match:
        return []
    start = _format_number_token(float(match.group(1)))
    end = _format_number_token(float(match.group(2)))
    return [f"{start}-{end}", f"{start} - {end}", f"{start}~{end}", f"{start} ~ {end}"]


def _parameter_value_match_score(normalized_text: str, parameter_record: ParameterRecord) -> int:
    tokens = _parameter_value_tokens(str(parameter_record.canonical_key or ""), parameter_record.value)
    return 3 if any(_contains_exact_value_token(normalized_text, token) for token in tokens) else 0


def _parameter_keyword_match_score(normalized_text: str, parameter_record: ParameterRecord) -> int:
    keywords = [_normalize_evidence_text(keyword) for keyword in _parameter_keywords(str(parameter_record.canonical_key or ""))]
    return 3 if any(keyword and keyword in normalized_text for keyword in keywords) else 0


def _parameter_unit_match_score(normalized_text: str, parameter_record: ParameterRecord) -> int:
    if not _parameter_requires_unit(parameter_record):
        return 0
    unit_tokens = [_normalize_evidence_text(token) for token in _parameter_unit_tokens(str(parameter_record.canonical_key or ""))]
    return 2 if any(token and token in normalized_text for token in unit_tokens) else 0


def _parameter_unit_tokens(canonical_key: str) -> list[str]:
    mapping = {
        "hydrolysis_temperature_C": ["degc"],
        "concentration_temperature_C": ["degc"],
        "drying_temperature_C": ["degc"],
        "spinning_channel_temperature_C": ["degc"],
        "service_temperature_C": ["degc"],
        "sintering_temperature_C": ["degc"],
        "target_temperature_C": ["degc"],
        "feed_pressure_MPa": ["mpa"],
        "relative_humidity_percent": ["%"],
        "average_fiber_diameter_um": ["um"],
        "tensile_strength_MPa": ["gpa", "mpa"],
        "holding_time_h": ["h", "min"],
        "hydrolysis_time_h": ["h", "min"],
        "peptization_time_h": ["h", "min"],
        "concentration_time_h": ["h", "min"],
        "strength_retention_percent": ["%"],
        "take_up_speed_m_min": ["m/min"],
        "heating_rate_C_min": ["degc/min"],
    }
    return mapping.get(canonical_key, [])


def _parameter_requires_unit(parameter_record: ParameterRecord) -> bool:
    return str(parameter_record.canonical_key or "") not in {"aluminum_source", "peptizing_agent"}


def _full_text_match_threshold(parameter_record: ParameterRecord) -> int:
    return 6 if str(parameter_record.canonical_key or "") in {"aluminum_source", "peptizing_agent"} else 8


def _normalize_evidence_text(text: str) -> str:
    normalized = str(text or "").lower()
    for source, target in {
        "μm": "um",
        "µm": "um",
        "µ": "u",
        "℃": "degc",
        "°c": "degc",
        "掳c": "degc",
        "鈩?": "degc",
    }.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"degc\s*(?:[·•\.]|\s*×\s*)\s*min\^-?1", "degc/min", normalized)
    normalized = re.sub(r"degc\s*/\s*min", "degc/min", normalized)
    normalized = re.sub(r"m\s*(?:[·•\.]|\s*×\s*)\s*min\^-?1", "m/min", normalized)
    normalized = re.sub(r"m\s*/\s*min", "m/min", normalized)
    normalized = re.sub(r"\s*[-–—~]\s*", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_non_evidence_markdown_line(text: str) -> bool:
    return text.startswith("![](") or text.startswith("CSV:") or text.startswith("JSON:")


def _looks_like_reference_section(section: str) -> bool:
    normalized = _normalize_evidence_text(section)
    return "参考文献" in normalized or "references" in normalized


def _looks_like_reference_entry(text: str) -> bool:
    return bool(re.match(r"^\[\d+\]", text) or re.match(r"^\d+\.\s+[A-Z][A-Za-z]+", text))


def _contains_figure_or_table_mention(text: str) -> bool:
    return bool(re.search(r"(?:图|fig\.?|table|tab\.?)\s*\d+", text, flags=re.IGNORECASE))


def _is_preferred_evidence_context(section: str, text: str, table_id: str | None) -> bool:
    if table_id:
        return True
    normalized_section = _normalize_evidence_text(section)
    if any(
        token in normalized_section
        for token in [
            "实验",
            "结果",
            "讨论",
            "结论",
            "method",
            "experiment",
            "result",
            "discussion",
            "conclusion",
        ]
    ):
        return True
    return _contains_figure_or_table_mention(text)


def _slugify_section(section: str) -> str:
    cleaned = re.sub(r"[^\w一-鿿-]+", "_", str(section or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "full_text"


def _format_number_token(number: float) -> str:
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _normalize_candidate_value_for_target(
    *,
    target_key: str,
    candidate_key: str,
    candidate_value: Any,
) -> Any | None:
    aliases = {
        "viscosity_Pa_s": {"viscosity_Pa_s": 1.0},
        "spinning_channel_temperature_C": {"spinning_channel_temperature_C": 1.0},
        "feed_pressure_MPa": {"feed_pressure_MPa": 1.0},
        "relative_humidity_percent": {"relative_humidity_percent": 1.0},
        "average_fiber_diameter_um": {
            "average_fiber_diameter_um": 1.0,
            "gel_fiber_diameter_um": 1.0,
            "ceramic_fiber_diameter_um": 1.0,
        },
        "tensile_strength_MPa": {
            "tensile_strength_MPa": 1.0,
            "ceramic_fiber_tensile_strength_GPa": 1000.0,
            "tensile_strength_GPa": 1000.0,
        },
        "service_temperature_C": {"service_temperature_C": 1.0},
        "holding_time_h": {"holding_time_h": 1.0},
        "strength_retention_percent": {"strength_retention_percent": 1.0},
    }
    scale = (aliases.get(target_key) or {}).get(candidate_key)
    if scale is None:
        return None
    number = _coerce_float(candidate_value)
    if number is None:
        return candidate_value if scale == 1.0 else None
    return number * scale


def _parameter_values_match(left: Any, right: Any) -> bool:
    if left == right:
        return True
    left_number = _coerce_float(left)
    right_number = _coerce_float(right)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) < 1e-9
    return str(left).strip() == str(right).strip()


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_evidence_ref_models(evidence_refs: list[EvidenceRef | str]) -> list[EvidenceRef]:
    models: list[EvidenceRef] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for ref in evidence_refs:
        if isinstance(ref, EvidenceRef):
            marker = (ref.source_id, ref.figure_id, ref.table_id)
            if marker in seen:
                continue
            seen.add(marker)
            models.append(ref)
    return models


def _missing_evidence_reason(
    parameter_record: ParameterRecord,
    ontology: dict[str, dict[str, Any]],
) -> str | None:
    canonical_key = str(parameter_record.canonical_key or "")
    ontology_entry = ontology.get(canonical_key) or {}
    if not ontology_entry.get("is_core_statistical_field"):
        return None
    return "no_explicit_evidence_inherited_or_matched"


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
