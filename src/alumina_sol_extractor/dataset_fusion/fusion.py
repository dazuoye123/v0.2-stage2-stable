"""Stage 5 fusion logic for Stage 3 and Stage 4 outputs."""

from __future__ import annotations

import itertools
from collections import defaultdict
from pathlib import Path
from typing import Any

from alumina_sol_extractor.ontology import get_canonical_keys, normalize_key

from .loaders import load_paper_inputs
from .models import EvidenceRecord, PaperRecord, ParameterRow, SampleRecord, SpectraRecord
from .report import render_fusion_report
from .validators import build_quality_summary

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_stage5_dataset_fusion(
    *,
    paper_id: str,
    output_dir: Path | str,
    stage3_dir: Path | str | None = None,
    stage4_dir: Path | str | None = None,
    output_dataset_dir: Path | str | None = None,
) -> dict[str, Any]:
    inputs = load_paper_inputs(
        output_dir,
        stage3_dir=stage3_dir,
        stage4_dir=stage4_dir,
        output_dataset_dir=output_dataset_dir,
    )
    stage3 = inputs["stage3"]
    stage4 = inputs["stage4"]

    paper = _build_paper_record(paper_id=paper_id, paper_basic_info=stage3.get("paper_basic_info", {}))
    evidence = _build_evidence_records(stage3.get("evidence_objects", []))
    spectra = _build_spectra_records(
        stage4.get("spectra_extractions", []),
        stage4.get("quality_review", {}).get("figures", []),
    )
    parameters, weak_links, ontology_gaps, rejected_parameters = _build_parameter_rows(
        paper_id=paper_id,
        global_constants=stage3.get("global_constants", {}),
        data_points=stage3.get("data_points", []),
        experiment_series=stage3.get("experiment_series", []),
        spectra=spectra,
    )
    evidence_index = _build_evidence_index(evidence)
    spectra_index = {item.get("figure_id"): item for item in spectra if item.get("figure_id")}
    _link_parameters(parameters, evidence_index=evidence_index, spectra_index=spectra_index, weak_links=weak_links)
    samples = _build_sample_rows(
        data_points=stage3.get("data_points", []),
        experiment_series=stage3.get("experiment_series", []),
        parameters=parameters,
        evidence_index=evidence_index,
        spectra_index=spectra_index,
        default_material_type=paper.get("material_system"),
    )
    figures = _build_figure_rows(evidence=evidence, spectra=spectra)
    final_dataset_rows = _build_final_dataset_rows(parameters)
    fusion_warnings = _collect_fusion_warnings(parameters, spectra, weak_links, inputs)
    quality_summary = build_quality_summary(
        stage3_summary=stage3.get("summary", {}),
        stage4_summary=stage4.get("summary", {}),
        stage4_review=stage4.get("quality_review", {}),
        parameters=parameters,
        evidence=evidence,
        spectra=spectra,
        samples=samples,
        fusion_warnings=fusion_warnings,
        rejected_parameters=rejected_parameters,
    )
    bundle = {
        "paper": paper,
        "evidence": evidence,
        "spectra": spectra,
        "parameters": parameters,
        "samples": samples,
        "figures": figures,
        "final_dataset_rows": final_dataset_rows,
        "quality_summary": quality_summary,
        "weak_links": weak_links,
        "ontology_gaps": ontology_gaps,
        "rejected_parameters": rejected_parameters,
        "inputs": {
            "dirs": {key: str(value) for key, value in inputs["dirs"].items()},
            "file_index": inputs["file_index"],
            "file_presence": inputs["file_presence"],
        },
    }
    bundle["fusion_report"] = render_fusion_report(bundle)
    return bundle


