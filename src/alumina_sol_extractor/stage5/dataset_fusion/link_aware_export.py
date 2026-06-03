"""Link-aware final dataset exports built from Stage 5 and Stage 5.5 outputs."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.exporters import write_json, write_markdown
from alumina_sol_extractor.dataset_fusion.link_aware_fields import (
    CORE_SAMPLE_MATRIX_KEYS,
    EVIDENCE_PARAMETER_LINK_FIELDS,
    FINAL_PARAMETERS_LINKED_FIELDS,
    FINAL_SHOWCASE_FIELDS,
    PROCESS_STEPS_TABLE_FIELDS,
    SAMPLE_PARAMETER_MATRIX_FIELDS,
    SAMPLE_PARAMETER_MATRIX_LONG_FIELDS,
    SAMPLE_MATRIX_MISSING_DIAGNOSIS_FIELDS,
    SPECTRA_PARAMETER_LINK_FIELDS,
    build_sample_parameter_matrix_fields,
)
from alumina_sol_extractor.dataset_fusion.link_aware_io import (
    build_link_aware_diagnosis,
    build_link_aware_readme,
    build_link_aware_summary,
    safe_write,
    write_csv_with_fields,
    write_parquet_with_fields,
)
from alumina_sol_extractor.dataset_fusion.loaders import read_json, read_jsonl
from alumina_sol_extractor.dataset_fusion.spectra_units import (
    coerce_peak_unit,
    normalize_parameter_unit,
    normalize_unit_text as normalize_shared_unit_text,
)
from alumina_sol_extractor.ontology.ontology_loader import get_ontology_entry_map
from alumina_sol_extractor.stage5.dataset_fusion.semantics import (
    CHARACTERIZATION_CATEGORY_HINTS,
    classify_parameter_semantic_role,
    resolve_paper_identity_from_final_dataset_dir,
)

_build_link_aware_summary = build_link_aware_summary
_build_link_aware_readme = build_link_aware_readme
_safe_write = safe_write
_write_csv_with_fields = write_csv_with_fields
_write_parquet_with_fields = write_parquet_with_fields


def load_link_aware_inputs(final_dataset_dir: Path | str) -> dict[str, Any]:
    final_dataset_dir = Path(final_dataset_dir)
    linking_dir = final_dataset_dir / "linking"
    return {
        "final_dataset_dir": final_dataset_dir,
        "paper": read_json(final_dataset_dir / "paper.json", default={}) or {},
        "samples": read_jsonl(final_dataset_dir / "samples.jsonl"),
        "parameters": read_jsonl(final_dataset_dir / "parameters.jsonl"),
        "process_steps": read_jsonl(final_dataset_dir / "process_steps.jsonl"),
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
    include_showcase: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    inputs = load_link_aware_inputs(final_dataset_dir)
    ontology_map = get_ontology_entry_map(project_root)
    paper = inputs["paper"]
    paper_id = paper_id or paper.get("paper_id") or Path(final_dataset_dir).parent.name
    title = paper.get("title") or paper_id
    output_dir = Path(output_dir) if output_dir else Path(final_dataset_dir) / "link_aware_exports"
    paper_identity = resolve_paper_identity_from_final_dataset_dir(Path(final_dataset_dir))

    parameters = inputs["parameters"]
    process_steps = inputs["process_steps"]
    evidence = inputs["evidence"]
    spectra = inputs["spectra"]
    samples = inputs["samples"]
    links = inputs["links"]

    parameter_semantic_qa = _build_parameter_semantic_qa(
        parameters,
        paper_identity=paper_identity,
        ontology_map=ontology_map,
    )
    semantic_lookup = {row["parameter_id"]: row for row in parameter_semantic_qa}
    included_parameter_ids = {
        row["parameter_id"]
        for row in parameter_semantic_qa
        if bool(row.get("included_in_main_parameter_landscape"))
    }
    included_parameters = [row for row in parameters if row.get("parameter_id") in included_parameter_ids]
    excluded_parameters = [
        _build_excluded_parameter_row(
            row,
            semantic_lookup.get(row.get("parameter_id"), {}),
            paper_identity=paper_identity,
        )
        for row in parameters
        if row.get("parameter_id") not in included_parameter_ids
    ]

    indexes = _build_indexes(included_parameters, process_steps, evidence, spectra, samples, links)
    evidence_parameter_links = _build_evidence_parameter_links(
        paper_id=paper_id,
        parameters=included_parameters,
        evidence=evidence,
        links=links,
        indexes=indexes,
        paper_identity=paper_identity,
    )
    process_step_parameter_links = [
        row for row in evidence_parameter_links if row.get("source_type") == "process_step"
    ]
    spectra_parameter_links = _build_spectra_parameter_links(
        paper_id=paper_id,
        parameters=included_parameters,
        evidence_parameter_links=evidence_parameter_links,
        spectra=spectra,
        links=links,
        indexes=indexes,
        paper_identity=paper_identity,
    )
    final_parameters_linked = _build_final_parameters_linked(
        paper_id=paper_id,
        title=title,
        paper=paper,
        parameters=included_parameters,
        evidence=evidence,
        spectra=spectra,
        links=links,
        ontology_map=ontology_map,
        indexes=indexes,
        evidence_parameter_links=evidence_parameter_links,
        spectra_parameter_links=spectra_parameter_links,
        paper_identity=paper_identity,
        semantic_lookup=semantic_lookup,
    )
    sample_parameter_matrix_long = _build_sample_parameter_matrix_long(
        paper_id=paper_id,
        samples=samples,
        final_parameters_linked=final_parameters_linked,
        evidence_parameter_links=evidence_parameter_links,
        spectra_parameter_links=spectra_parameter_links,
        paper_identity=paper_identity,
    )
    sample_parameter_matrix = _build_sample_parameter_matrix(
        paper_id=paper_id,
        title=title,
        paper=paper,
        samples=samples,
        sample_parameter_matrix_long=sample_parameter_matrix_long,
        spectra=spectra,
        paper_identity=paper_identity,
    )
    sample_matrix_missing_diagnosis = _build_sample_matrix_missing_diagnosis(
        samples=samples,
        final_parameters_linked=final_parameters_linked,
        sample_parameter_matrix=sample_parameter_matrix,
        sample_parameter_matrix_long=sample_parameter_matrix_long,
        paper_identity=paper_identity,
    )
    sample_parameter_matrix_fields = build_sample_parameter_matrix_fields(
        _collect_sample_matrix_dynamic_keys(sample_parameter_matrix)
    )
    process_steps_table = _build_process_steps_table(
        paper_id=paper_id,
        title=title,
        process_steps=process_steps,
        indexes=indexes,
        paper_identity=paper_identity,
    )
    final_showcase_table = _build_final_showcase_table(
        paper_id=paper_id,
        title=title,
        final_parameters_linked=final_parameters_linked,
        samples=samples,
        include_showcase=include_showcase,
    )
    write_warnings: list[str] = []
    locked_files: list[str] = []
    fallback_outputs: list[str] = []
    summary = build_link_aware_summary(
        final_parameters_linked=final_parameters_linked,
        evidence_parameter_links=evidence_parameter_links,
        spectra_parameter_links=spectra_parameter_links,
        sample_parameter_matrix=sample_parameter_matrix,
        showcase_rows=final_showcase_table,
        include_showcase=include_showcase,
        excluded_parameters=excluded_parameters,
        parameter_semantic_qa=parameter_semantic_qa,
        paper_identity=paper_identity,
    )
    summary["sample_parameter_matrix_long_rows"] = len(sample_parameter_matrix_long)
    summary["sample_matrix_missing_diagnosis_rows"] = len(sample_matrix_missing_diagnosis)

    if write_outputs:
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_write(
            output_dir / "final_parameters_linked.csv",
            lambda path: write_csv_with_fields(path, final_parameters_linked, FINAL_PARAMETERS_LINKED_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "final_parameters_linked.parquet",
            lambda path: write_parquet_with_fields(path, final_parameters_linked, FINAL_PARAMETERS_LINKED_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "sample_parameter_matrix.csv",
            lambda path: write_csv_with_fields(path, sample_parameter_matrix, sample_parameter_matrix_fields),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "sample_parameter_matrix_long.csv",
            lambda path: write_csv_with_fields(path, sample_parameter_matrix_long, SAMPLE_PARAMETER_MATRIX_LONG_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "sample_matrix_missing_diagnosis.csv",
            lambda path: write_csv_with_fields(path, sample_matrix_missing_diagnosis, SAMPLE_MATRIX_MISSING_DIAGNOSIS_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "evidence_parameter_links.csv",
            lambda path: write_csv_with_fields(path, evidence_parameter_links, EVIDENCE_PARAMETER_LINK_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "process_step_parameter_links.csv",
            lambda path: write_csv_with_fields(path, process_step_parameter_links, EVIDENCE_PARAMETER_LINK_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "spectra_parameter_links.csv",
            lambda path: write_csv_with_fields(path, spectra_parameter_links, SPECTRA_PARAMETER_LINK_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "process_steps_table.csv",
            lambda path: write_csv_with_fields(path, process_steps_table, PROCESS_STEPS_TABLE_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        safe_write(
            output_dir / "final_showcase_table.csv",
            lambda path: write_csv_with_fields(path, final_showcase_table, FINAL_SHOWCASE_FIELDS),
            write_warnings,
            locked_files=locked_files,
            fallback_outputs=fallback_outputs,
        )
        if excluded_parameters:
            excluded_fields = list(excluded_parameters[0].keys())
            safe_write(
                output_dir / "excluded_parameters.csv",
                lambda path: write_csv_with_fields(path, excluded_parameters, excluded_fields),
                write_warnings,
                locked_files=locked_files,
                fallback_outputs=fallback_outputs,
            )
            _safe_write(
                output_dir / "excluded_parameters.jsonl",
                lambda path: path.write_text(
                    "\n".join(json.dumps(row, ensure_ascii=False) for row in excluded_parameters) + "\n",
                    encoding="utf-8",
                ),
                write_warnings,
                locked_files=locked_files,
                fallback_outputs=fallback_outputs,
            )
        if parameter_semantic_qa:
            semantic_fields = list(parameter_semantic_qa[0].keys())
            safe_write(
                output_dir / "parameter_semantic_qa.csv",
                lambda path: write_csv_with_fields(path, parameter_semantic_qa, semantic_fields),
                write_warnings,
                locked_files=locked_files,
                fallback_outputs=fallback_outputs,
            )
        summary["output_warnings"] = write_warnings
        summary["locked_files"] = locked_files
        summary["fallback_outputs"] = fallback_outputs
        summary["process_steps_table_current_is_stale"] = "process_steps_table.csv" in locked_files
        readme = build_link_aware_readme(include_showcase=include_showcase, output_warnings=write_warnings)
        write_json(output_dir / "link_aware_export_summary.json", summary)
        write_markdown(output_dir / "link_aware_export_readme.md", readme)
        write_markdown(output_dir / "link_aware_export_diagnosis.md", build_link_aware_diagnosis(output_dir))

    summary.setdefault("output_warnings", write_warnings)
    summary.setdefault("locked_files", locked_files)
    summary.setdefault("fallback_outputs", fallback_outputs)
    summary.setdefault("process_steps_table_current_is_stale", "process_steps_table.csv" in locked_files)

    return {
        "paper_id": paper_id,
        "title": title,
        "output_dir": str(output_dir),
        "summary": summary,
        "final_parameters_linked": final_parameters_linked,
        "sample_parameter_matrix_long": sample_parameter_matrix_long,
        "sample_parameter_matrix": sample_parameter_matrix,
        "sample_matrix_missing_diagnosis": sample_matrix_missing_diagnosis,
        "process_steps_table": process_steps_table,
        "evidence_parameter_links": evidence_parameter_links,
        "process_step_parameter_links": process_step_parameter_links,
        "spectra_parameter_links": spectra_parameter_links,
        "final_showcase_table": final_showcase_table,
        "excluded_parameters": excluded_parameters,
        "parameter_semantic_qa": parameter_semantic_qa,
        "paper_identity": paper_identity,
    }


def _build_indexes(
    parameters: list[dict[str, Any]],
    process_steps: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, Any]:
    process_steps_by_id = {}
    for index, row in enumerate(process_steps, start=1):
        step_id = row.get("step_id") or f"process-step-{index:03d}"
        row.setdefault("step_id", step_id)
        process_steps_by_id[step_id] = row
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
    links_by_process_step = defaultdict(list)
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
            ("process_step", link.get("source_id") if link.get("source_type") == "process_step" else None, links_by_process_step),
            ("process_step", link.get("target_id") if link.get("target_type") == "process_step" else None, links_by_process_step),
        ):
            if key:
                bucket[key].append(link)
        if link.get("source_type") == "spectra_peak" and link.get("source_id"):
            links_by_spectra[link["source_id"]].append(link)
    return {
        "evidence_by_id": evidence_by_id,
        "evidence_by_figure": evidence_by_figure,
        "process_steps_by_id": process_steps_by_id,
        "spectra_by_id": spectra_by_id,
        "spectra_by_figure": spectra_by_figure,
        "samples_by_id": samples_by_id,
        "parameters_by_id": parameters_by_id,
        "links_by_parameter": links_by_parameter,
        "links_by_evidence": links_by_evidence,
        "links_by_process_step": links_by_process_step,
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
    paper_identity: dict[str, Any],
    semantic_lookup: dict[str, dict[str, Any]],
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
        semantic = semantic_lookup.get(str(parameter_id), {})
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
        process_step_rows = [row for row in evidence_rows if row.get("source_type") == "process_step"]
        evidence_object_rows = [row for row in evidence_rows if row.get("source_type") == "evidence_object" or row.get("created_by") == "direct_evidence_refs"]
        text_reference_rows = [
            row
            for row in evidence_rows
            if row.get("source_type") == "text_reference" or row.get("created_by") == "direct_text_evidence_refs"
        ]
        linked_evidence_rows = [*evidence_object_rows, *text_reference_rows]
        spectra_rows = spectra_link_rows_by_parameter.get(parameter_id, [])
        linked_evidence_ids = _sorted_unique(
            explicit_evidence_ids
            + [row.get("evidence_id") for row in evidence_object_rows]
            + [row.get("source_id") for row in process_step_rows if row.get("source_id")]
        )
        linked_figure_ids = _sorted_unique(
            _coerce_str_list(parameter.get("linked_figure_ids"))
            + [row.get("figure_id") for row in evidence_object_rows]
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
        evidence_text_preview = _sorted_unique(
            [row.get("evidence_text_preview") for row in process_step_rows if row.get("evidence_text_preview")]
            + [row.get("evidence_text_preview") for row in linked_evidence_rows if row.get("evidence_text_preview")]
        )

        value_meta = _normalize_parameter_value(parameter.get("value"), parameter.get("unit"), parameter.get("canonical_key"))
        evidence_status = _resolve_evidence_status(
            explicit_evidence_ids,
            linked_evidence_rows,
            spectra_rows,
            linked_sample_ids,
            process_step_rows,
        )
        quality_flags = list(parameter.get("quality_flags") or [])
        if len(linked_sample_ids) > 1:
            quality_flags.append("multiple_sample_links")

        direct_strong_evidence_rows = [
            row
            for row in text_reference_rows
            if row.get("confidence") == "high"
        ]
        strong_link_count = sum(
            1
            for link in parameter_links
            if (link.get("confidence") in {"high", "medium"} and link.get("link_type") != "weak_supports")
        ) + len([row for row in evidence_rows if row.get("created_by") in {"direct_evidence_refs", "deterministic_process_step_value_match"}]) + len(direct_strong_evidence_rows)
        weak_link_count = sum(
            1
            for link in parameter_links
            if link.get("confidence") == "low" or link.get("link_type") == "weak_supports"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "paper_category": paper_identity.get("paper_category"),
                "paper_category_status": paper_identity.get("paper_category_status"),
                "paper_dir": paper_identity.get("paper_dir"),
                "title": title,
                "parameter_id": parameter_id,
                "canonical_key": canonical_key,
                "zh_name": ontology_entry.get("zh_name") or canonical_key,
                "en_name": ontology_entry.get("en_name") or canonical_key,
                "category": paper_identity.get("paper_category"),
                "local_category": ontology_entry.get("category"),
                "source_category": parameter.get("category"),
                "parameter_semantic_role": semantic.get("parameter_semantic_role", "synthesis_process_property"),
                "included_in_main_parameter_landscape": semantic.get("included_in_main_parameter_landscape", True),
                "exclusion_reason": semantic.get("exclusion_reason", ""),
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
                "source_file": f"{paper_identity.get('paper_dir')}/final_dataset/parameters.jsonl" if paper_identity.get("paper_dir") else "final_dataset/parameters.jsonl",
                "source_stage": "stage3.final_dataset.parameters",
                "link_count": len(parameter_links) + len(explicit_evidence_ids) + len(text_reference_rows),
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
    sample_parameter_matrix_long: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    long_rows_by_sample = defaultdict(list)
    for row in sample_parameter_matrix_long:
        sample_id = row.get("sample_id")
        if sample_id:
            long_rows_by_sample[str(sample_id)].append(row)
    sample_matrix_parameter_keys: list[str] = list(CORE_SAMPLE_MATRIX_KEYS)
    seen_matrix_parameter_keys = set(sample_matrix_parameter_keys)
    for item in sample_parameter_matrix_long:
        canonical_key = _string_or_none(item.get("canonical_key"))
        if not canonical_key or canonical_key in seen_matrix_parameter_keys:
            continue
        seen_matrix_parameter_keys.add(canonical_key)
        sample_matrix_parameter_keys.append(canonical_key)
    spectra_by_id = {_spectra_id_for_figure(item.get("figure_id")): item for item in spectra if item.get("figure_id")}
    for sample in samples:
        sample_id = _string_or_none(sample.get("sample_id"))
        sample_long_rows = long_rows_by_sample.get(sample_id, [])
        sample_parameter_ids = {
            str(item.get("parameter_id"))
            for item in sample_long_rows
            if item.get("parameter_id")
        }
        linked_evidence_ids = _sorted_unique(
            [
                evidence_id
                for item in sample_long_rows
                for evidence_id in str(item.get("linked_evidence_ids") or "").split("; ")
                if evidence_id
            ]
        )
        linked_spectra_ids = _sorted_unique(
            [
                spectra_id if str(spectra_id).startswith("spectra-") else _spectra_id_for_figure(spectra_id)
                for item in sample_long_rows
                for spectra_id in str(item.get("linked_spectra_ids") or "").split("; ")
                if spectra_id
            ]
        )
        linked_process_step_ids = _sorted_unique(
            [
                step_id
                for item in sample_long_rows
                for step_id in str(item.get("linked_process_step_ids") or "").split("; ")
                if step_id
            ]
        )
        linked_figure_ids = _sorted_unique(
            [
                figure_id
                for spectra_id in linked_spectra_ids
                for figure_id in [_string_or_none(spectra_by_id.get(spectra_id, {}).get("figure_id"))]
                if figure_id
            ]
        )
        linked_techniques = _sorted_unique(
            [
                spectra_by_id.get(spectra_id, {}).get("technique")
                for spectra_id in linked_spectra_ids
                if spectra_by_id.get(spectra_id, {}).get("technique")
            ]
        )
        value_rows_by_key = defaultdict(list)
        for item in sample_long_rows:
            canonical_key = _string_or_none(item.get("canonical_key"))
            if not canonical_key:
                continue
            value_rows_by_key[canonical_key].append(item)
        unique_linked_parameter_count = len(sample_parameter_ids)
        sample_parameter_value_count = sum(1 for item in sample_long_rows if _string_or_none(item.get("value")))
        linked_process_step_edge_count = sum(
            int(item.get("_linked_process_step_edge_count") or 0) for item in sample_long_rows
        )
        linked_evidence_edge_count = sum(int(item.get("_linked_evidence_edge_count") or 0) for item in sample_long_rows)
        linked_spectra_edge_count = sum(int(item.get("_linked_spectra_edge_count") or 0) for item in sample_long_rows)
        row: dict[str, Any] = {
            "paper_id": paper_id,
            "paper_category": paper_identity.get("paper_category"),
            "paper_category_status": paper_identity.get("paper_category_status"),
            "paper_dir": paper_identity.get("paper_dir"),
            "title": title,
            "sample_id": sample_id,
            "sample_name": sample.get("sample_name"),
            "material_system": paper.get("material_system"),
            "process_route": paper.get("process_route"),
            "parameter_count": len(sample.get("linked_parameters") or []),
            "linked_parameter_count": len(sample_long_rows),
            "matrix_parameter_field_count": 0,
            "sample_parameter_value_count": sample_parameter_value_count,
            "unique_linked_parameter_count": unique_linked_parameter_count,
            "linked_parameter_edge_count": linked_evidence_edge_count + linked_spectra_edge_count + linked_process_step_edge_count,
            "linked_evidence_edge_count": linked_evidence_edge_count,
            "linked_spectra_edge_count": linked_spectra_edge_count,
            "linked_process_step_edge_count": linked_process_step_edge_count,
            "evidence_count": len(linked_evidence_ids),
            "spectra_count": len(linked_spectra_ids),
            "evidence_linked_parameter_count": sum(
                1
                for item in sample_long_rows
                if item.get("evidence_status") in {"strong_evidence", "process_step_evidence", "linked_evidence"}
            ),
            "process_step_linked_parameter_count": sum(
                1 for item in sample_long_rows if item.get("evidence_status") == "process_step_evidence"
            ),
            "spectra_linked_parameter_count": sum(1 for item in sample_long_rows if item.get("linked_spectra_ids")),
            "linked_spectra_count": len(linked_spectra_ids),
            "linked_spectra_ids": "; ".join(linked_spectra_ids),
            "linked_spectra_figure_ids": "; ".join(
                _sorted_unique([spectra_by_id.get(spectra_id, {}).get("figure_id") for spectra_id in linked_spectra_ids])
            ),
            "linked_spectra_techniques": "; ".join(linked_techniques),
            "linked_figure_ids": "; ".join(linked_figure_ids),
        }
        multi_value_keys: list[str] = []
        for canonical_key in sample_matrix_parameter_keys:
            values = [
                _string_or_none(item.get("value"))
                for item in value_rows_by_key.get(canonical_key, [])
                if _string_or_none(item.get("value"))
            ]
            unique_values = _sorted_unique(values)
            if len(unique_values) > 1:
                multi_value_keys.append(canonical_key)
            row[canonical_key] = "; ".join(unique_values)
        row["matrix_parameter_field_count"] = sum(1 for canonical_key in sample_matrix_parameter_keys if row.get(canonical_key))
        row["multi_value_flags"] = "; ".join(multi_value_keys)
        rows.append(row)
    return rows


_SAMPLE_MATRIX_GLOBAL_BROADCAST_KEYS = {
    "reaction_temperature_C",
    "cooling_water_temperature_C",
    "reactor_volume_m3",
    "stirring_method",
    "aluminum_source",
    "silicon_source",
    "solid_content_wt_percent",
    "pH",
    "weight_kg",
}

_SAMPLE_MATRIX_NON_BROADCAST_KEYS = {
    "xrd_peak_position_2theta_deg",
    "ftir_peak_position_cm_1",
    "raman_peak_position_cm_1",
    "nmr_27Al_peak_position_ppm",
    "dsc_peak_temperature_C",
    "mass_loss_wt_percent",
    "tensile_strength_MPa",
    "elongation_at_break_percent",
    "average_fiber_diameter_um",
}


def _build_sample_parameter_matrix_long(
    *,
    paper_id: str,
    samples: list[dict[str, Any]],
    final_parameters_linked: list[dict[str, Any]],
    evidence_parameter_links: list[dict[str, Any]],
    spectra_parameter_links: list[dict[str, Any]],
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample_names = {
        str(sample.get("sample_id")): sample.get("sample_name")
        for sample in samples
        if sample.get("sample_id")
    }
    evidence_rows_by_parameter = defaultdict(list)
    process_step_ids_by_parameter = defaultdict(list)
    spectra_rows_by_parameter = defaultdict(list)
    for row in evidence_parameter_links:
        parameter_id = _string_or_none(row.get("parameter_id"))
        if not parameter_id:
            continue
        evidence_rows_by_parameter[parameter_id].append(row)
        if row.get("source_type") == "process_step" and row.get("source_id"):
            process_step_ids_by_parameter[parameter_id].append(str(row.get("source_id")))
    for row in spectra_parameter_links:
        parameter_id = _string_or_none(row.get("parameter_id"))
        if parameter_id:
            spectra_rows_by_parameter[parameter_id].append(row)

    direct_sample_rows_by_key = defaultdict(list)
    unresolved_rows_by_key = defaultdict(list)
    for row in final_parameters_linked:
        canonical_key = _string_or_none(row.get("canonical_key"))
        if not canonical_key or not _display_value(row):
            continue
        sample_ids = _linked_sample_ids_from_final_row(row)
        if sample_ids:
            direct_sample_rows_by_key[canonical_key].append(row)
        else:
            unresolved_rows_by_key[canonical_key].append(row)

    for row in final_parameters_linked:
        canonical_key = _string_or_none(row.get("canonical_key"))
        parameter_id = _string_or_none(row.get("parameter_id"))
        value = _display_value(row)
        if not canonical_key or not parameter_id or not value:
            continue
        sample_ids = _linked_sample_ids_from_final_row(row)
        if sample_ids:
            for sample_id in sample_ids:
                rows.append(
                    _build_sample_matrix_long_row(
                        paper_id=paper_id,
                        sample_id=sample_id,
                        sample_name=sample_names.get(sample_id),
                        parameter_row=row,
                        evidence_rows=evidence_rows_by_parameter.get(parameter_id, []),
                        spectra_rows=spectra_rows_by_parameter.get(parameter_id, []),
                        linked_process_step_ids=process_step_ids_by_parameter.get(parameter_id, []),
                        value_origin="direct_sample_link",
                        warning=None,
                        paper_identity=paper_identity,
                    )
                )
            continue

        if not _can_broadcast_parameter_to_all_samples(
            row,
            direct_sample_rows_for_key=direct_sample_rows_by_key.get(canonical_key, []),
        ):
            continue
        for sample in samples:
            sample_id = _string_or_none(sample.get("sample_id"))
            if not sample_id:
                continue
            rows.append(
                _build_sample_matrix_long_row(
                    paper_id=paper_id,
                    sample_id=sample_id,
                    sample_name=sample.get("sample_name"),
                    parameter_row=row,
                    evidence_rows=evidence_rows_by_parameter.get(parameter_id, []),
                    spectra_rows=spectra_rows_by_parameter.get(parameter_id, []),
                    linked_process_step_ids=process_step_ids_by_parameter.get(parameter_id, []),
                    value_origin="broadcast_global",
                    warning="broadcast_from_global_constant",
                    paper_identity=paper_identity,
                )
            )
    return rows


def _build_sample_matrix_long_row(
    *,
    paper_id: str,
    sample_id: str,
    sample_name: str | None,
    parameter_row: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    spectra_rows: list[dict[str, Any]],
    linked_process_step_ids: list[str],
    value_origin: str,
    warning: str | None,
    paper_identity: dict[str, Any],
) -> dict[str, Any]:
    confidence = "high" if value_origin == "direct_sample_link" else "medium"
    if parameter_row.get("sample_resolution_source") == "unresolved":
        confidence = "medium"
    linked_evidence_ids = _sorted_unique(
        [row.get("evidence_id") for row in evidence_rows if row.get("source_type") != "process_step" and row.get("evidence_id")]
        + [row.get("source_id") for row in evidence_rows if row.get("source_type") == "text_reference" and row.get("source_id")]
    )
    linked_spectra_ids = _sorted_unique([row.get("spectra_id") for row in spectra_rows if row.get("spectra_id")])
    return {
        "paper_id": paper_id,
        "paper_category": paper_identity.get("paper_category"),
        "paper_category_status": paper_identity.get("paper_category_status"),
        "paper_dir": paper_identity.get("paper_dir"),
        "sample_id": sample_id,
        "sample_name": sample_name,
        "canonical_key": parameter_row.get("canonical_key"),
        "value": _display_value(parameter_row),
        "unit": parameter_row.get("unit"),
        "parameter_id": parameter_row.get("parameter_id"),
        "value_origin": value_origin,
        "evidence_status": parameter_row.get("evidence_status"),
        "linked_evidence_ids": "; ".join(linked_evidence_ids),
        "linked_spectra_ids": "; ".join(linked_spectra_ids),
        "linked_process_step_ids": "; ".join(_sorted_unique(linked_process_step_ids)),
        "confidence": confidence,
        "warning": warning,
        "_linked_evidence_edge_count": len([row for row in evidence_rows if row.get("source_type") != "process_step"]),
        "_linked_spectra_edge_count": len(spectra_rows),
        "_linked_process_step_edge_count": len(_sorted_unique(linked_process_step_ids)),
    }


def _build_sample_matrix_missing_diagnosis(
    *,
    samples: list[dict[str, Any]],
    final_parameters_linked: list[dict[str, Any]],
    sample_parameter_matrix: list[dict[str, Any]],
    sample_parameter_matrix_long: list[dict[str, Any]],
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    matrix_rows_by_sample = {
        str(row.get("sample_id")): row
        for row in sample_parameter_matrix
        if row.get("sample_id")
    }
    long_rows_by_sample_and_key = defaultdict(list)
    extracted_rows_by_key = defaultdict(list)
    direct_rows_by_sample_and_key = defaultdict(list)
    broadcast_rows_by_sample_and_key = defaultdict(list)
    sample_matrix_keys = set(CORE_SAMPLE_MATRIX_KEYS)
    for row in final_parameters_linked:
        canonical_key = _string_or_none(row.get("canonical_key"))
        if not canonical_key:
            continue
        sample_matrix_keys.add(canonical_key)
        extracted_rows_by_key[canonical_key].append(row)
        for sample_id in _linked_sample_ids_from_final_row(row):
            direct_rows_by_sample_and_key[(sample_id, canonical_key)].append(row)
    for row in sample_parameter_matrix_long:
        sample_id = _string_or_none(row.get("sample_id"))
        canonical_key = _string_or_none(row.get("canonical_key"))
        if not sample_id or not canonical_key:
            continue
        long_rows_by_sample_and_key[(sample_id, canonical_key)].append(row)
        if row.get("value_origin") == "broadcast_global":
            broadcast_rows_by_sample_and_key[(sample_id, canonical_key)].append(row)

    diagnosis_rows: list[dict[str, Any]] = []
    for sample in samples:
        sample_id = _string_or_none(sample.get("sample_id"))
        if not sample_id:
            continue
        sample_name = sample.get("sample_name")
        matrix_row = matrix_rows_by_sample.get(sample_id, {})
        for canonical_key in sorted(sample_matrix_keys):
            matrix_value_present = bool(_string_or_none(matrix_row.get(canonical_key)))
            if matrix_value_present:
                continue
            rows_for_key = extracted_rows_by_key.get(canonical_key, [])
            direct_rows = direct_rows_by_sample_and_key.get((sample_id, canonical_key), [])
            long_rows = long_rows_by_sample_and_key.get((sample_id, canonical_key), [])
            broadcast_rows = broadcast_rows_by_sample_and_key.get((sample_id, canonical_key), [])
            final_parameter_exists = bool(rows_for_key)
            has_sample_link = bool(direct_rows)
            has_global_value = bool(broadcast_rows) or any(
                _can_broadcast_parameter_to_all_samples(
                    row,
                    direct_sample_rows_for_key=[
                        candidate
                        for candidate in rows_for_key
                        if _linked_sample_ids_from_final_row(candidate)
                    ],
                )
                for row in rows_for_key
            )
            missing_reason, recommended_action = _classify_sample_matrix_missing_reason(
                sample_id=sample_id,
                canonical_key=canonical_key,
                rows_for_key=rows_for_key,
                direct_rows=direct_rows,
                long_rows=long_rows,
                has_global_value=has_global_value,
            )
            diagnosis_rows.append(
                {
                    "paper_id": paper_identity.get("paper_id"),
                    "paper_category": paper_identity.get("paper_category"),
                    "paper_category_status": paper_identity.get("paper_category_status"),
                    "paper_dir": paper_identity.get("paper_dir"),
                    "sample_id": sample_id,
                    "sample_name": sample_name,
                    "canonical_key": canonical_key,
                    "matrix_value_present": False,
                    "final_parameter_exists": final_parameter_exists,
                    "has_sample_link": has_sample_link,
                    "has_global_value": has_global_value,
                    "missing_reason": missing_reason,
                    "recommended_action": recommended_action,
                }
            )
    return diagnosis_rows


def _classify_sample_matrix_missing_reason(
    *,
    sample_id: str,
    canonical_key: str,
    rows_for_key: list[dict[str, Any]],
    direct_rows: list[dict[str, Any]],
    long_rows: list[dict[str, Any]],
    has_global_value: bool,
) -> tuple[str, str]:
    if not rows_for_key:
        return "no_parameter_extracted", "leave_blank"
    if direct_rows and not long_rows:
        return "sample_linked_but_missing_from_matrix", "fix_matrix_bug"
    if has_global_value and not long_rows:
        return "global_applies_to_all_samples", "broadcast_global_if_allowed"
    unresolved_rows = [row for row in rows_for_key if not _linked_sample_ids_from_final_row(row)]
    if unresolved_rows:
        sample_level_unresolved = [row for row in unresolved_rows if not _is_not_sample_level_parameter(row)]
        if sample_level_unresolved:
            return "extracted_but_unresolved_sample", "needs_sample_resolution"
    if any(_linked_sample_ids_from_final_row(row) for row in rows_for_key):
        return "parameter_belongs_to_other_samples", "leave_blank"
    if any(_is_not_sample_level_parameter(row) for row in rows_for_key):
        return "not_sample_level", "leave_blank"
    return "extracted_but_unresolved_sample", "needs_sample_resolution"


def _linked_sample_ids_from_final_row(row: dict[str, Any]) -> list[str]:
    sample_ids = _split_semicolon_field(row.get("linked_sample_ids"))
    resolved_sample_id = _string_or_none(row.get("resolved_sample_id"))
    if resolved_sample_id and resolved_sample_id not in sample_ids:
        sample_ids.insert(0, resolved_sample_id)
    return _sorted_unique(sample_ids)


def _can_broadcast_parameter_to_all_samples(
    row: dict[str, Any],
    *,
    direct_sample_rows_for_key: list[dict[str, Any]],
) -> bool:
    canonical_key = _string_or_none(row.get("canonical_key"))
    source_scope = (_string_or_none(row.get("source_scope")) or "").casefold()
    if not canonical_key or canonical_key not in _SAMPLE_MATRIX_GLOBAL_BROADCAST_KEYS:
        return False
    if direct_sample_rows_for_key:
        return False
    value = _display_value(row)
    if not value:
        return False
    if canonical_key in _SAMPLE_MATRIX_NON_BROADCAST_KEYS:
        return False
    if _is_not_sample_level_parameter(row):
        return False
    if "global" not in source_scope and "paper" not in source_scope:
        return False
    return bool(value)


def _is_not_sample_level_parameter(row: dict[str, Any]) -> bool:
    canonical_key = _string_or_none(row.get("canonical_key")) or ""
    source_scope = (_string_or_none(row.get("source_scope")) or "").casefold()
    category = (_string_or_none(row.get("category")) or "").casefold()
    if canonical_key in _SAMPLE_MATRIX_NON_BROADCAST_KEYS:
        return True
    if "peak_position" in canonical_key:
        return True
    if canonical_key.startswith(("xrd_", "ftir_", "raman_", "nmr_")):
        return True
    if "spectra" in source_scope or "figure" in source_scope or "stage4" in source_scope:
        return True
    if "performance" in source_scope or "result" in source_scope:
        return True
    if category in {"spectra", "spectral_feature", "figure_observation", "performance"}:
        return True
    return False


def _split_semicolon_field(value: Any) -> list[str]:
    text = _string_or_none(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _build_parameter_semantic_qa(
    parameters: list[dict[str, Any]],
    *,
    paper_identity: dict[str, Any],
    ontology_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in parameters:
        canonical_key = row.get("canonical_key")
        ontology_entry = ontology_map.get(str(canonical_key), {}) if canonical_key else {}
        source_category = row.get("category")
        local_category = ontology_entry.get("category")
        semantic_role, included, exclusion_reason = classify_parameter_semantic_role(
            canonical_key=canonical_key,
            source_scope=row.get("source_scope"),
            local_category=local_category,
            source_category=source_category,
            normalization_note=row.get("normalization_note"),
        )
        value_num = row.get("value")
        try:
            numeric_value = float(value_num)
        except (TypeError, ValueError):
            numeric_value = None
        rows.append(
            {
                "paper_id": row.get("paper_id") or paper_identity.get("paper_id"),
                "paper_category": paper_identity.get("paper_category"),
                "paper_category_status": paper_identity.get("paper_category_status"),
                "paper_dir": paper_identity.get("paper_dir"),
                "parameter_id": row.get("parameter_id"),
                "original_name": row.get("raw_name"),
                "canonical_name": canonical_key,
                "canonical_key": canonical_key,
                "local_category": local_category,
                "source_category": source_category,
                "parameter_family": _infer_parameter_family_from_key(canonical_key, local_category, row.get("source_scope")),
                "raw_value": row.get("value"),
                "numeric_value": numeric_value,
                "unit": row.get("unit"),
                "source_scope": row.get("source_scope"),
                "source_file": f"{paper_identity.get('paper_dir')}/final_dataset/parameters.jsonl" if paper_identity.get("paper_dir") else "final_dataset/parameters.jsonl",
                "source_stage": "stage5.materialization",
                "parameter_semantic_role": semantic_role,
                "included_in_main_parameter_landscape": included,
                "exclusion_reason": exclusion_reason,
            }
        )
    return rows


def _build_excluded_parameter_row(
    row: dict[str, Any],
    semantic_row: dict[str, Any],
    *,
    paper_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "paper_id": row.get("paper_id") or paper_identity.get("paper_id"),
        "paper_category": paper_identity.get("paper_category"),
        "paper_category_status": paper_identity.get("paper_category_status"),
        "paper_dir": paper_identity.get("paper_dir"),
        "parameter_id": row.get("parameter_id"),
        "original_name": row.get("raw_name"),
        "canonical_name": row.get("canonical_key"),
        "parameter_family": semantic_row.get("parameter_family"),
        "raw_value": row.get("value"),
        "numeric_value": semantic_row.get("numeric_value"),
        "unit": row.get("unit"),
        "source_file": semantic_row.get("source_file"),
        "source_stage": semantic_row.get("source_stage"),
        "exclusion_reason": semantic_row.get("exclusion_reason"),
        "parameter_semantic_role": semantic_row.get("parameter_semantic_role"),
    }


def _infer_parameter_family_from_key(canonical_key: Any, local_category: Any, source_scope: Any) -> str:
    key = _string_or_none(canonical_key) or ""
    lower = key.lower()
    local = (_string_or_none(local_category) or "").lower()
    scope = (_string_or_none(source_scope) or "").lower()
    if any(token in lower for token in ("xrd_peak", "2theta")):
        return "XRD peak"
    if "ftir_peak" in lower:
        return "FTIR peak"
    if lower.startswith("nmr_") or "chemical_shift" in lower:
        return "NMR shift"
    if "raman_peak" in lower:
        return "Raman peak"
    if lower.startswith(("tg_", "dsc_")) or "thermal_event" in lower:
        return "TG/DSC event"
    if "spectra" in scope or local in CHARACTERIZATION_CATEGORY_HINTS:
        return "characterization output"
    if "ph" == lower or lower.endswith("_ph"):
        return "pH"
    return local_category or "other"


def _collect_sample_matrix_dynamic_keys(rows: list[dict[str, Any]]) -> list[str]:
    reserved_fields = set(SAMPLE_PARAMETER_MATRIX_FIELDS)
    dynamic_keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key in reserved_fields or key in seen:
                continue
            seen.add(key)
            dynamic_keys.append(key)
    return dynamic_keys


def _build_process_steps_table(
    *,
    paper_id: str,
    title: str,
    process_steps: list[dict[str, Any]],
    indexes: dict[str, Any],
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(process_steps, start=1):
        step_id = step.get("step_id") or f"{paper_id}-step-{index:03d}"
        step_links = [
            link
            for link in indexes["links_by_process_step"].get(step_id, [])
            if {link.get("source_type"), link.get("target_type")} == {"process_step", "parameter"}
        ]
        linked_parameters = []
        for link in step_links:
            parameter_id = link.get("target_id") if link.get("target_type") == "parameter" else link.get("source_id")
            parameter_row = indexes["parameters_by_id"].get(parameter_id)
            if parameter_row:
                linked_parameters.append((link, parameter_row))
        rows.append(
            {
                "paper_id": paper_id,
                "paper_category": paper_identity.get("paper_category"),
                "paper_category_status": paper_identity.get("paper_category_status"),
                "paper_dir": paper_identity.get("paper_dir"),
                "title": title,
                "step_id": step_id,
                "step_order": step.get("step_order") or index,
                "section": step.get("section"),
                "action": step.get("action"),
                "action_zh": step.get("action_zh"),
                "reagent_name": step.get("reagent_name"),
                "reagent_formula": step.get("reagent_formula"),
                "reagent_amount": step.get("reagent_amount"),
                "reagent_unit": step.get("reagent_unit"),
                "reagent_role": step.get("reagent_role"),
                "condition_key": step.get("condition_key"),
                "condition_value": step.get("condition_value"),
                "condition_unit": step.get("condition_unit"),
                "equipment": step.get("equipment"),
                "duration_value": step.get("duration_value"),
                "duration_unit": step.get("duration_unit"),
                "temperature_value": step.get("temperature_value"),
                "temperature_unit": step.get("temperature_unit"),
                "heating_rate_value": step.get("heating_rate_value"),
                "heating_rate_unit": step.get("heating_rate_unit"),
                "product_or_outcome": step.get("product_or_outcome"),
                "linked_parameter_keys": "; ".join(_coerce_str_list(step.get("linked_parameter_keys"))),
                "linked_parameter_ids": "; ".join(_sorted_unique([row.get("parameter_id") for _, row in linked_parameters])),
                "linked_canonical_keys": "; ".join(_sorted_unique([row.get("canonical_key") for _, row in linked_parameters])),
                "linked_values": "; ".join(
                    _sorted_unique([_display_value_from_parameter(row) for _, row in linked_parameters if _display_value_from_parameter(row)])
                ),
                "linked_units": "; ".join(
                    _sorted_unique([
                        _normalize_unit_text(row.get("unit")) or _infer_unit_from_canonical_key(row.get("canonical_key"))
                        for _, row in linked_parameters
                    ])
                ),
                "link_confidences": "; ".join(_sorted_unique([link.get("confidence") for link, _ in linked_parameters])),
                "evidence_text": step.get("evidence_text"),
                "source_file": f"{paper_identity.get('paper_dir')}/final_dataset/process_steps.jsonl" if paper_identity.get("paper_dir") else "final_dataset/process_steps.jsonl",
                "source_stage": "stage5.link_aware_export",
                "confidence": step.get("confidence"),
                "needs_manual_review": step.get("needs_manual_review"),
            }
        )
    return rows


def _build_evidence_parameter_links(
    *,
    paper_id: str,
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    links: list[dict[str, Any]],
    indexes: dict[str, Any],
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_id = indexes["evidence_by_id"]
    parameter_by_id = indexes["parameters_by_id"]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_row(
        source_type: str,
        source_id: str | None,
        evidence_text_preview: str | None,
        evidence_row: dict[str, Any] | None,
        parameter_row: dict[str, Any],
        *,
        link_type: str,
        confidence: str,
        reasoning: str | None,
        created_by: str,
        validation_status: str = "accepted",
    ) -> None:
        key = (str(source_type), str(source_id), str(parameter_row.get("parameter_id")))
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "paper_id": paper_id,
                "paper_category": paper_identity.get("paper_category"),
                "paper_category_status": paper_identity.get("paper_category_status"),
                "paper_dir": paper_identity.get("paper_dir"),
                "source_type": source_type,
                "source_id": source_id,
                "evidence_text_preview": evidence_text_preview,
                "evidence_id": evidence_row.get("evidence_id") if evidence_row else None,
                "evidence_type": evidence_row.get("evidence_type") if evidence_row else source_type,
                "figure_id": evidence_row.get("figure_id") if evidence_row else None,
                "table_id": evidence_row.get("table_id") if evidence_row else None,
                "figure_type": evidence_row.get("figure_type") if evidence_row else None,
                "caption": evidence_row.get("caption") if evidence_row else None,
                "parameter_id": parameter_row.get("parameter_id"),
                "canonical_key": parameter_row.get("canonical_key"),
                "parameter_value": parameter_row.get("value"),
                "unit": None
                if parameter_row.get("unit") == "text"
                else normalize_parameter_unit(parameter_row.get("unit"), parameter_row.get("canonical_key")),
                "sample_id": parameter_row.get("sample_id"),
                "source_file": f"{paper_identity.get('paper_dir')}/final_dataset/linking/links.jsonl" if paper_identity.get("paper_dir") else "final_dataset/linking/links.jsonl",
                "source_stage": "stage5.link_aware_export",
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
        if {source_type, target_type} == {"evidence_object", "parameter"}:
            evidence_id = link.get("source_id") if source_type == "evidence_object" else link.get("target_id")
            parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
            evidence_row = evidence_by_id.get(evidence_id)
            parameter_row = parameter_by_id.get(parameter_id)
            if evidence_row and parameter_row:
                add_row(
                    "evidence_object",
                    evidence_id,
                    _evidence_preview(evidence_row, limit=120),
                    evidence_row,
                    parameter_row,
                    link_type=link.get("link_type") or "supports",
                    confidence=link.get("confidence") or "medium",
                    reasoning=link.get("reasoning"),
                    created_by=link.get("created_by") or "llm",
                    validation_status=link.get("validation_status") or "accepted",
                )
            continue
        if {source_type, target_type} == {"process_step", "parameter"}:
            process_step_id = link.get("source_id") if source_type == "process_step" else link.get("target_id")
            parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
            process_step_row = indexes["process_steps_by_id"].get(process_step_id)
            parameter_row = parameter_by_id.get(parameter_id)
            if process_step_row and parameter_row:
                add_row(
                    "process_step",
                    process_step_id,
                    _truncate(str(process_step_row.get("evidence_text") or ""), 120),
                    None,
                    parameter_row,
                    link_type=link.get("link_type") or "supports",
                    confidence=link.get("confidence") or "medium",
                    reasoning=link.get("reasoning"),
                    created_by=link.get("created_by") or "deterministic_process_step_value_match",
                    validation_status=link.get("validation_status") or "accepted",
                )

    evidence_by_figure = indexes["evidence_by_figure"]
    for parameter_row in parameters:
        explicit_ids = _extract_explicit_evidence_ids(parameter_row.get("evidence_refs"), evidence_by_id, evidence_by_figure)
        for evidence_id in explicit_ids:
            evidence_row = evidence_by_id.get(evidence_id)
            if evidence_row:
                add_row(
                    "evidence_object",
                    evidence_id,
                    _evidence_preview(evidence_row, limit=120),
                    evidence_row,
                    parameter_row,
                    link_type="supports",
                    confidence="high",
                    reasoning="parameter.evidence_refs contains evidence reference",
                    created_by="direct_evidence_refs",
                )
        for text_ref in _extract_direct_text_evidence_refs(parameter_row):
            add_row(
                "text_reference",
                text_ref["source_id"],
                text_ref["evidence_text_preview"],
                None,
                parameter_row,
                link_type="supports",
                confidence=text_ref["confidence"],
                reasoning=text_ref["reasoning"],
                created_by="direct_text_evidence_refs",
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
    paper_identity: dict[str, Any],
) -> list[dict[str, Any]]:
    parameter_by_id = indexes["parameters_by_id"]
    spectra_by_id = indexes["spectra_by_id"]
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
        observed_value: Any,
        observed_unit: str | None,
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
                "paper_category": paper_identity.get("paper_category"),
                "paper_category_status": paper_identity.get("paper_category_status"),
                "paper_dir": paper_identity.get("paper_dir"),
                "spectra_id": spectra_id,
                "figure_id": figure_id,
                "figure_type": figure_type,
                "technique": technique,
                "peak_position": peak_position,
                "peak_unit": peak_unit,
                "assignment": assignment,
                "source": source,
                "observed_value": observed_value,
                "observed_unit": observed_unit,
                "parameter_id": parameter_id,
                "canonical_key": canonical_key,
                "parameter_value": parameter_value,
                "unit": None if unit == "text" else normalize_parameter_unit(unit, canonical_key),
                "sample_id": sample_id,
                "source_file": f"{paper_identity.get('paper_dir')}/final_dataset/spectra.jsonl" if paper_identity.get("paper_dir") else "final_dataset/spectra.jsonl",
                "source_stage": "stage5.link_aware_export",
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
            peak_unit=coerce_peak_unit(
                peak.get("unit"),
                figure_type=spectra_row.get("figure_type"),
                canonical_key=parameter_row.get("canonical_key"),
                technique=spectra_row.get("technique"),
            ),
            assignment=peak.get("assignment"),
            source=peak.get("source"),
            observed_value=peak.get("position"),
            observed_unit=coerce_peak_unit(
                peak.get("unit"),
                figure_type=spectra_row.get("figure_type"),
                canonical_key=parameter_row.get("canonical_key"),
                technique=spectra_row.get("technique"),
            ),
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

    for link in links:
        source_type = link.get("source_type")
        target_type = link.get("target_type")
        if {source_type, target_type} != {"spectra_record", "parameter"}:
            continue
        spectra_id = link.get("source_id") if source_type == "spectra_record" else link.get("target_id")
        parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
        parameter_row = parameter_by_id.get(parameter_id)
        spectra_row = spectra_by_id.get(spectra_id)
        if not (parameter_row and spectra_row):
            continue
        observed_value, observed_unit = _pick_observed_value_for_parameter(parameter_row, spectra_row)
        add_row(
            spectra_id=spectra_id,
            figure_id=spectra_row.get("figure_id"),
            figure_type=spectra_row.get("figure_type"),
            technique=spectra_row.get("technique"),
            peak_position=None,
            peak_unit=None,
            assignment=None,
            source=None,
            observed_value=observed_value,
            observed_unit=observed_unit,
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

    for link in links:
        source_type = link.get("source_type")
        target_type = link.get("target_type")
        if {source_type, target_type} != {"visual_extraction", "parameter"}:
            continue
        visual_id = link.get("source_id") if source_type == "visual_extraction" else link.get("target_id")
        parameter_id = link.get("target_id") if target_type == "parameter" else link.get("source_id")
        parameter_row = parameter_by_id.get(parameter_id)
        visual_info = _parse_visual_source_id(visual_id)
        spectra_row = spectra_by_id.get(_spectra_id_for_figure(visual_info["figure_id"])) if visual_info else None
        if not (parameter_row and spectra_row):
            continue
        observed_value, observed_unit = _pick_observed_value_for_parameter(parameter_row, spectra_row, preferred_key=visual_info.get("source_key"))
        add_row(
            spectra_id=_spectra_id_for_figure(visual_info["figure_id"]),
            figure_id=spectra_row.get("figure_id"),
            figure_type=spectra_row.get("figure_type"),
            technique=spectra_row.get("technique"),
            peak_position=None,
            peak_unit=None,
            assignment=None,
            source=visual_info.get("source_key"),
            observed_value=observed_value,
            observed_unit=observed_unit,
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
        for row in evidence_links:
            parameter_row = parameter_by_id.get(row.get("parameter_id"))
            if not parameter_row:
                continue
            all_units = "; ".join(
                _sorted_unique(
                    [
                        coerce_peak_unit(
                            peak.get("unit"),
                            figure_type=spectra_row.get("figure_type"),
                            canonical_key=parameter_row.get("canonical_key"),
                            technique=spectra_row.get("technique"),
                        )
                        for peak in spectra_row.get("peaks", [])
                        if peak.get("unit")
                    ]
                )
            )
            all_assignments = "; ".join(_sorted_unique([peak.get("assignment") for peak in spectra_row.get("peaks", []) if peak.get("assignment")]))
            all_sources = "; ".join(_sorted_unique([peak.get("source") for peak in spectra_row.get("peaks", []) if peak.get("source")]))
            add_row(
                spectra_id=spectra_id,
                figure_id=spectra_row.get("figure_id"),
                figure_type=spectra_row.get("figure_type"),
                technique=spectra_row.get("technique"),
                peak_position=all_positions or None,
                peak_unit=all_units or None,
                assignment=all_assignments or None,
                source=all_sources or None,
                observed_value=all_positions or None,
                observed_unit=all_units or None,
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
    include_showcase: bool,
) -> list[dict[str, Any]]:
    if not include_showcase:
        return []
    sample_names = {row.get("sample_id"): row.get("sample_name") for row in samples if row.get("sample_id")}
    priority = {
        "strong_evidence": 0,
        "process_step_evidence": 1,
        "linked_evidence": 2,
        "linked_spectra": 3,
        "sample_link_only": 4,
        "missing": 5,
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
            "process_step_evidence": "evidence-linked",
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



def _normalize_parameter_value(value: Any, unit: Any, canonical_key: Any = None) -> dict[str, Any]:
    unit_text = normalize_parameter_unit(unit, canonical_key) or _infer_unit_from_canonical_key(canonical_key)
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


def _extract_direct_text_evidence_refs(parameter_row: dict[str, Any]) -> list[dict[str, str]]:
    rows_by_source_id: dict[str, dict[str, str]] = {}
    fallback_preview = next(
        (
            candidate
            for candidate in (
                _string_or_none(parameter_row.get("quote_or_context")),
                _string_or_none(parameter_row.get("source_text")),
                _string_or_none(parameter_row.get("text")),
                _string_or_none(parameter_row.get("raw_name")),
            )
            if candidate
        ),
        None,
    )

    def add_row(
        source_id: str,
        *,
        evidence_text_preview: str | None,
        confidence: str,
        reasoning: str,
    ) -> None:
        existing = rows_by_source_id.get(source_id)
        if existing is None:
            rows_by_source_id[source_id] = {
                "source_id": source_id,
                "evidence_text_preview": _truncate(evidence_text_preview or source_id, 120),
                "confidence": confidence,
                "reasoning": reasoning,
            }
            return
        if _confidence_rank(confidence) > _confidence_rank(existing.get("confidence")):
            existing["confidence"] = confidence
        if evidence_text_preview and existing.get("evidence_text_preview") == source_id:
            existing["evidence_text_preview"] = _truncate(evidence_text_preview, 120)

    for ref in parameter_row.get("evidence_refs") or []:
        source_id = None
        quote_or_context = None
        section = None
        confidence = "medium"
        if isinstance(ref, dict):
            source_id = _string_or_none(ref.get("source_id"))
            quote_or_context = _string_or_none(ref.get("quote_or_context"))
            section = _string_or_none(ref.get("section"))
            confidence = _normalize_confidence_label(ref.get("confidence"))
        elif isinstance(ref, str):
            source_id = _string_or_none(ref)
        if not source_id or not source_id.startswith("text:"):
            continue
        preview_source = quote_or_context or section or fallback_preview or source_id
        reasoning = "parameter already carries text reference in evidence_refs"
        if section:
            reasoning = f"{reasoning} ({section})"
        add_row(
            source_id,
            evidence_text_preview=preview_source,
            confidence=confidence,
            reasoning=reasoning,
        )

    for source_id in _extract_matched_full_text_refs(parameter_row.get("normalization_note")):
        add_row(
            source_id,
            evidence_text_preview=fallback_preview or source_id,
            confidence="medium",
            reasoning="derived from normalization_note matched_full_text text reference",
        )

    return list(rows_by_source_id.values())


def _extract_matched_full_text_refs(normalization_note: Any) -> list[str]:
    note = _string_or_none(normalization_note)
    if not note:
        return []
    return _sorted_unique(re.findall(r"matched_full_text:(text:[^;,\s]+)", note))


def _confidence_rank(label: Any) -> int:
    normalized = _normalize_confidence_label(label)
    return {"low": 0, "medium": 1, "high": 2}.get(normalized, 1)


def _parse_peak_source_id(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    match = re.match(r"^(spectra-.+)-peak-(\d+)$", str(source_id))
    if not match:
        return None
    return {"spectra_id": match.group(1), "peak_index": int(match.group(2))}


def _parse_visual_source_id(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    match = re.match(r"^visual-(.+?)-([^:-]+(?:_[^:-]+)*)$", str(source_id))
    if not match:
        return None
    return {"figure_id": match.group(1), "source_key": match.group(2)}


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


def _pick_observed_value_for_parameter(
    parameter_row: dict[str, Any],
    spectra_row: dict[str, Any],
    *,
    preferred_key: str | None = None,
) -> tuple[Any, str | None]:
    quantitative_values = spectra_row.get("quantitative_values") or {}
    if preferred_key and preferred_key in quantitative_values:
        return quantitative_values.get(preferred_key), _infer_observed_unit(preferred_key)
    canonical_key = str(parameter_row.get("canonical_key") or "")
    if canonical_key in quantitative_values:
        return quantitative_values.get(canonical_key), _infer_observed_unit(canonical_key)
    for key in (
        preferred_key,
        canonical_key,
        "particle_size_nm",
        "estimated_size_nm",
        "fiber_diameter_um",
        "average_fiber_diameter_um",
    ):
        if key and spectra_row.get(key) is not None:
            return spectra_row.get(key), _infer_observed_unit(key)
    return None, None


def _infer_observed_unit(key: str | None) -> str | None:
    if not key:
        return None
    text = str(key)
    if text.endswith("_nm"):
        return "nm"
    if text.endswith("_um"):
        return "um"
    if text.endswith("_wt_percent"):
        return "wt_percent"
    if text.endswith("_C"):
        return "C"
    return None


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


def _normalize_unit_text(unit: Any) -> str | None:
    return normalize_shared_unit_text(unit)


def _infer_unit_from_canonical_key(canonical_key: Any) -> str | None:
    key = _string_or_none(canonical_key)
    if not key:
        return None
    lookup = {
        "pH": None,
        "applied_voltage_kV": "kV",
        "collector_distance_cm": "cm",
        "feed_rate_ml_h": "mL/h",
        "holding_time_h": "h",
        "heating_rate_C_min": "C/min",
        "calcination_temperature_C": "C",
        "target_temperature_C": "C",
        "ambient_temperature_C": "C",
        "particle_size_nm": "nm",
        "average_fiber_diameter_um": "um",
        "mass_loss_wt_percent": "wt%",
        "pvp_content_wt_percent": "wt%",
        "xrd_peak_position_2theta_deg": "2theta_deg",
        "ftir_peak_position_cm_1": "cm-1",
        "raman_peak_position_cm_1": "cm-1",
        "nmr_27Al_peak_position_ppm": "ppm",
        "viscosity_Pa_s": "Pa*s",
    }
    if key in lookup:
        return lookup[key]
    suffix_lookup = (
        ("_nm", "nm"),
        ("_um", "um"),
        ("_wt_percent", "wt%"),
        ("_ppm", "ppm"),
        ("_kV", "kV"),
        ("_MPa", "MPa"),
        ("_kg", "kg"),
        ("_m3", "m3"),
        ("_cm", "cm"),
        ("_mm", "mm"),
        ("_mL", "mL"),
        ("_ml_h", "mL/h"),
        ("_m_min", "m/min"),
        ("_h", "h"),
        ("_C", "C"),
        ("_cm_1", "cm-1"),
        ("_2theta_deg", "2theta_deg"),
    )
    for suffix, inferred_unit in suffix_lookup:
        if key.endswith(suffix):
            return inferred_unit
    return None


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value)]


def _normalize_confidence_label(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value >= 0.75:
            return "high"
        if value >= 0.4:
            return "medium"
        return "low"
    text = (_string_or_none(value) or "").casefold()
    if text in {"high", "medium", "low"}:
        return text
    return "medium"


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
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def _display_value(row: dict[str, Any]) -> str:
    if row.get("value_text"):
        return str(row["value_text"])
    if row.get("value_num") is not None:
        value = row["value_num"]
        unit = _normalize_unit_text(row.get("unit"))
        if float(value).is_integer():
            text = str(int(float(value)))
        else:
            text = str(value)
        return text if unit is None else f"{text} {unit}"
    if row.get("value_min") is not None and row.get("value_max") is not None:
        unit = _normalize_unit_text(row.get("unit"))
        range_text = f"{row['value_min']}-{row['value_max']}"
        return range_text if unit is None else f"{range_text} {unit}"
    return _stringify(row.get("value_raw"))


def _showcase_confidence(link_confidences: Any) -> str:
    text = _string_or_none(link_confidences) or ""
    for item in ("high", "medium", "low"):
        if item in text:
            return item
    return ""



def _display_value_from_parameter(row: dict[str, Any]) -> str:
    value_meta = _normalize_parameter_value(row.get("value"), row.get("unit"), row.get("canonical_key"))
    display_row = {
        "value_text": value_meta.get("value_text"),
        "value_num": value_meta.get("value_num"),
        "value_min": value_meta.get("value_min"),
        "value_max": value_meta.get("value_max"),
        "value_raw": value_meta.get("value_raw"),
        "unit": value_meta.get("unit"),
    }
    return _display_value(display_row)


def _resolve_evidence_status(
    explicit_evidence_ids: list[str],
    evidence_rows: list[dict[str, Any]],
    spectra_rows: list[dict[str, Any]],
    linked_sample_ids: list[str],
    process_step_rows: list[dict[str, Any]] | None = None,
) -> str:
    if explicit_evidence_ids:
        return "strong_evidence"
    if process_step_rows:
        return "process_step_evidence"
    if evidence_rows:
        return "linked_evidence"
    if spectra_rows:
        return "linked_spectra"
    if linked_sample_ids:
        return "sample_link_only"
    return "missing"

