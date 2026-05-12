from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def test_ph_text_evidence_generates_deterministic_link() -> None:
    paper = {"paper_id": "paper-1"}
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
    evidence = [
        {
            "evidence_id": "ev-ph",
            "evidence_type": "text",
            "fact_summary": ["When the sol precursor pH value was about 2, stable gel fibers formed."],
            "detailed_observation": "When the sol precursor pH value was about 2, stable gel fibers formed.",
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

    assert any(link["source_id"] == "ev-ph" and link["target_id"] == "param-ph" for link in links)


def test_range_evidence_with_unit_generates_pvp_link() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-pvp",
            "canonical_key": "pvp_content_wt_percent",
            "raw_name": "PVP content",
            "value": "1-2",
            "unit": "wt%",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        }
    ]
    evidence = [
        {
            "evidence_id": "ev-pvp",
            "evidence_type": "text",
            "fact_summary": ["The PVP content was 1%–2% and the fibers remained stable."],
            "detailed_observation": "The PVP content was 1%–2% and the fibers remained stable.",
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

    assert any(link["source_id"] == "ev-pvp" and link["target_id"] == "param-pvp" for link in links)


def test_ambient_temperature_text_generates_link_without_misclassifying_other_fields() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-ambient",
            "canonical_key": "ambient_temperature_C",
            "raw_name": "ambient temperature",
            "value": 30,
            "unit": "C",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": [],
        },
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
        },
    ]
    evidence = [
        {
            "evidence_id": "ev-temp",
            "evidence_type": "text",
            "fact_summary": ["The operation box was kept at 30 °C during spinning."],
            "detailed_observation": "The operation box was kept at 30 °C during spinning.",
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

    assert any(link["source_id"] == "ev-temp" and link["target_id"] == "param-ambient" for link in links)
    assert not any(link["target_id"] == "param-viscosity" for link in links)