def _build_paper_record(*, paper_id: str, paper_basic_info: dict[str, Any]) -> dict[str, Any]:
    title = paper_basic_info.get("title")
    authors = paper_basic_info.get("authors", [])
    year = paper_basic_info.get("year")
    source_file = paper_basic_info.get("source_file")
    material_system = paper_basic_info.get("material_system")
    process_route = paper_basic_info.get("process_route")
    keywords = paper_basic_info.get("keywords", [])
    abstract = paper_basic_info.get("abstract")
    material_system, process_route = _apply_paper_fallbacks(
        material_system=material_system,
        process_route=process_route,
        title=title,
        abstract=abstract,
        keywords=keywords,
        source_file=source_file,
    )
    payload = PaperRecord(
        paper_id=paper_id,
        title=title,
        authors=authors,
        year=year,
        source_file=source_file,
        material_system=material_system,
        process_route=process_route,
        keywords=keywords,
        abstract=abstract,
    ).model_dump()
    return payload


def _build_evidence_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for record in records:
        payload.append(
            EvidenceRecord(
                evidence_id=record.get("evidence_id"),
                figure_id=record.get("figure_id"),
                table_id=record.get("table_id"),
                evidence_type=record.get("evidence_type"),
                figure_type=record.get("figure_type"),
                caption=record.get("caption"),
                fact_summary=_ensure_str_list(record.get("fact_summary") or record.get("key_facts")),
                detailed_observation=record.get("detailed_observation"),
                source_section=record.get("source_section"),
                confidence=record.get("confidence"),
            ).model_dump()
        )
    return payload


