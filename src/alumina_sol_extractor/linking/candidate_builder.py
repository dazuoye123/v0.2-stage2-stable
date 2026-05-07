"""Build constrained linking candidates from Stage 5 final_dataset outputs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dataset_fusion.loaders import read_json, read_jsonl

from .models import LinkCandidate, LinkRecord

DEFAULT_LINK_FAMILIES = {
    "spectra_peak_to_parameter",
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


def load_final_dataset_inputs(final_dataset_dir: Path | str) -> dict[str, Any]:
    final_dataset_dir = Path(final_dataset_dir)
    return {
        "paper": read_json(final_dataset_dir / "paper.json", default={}) or {},
        "samples": read_jsonl(final_dataset_dir / "samples.jsonl"),
        "parameters": read_jsonl(final_dataset_dir / "parameters.jsonl"),
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
    link_types: set[str] | None = None,
    max_candidates_per_type: int = 50,
) -> list[dict[str, Any]]:
    families = link_types or DEFAULT_LINK_FAMILIES
    candidates: list[LinkCandidate] = []
    counters: dict[str, int] = defaultdict(int)
    paper_id = paper.get("paper_id")

    evidence_by_figure = _group_by(evidence, "figure_id")
    evidence_by_id = {item.get("evidence_id"): item for item in evidence if item.get("evidence_id")}
    spectra_by_figure = {item.get("figure_id"): item for item in spectra if item.get("figure_id")}
    samples_by_id = {item.get("sample_id"): item for item in samples if item.get("sample_id")}

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
            evidence_refs = set(_coerce_str_list(parameter.get("evidence_refs")))
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
                    linked_figures = set(_coerce_str_list(parameter.get("linked_figure_ids")))
                    linked_spectra = set(_coerce_str_list(parameter.get("linked_spectra_ids")))
                    evidence_refs = set(_coerce_str_list(parameter.get("evidence_refs")))
                    same_figure = figure_id in linked_figures or figure_id in linked_spectra or bool(linked_evidence_ids & evidence_refs)
                    score = 0.6
                    if same_figure:
                        score += 0.3
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
                            candidate_reason="technique_and_numeric_tolerance_match",
                            deterministic_score=min(score, 1.0),
                            needs_llm=not same_figure,
                            candidate_status="deterministic" if same_figure and score >= 0.85 else "needs_llm",
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
            confidence = "high"
        elif candidate.source_type == "parameter" and candidate.target_type == "sample":
            link_type = "describes"
            confidence = "high"
        elif candidate.source_type == "spectra_peak" and candidate.target_type == "parameter":
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
                created_by="deterministic",
            ).model_dump()
        )
        counter += 1
    return links, unresolved


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
