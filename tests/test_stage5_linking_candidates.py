from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def sample_inputs():
    paper = {"paper_id": "paper-1", "title": "Test Paper"}
    parameters = [
        {
            "parameter_id": "param-nmr-625",
            "paper_id": "paper-1",
            "sample_id": None,
            "canonical_key": "nmr_27Al_peak_position_ppm",
            "raw_name": "27Al NMR peak",
            "value": 62.5,
            "unit": "ppm",
            "evidence_refs": [],
            "linked_figure_ids": [],
            "linked_spectra_ids": ["图2.2"],
        },
        {
            "parameter_id": "param-temp",
            "paper_id": "paper-1",
            "sample_id": None,
            "canonical_key": "start_temperature_C",
            "raw_name": "起始反应温度",
            "value": 50,
            "unit": "°C",
            "evidence_refs": ["图2.4"],
            "linked_figure_ids": ["图2.4"],
            "linked_spectra_ids": [],
        },
    ]
    evidence = [
        {
            "evidence_id": "图2.2",
            "figure_id": "图2.2",
            "figure_type": "nmr_spectrum",
            "caption": "27Al NMR 谱图",
            "fact_summary": ["62.5 ppm peak for Al13"],
        },
        {
            "evidence_id": "图2.4",
            "figure_id": "图2.4",
            "figure_type": "nmr_spectrum",
            "caption": "temperature evidence",
            "fact_summary": ["50 °C gives the strongest peak"],
        },
    ]
    spectra = [
        {
            "figure_id": "图2.2",
            "figure_type": "nmr_spectrum",
            "schema_name": "NMRExtraction",
            "technique": "27Al NMR",
            "peaks": [
                {"position": 62.5, "unit": "ppm", "assignment": "Al13^7+", "source_text": "62.5 ppm peak"},
                {"position": 62.8, "unit": "ppm", "assignment": "nearby", "source_text": "nearby peak"},
            ],
        }
    ]
    samples = [
        {
            "sample_id": "sample-1",
            "sample_name": "sample one",
            "linked_parameters": [],
            "linked_evidence": ["图2.2"],
            "linked_spectra": ["图2.2"],
        }
    ]
    return paper, parameters, evidence, spectra, samples


def test_same_figure_generates_candidate():
    paper, parameters, evidence, spectra, samples = sample_inputs()
    candidates = build_link_candidates(paper, parameters, evidence, spectra, samples, max_candidates_per_type=20)
    same_figure = [
        item
        for item in candidates
        if item["source_type"] == "spectra_record"
        and item["target_type"] == "evidence_object"
        and item["source_figure_id"] == "图2.2"
        and item["target_id"] == "图2.2"
    ]
    assert same_figure


def test_parameter_evidence_ref_generates_deterministic_link():
    paper, parameters, evidence, spectra, samples = sample_inputs()
    candidates = build_link_candidates(paper, parameters, evidence, spectra, samples, max_candidates_per_type=20)
    links, unresolved = build_deterministic_links(candidates)
    assert any(item["source_id"] == "图2.4" and item["target_id"] == "param-temp" for item in links)
    assert unresolved


def test_nmr_peak_candidate_matches_62_5_ppm():
    paper, parameters, evidence, spectra, samples = sample_inputs()
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence,
        spectra,
        samples,
        link_types={"spectra_peak_to_parameter"},
        max_candidates_per_type=20,
    )
    match = [
        item
        for item in candidates
        if item["source_type"] == "spectra_peak"
        and item["target_id"] == "param-nmr-625"
        and item["source_value"] == 62.5
    ]
    assert match
    assert any(item["candidate_status"] == "deterministic" for item in match)


def test_numeric_tolerance_applies_for_slightly_offset_peak():
    paper, parameters, evidence, spectra, samples = sample_inputs()
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence,
        spectra,
        samples,
        link_types={"spectra_peak_to_parameter"},
        max_candidates_per_type=20,
    )
    nearby = [
        item
        for item in candidates
        if item["source_type"] == "spectra_peak"
        and item["source_value"] == 62.8
        and item["target_id"] == "param-nmr-625"
    ]
    assert nearby


def test_candidate_ids_are_unique():
    paper, parameters, evidence, spectra, samples = sample_inputs()
    candidates = build_link_candidates(paper, parameters, evidence, spectra, samples, max_candidates_per_type=20)
    ids = [item["candidate_id"] for item in candidates]
    assert len(ids) == len(set(ids))
