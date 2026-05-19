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


def test_process_step_links_drying_temperature_without_hydrolysis_false_positive() -> None:
    paper = {"paper_id": "paper-1", "title": "Drying Test"}
    parameters = [
        {
            "parameter_id": "param-drying",
            "canonical_key": "drying_temperature_C",
            "raw_name": "drying temperature",
            "value": 90,
            "unit": "C",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-hydrolysis",
            "canonical_key": "hydrolysis_temperature_C",
            "raw_name": "hydrolysis temperature",
            "value": 90,
            "unit": "C",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-dry",
            "action": "dry",
            "action_zh": "干燥",
            "temperature_value": 90,
            "temperature_unit": "C",
            "evidence_text": "The gel fibers were dried at 90 C before the next step.",
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
    target_ids = {link["target_id"] for link in links}

    assert "param-drying" in target_ids
    assert "param-hydrolysis" not in target_ids
    assert unresolved == []


def test_process_step_links_concentration_temperature_and_time() -> None:
    paper = {"paper_id": "paper-1", "title": "Concentration Test"}
    parameters = [
        {
            "parameter_id": "param-temp",
            "canonical_key": "concentration_temperature_C",
            "raw_name": "concentration temperature",
            "value": 45,
            "unit": "C",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-time",
            "canonical_key": "concentration_time_h",
            "raw_name": "concentration time",
            "value": "18-24",
            "unit": "h",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-concentrate",
            "action": "concentrate",
            "action_zh": "减压浓缩",
            "temperature_value": 45,
            "temperature_unit": "C",
            "duration_value": "18–24",
            "duration_unit": "h",
            "evidence_text": "The spinning dope was concentrated in a 45 C water bath under reduced pressure for 18–24 h.",
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
    target_ids = {link["target_id"] for link in links}

    assert "param-temp" in target_ids
    assert "param-time" in target_ids
    assert unresolved == []


def test_process_step_links_peptization_time_without_hydrolysis_false_positive() -> None:
    paper = {"paper_id": "paper-1", "title": "Peptization Test"}
    parameters = [
        {
            "parameter_id": "param-peptization",
            "canonical_key": "peptization_time_h",
            "raw_name": "peptization time",
            "value": 4,
            "unit": "h",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-hydrolysis",
            "canonical_key": "hydrolysis_time_h",
            "raw_name": "hydrolysis time",
            "value": 4,
            "unit": "h",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-peptize",
            "action": "stir",
            "action_zh": "调节pH并搅拌",
            "duration_value": 4,
            "duration_unit": "h",
            "evidence_text": "After adding concentrated nitric acid to adjust pH, the sol was stirred for 4 h.",
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
    target_ids = {link["target_id"] for link in links}

    assert "param-peptization" in target_ids
    assert "param-hydrolysis" not in target_ids
    assert unresolved == []


def test_process_step_links_take_up_speed_from_take_up_context() -> None:
    paper = {"paper_id": "paper-1", "title": "Take-Up Test"}
    parameters = [
        {
            "parameter_id": "param-takeup",
            "canonical_key": "take_up_speed_m_min",
            "raw_name": "take-up speed",
            "value": 160,
            "unit": "m/min",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-takeup",
            "action": "take_up",
            "action_zh": "收丝牵引",
            "evidence_text": "The green fibers were collected by take-up winding at a line speed of 160 m/min.",
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

    assert any(link["target_id"] == "param-takeup" for link in links)
    assert unresolved == []


def test_process_step_links_heating_rate_from_heat_treatment_context() -> None:
    paper = {"paper_id": "paper-1", "title": "Heating Rate Test"}
    parameters = [
        {
            "parameter_id": "param-rate",
            "canonical_key": "heating_rate_C_min",
            "raw_name": "heating rate",
            "value": "1-5",
            "unit": "C/min",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-sinter",
            "action": "sinter",
            "action_zh": "升温烧结",
            "evidence_text": "The fibers were heated for sintering at 1-5 C/min before reaching the target temperature.",
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

    assert any(link["target_id"] == "param-rate" for link in links)
    assert unresolved == []


def test_process_step_does_not_numeric_substring_match_collector_distance() -> None:
    paper = {"paper_id": "paper-1", "title": "Substring Guard Test"}
    parameters = [
        {
            "parameter_id": "param-distance",
            "canonical_key": "collector_distance_cm",
            "raw_name": "collector distance",
            "value": 20,
            "unit": "cm",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
        {
            "parameter_id": "param-hold",
            "canonical_key": "holding_time_h",
            "raw_name": "holding time",
            "value": 2,
            "unit": "h",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
    ]
    process_steps = [
        {
            "step_id": "step-calcine",
            "action": "calcine",
            "action_zh": "煅烧",
            "temperature_value": 1200,
            "temperature_unit": "C",
            "duration_value": 2,
            "duration_unit": "h",
            "evidence_text": "再于 1200°C 煅烧 2 h",
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
    target_ids = {link["target_id"] for link in links}

    assert "param-distance" not in target_ids
    assert "param-hold" in target_ids
    assert unresolved == []


def test_process_step_links_collector_distance_in_distance_context() -> None:
    paper = {"paper_id": "paper-1", "title": "Collector Distance Test"}
    parameters = [
        {
            "parameter_id": "param-distance",
            "canonical_key": "collector_distance_cm",
            "raw_name": "collector distance",
            "value": 20,
            "unit": "cm",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-electrospin-distance",
            "action": "electrospin",
            "action_zh": "静电纺丝",
            "evidence_text": "喷丝头与接收板距离为 20 cm",
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

    assert any(link["target_id"] == "param-distance" for link in links)
    assert unresolved == []


def test_process_step_ph_requires_explicit_ph_context() -> None:
    paper = {"paper_id": "paper-1", "title": "pH Context Test"}
    parameters = [
        {
            "parameter_id": "param-ph",
            "canonical_key": "pH",
            "raw_name": "pH",
            "value": 2,
            "unit": "dimensionless",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-range",
            "action": "spin",
            "action_zh": "纺丝",
            "evidence_text": "PVP质量分数为1%–2%，纺丝操作箱恒温30°C。",
        },
        {
            "step_id": "step-ph",
            "action": "adjust",
            "action_zh": "调节pH",
            "evidence_text": "加入盐酸调节 pH 至 2。",
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
    step_ids = {link["source_id"] for link in links if link["target_id"] == "param-ph"}

    assert "step-range" not in step_ids
    assert "step-ph" in step_ids
    assert unresolved == []
