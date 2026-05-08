from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def _base_inputs():
    paper = {"paper_id": "paper-1", "title": "Test Paper"}
    parameters = [
        {
            "parameter_id": "param-voltage",
            "canonical_key": "applied_voltage_kV",
            "raw_name": "applied voltage",
            "value": 18,
            "unit": "kV",
            "sample_id": "S1",
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-distance",
            "canonical_key": "collector_distance_cm",
            "raw_name": "collector distance",
            "value": 20,
            "unit": "cm",
            "sample_id": "S1",
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-feed",
            "canonical_key": "feed_rate_ml_h",
            "raw_name": "feed rate",
            "value": 2.8,
            "unit": "mL/h",
            "sample_id": "S1",
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-calcine",
            "canonical_key": "calcination_temperature_C",
            "raw_name": "calcination temperature",
            "value": 600,
            "unit": "℃",
            "sample_id": "S1",
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-electrospin",
            "action": "electrospin",
            "action_zh": "静电纺丝",
            "condition_key": "electrospin_conditions",
            "linked_parameter_keys": ["applied_voltage_kV", "collector_distance_cm", "feed_rate_ml_h"],
            "evidence_text": "外加电场 18 kV，喷丝头与接收板的距离为 20 cm，进料速率为 2.8 mL/h。",
        },
        {
            "step_id": "step-heat",
            "action": "heat",
            "action_zh": "热处理",
            "temperature_value": 600,
            "temperature_unit": "℃",
            "duration_value": 2,
            "duration_unit": "h",
            "evidence_text": "以 1 ℃/min 的速率升温至 600 ℃，保持 2 h。",
        },
        {
            "step_id": "step-reagent",
            "action": "add",
            "action_zh": "加入",
            "reagent_name": "冰醋酸",
            "reagent_amount": 0.6,
            "reagent_unit": "mL",
            "reagent_role": "acid",
            "evidence_text": "加入 0.6 mL 冰醋酸。",
        },
    ]
    return paper, parameters, process_steps


def test_process_step_evidence_links_numeric_conditions() -> None:
    paper, parameters, process_steps = _base_inputs()
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=[],
        spectra=[],
        samples=[],
        process_steps=process_steps,
        link_types={"process_step_to_parameter"},
        max_candidates_per_type=20,
    )
    links, unresolved = build_deterministic_links(candidates)
    assert any(link["target_id"] == "param-voltage" for link in links)
    assert any(link["target_id"] == "param-distance" for link in links)
    assert any(link["target_id"] == "param-feed" for link in links)
    assert any(link["target_id"] == "param-calcine" for link in links)
    assert all(item["source_type"] == "process_step" for item in links)
    assert unresolved == []


def test_process_step_reagent_amount_without_parameter_does_not_fabricate_match() -> None:
    paper, parameters, process_steps = _base_inputs()
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=[],
        spectra=[],
        samples=[],
        process_steps=process_steps,
        link_types={"process_step_to_parameter"},
        max_candidates_per_type=20,
    )
    assert all("ice acetic acid" not in str(item.get("candidate_reason", "")).lower() for item in candidates)
