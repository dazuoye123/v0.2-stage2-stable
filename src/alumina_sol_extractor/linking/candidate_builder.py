"""Build constrained linking candidates from Stage 5 final_dataset outputs."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.loaders import read_json, read_jsonl

from .models import LinkCandidate, LinkRecord

DEFAULT_LINK_FAMILIES = {
    "process_step_to_parameter",
    "spectra_peak_to_parameter",
    "spectra_record_to_parameter",
    "visual_extraction_to_parameter",
    "evidence_to_parameter",
    "spectra_to_evidence",
    "parameter_to_sample",
}

PEAK_MATCH_RULES: dict[str, dict[str, Any]] = {
    "nmr_spectrum": {"canonical_keys": {"nmr_27Al_peak_position_ppm"}, "tolerance": 0.5},
    "ftir_spectrum": {"canonical_keys": {"ftir_peak_position_cm_1"}, "tolerance": 10.0},
    "ir_spectrum": {"canonical_keys": {"ftir_peak_position_cm_1"}, "tolerance": 10.0},
    "raman_spectrum": {"canonical_keys": {"raman_peak_position_cm_1"}, "tolerance": 10.0},
    "xrd_pattern": {"canonical_keys": {"xrd_peak_position_2theta_deg"}, "tolerance": 0.5},
}

CONFIDENCE_SCORE = {"high": 0.95, "medium": 0.7, "low": 0.4}

SPECTRA_RECORD_MATCH_RULES: dict[str, dict[str, Any]] = {
    "tg_curve": {
        "temperature_keys": {"calcination_temperature_C", "target_temperature_C"},
        "mass_loss_keys": {"mass_loss_wt_percent"},
    },
    "dsc_curve": {
        "temperature_keys": {"calcination_temperature_C", "target_temperature_C"},
    },
    "tg_dsc_curve": {
        "temperature_keys": {"calcination_temperature_C", "target_temperature_C"},
        "mass_loss_keys": {"mass_loss_wt_percent"},
    },
}

VISUAL_EXTRACTION_MATCH_RULES: dict[str, dict[str, Any]] = {
    "sem_image": {
        "size_keys": {"particle_size_nm", "average_fiber_diameter_um", "fiber_diameter_um"},
    },
    "tem_image": {
        "size_keys": {"particle_size_nm", "average_fiber_diameter_um", "fiber_diameter_um"},
    },
    "microscopy": {
        "size_keys": {"particle_size_nm", "average_fiber_diameter_um", "fiber_diameter_um"},
    },
}

SEMANTIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "particle_size_nm": ("particle size", "粒径", "胶粒"),
    "mass_loss_wt_percent": ("mass loss", "总失重", "质量损失", "失重"),
    "pvp_content_wt_percent": ("pvp", "质量分数", "wt_percent"),
    "aluminum_source": ("铝粉", "异丙醇铝", "aluminum powder", "aluminum source"),
    "nitrate_source": ("硝酸铝", "九水合硝酸铝", "nitrate", "aluminum nitrate"),
    "solvent_type": ("去离子水", "deionized water", "deionised water", "water"),
    "water_source": ("去离子水", "deionized water", "deionised water", "water"),
    "feeding_method": ("分批加入", "一次性加入", "滴加", "加入方式", "feeding method"),
    "start_temperature_c": ("加热至", "起始温度", "start temperature", "70"),
    "reaction_temperature_c": ("反应温度", "加热至", "升温至", "90"),
    "reaction_time_h": ("反应时间", "保温", "持续", "继续反应"),
    "hydrolysis_temperature_c": ("水解温度", "hydrolysis temperature"),
    "hydrolysis_time_h": ("水解时间", "hydrolysis time"),
    "stirring_speed_rpm": ("搅拌速度", "转速", "rpm"),
    "al_to_nitrate_molar_ratio": ("铝硝比", "al/no3", "摩尔比"),
    "ambient_temperature_c": ("ambient temperature", "operation box", "spinning chamber", "恒温", "环境温度", "操作箱"),
    "ph": ("ph", "酸度"),
    "applied_voltage_kv": ("voltage", "电场", "电压"),
    "collector_distance_cm": ("distance", "接收板", "喷丝头", "距离"),
    "feed_rate_ml_h": ("feed rate", "进料速率", "送料速率"),
    "calcination_temperature_c": ("calcination", "煅烧", "热处理", "升温至", "temperature"),
    "target_temperature_c": ("temperature", "升温至", "热处理"),
    "holding_time_h": ("holding", "hold", "保持", "保温"),
    "heating_rate_c_min": ("heating rate", "升温速率", "速率"),
}


def load_final_dataset_inputs(final_dataset_dir: Path | str) -> dict[str, Any]:
    final_dataset_dir = Path(final_dataset_dir)
    return {
        "paper": read_json(final_dataset_dir / "paper.json", default={}) or {},
        "samples": read_jsonl(final_dataset_dir / "samples.jsonl"),
        "parameters": read_jsonl(final_dataset_dir / "parameters.jsonl"),
        "process_steps": read_jsonl(final_dataset_dir / "process_steps.jsonl"),
        "evidence": read_jsonl(final_dataset_dir / "evidence.jsonl"),
        "spectra": read_jsonl(final_dataset_dir / "spectra.jsonl"),
        "quality_summary": read_json(final_dataset_dir / "quality_summary.json", default={}) or {},
        "fusion_report": (final_dataset_dir / "fusion_report.md").read_text(encoding="utf-8")
        if (final_dataset_dir / "fusion_report.md").exists()
        else "",
        "figures": read_jsonl(final_dataset_dir / "figures.jsonl"),
    }


def build_link_candidates(
    paper: dict[str, Any],
    parameters: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    spectra: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    *,
    process_steps: list[dict[str, Any]] | None = None,
    link_types: set[str] | None = None,
    max_candidates_per_type: int = 50,
) -> list[dict[str, Any]]:
    families = link_types or DEFAULT_LINK_FAMILIES
    process_steps = process_steps or []
    candidates: list[LinkCandidate] = []
    counters: dict[str, int] = defaultdict(int)
    paper_id = paper.get("paper_id")

    evidence_by_figure = _group_by(evidence, "figure_id")
    evidence_by_id = {item.get("evidence_id"): item for item in evidence if item.get("evidence_id")}
    spectra_by_figure = {item.get("figure_id"): item for item in spectra if item.get("figure_id")}
    samples_by_id = {item.get("sample_id"): item for item in samples if item.get("sample_id")}
    parameters_by_key = _group_by(parameters, "canonical_key")

    if "process_step_to_parameter" in families:
        for index, process_step in enumerate(process_steps, start=1):
            source_id = str(process_step.get("step_id") or f"process-step-{index:03d}")
            candidate_specs = _match_process_step_to_parameters(process_step, parameters, parameters_by_key)
            for candidate_spec in candidate_specs:
                if counters["process_step_to_parameter"] >= max_candidates_per_type:
                    break
                parameter = candidate_spec["parameter"]
                candidates.append(
                    _candidate(
                        family="process_step_to_parameter",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="process_step",
                        source_id=source_id,
                        source_text=_process_step_summary_text(process_step),
                        source_value=candidate_spec.get("matched_value"),
                        source_unit=candidate_spec.get("matched_unit"),
                        source_figure_id=None,
                        target_type="parameter",
                        target_id=parameter.get("parameter_id"),
                        target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        target_value=parameter.get("value"),
                        target_unit=parameter.get("unit"),
                        target_figure_id=next(iter(_coerce_str_list(parameter.get("linked_figure_ids"))), None),
                        candidate_reason=candidate_spec["reason"],
                        deterministic_score=float(candidate_spec["score"]),
                        needs_llm=bool(candidate_spec.get("needs_llm")),
                        candidate_status="deterministic" if not candidate_spec.get("needs_llm") else "needs_llm",
                    )
                )

    if "spectra_to_evidence" in families:
        for spectra_record in spectra:
            figure_id = spectra_record.get("figure_id")
            if not figure_id:
                continue
            for evidence_record in evidence_by_figure.get(figure_id, []):
                if counters["spectra_to_evidence"] >= max_candidates_per_type:
                    break
                candidates.append(
                    _candidate(
                        family="spectra_to_evidence",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="spectra_record",
                        source_id=f"spectra-{figure_id}",
                        source_text=_spectra_summary_text(spectra_record),
                        source_value=None,
                        source_unit=None,
                        source_figure_id=figure_id,
                        target_type="evidence_object",
                        target_id=evidence_record.get("evidence_id"),
                        target_text=evidence_record.get("caption") or _join_text(evidence_record.get("fact_summary")),
                        target_value=None,
                        target_unit=None,
                        target_figure_id=figure_id,
                        candidate_reason="same_figure_id",
                        deterministic_score=1.0,
                        needs_llm=False,
                        candidate_status="deterministic",
                    )
                )

    if "evidence_to_parameter" in families:
        for parameter in parameters:
            evidence_refs = _extract_reference_ids(parameter.get("evidence_refs"))
            linked_figures = set(_coerce_str_list(parameter.get("linked_figure_ids")))
            linked_spectra = set(_coerce_str_list(parameter.get("linked_spectra_ids")))
            for evidence_id in evidence_refs:
                evidence_record = evidence_by_id.get(evidence_id)
                if not evidence_record:
                    continue
                if counters["evidence_to_parameter"] >= max_candidates_per_type:
                    break
                candidates.append(
                    _candidate(
                        family="evidence_to_parameter",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="evidence_object",
                        source_id=evidence_id,
                        source_text=evidence_record.get("caption") or _join_text(evidence_record.get("fact_summary")),
                        source_value=None,
                        source_unit=None,
                        source_figure_id=evidence_record.get("figure_id"),
                        target_type="parameter",
                        target_id=parameter.get("parameter_id"),
                        target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        target_value=parameter.get("value"),
                        target_unit=parameter.get("unit"),
                        target_figure_id=None,
                        candidate_reason="parameter_evidence_refs_contains_evidence_id",
                        deterministic_score=1.0,
                        needs_llm=False,
                        candidate_status="deterministic",
                    )
                )

            if counters["evidence_to_parameter"] >= max_candidates_per_type:
                continue

            if not evidence_refs and (linked_figures or linked_spectra):
                figure_candidates = linked_figures | linked_spectra
                for figure_id in figure_candidates:
                    for evidence_record in evidence_by_figure.get(figure_id, []):
                        if counters["evidence_to_parameter"] >= max_candidates_per_type:
                            break
                        candidates.append(
                            _candidate(
                                family="evidence_to_parameter",
                                counters=counters,
                                paper_id=paper_id,
                                source_type="evidence_object",
                                source_id=evidence_record.get("evidence_id"),
                                source_text=evidence_record.get("caption") or _join_text(evidence_record.get("fact_summary")),
                                source_value=None,
                                source_unit=None,
                                source_figure_id=evidence_record.get("figure_id"),
                                target_type="parameter",
                                target_id=parameter.get("parameter_id"),
                                target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                                target_value=parameter.get("value"),
                                target_unit=parameter.get("unit"),
                                target_figure_id=None,
                                candidate_reason="linked_figure_or_spectra_overlap",
                                deterministic_score=0.55,
                                needs_llm=True,
                                candidate_status="needs_llm",
                            )
                        )

        for evidence_record in evidence:
            if counters["evidence_to_parameter"] >= max_candidates_per_type:
                break
            candidate_specs = _match_evidence_to_parameters(evidence_record, parameters)
            for candidate_spec in candidate_specs:
                if counters["evidence_to_parameter"] >= max_candidates_per_type:
                    break
                parameter = candidate_spec["parameter"]
                candidates.append(
                    _candidate(
                        family="evidence_to_parameter",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="evidence_object",
                        source_id=evidence_record.get("evidence_id"),
                        source_text=_evidence_summary_text(evidence_record),
                        source_value=candidate_spec.get("matched_value"),
                        source_unit=candidate_spec.get("matched_unit"),
                        source_figure_id=evidence_record.get("figure_id"),
                        target_type="parameter",
                        target_id=parameter.get("parameter_id"),
                        target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        target_value=parameter.get("value"),
                        target_unit=parameter.get("unit"),
                        target_figure_id=next(iter(_coerce_str_list(parameter.get("linked_figure_ids"))), None),
                        candidate_reason=candidate_spec["reason"],
                        deterministic_score=float(candidate_spec["score"]),
                        needs_llm=bool(candidate_spec.get("needs_llm")),
                        candidate_status="deterministic" if not candidate_spec.get("needs_llm") else "needs_llm",
                    )
                )

    if "parameter_to_sample" in families:
        for parameter in parameters:
            sample_id = parameter.get("sample_id")
            if sample_id and sample_id in samples_by_id:
                sample = samples_by_id[sample_id]
                if counters["parameter_to_sample"] >= max_candidates_per_type:
                    break
                candidates.append(
                    _candidate(
                        family="parameter_to_sample",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="parameter",
                        source_id=parameter.get("parameter_id"),
                        source_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        source_value=parameter.get("value"),
                        source_unit=parameter.get("unit"),
                        source_figure_id=None,
                        target_type="sample",
                        target_id=sample_id,
                        target_text=sample.get("sample_name") or sample_id,
                        target_value=None,
                        target_unit=None,
                        target_figure_id=None,
                        candidate_reason="sample_id_match",
                        deterministic_score=1.0,
                        needs_llm=False,
                        candidate_status="deterministic",
                    )
                )
                continue
            for sample in samples:
                linked_parameters = set(_coerce_str_list(sample.get("linked_parameters")))
                if parameter.get("parameter_id") in linked_parameters:
                    if counters["parameter_to_sample"] >= max_candidates_per_type:
                        break
                    candidates.append(
                        _candidate(
                            family="parameter_to_sample",
                            counters=counters,
                            paper_id=paper_id,
                            source_type="parameter",
                            source_id=parameter.get("parameter_id"),
                            source_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                            source_value=parameter.get("value"),
                            source_unit=parameter.get("unit"),
                            source_figure_id=None,
                            target_type="sample",
                            target_id=sample.get("sample_id"),
                            target_text=sample.get("sample_name") or sample.get("sample_id"),
                            target_value=None,
                            target_unit=None,
                            target_figure_id=None,
                            candidate_reason="sample_linked_parameters_contains_parameter_id",
                            deterministic_score=1.0,
                            needs_llm=False,
                            candidate_status="deterministic",
                        )
                    )

    if "spectra_peak_to_parameter" in families:
        for spectra_record in spectra:
            figure_id = spectra_record.get("figure_id")
            rule = PEAK_MATCH_RULES.get(spectra_record.get("figure_type"))
            if not figure_id or not rule:
                continue
            linked_evidence_ids = {item.get("evidence_id") for item in evidence_by_figure.get(figure_id, []) if item.get("evidence_id")}
            for index, peak in enumerate(spectra_record.get("peaks", []), start=1):
                position = _to_float(peak.get("position"))
                if position is None:
                    continue
                for parameter in parameters:
                    if parameter.get("canonical_key") not in rule["canonical_keys"]:
                        continue
                    target_value = _to_float(parameter.get("value"))
                    if target_value is None or abs(target_value - position) > float(rule["tolerance"]):
                        continue
                    delta = abs(target_value - position)
                    linked_figures = set(_coerce_str_list(parameter.get("linked_figure_ids")))
                    linked_spectra = set(_coerce_str_list(parameter.get("linked_spectra_ids")))
                    evidence_refs = _extract_reference_ids(parameter.get("evidence_refs"))
                    peak_source_id = f"spectra-{figure_id}-peak-{index:02d}"
                    same_figure = (
                        figure_id in linked_figures
                        or figure_id in linked_spectra
                        or figure_id in evidence_refs
                        or peak_source_id in evidence_refs
                        or bool(linked_evidence_ids & evidence_refs)
                    )
                    score = 0.55 if delta > 0 else 0.6
                    if same_figure:
                        score += 0.2 if delta > 0 else 0.3
                    if peak.get("assignment") and parameter.get("raw_name") and str(peak.get("assignment")).lower() in str(parameter.get("raw_name")).lower():
                        score += 0.05
                    if counters["spectra_peak_to_parameter"] >= max_candidates_per_type:
                        break
                    candidates.append(
                        _candidate(
                            family="spectra_peak_to_parameter",
                            counters=counters,
                            paper_id=paper_id,
                            source_type="spectra_peak",
                            source_id=f"spectra-{figure_id}-peak-{index:02d}",
                            source_text=peak.get("assignment") or peak.get("source_text") or _spectra_summary_text(spectra_record),
                            source_value=position,
                            source_unit=peak.get("unit"),
                            source_figure_id=figure_id,
                            target_type="parameter",
                            target_id=parameter.get("parameter_id"),
                            target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                            target_value=parameter.get("value"),
                            target_unit=parameter.get("unit"),
                            target_figure_id=next(iter(linked_figures), None),
                            candidate_reason="technique_and_approximate_numeric_match" if delta > 0 else "technique_and_numeric_tolerance_match",
                            deterministic_score=min(score, 1.0),
                            needs_llm=not same_figure,
                            candidate_status="deterministic" if same_figure and score >= 0.7 else "needs_llm",
                        )
                    )

    if "spectra_record_to_parameter" in families:
        for spectra_record in spectra:
            figure_id = spectra_record.get("figure_id")
            if not figure_id:
                continue
            candidate_specs = _match_spectra_record_to_parameters(spectra_record, parameters)
            for candidate_spec in candidate_specs:
                if counters["spectra_record_to_parameter"] >= max_candidates_per_type:
                    break
                parameter = candidate_spec["parameter"]
                candidates.append(
                    _candidate(
                        family="spectra_record_to_parameter",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="spectra_record",
                        source_id=_spectra_record_id(figure_id),
                        source_text=candidate_spec.get("source_text") or _spectra_summary_text(spectra_record),
                        source_value=candidate_spec.get("matched_value"),
                        source_unit=candidate_spec.get("matched_unit"),
                        source_figure_id=figure_id,
                        target_type="parameter",
                        target_id=parameter.get("parameter_id"),
                        target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        target_value=parameter.get("value"),
                        target_unit=parameter.get("unit"),
                        target_figure_id=figure_id,
                        candidate_reason=candidate_spec["reason"],
                        deterministic_score=float(candidate_spec["score"]),
                        needs_llm=bool(candidate_spec.get("needs_llm", False)),
                        candidate_status="deterministic" if not candidate_spec.get("needs_llm") else "needs_llm",
                    )
                )

    if "visual_extraction_to_parameter" in families:
        for spectra_record in spectra:
            figure_id = spectra_record.get("figure_id")
            if not figure_id:
                continue
            candidate_specs = _match_visual_extraction_to_parameters(spectra_record, parameters)
            for candidate_spec in candidate_specs:
                if counters["visual_extraction_to_parameter"] >= max_candidates_per_type:
                    break
                parameter = candidate_spec["parameter"]
                candidates.append(
                    _candidate(
                        family="visual_extraction_to_parameter",
                        counters=counters,
                        paper_id=paper_id,
                        source_type="visual_extraction",
                        source_id=f"visual-{figure_id}-{candidate_spec['source_key']}",
                        source_text=candidate_spec.get("source_text") or _spectra_summary_text(spectra_record),
                        source_value=candidate_spec.get("matched_value"),
                        source_unit=candidate_spec.get("matched_unit"),
                        source_figure_id=figure_id,
                        target_type="parameter",
                        target_id=parameter.get("parameter_id"),
                        target_text=parameter.get("raw_name") or parameter.get("canonical_key"),
                        target_value=parameter.get("value"),
                        target_unit=parameter.get("unit"),
                        target_figure_id=figure_id,
                        candidate_reason=candidate_spec["reason"],
                        deterministic_score=float(candidate_spec["score"]),
                        needs_llm=bool(candidate_spec.get("needs_llm", False)),
                        candidate_status="deterministic" if not candidate_spec.get("needs_llm") else "needs_llm",
                    )
                )

    return [item.model_dump() for item in candidates]


def build_deterministic_links(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    links: list[LinkRecord] = []
    unresolved: list[dict[str, Any]] = []
    counter = 1
    for candidate_dict in candidates:
        candidate = LinkCandidate.model_validate(candidate_dict)
        if candidate.candidate_status != "deterministic":
            unresolved.append({**candidate.model_dump(), "unmatched_reason": "needs_llm_review"})
            continue
        if candidate.source_type == "spectra_record" and candidate.target_type == "evidence_object":
            link_type = "same_figure"
            confidence = "high"
        elif candidate.source_type == "evidence_object" and candidate.target_type == "parameter":
            link_type = "supports"
            confidence = "high" if candidate.deterministic_score >= 0.9 else "medium"
        elif candidate.source_type == "parameter" and candidate.target_type == "sample":
            link_type = "describes"
            confidence = "high"
        elif candidate.source_type == "spectra_peak" and candidate.target_type == "parameter":
            link_type = "supports"
            confidence = "high" if candidate.deterministic_score >= 0.9 else "medium"
        elif candidate.source_type == "process_step" and candidate.target_type == "parameter":
            link_type = "supports"
            confidence = "high" if candidate.deterministic_score >= 0.9 else "medium"
        elif candidate.source_type == "spectra_record" and candidate.target_type == "parameter":
            link_type = "supports"
            confidence = "high" if candidate.deterministic_score >= 0.9 else "medium"
        elif candidate.source_type == "visual_extraction" and candidate.target_type == "parameter":
            link_type = "supports"
            confidence = "high" if candidate.deterministic_score >= 0.9 else "medium"
        else:
            unresolved.append({**candidate.model_dump(), "unmatched_reason": "unsupported_deterministic_pair"})
            continue
        links.append(
            LinkRecord(
                link_id=f"link-{counter:05d}",
                paper_id=candidate.paper_id,
                source_type=candidate.source_type,
                source_id=candidate.source_id,
                target_type=candidate.target_type,
                target_id=candidate.target_id,
                link_type=link_type,
                confidence=confidence,
                confidence_score=CONFIDENCE_SCORE.get(confidence),
                reasoning=candidate.candidate_reason,
                evidence_text=candidate.source_text,
                validation_status="accepted",
                validation_warnings=[],
                created_by=_deterministic_created_by(candidate),
            ).model_dump()
        )
        counter += 1
    return links, unresolved


def _deterministic_created_by(candidate: LinkCandidate) -> str:
    if candidate.source_type == "process_step" and candidate.target_type == "parameter":
        return "deterministic_process_step_value_match"
    if candidate.source_type == "evidence_object" and candidate.target_type == "parameter":
        if "evidence_refs" in str(candidate.candidate_reason or ""):
            return "direct_evidence_refs"
        return "deterministic_evidence_value_match"
    if candidate.source_type == "spectra_peak" and candidate.target_type == "parameter":
        return "deterministic_spectra_peak_value_match"
    if candidate.source_type == "spectra_record" and candidate.target_type == "parameter":
        return "deterministic_spectra_record_value_match"
    if candidate.source_type == "visual_extraction" and candidate.target_type == "parameter":
        return "deterministic_visual_value_match"
    if candidate.source_type == "parameter" and candidate.target_type == "sample":
        return "deterministic_parameter_sample_match"
    if candidate.source_type == "spectra_record" and candidate.target_type == "evidence_object":
        return "deterministic_same_figure_match"
    return "deterministic"


def _candidate(
    *,
    family: str,
    counters: dict[str, int],
    paper_id: str | None,
    source_type: str,
    source_id: str | None,
    source_text: str | None,
    source_value: float | int | str | None,
    source_unit: str | None,
    source_figure_id: str | None,
    target_type: str,
    target_id: str | None,
    target_text: str | None,
    target_value: float | int | str | None,
    target_unit: str | None,
    target_figure_id: str | None,
    candidate_reason: str,
    deterministic_score: float,
    needs_llm: bool,
    candidate_status: str,
) -> LinkCandidate:
    counters[family] += 1
    return LinkCandidate(
        candidate_id=f"{family}-{counters[family]:05d}",
        paper_id=paper_id,
        source_type=source_type,
        source_id=str(source_id),
        source_text=source_text,
        source_value=source_value,
        source_unit=source_unit,
        source_figure_id=source_figure_id,
        target_type=target_type,
        target_id=str(target_id),
        target_text=target_text,
        target_value=target_value,
        target_unit=target_unit,
        target_figure_id=target_figure_id,
        candidate_reason=candidate_reason,
        deterministic_score=deterministic_score,
        needs_llm=needs_llm,
        candidate_status=candidate_status,
    )


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value:
            grouped[str(value)].append(row)
    return grouped


def _join_text(value: Any) -> str | None:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _spectra_summary_text(record: dict[str, Any]) -> str | None:
    parts = [
        record.get("technique"),
        record.get("schema_name"),
        record.get("figure_type"),
    ]
    text = " | ".join(str(part) for part in parts if part)
    return text or None


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _normalize_unit_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = _normalize_match_text(text)
    normalized = normalized.replace("ml h^-1", "ml_h").replace("ml h-1", "ml_h")
    normalized = normalized.replace("c min-1", "c_min").replace("c min^-1", "c_min")
    normalized = normalized.replace("per_min", "_min")
    normalized = normalized.replace("wt%", "wt_percent").replace("wt.%", "wt_percent")
    if normalized == "%":
        normalized = "wt_percent"
    if normalized == "dimensionless":
        return None
    return normalized

def _text_contains_value(text: str | None, value: Any, unit: Any = None, tolerance: float = 0.0) -> bool:
    if not text:
        return False
    haystack = _normalize_match_text(text)
    numeric = _to_float(value)
    if numeric is not None:
        value_tokens = {f"{numeric:g}", f"{numeric:.1f}", f"{numeric:.2f}"}
        unit_text = _normalize_unit_text(unit)
        for token in value_tokens:
            token_pattern = rf"(?<![\d.]){re.escape(token)}(?![\d.])"
            if unit_text:
                unit_pattern = rf"{token_pattern}\s*{re.escape(unit_text)}(?![a-z])"
                if re.search(unit_pattern, haystack):
                    return True
                continue
            if re.search(token_pattern, haystack):
                return True
        if tolerance > 0:
            for range_match in re.finditer(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)", haystack):
                low = float(range_match.group(1))
                high = float(range_match.group(2))
                if low - tolerance <= numeric <= high + tolerance:
                    return True
        return False
    value_text = _normalize_match_text(str(value))
    range_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*", value_text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        unit_text = _normalize_unit_text(unit)
        if unit_text and unit_text not in haystack:
            return False
        haystack_for_range = haystack.replace(unit_text, "") if unit_text else haystack
        for observed_range in re.finditer(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)", haystack_for_range):
            observed_low = float(observed_range.group(1))
            observed_high = float(observed_range.group(2))
            if abs(low - observed_low) <= max(tolerance, 0.05) and abs(high - observed_high) <= max(tolerance, 0.05):
                return True
    return bool(value_text) and value_text in haystack


def _normalize_match_text(text: str) -> str:
    normalized = str(text).lower()
    for token in ("\u2013", "\u2014", "\uff5e", "~"):
        normalized = normalized.replace(token, "-")
    replacements = {
        "pa*s": "pa_s",
        "pa.s": "pa_s",
        "pa\u00b7s": "pa_s",
        "ml/h": "ml_h",
        "ml h-1": "ml_h",
        "ml\u00b7h-1": "ml_h",
        "ml h^-1": "ml_h",
        "\u00b0c/min": "c_min",
        "\u2103/min": "c_min",
        "c/min": "c_min",
        "per min": "per_min",
        "2\u03b8": "2theta",
        "cm^-1": "cm-1",
        "wt%": "wt_percent",
        "wt.%": "wt_percent",
        "%": "wt_percent",
        "\u2103": "c",
        "\u00b0c": "c",
        "\u00b0": "",
        "ph \u503c": "ph",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    return normalized


def _normalized_parameter_unit(parameter: dict[str, Any]) -> str | None:
    unit = parameter.get("unit")
    return None if unit == "text" else _normalize_unit_text(unit)


def _process_step_summary_text(process_step: dict[str, Any]) -> str | None:
    parts = [
        process_step.get("evidence_text"),
        process_step.get("product_or_outcome"),
        process_step.get("reagent_name"),
        process_step.get("equipment"),
    ]
    joined = " | ".join(str(item) for item in parts if item)
    return joined or None


def _evidence_summary_text(evidence_record: dict[str, Any]) -> str | None:
    parts = [
        evidence_record.get("caption"),
        _join_text(evidence_record.get("fact_summary")),
        evidence_record.get("detailed_observation"),
    ]
    joined = " | ".join(str(item) for item in parts if item)
    return joined or None


def _linked_key_match(process_step: dict[str, Any], parameter: dict[str, Any]) -> bool:
    linked_keys = set(_coerce_str_list(process_step.get("linked_parameter_keys")))
    canonical_key = str(parameter.get("canonical_key") or "")
    return bool(canonical_key and canonical_key in linked_keys)


def _match_process_step_to_parameters(
    process_step: dict[str, Any],
    parameters: list[dict[str, Any]],
    parameters_by_key: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    text = _process_step_summary_text(process_step) or ""
    action = str(process_step.get("action") or "").lower()
    action_zh = str(process_step.get("action_zh") or "")
    condition_key = str(process_step.get("condition_key") or "").lower()
    normalized_text = _normalize_match_text(text)
    normalized_action = _normalize_match_text(action_zh)
    matches: list[dict[str, Any]] = []
    candidate_specs = [
        (
            process_step.get("condition_key"),
            process_step.get("condition_value"),
            process_step.get("condition_unit"),
            0.95,
        ),
        ("holding_time_h", process_step.get("duration_value"), process_step.get("duration_unit"), 0.92),
        ("heating_rate_C_min", process_step.get("heating_rate_value"), process_step.get("heating_rate_unit"), 0.92),
        (
            "calcination_temperature_C" if action in {"heat", "calcine"} else process_step.get("condition_key"),
            process_step.get("temperature_value"),
            process_step.get("temperature_unit"),
            0.9,
        ),
    ]
    for canonical_key, matched_value, matched_unit, base_score in candidate_specs:
        if not canonical_key or matched_value is None:
            continue
        for parameter in parameters_by_key.get(str(canonical_key), []):
            if _parameter_value_matches(parameter, matched_value, matched_unit):
                score = base_score
                if _linked_key_match(process_step, parameter):
                    score += 0.05
                matches.append(
                    {
                        "parameter": parameter,
                        "matched_value": matched_value,
                        "matched_unit": matched_unit,
                        "score": min(score, 1.0),
                        "reason": f"process_step_{canonical_key}_value_match",
                        "needs_llm": False,
                    }
                )
    for parameter in parameters:
        if parameter.get("canonical_key") not in {"applied_voltage_kV", "collector_distance_cm", "feed_rate_ml_h"}:
            continue
        if any(item["parameter"].get("parameter_id") == parameter.get("parameter_id") for item in matches):
            continue
        if not _process_step_text_value_context_allowed(
            str(parameter.get("canonical_key") or ""),
            normalized_text,
            normalized_action,
            condition_key,
        ):
            continue
        if _parameter_value_matches(parameter, parameter.get("value"), parameter.get("unit")) and _text_contains_value(text, parameter.get("value"), parameter.get("unit")):
            matches.append(
                {
                    "parameter": parameter,
                    "matched_value": parameter.get("value"),
                    "matched_unit": parameter.get("unit"),
                    "score": 0.9,
                    "reason": "process_step_text_value_match",
                    "needs_llm": False,
                }
            )
    for parameter in parameters:
        if any(item["parameter"].get("parameter_id") == parameter.get("parameter_id") for item in matches):
            continue
        semantic_match = _match_process_step_semantics(process_step, parameter)
        if semantic_match is None:
            continue
        matches.append(semantic_match)
    return _dedupe_match_specs(matches)


def _match_process_step_semantics(
    process_step: dict[str, Any],
    parameter: dict[str, Any],
) -> dict[str, Any] | None:
    canonical_key = str(parameter.get("canonical_key") or "")
    if not canonical_key:
        return None
    summary_text = _process_step_summary_text(process_step) or ""
    normalized_text = _normalize_match_text(summary_text)
    if not normalized_text:
        return None
    value = parameter.get("value")
    unit = None if parameter.get("unit") == "text" else parameter.get("unit")

    reagent_name = str(process_step.get("reagent_name") or "").strip()
    formula = str(process_step.get("reagent_formula") or "").strip()
    action_zh = str(process_step.get("action_zh") or "")
    action = str(process_step.get("action") or "").lower()
    condition_key = str(process_step.get("condition_key") or "").lower()
    normalized_action = _normalize_match_text(action_zh)
    normalized_reagent_blob = _normalize_match_text(" ".join(part for part in [reagent_name, formula, summary_text] if part))

    def _contains_any(text: str, tokens: tuple[str, ...] | list[str]) -> bool:
        return any(_normalize_match_text(token) in text for token in tokens if token)

    drying_context = _contains_any(normalized_text, ["干燥", "drying", "dry"]) or _contains_any(normalized_action, ["干燥", "dry"])
    concentration_context = (
        _contains_any(normalized_text, ["减压浓缩", "浓缩", "真空浓缩", "vacuum concentration", "concentrat", "water bath", "水浴"])
        or "concentration" in condition_key
    )
    peptization_context = (
        _contains_any(normalized_text, ["胶溶", "peptization", "硝酸", "nitric acid", "调节ph", "ph", "继续搅拌"])
        and _contains_any(normalized_text, ["胶溶", "peptization", "硝酸", "nitric acid", "调节ph", "ph"])
    )
    take_up_context = _contains_any(
        normalized_text,
        ["收丝", "牵引", "take-up", "take up", "winding", "wind-up", "line speed", "线速度", "draw"],
    )
    heat_treatment_context = (
        action in {"heat", "calcine", "sinter"}
        or _contains_any(normalized_action, ["升温", "烧结", "煅烧", "热处理"])
        or _contains_any(normalized_text, ["升温", "烧结", "煅烧", "热处理", "sinter", "calcination", "calcine"])
    )
    hydrolysis_context = _contains_any(normalized_text, ["水解", "hydrolysis"])
    reaction_context = _contains_any(normalized_text, ["反应", "reaction"])

    if canonical_key in {"aluminum_source", "nitrate_source", "solvent_type", "water_source"}:
        if canonical_key == "aluminum_source" and _contains_any(
            normalized_reagent_blob,
            ["铝粉", "aluminum powder", "aluminium powder", "异丙醇铝", "aluminum isopropanol", "aluminium isopropanol"],
        ):
            return _build_process_step_match(parameter, value, unit, 0.82, "process_step_reagent_semantic_match")
        if canonical_key == "nitrate_source" and _contains_any(
            normalized_reagent_blob,
            ["硝酸铝", "九水合硝酸铝", "硝酸铝溶液", "aluminum nitrate", "aluminium nitrate", "nitrate"],
        ):
            return _build_process_step_match(parameter, value, unit, 0.82, "process_step_reagent_semantic_match")
        if canonical_key in {"solvent_type", "water_source"} and _contains_any(
            normalized_reagent_blob,
            ["去离子水", "deionized water", "deionised water", "water"],
        ):
            return _build_process_step_match(parameter, value, unit, 0.72, "process_step_solvent_semantic_match")

    if canonical_key == "drying_temperature_C":
        temperature_value = process_step.get("temperature_value")
        if temperature_value is not None and drying_context:
            if _parameter_value_matches(parameter, temperature_value, process_step.get("temperature_unit")):
                return _build_process_step_match(
                    parameter,
                    temperature_value,
                    process_step.get("temperature_unit"),
                    0.9,
                    "process_step_drying_temperature_semantic_match",
                )
            if value is None:
                return _build_process_step_match(
                    parameter,
                    temperature_value,
                    process_step.get("temperature_unit"),
                    0.76,
                    "process_step_drying_temperature_observed_value_semantic_match",
                )

    if canonical_key == "concentration_temperature_C":
        temperature_value = process_step.get("temperature_value")
        if temperature_value is not None and concentration_context:
            if _parameter_value_matches(parameter, temperature_value, process_step.get("temperature_unit")):
                return _build_process_step_match(
                    parameter,
                    temperature_value,
                    process_step.get("temperature_unit"),
                    0.9,
                    "process_step_concentration_temperature_semantic_match",
                )
            if value is None:
                return _build_process_step_match(
                    parameter,
                    temperature_value,
                    process_step.get("temperature_unit"),
                    0.76,
                    "process_step_concentration_temperature_observed_value_semantic_match",
                )

    if canonical_key == "concentration_time_h":
        duration_value = process_step.get("duration_value")
        if duration_value is not None and concentration_context:
            if _parameter_value_matches(parameter, duration_value, process_step.get("duration_unit")):
                return _build_process_step_match(
                    parameter,
                    duration_value,
                    process_step.get("duration_unit"),
                    0.88,
                    "process_step_concentration_duration_semantic_match",
                )
            if value is None:
                return _build_process_step_match(
                    parameter,
                    duration_value,
                    process_step.get("duration_unit"),
                    0.74,
                    "process_step_concentration_duration_observed_value_semantic_match",
                )

    if canonical_key == "peptization_time_h":
        duration_value = process_step.get("duration_value")
        if duration_value is not None and peptization_context:
            if _parameter_value_matches(parameter, duration_value, process_step.get("duration_unit")):
                return _build_process_step_match(
                    parameter,
                    duration_value,
                    process_step.get("duration_unit"),
                    0.88,
                    "process_step_peptization_duration_semantic_match",
                )
            if value is None:
                return _build_process_step_match(
                    parameter,
                    duration_value,
                    process_step.get("duration_unit"),
                    0.74,
                    "process_step_peptization_duration_observed_value_semantic_match",
                )

    if canonical_key == "take_up_speed_m_min" and take_up_context:
        if value is not None and _text_contains_value(normalized_text, value, unit, tolerance=0.05):
            return _build_process_step_match(parameter, value, unit, 0.84, "process_step_take_up_speed_text_match")

    if canonical_key == "heating_rate_C_min" and heat_treatment_context:
        heating_rate_value = process_step.get("heating_rate_value")
        heating_rate_unit = process_step.get("heating_rate_unit")
        if heating_rate_value is not None:
            if _parameter_value_matches(parameter, heating_rate_value, heating_rate_unit):
                return _build_process_step_match(
                    parameter,
                    heating_rate_value,
                    heating_rate_unit,
                    0.88,
                    "process_step_heating_rate_semantic_match",
                )
            if value is None:
                return _build_process_step_match(
                    parameter,
                    heating_rate_value,
                    heating_rate_unit,
                    0.74,
                    "process_step_heating_rate_observed_value_semantic_match",
                )
        if value is not None and _text_contains_value(normalized_text, value, unit, tolerance=0.05):
            return _build_process_step_match(parameter, value, unit, 0.82, "process_step_heating_rate_text_match")

    if canonical_key in {"start_temperature_C", "reaction_temperature_C", "hydrolysis_temperature_C"}:
        temperature_value = process_step.get("temperature_value")
        if temperature_value is not None:
            blocked_hydrolysis_match = canonical_key == "hydrolysis_temperature_C" and (
                drying_context or concentration_context or peptization_context
            )
            blocked_reaction_match = canonical_key == "reaction_temperature_C" and (drying_context or concentration_context)
            if blocked_hydrolysis_match or blocked_reaction_match:
                return None
            if _parameter_value_matches(parameter, temperature_value, process_step.get("temperature_unit")):
                return _build_process_step_match(parameter, temperature_value, process_step.get("temperature_unit"), 0.86, "process_step_temperature_semantic_match")
            if value is None and (
                _process_step_semantic_keyword_match(canonical_key, normalized_text)
                or (
                    canonical_key == "hydrolysis_temperature_C"
                    and hydrolysis_context
                )
                or (
                    canonical_key == "reaction_temperature_C"
                    and reaction_context
                )
                or (
                    canonical_key == "start_temperature_C"
                    and _contains_any(normalized_text, ["起始温度", "初始温度", "start temperature"])
                )
            ):
                return _build_process_step_match(
                    parameter,
                    temperature_value,
                    process_step.get("temperature_unit"),
                    0.72,
                    "process_step_temperature_observed_value_semantic_match",
                )

    if canonical_key in {"reaction_time_h", "hydrolysis_time_h"}:
        duration_value = process_step.get("duration_value")
        if duration_value is not None:
            blocked_hydrolysis_match = canonical_key == "hydrolysis_time_h" and (
                drying_context or concentration_context or peptization_context
            )
            blocked_reaction_match = canonical_key == "reaction_time_h" and (drying_context or concentration_context)
            if blocked_hydrolysis_match or blocked_reaction_match:
                return None
            if _parameter_value_matches(parameter, duration_value, process_step.get("duration_unit")):
                return _build_process_step_match(parameter, duration_value, process_step.get("duration_unit"), 0.84, "process_step_duration_semantic_match")
            if value is None and (
                _process_step_semantic_keyword_match(canonical_key, normalized_text)
                or (
                    canonical_key == "hydrolysis_time_h"
                    and hydrolysis_context
                )
                or (
                    canonical_key == "reaction_time_h"
                    and reaction_context
                )
            ):
                return _build_process_step_match(
                    parameter,
                    duration_value,
                    process_step.get("duration_unit"),
                    0.74,
                    "process_step_duration_observed_value_semantic_match",
                )

    if canonical_key == "feeding_method":
        if _contains_any(normalized_text, ["分批加入", "一次性加入", "滴加"]):
            if value is None or _text_contains_value(normalized_text, value, unit):
                return _build_process_step_match(parameter, value, unit, 0.76, "process_step_feeding_method_match")
        normalized_value = _normalize_match_text(str(value or ""))
        if normalized_value and normalized_value in normalized_text and _contains_any(normalized_text, ["加入", "加料", "投料", "滴加"]):
            return _build_process_step_match(parameter, value, unit, 0.74, "process_step_feeding_method_text_match")

    if canonical_key in {"stirring_speed_rpm", "Al_to_nitrate_molar_ratio", "ph"}:
        if value is not None and _text_contains_value(normalized_text, value, unit, tolerance=0.05):
            return _build_process_step_match(parameter, value, unit, 0.8, "process_step_text_value_match")

    if canonical_key == "ph" and ("ph" in normalized_text or _contains_any(normalized_text, ["酸度"])):
        if value is not None and _text_contains_value(normalized_text, value, unit, tolerance=0.05):
            return _build_process_step_match(parameter, value, unit, 0.82, "process_step_ph_match")

    if canonical_key == "feeding_method" and (_contains_any(_normalize_match_text(action_zh), ["加入"]) or "add" in condition_key):
        if value and _normalize_match_text(str(value)) in normalized_text:
            return _build_process_step_match(parameter, value, unit, 0.74, "process_step_feeding_method_text_match")

    return None

def _process_step_semantic_keyword_match(canonical_key: str, text: str) -> bool:
    keyword_tokens = SEMANTIC_KEYWORDS.get(canonical_key.lower()) or ()
    normalized_tokens = [_normalize_match_text(token) for token in keyword_tokens if token]
    return any(token in text for token in normalized_tokens)


def _process_step_text_value_context_allowed(
    canonical_key: str,
    normalized_text: str,
    normalized_action: str,
    condition_key: str,
) -> bool:
    def _contains_any(text: str, tokens: tuple[str, ...] | list[str]) -> bool:
        return any(_normalize_match_text(token) in text for token in tokens if token)

    if canonical_key == "collector_distance_cm":
        return (
            _contains_any(
                normalized_text,
                ["distance", "collector distance", "距离", "间距", "接收板", "喷丝头", "collector", "needle"],
            )
            or _contains_any(normalized_action, ["electrospin", "静电纺丝"])
            or "collector_distance" in condition_key
        )
    if canonical_key == "applied_voltage_kV":
        return (
            _contains_any(normalized_text, ["voltage", "electric field", "电压", "电场", "kv"])
            or _contains_any(normalized_action, ["electrospin", "静电纺丝"])
            or "voltage" in condition_key
        )
    if canonical_key == "feed_rate_ml_h":
        return (
            _contains_any(normalized_text, ["feed rate", "进料", "送料", "送液", "feeding rate", "ml_h"])
            or _contains_any(normalized_action, ["electrospin", "spinning", "静电纺丝", "纺丝"])
            or "feed_rate" in condition_key
        )
    return True


def _build_process_step_match(
    parameter: dict[str, Any],
    matched_value: Any,
    matched_unit: Any,
    score: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "parameter": parameter,
        "matched_value": matched_value,
        "matched_unit": matched_unit,
        "score": min(score, 1.0),
        "reason": reason,
        "needs_llm": False,
    }


def _evidence_semantic_match(parameter: dict[str, Any], evidence_text: str) -> bool:
    canonical_key = str(parameter.get("canonical_key") or "").lower()
    text = _normalize_match_text(evidence_text)
    if "viscosity" in canonical_key:
        return "viscosity" in text or "pa_s" in text
    if "nmr" in canonical_key:
        return "nmr" in text or "ppm" in text
    if "ftir" in canonical_key:
        return "ftir" in text or " ir " in f" {text} " or "cm-1" in text
    if "xrd" in canonical_key:
        return "xrd" in text or "2theta" in text or "2θ" in text or "diffraction" in text
    if "raman" in canonical_key:
        return "raman" in text or "cm-1" in text
    keyword_tokens = SEMANTIC_KEYWORDS.get(canonical_key)
    if keyword_tokens and any(_normalize_match_text(token) in text for token in keyword_tokens):
        return True
    raw_name = str(parameter.get("raw_name") or "").strip().lower()
    return bool(raw_name and _normalize_match_text(raw_name) in text)

def _match_evidence_to_parameters(evidence_record: dict[str, Any], parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = _evidence_summary_text(evidence_record) or ""
    figure_type = str(evidence_record.get("figure_type") or "").lower()
    matches: list[dict[str, Any]] = []
    for parameter in parameters:
        parameter_id = parameter.get("parameter_id")
        if not parameter_id:
            continue
        if not _evidence_semantic_match(parameter, text):
            continue
        value = parameter.get("value")
        unit = None if parameter.get("unit") == "text" else parameter.get("unit")
        if value is None:
            continue
        if not _text_contains_value(text, value, unit, tolerance=0.05):
            continue
        score = 0.88
        if figure_type and any(token in figure_type for token in ("nmr", "ftir", "xrd", "raman")):
            score += 0.04
        matches.append(
            {
                "parameter": parameter,
                "matched_value": value,
                "matched_unit": unit,
                "score": min(score, 1.0),
                "reason": "evidence_text_value_and_semantic_match",
                "needs_llm": False,
            }
        )
    return _dedupe_match_specs(matches)


def _parameter_value_matches(parameter: dict[str, Any], value: Any, unit: Any) -> bool:
    target_value = parameter.get("value")
    target_numeric = _to_float(target_value)
    source_numeric = _to_float(value)
    normalized_parameter_unit = _normalized_parameter_unit(parameter)
    normalized_source_unit = _normalize_unit_text(unit)
    if normalized_parameter_unit and normalized_source_unit and normalized_parameter_unit != normalized_source_unit:
        return False
    if target_numeric is not None and source_numeric is not None:
        tolerance = 0.05 if normalized_parameter_unit in {"ml_h", "ppm", "pa_s"} else 0.5
        return abs(target_numeric - source_numeric) <= tolerance
    target_range = _parse_numeric_range(target_value)
    source_range = _parse_numeric_range(value)
    if target_range and source_range:
        return target_range == source_range
    return str(target_value).strip().lower() == str(value).strip().lower()


def _parse_numeric_range(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    text = (
        str(value)
        .strip()
        .replace("–", "-")
        .replace("—", "-")
        .replace("~", "-")
        .replace("−", "-")
        .replace(" ", "")
    )
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    low = float(match.group(1))
    high = float(match.group(2))
    if low > high:
        low, high = high, low
    return (low, high)



def _extract_reference_ids(refs: Any) -> set[str]:
    values = refs if isinstance(refs, list) else [refs] if refs is not None else []
    tokens: set[str] = set()
    for ref in values:
        if isinstance(ref, dict):
            for key in ("source_id", "evidence_id", "figure_id", "table_id"):
                value = ref.get(key)
                if value:
                    tokens.add(str(value))
        elif ref is not None:
            text = str(ref).strip()
            if text:
                tokens.add(text)
    return tokens


def _spectra_record_id(figure_id: Any) -> str:
    return f"spectra-{figure_id}"


def _match_spectra_record_to_parameters(
    spectra_record: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    figure_type = str(spectra_record.get("figure_type") or "").lower()
    rule = SPECTRA_RECORD_MATCH_RULES.get(figure_type)
    if not rule:
        return []
    matches: list[dict[str, Any]] = []
    temperature_observations: list[tuple[Any, str]] = []
    mass_loss_observations: list[tuple[Any, str]] = []

    for peak in spectra_record.get("peaks", []) or []:
        temperature = peak.get("temperature")
        if temperature is not None:
            temperature_observations.append((temperature, peak.get("description") or _spectra_summary_text(spectra_record)))
        mass_loss = peak.get("mass_loss_percent")
        if mass_loss is not None:
            mass_loss_observations.append((mass_loss, peak.get("description") or _spectra_summary_text(spectra_record)))

    for item in spectra_record.get("transition_temperatures", []) or []:
        temperature_observations.append((item, _spectra_summary_text(spectra_record)))
    for key in ("mass_loss_percent", "residual_mass_percent"):
        value = spectra_record.get(key)
        if value is not None:
            mass_loss_observations.append((value, _spectra_summary_text(spectra_record)))

    for temperature, source_text in temperature_observations:
        for parameter in parameters:
            if parameter.get("canonical_key") not in rule.get("temperature_keys", set()):
                continue
            if _parameter_value_matches(parameter, temperature, "C"):
                matches.append({
                    "parameter": parameter,
                    "matched_value": temperature,
                    "matched_unit": "C",
                    "score": 0.9,
                    "reason": "spectra_record_temperature_match",
                    "needs_llm": False,
                    "source_text": source_text,
                })

    for mass_loss, source_text in mass_loss_observations:
        for parameter in parameters:
            if parameter.get("canonical_key") not in rule.get("mass_loss_keys", set()):
                continue
            if _parameter_value_matches(parameter, mass_loss, "wt_percent"):
                matches.append({
                    "parameter": parameter,
                    "matched_value": mass_loss,
                    "matched_unit": "wt_percent",
                    "score": 0.88,
                    "reason": "spectra_record_mass_loss_match",
                    "needs_llm": False,
                    "source_text": source_text,
                })
    return _dedupe_match_specs(matches)


def _match_visual_extraction_to_parameters(
    spectra_record: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    figure_type = str(spectra_record.get("figure_type") or "").lower()
    rule = VISUAL_EXTRACTION_MATCH_RULES.get(figure_type)
    if not rule:
        return []
    candidate_values: list[tuple[str, Any, Any]] = []
    quantitative_values = spectra_record.get("quantitative_values") or {}
    for key, value in quantitative_values.items():
        unit = None
        if str(key).endswith("_nm"):
            unit = "nm"
        elif str(key).endswith("_um"):
            unit = "um"
        candidate_values.append((str(key), value, unit))
    for top_level_key in ("particle_size_nm", "estimated_size_nm", "fiber_diameter_um", "average_fiber_diameter_um"):
        if spectra_record.get(top_level_key) is not None:
            unit = "nm" if top_level_key.endswith("_nm") else "um"
            candidate_values.append((top_level_key, spectra_record.get(top_level_key), unit))

    matches: list[dict[str, Any]] = []
    for source_key, observed_value, observed_unit in candidate_values:
        for parameter in parameters:
            if parameter.get("canonical_key") not in rule.get("size_keys", set()):
                continue
            if _parameter_value_matches(parameter, observed_value, observed_unit):
                matches.append({
                    "parameter": parameter,
                    "matched_value": observed_value,
                    "matched_unit": observed_unit,
                    "score": 0.9,
                    "reason": "visual_extraction_numeric_match",
                    "needs_llm": False,
                    "source_key": source_key,
                    "source_text": _spectra_summary_text(spectra_record),
                })
    deduped = _dedupe_match_specs(matches)
    for row in deduped:
        row.setdefault("source_key", row.get("parameter", {}).get("canonical_key") or "observed_value")
    return deduped

def _dedupe_match_specs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        parameter = row["parameter"]
        parameter_id = str(parameter.get("parameter_id") or "")
        if not parameter_id:
            continue
        current = best.get(parameter_id)
        if current is None or float(row.get("score", 0.0)) > float(current.get("score", 0.0)):
            best[parameter_id] = row
    return list(best.values())
