from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def test_text_evidence_matches_parameter_value_and_unit() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-viscosity",
            "canonical_key": "viscosity_Pa_s",
            "raw_name": "viscosity",
            "value": "0.27-0.38",
            "unit": "Pa*s",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    evidence = [
        {
            "evidence_id": "ev-viscosity",
            "evidence_type": "text",
            "caption": None,
            "fact_summary": ["The spinnable sol viscosity was 0.27-0.38 Pa*s."],
            "detailed_observation": "The spinnable sol viscosity was 0.27-0.38 Pa*s.",
            "source_section": "results",
        }
    ]
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=evidence,
        spectra=[],
        samples=[],
        process_steps=[],
        link_types={"evidence_to_parameter"},
        max_candidates_per_type=20,
    )
    links, _ = build_deterministic_links(candidates)
    assert any(link["source_id"] == "ev-viscosity" and link["target_id"] == "param-viscosity" for link in links)


def test_unrelated_text_evidence_is_not_forced_into_link() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-viscosity",
            "canonical_key": "viscosity_Pa_s",
            "raw_name": "viscosity",
            "value": "0.27-0.38",
            "unit": "Pa*s",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    evidence = [
        {
            "evidence_id": "ev-xrd",
            "figure_id": "图2.3",
            "figure_type": "xrd_pattern",
            "caption": "XRD pattern",
            "fact_summary": ["The XRD pattern shows the alpha phase transformation."],
            "detailed_observation": "No viscosity value is described here.",
            "source_section": "results",
        }
    ]
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=evidence,
        spectra=[],
        samples=[],
        process_steps=[],
        link_types={"evidence_to_parameter"},
        max_candidates_per_type=20,
    )
    assert not any(item["source_id"] == "ev-xrd" and item["target_id"] == "param-viscosity" for item in candidates)