def _build_spectra_records(
    extractions: list[dict[str, Any]],
    quality_review_figures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_by_figure = {str(item.get("figure_id")): item for item in quality_review_figures if item.get("figure_id")}
    payload: list[dict[str, Any]] = []
    for record in extractions:
        review = review_by_figure.get(str(record.get("figure_id")))
        source_distribution = review.get("source_distribution", {}) if review else _infer_source_distribution(record)
        payload.append(
            SpectraRecord(
                figure_id=record.get("figure_id"),
                figure_type=record.get("figure_type"),
                schema_name=record.get("schema_name"),
                technique=record.get("technique"),
                extraction_mode=record.get("extraction_mode"),
                peaks=record.get("peaks") or [],
                source_distribution=source_distribution,
                confidence=record.get("confidence"),
                warning_codes=review.get("warning_codes", []) if review else [],
                quality_review_assessment=review.get("assessment") if review else None,
                conflict_warnings=review.get("conflict_warnings", []) if review else list(record.get("conflict_warnings") or []),
            ).model_dump()
            | {
                "quantitative_values": record.get("quantitative_values") or {},
                "species_quantification": record.get("species_quantification") or {},
                "curve_type": record.get("curve_type"),
                "equation": record.get("equation"),
                "fitted_parameters": record.get("fitted_parameters") or {},
                "method_summary": review.get("method_summary") if review else None,
            }
        )
    return payload


def _build_parameter_rows(
    *,
    paper_id: str,
    global_constants: dict[str, Any],
    data_points: list[dict[str, Any]],
    experiment_series: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    weak_links: list[dict[str, Any]] = []
    ontology_gaps: list[str] = []
    rejected_parameters: list[dict[str, Any]] = []
    counter = itertools.count(1)

    for record in global_constants.get("additional_parameter_records", []) or []:
        records.extend(
            _normalize_parameter_like_record(
                record,
                paper_id=paper_id,
                sample_id=None,
                series_id=None,
                source_scope="global_constants.additional_parameter_records",
                counter=counter,
            )
        )

    for series_index, series in enumerate(experiment_series, start=1):
        series_id = _string_or_none(series.get("series_id")) or f"series_{series_index}"
        for record in _extract_parameter_records_from_mapping(
            series.get("variables") or {},
            base_scope="experiment_series.variables",
            raw_name_prefix="variables",
        ):
            records.extend(
                _normalize_parameter_like_record(
                    record,
                    paper_id=paper_id,
                    sample_id=None,
                    series_id=series_id,
                    source_scope=record.pop("_source_scope", "experiment_series.variables"),
                    counter=counter,
                )
            )

    for data_point in data_points:
        sample_id = _string_or_none(data_point.get("sample_id"))
        for section_name in ("independent_variable_values", "additional_parameter_records"):
            for record in data_point.get(section_name, []) or []:
                records.extend(
                    _normalize_parameter_like_record(
                        record,
                        paper_id=paper_id,
                        sample_id=sample_id,
                        series_id=None,
                        source_scope=f"data_point.{section_name}",
                        counter=counter,
                    )
                )
        for mapping_name in ("process_parameters", "results"):
            mapping = data_point.get(mapping_name) or {}
            extracted = _extract_parameter_records_from_mapping(mapping, base_scope=f"data_point.{mapping_name}")
            for record in extracted:
                records.extend(
                    _normalize_parameter_like_record(
                        record,
                        paper_id=paper_id,
                        sample_id=sample_id,
                        series_id=None,
                        source_scope=record.pop("_source_scope", f"data_point.{mapping_name}"),
                        counter=counter,
                    )
                )
        extended_data = data_point.get("extended_data") or {}
        extracted_extended = _extract_parameter_records_from_mapping(
            extended_data,
            base_scope="data_point.extended_data",
        )
        for record in extracted_extended:
            records.extend(
                _normalize_parameter_like_record(
                    record,
                    paper_id=paper_id,
                    sample_id=sample_id,
                    series_id=None,
                    source_scope=record.pop("_source_scope", "data_point.extended_data"),
                    counter=counter,
                )
            )

    accepted_records: list[dict[str, Any]] = []
    for record in records:
        if _is_invalid_canonical_key(record.get("canonical_key")):
            rejected_parameters.append(
                {
                    "parameter_id": record.get("parameter_id"),
                    "raw_name": record.get("raw_name"),
                    "canonical_key": record.get("canonical_key"),
                    "source_scope": record.get("source_scope"),
                    "reason": "invalid_canonical_key",
                }
            )
            continue
        accepted_records.append(record)

    for record in accepted_records:
        if not record.get("canonical_key"):
            ontology_gaps.append(record.get("raw_name") or record.get("parameter_id"))
        if not record.get("evidence_refs"):
            weak_match = _find_weak_spectra_link(record, spectra)
            if weak_match:
                record["quality_flags"].append("weak_link_from_spectra")
                weak_links.append(
                    {
                        "parameter_id": record["parameter_id"],
                        "canonical_key": record.get("canonical_key"),
                        "figure_id": weak_match.get("figure_id"),
                        "reason": "weak_link_from_spectra",
                    }
                )
    ontology_gaps = list(dict.fromkeys(item for item in ontology_gaps if item))
    return accepted_records, weak_links, ontology_gaps, rejected_parameters


def _extract_parameter_records_from_mapping(
    payload: dict[str, Any],
    *,
    base_scope: str,
    raw_name_prefix: str | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            if "canonical_key" in node and ("value" in node or "raw_text" in node):
                records.append(dict(node) | {"_source_scope": f"{base_scope}.{'.'.join(path)}" if path else base_scope})
                return
            for key, value in node.items():
                visit(value, [*path, key])
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, [*path, str(index)])
            return
        if node is None:
            return
        raw_name = _pick_parameter_name(path, raw_name_prefix or base_scope)
        records.append(
            {
                "canonical_key": raw_name,
                "raw_name": raw_name,
                "value": node,
                "unit": None,
                "raw_text": str(node),
                "evidence_refs": [],
                "normalization_note": f"generated_from_{base_scope}",
                "_source_scope": f"{base_scope}.{'.'.join(path)}" if path else base_scope,
            }
        )

    visit(payload, [])
    return records


def _normalize_parameter_like_record(
    record: dict[str, Any],
    *,
    paper_id: str,
    sample_id: str | None,
    series_id: str | None,
    source_scope: str,
    counter: itertools.count,
) -> list[dict[str, Any]]:
    base = dict(record)
    value = base.get("value")
    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            split_record = dict(base)
            split_record["value"] = item
            note = _append_note(
                split_record.get("normalization_note"),
                f"stage5_split_list_value:index={index};original_length={len(value)}",
            )
            split_record["normalization_note"] = note
            rows.extend(
                _normalize_parameter_like_record(
                    split_record,
                    paper_id=paper_id,
                    sample_id=sample_id,
                    series_id=series_id,
                    source_scope=source_scope,
                    counter=counter,
                )
            )
        return rows

    parameter_id = f"{paper_id}-param-{next(counter):05d}"
    raw_name = _string_or_none(base.get("raw_name"))
    canonical_key = _coerce_canonical_key(base.get("canonical_key"), raw_name)
    quality_flags = list(base.get("quality_flags") or [])
    if not canonical_key:
        quality_flags.append("canonical_key_missing")
    row = ParameterRow(
        parameter_id=parameter_id,
        paper_id=paper_id,
        sample_id=sample_id,
        series_id=series_id,
        canonical_key=canonical_key,
        raw_name=raw_name,
        value=value,
        unit=base.get("unit"),
        min_value=base.get("min_value"),
        max_value=base.get("max_value"),
        source_scope=source_scope,
        evidence_refs=list(base.get("evidence_refs") or []),
        confidence=base.get("confidence"),
        normalization_note=base.get("normalization_note"),
        quality_flags=quality_flags,
    ).model_dump()
    row["linked_evidence_ids"] = []
    row["linked_figure_ids"] = []
    row["linked_spectra_ids"] = []
    return [row]


def _build_evidence_index(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        for key in ("evidence_id", "figure_id", "table_id"):
            value = row.get(key)
            if value:
                index[str(value)].append(row)
    return index


def _link_parameters(
    parameters: list[dict[str, Any]],
    *,
    evidence_index: dict[str, list[dict[str, Any]]],
    spectra_index: dict[str, dict[str, Any]],
    weak_links: list[dict[str, Any]],
) -> None:
    weak_by_parameter = {item["parameter_id"]: item for item in weak_links}
    for row in parameters:
        evidence_ids: list[str] = []
        figure_ids: list[str] = []
        spectra_ids: list[str] = []
        for token in _extract_reference_tokens(row.get("evidence_refs") or []):
            for evidence_record in evidence_index.get(token, []):
                evidence_id = evidence_record.get("evidence_id")
                figure_id = evidence_record.get("figure_id")
                if evidence_id and evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
                if figure_id and figure_id not in figure_ids:
                    figure_ids.append(figure_id)
                    if figure_id in spectra_index and figure_id not in spectra_ids:
                        spectra_ids.append(figure_id)
        if not evidence_ids and row["parameter_id"] in weak_by_parameter:
            weak_figure_id = weak_by_parameter[row["parameter_id"]]["figure_id"]
            if weak_figure_id and weak_figure_id in spectra_index:
                spectra_ids.append(weak_figure_id)
        row["linked_evidence_ids"] = evidence_ids
        row["linked_figure_ids"] = figure_ids
        row["linked_spectra_ids"] = spectra_ids


def _build_sample_rows(
    *,
    data_points: list[dict[str, Any]],
    experiment_series: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    evidence_index: dict[str, list[dict[str, Any]]],
    spectra_index: dict[str, dict[str, Any]],
    default_material_type: str | None,
) -> list[dict[str, Any]]:
    parameter_ids_by_sample: dict[str, list[str]] = defaultdict(list)
    linked_evidence_by_sample: dict[str, list[str]] = defaultdict(list)
    linked_spectra_by_sample: dict[str, list[str]] = defaultdict(list)
    for row in parameters:
        sample_id = row.get("sample_id")
        if not sample_id:
            continue
        parameter_ids_by_sample[sample_id].append(row["parameter_id"])
        for evidence_id in row.get("linked_evidence_ids", []):
            if evidence_id not in linked_evidence_by_sample[sample_id]:
                linked_evidence_by_sample[sample_id].append(evidence_id)
        for spectra_id in row.get("linked_spectra_ids", []):
            if spectra_id not in linked_spectra_by_sample[sample_id]:
                linked_spectra_by_sample[sample_id].append(spectra_id)

    series_name_by_sample: dict[str, str] = {}
    for series in experiment_series:
        series_name = series.get("series_name") or series.get("objective") or series.get("research_question")
        for data_point in series.get("data_points", []) or []:
            if data_point.get("sample_id") and series_name:
                series_name_by_sample[str(data_point["sample_id"])] = str(series_name)

    rows: list[dict[str, Any]] = []
    for data_point in data_points:
        sample_id = _string_or_none(data_point.get("sample_id"))
        if not sample_id:
            continue
        record = SampleRecord(
            sample_id=sample_id,
            sample_name=data_point.get("sample_label") or data_point.get("sample_name"),
            material_type=default_material_type,
            process_context=series_name_by_sample.get(sample_id),
            linked_parameters=parameter_ids_by_sample.get(sample_id, []),
            linked_evidence=linked_evidence_by_sample.get(sample_id, []),
            linked_spectra=linked_spectra_by_sample.get(sample_id, []),
        ).model_dump()
        rows.append(record)
    return rows


def _build_figure_rows(*, evidence: list[dict[str, Any]], spectra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in evidence:
        figure_id = row.get("figure_id")
        if not figure_id:
            continue
        rows.setdefault(
            figure_id,
            {
                "figure_id": figure_id,
                "figure_type": row.get("figure_type"),
                "caption": row.get("caption"),
                "evidence_ids": [],
                "linked_spectra": [],
            },
        )
        evidence_id = row.get("evidence_id")
        if evidence_id and evidence_id not in rows[figure_id]["evidence_ids"]:
            rows[figure_id]["evidence_ids"].append(evidence_id)
    for row in spectra:
        figure_id = row.get("figure_id")
        if not figure_id:
            continue
        rows.setdefault(
            figure_id,
            {
                "figure_id": figure_id,
                "figure_type": row.get("figure_type"),
                "caption": None,
                "evidence_ids": [],
                "linked_spectra": [],
            },
        )
        rows[figure_id]["linked_spectra"].append(
            {
                "schema_name": row.get("schema_name"),
                "figure_type": row.get("figure_type"),
                "assessment": row.get("quality_review_assessment"),
            }
        )
    return list(rows.values())


def _build_final_dataset_rows(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in parameters:
        rows.append(
            {
                "paper_id": item.get("paper_id"),
                "sample_id": item.get("sample_id"),
                "canonical_key": item.get("canonical_key"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "evidence_count": len(item.get("linked_evidence_ids", [])),
                "linked_figure_ids": item.get("linked_figure_ids", []),
                "linked_spectra_ids": item.get("linked_spectra_ids", []),
                "quality_flags": item.get("quality_flags", []),
                "parameter_id": item.get("parameter_id"),
                "source_scope": item.get("source_scope"),
            }
        )
    return rows


def _collect_fusion_warnings(
    parameters: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    weak_links: list[dict[str, Any]],
    inputs: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for section_name, file_presence in inputs["file_presence"].items():
        for file_key, is_present in file_presence.items():
            if not is_present and file_key not in {"stage4_quality_review_md"}:
                warnings.append(f"missing_{section_name}_{file_key}")
    warnings.extend(
        "parameter_without_evidence"
        for item in parameters
        if not item.get("linked_evidence_ids") and "weak_link_from_spectra" not in set(item.get("quality_flags") or [])
    )
    warnings.extend(
        "paper_level_parameter_without_direct_evidence"
        for item in parameters
        if not item.get("linked_evidence_ids") and not item.get("sample_id")
    )
    warnings.extend("spectra_with_warning" for item in spectra if item.get("warning_codes") or item.get("conflict_warnings"))
    warnings.extend("weak_link_from_spectra" for _ in weak_links)
    return warnings


def _find_weak_spectra_link(parameter: dict[str, Any], spectra: list[dict[str, Any]]) -> dict[str, Any] | None:
    canonical_key = parameter.get("canonical_key")
    if not canonical_key:
        return None
    for spectra_record in spectra:
        if _spectra_supports_parameter(canonical_key, spectra_record):
            return {"figure_id": spectra_record.get("figure_id")}
    return None


def _spectra_supports_parameter(canonical_key: str, spectra_record: dict[str, Any]) -> bool:
    figure_type = str(spectra_record.get("figure_type") or "")
    if canonical_key in (spectra_record.get("quantitative_values") or {}):
        return True
    species_quantification = spectra_record.get("species_quantification") or {}
    if canonical_key in species_quantification:
        return True
    scalar_matches = {
        "Al13_fraction_percent": spectra_record.get("Al13_fraction_percent"),
        "Ala_fraction_percent": spectra_record.get("Ala_fraction_percent"),
        "Alb_fraction_percent": spectra_record.get("Alb_fraction_percent"),
        "Alc_fraction_percent": spectra_record.get("Alc_fraction_percent"),
    }
    if canonical_key in scalar_matches and scalar_matches[canonical_key] is not None:
        return True
    peak_map = {
        "nmr_spectrum": {"nmr_27Al_peak_position_ppm"},
        "ftir_spectrum": {"ftir_peak_position_cm_1"},
        "ir_spectrum": {"ftir_peak_position_cm_1"},
        "raman_spectrum": {"raman_peak_position_cm_1"},
        "xrd_pattern": {"xrd_peak_position_2theta_deg"},
    }
    return canonical_key in peak_map.get(figure_type, set()) and bool(spectra_record.get("peaks"))


def _extract_reference_tokens(refs: list[Any]) -> list[str]:
    tokens: list[str] = []
    for ref in refs:
        if isinstance(ref, dict):
            for key in ("source_id", "evidence_id", "figure_id", "table_id"):
                value = ref.get(key)
                if value:
                    text = str(value)
                    if text not in tokens:
                        tokens.append(text)
            continue
        if ref is None:
            continue
        text = str(ref)
        if text and text not in tokens:
            tokens.append(text)
    return tokens


def _ensure_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _append_note(existing: str | None, extra: str) -> str:
    if existing:
        return f"{existing}; {extra}"
    return extra


def _pick_parameter_name(path: list[str], fallback: str) -> str:
    if not path:
        return fallback
    for segment in reversed(path):
        text = str(segment).strip()
        if text and not text.isdigit():
            return text
    return fallback


def _coerce_canonical_key(raw_canonical: Any, raw_name: str | None) -> str | None:
    candidates = [raw_canonical, raw_name]
    known_keys = set(get_canonical_keys(PROJECT_ROOT))
    for candidate in candidates:
        text = _string_or_none(candidate)
        if not text:
            continue
        normalized = normalize_key(text, PROJECT_ROOT)
        if normalized:
            return normalized
        if text in known_keys:
            return text
    return _string_or_none(raw_canonical) or _string_or_none(raw_name)


def _is_invalid_canonical_key(value: Any) -> bool:
    text = _string_or_none(value)
    return text is None or text.isdigit()


def _apply_paper_fallbacks(
    *,
    material_system: str | None,
    process_route: str | None,
    title: str | None,
    abstract: str | None,
    keywords: list[Any] | None,
    source_file: str | None,
) -> tuple[str | None, str | None]:
    keyword_text = " ".join(str(item) for item in (keywords or []) if item not in (None, ""))
    combined = " ".join(item for item in [title, abstract, keyword_text, material_system, process_route, source_file] if item)
    combined_casefold = combined.casefold()
    looks_like_alumina_sol = any(
        marker in combined_casefold
        for marker in ("alumina sol", "fiber precursor", "high al13", "27al nmr", "al-ferron")
    ) or any(marker in combined for marker in ("铝溶胶", "前驱体", "高 Al13"))
    updated_material_system = material_system
    updated_process_route = process_route
    if looks_like_alumina_sol:
        if not updated_material_system or updated_material_system == "alumina-based ceramic fiber":
            updated_material_system = "alumina_fiber_precursor"
        if not updated_process_route or updated_process_route == "sol-gel dry spinning":
            updated_process_route = "alumina sol synthesis and characterization"
    return updated_material_system, updated_process_route
