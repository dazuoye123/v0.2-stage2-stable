from __future__ import annotations

from alumina_sol_extractor.stage5.linking import candidate_builder as cb


def test_sanitize_link_value_single_key_dict_returns_scalar() -> None:
    assert cb._sanitize_link_value({"base_to_aluminum_molar_ratio": 0.9}) == 0.9


def test_sanitize_link_value_multi_key_dict_returns_compact_json() -> None:
    value = cb._sanitize_link_value({"nA": 0.17, "pHA": 3.3, "nC": 3.0})
    assert value == '{"nA":0.17,"nC":3.0,"pHA":3.3}'


def test_candidate_sanitizes_target_value_dict() -> None:
    candidate = cb._candidate(
        family="process_step_to_parameter",
        counters={"process_step_to_parameter": 0},
        paper_id="paper-1",
        source_type="process_step",
        source_id="step-1",
        source_text="heat treatment",
        source_value={"base_to_aluminum_molar_ratio": 0.9},
        source_unit=None,
        source_figure_id=None,
        target_type="parameter",
        target_id="param-1",
        target_text="composition",
        target_value={"nA": 0.17, "pHA": 3.3, "nC": 3.0},
        target_unit=None,
        target_figure_id=None,
        candidate_reason="test",
        deterministic_score=0.95,
        needs_llm=False,
        candidate_status="deterministic",
    )

    assert candidate.source_value == 0.9
    assert candidate.target_value == '{"nA":0.17,"nC":3.0,"pHA":3.3}'


def test_build_deterministic_links_accepts_sanitized_candidate_values(monkeypatch) -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-1",
            "canonical_key": "start_temperature_C",
            "raw_name": "composition",
            "value": {"nA": 0.17, "pHA": 3.3, "nC": 3.0},
            "unit": None,
            "linked_figure_ids": [],
        }
    ]
    process_steps = [
        {
            "step_id": "step-1",
            "action": "mix",
            "action_zh": "mix",
            "evidence_text": "mix solution",
        }
    ]

    def fake_match(_process_step, params, _parameters_by_key):
        return [
            {
                "parameter": params[0],
                "matched_value": {"base_to_aluminum_molar_ratio": 0.9},
                "matched_unit": None,
                "score": 0.95,
                "reason": "test_match",
                "needs_llm": False,
            }
        ]

    monkeypatch.setattr(cb, "_match_process_step_to_parameters", fake_match)

    candidates = cb.build_link_candidates(
        paper,
        parameters,
        evidence=[],
        spectra=[],
        samples=[],
        process_steps=process_steps,
        link_types={"process_step_to_parameter"},
        max_candidates_per_type=5,
    )

    assert candidates[0]["source_value"] == 0.9
    assert candidates[0]["target_value"] == '{"nA":0.17,"nC":3.0,"pHA":3.3}'

    links, unresolved = cb.build_deterministic_links(candidates)
    assert len(links) == 1
    assert unresolved == []
