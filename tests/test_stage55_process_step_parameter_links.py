from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def test_process_steps_link_thesis_method_parameters() -> None:
    paper = {"paper_id": "paper-1", "title": "Test"}
    parameters = [
        {
            "parameter_id": "param-aluminum",
            "canonical_key": "aluminum_source",
            "raw_name": "铝源",
            "value": "铝粉",
            "unit": None,
            "sample_id": None,
            "evidence_refs": [],
        },
        {
            "parameter_id": "param-nitrate",
            "canonical_key": "nitrate_source",
            "raw_name": "硝酸盐来源",
            "value": "九水合硝酸铝",
            "unit": None,
            "sample_id": None,
            "evidence_refs": [],
        },
        {
            "parameter_id": "param-temp",
            "canonical_key": "reaction_temperature_C",
            "raw_name": "反应温度",
            "value": 90,
            "unit": "℃",
            "sample_id": None,
            "evidence_refs": [],
        },
        {
            "parameter_id": "param-time",
            "canonical_key": "reaction_time_h",
            "raw_name": "反应时间",
            "value": 5.5,
            "unit": "h",
            "sample_id": None,
            "evidence_refs": [],
        },
        {
            "parameter_id": "param-feed",
            "canonical_key": "feeding_method",
            "raw_name": "加入方式",
            "value": "分批加入",
            "unit": None,
            "sample_id": None,
            "evidence_refs": [],
        },
        {
            "parameter_id": "param-ph",
            "canonical_key": "ph",
            "raw_name": "pH",
            "value": 2,
            "unit": None,
            "sample_id": None,
            "evidence_refs": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-1",
            "action": "add",
            "action_zh": "加入",
            "reagent_name": "九水合硝酸铝",
            "evidence_text": "称取九水合硝酸铝和铝粉，加入去离子水。",
        },
        {
            "step_id": "step-2",
            "action": "heat",
            "action_zh": "加热",
            "temperature_value": 90,
            "temperature_unit": "℃",
            "duration_value": 5.5,
            "duration_unit": "h",
            "evidence_text": "升温至 90 ℃，继续反应 5.5 h。",
        },
        {
            "step_id": "step-3",
            "action": "add",
            "action_zh": "加入",
            "evidence_text": "铝粉分批加入，调节 pH 值为 2。",
        },
    ]

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
    target_ids = {link["target_id"] for link in links}

    assert "param-aluminum" in target_ids
    assert "param-nitrate" in target_ids
    assert "param-temp" in target_ids
    assert "param-time" in target_ids
    assert "param-feed" in target_ids
    assert "param-ph" in target_ids
    assert unresolved == []


def test_process_step_links_null_valued_duration_parameter_when_observed_value_is_explicit() -> None:
    paper = {"paper_id": "paper-1", "title": "Test"}
    parameters = [
        {
            "parameter_id": "param-time",
            "canonical_key": "reaction_time_h",
            "raw_name": "反应时间",
            "value": None,
            "unit": None,
            "sample_id": None,
            "evidence_refs": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-1",
            "action": "other",
            "action_zh": "其他",
            "duration_value": 5.5,
            "duration_unit": "小时",
            "evidence_text": "继续保持 90℃ 反应5.5小时",
        }
    ]

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

    assert unresolved == []
    assert len(links) == 1
    assert links[0]["target_id"] == "param-time"
    assert links[0]["reasoning"] == "process_step_duration_observed_value_semantic_match"
