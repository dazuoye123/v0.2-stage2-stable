from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def test_spectra_peak_value_match_generates_deterministic_link() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-ftir-467",
            "canonical_key": "ftir_peak_position_cm_1",
            "raw_name": "FTIR peak",
            "value": 467,
            "unit": "cm^-1",
            "sample_id": None,
            "evidence_refs": ["ev-ftir"],
            "linked_figure_ids": ["图2-2"],
            "linked_spectra_ids": ["图2-2"],
        }
    ]
    evidence = [
        {
            "evidence_id": "ev-ftir",
            "figure_id": "图2-2",
            "figure_type": "ftir_spectrum",
            "caption": "FTIR",
            "fact_summary": ["467 cm^-1 peak"],
        }
    ]
    spectra = [
        {
            "figure_id": "图2-2",
            "figure_type": "ftir_spectrum",
            "technique": "FTIR",
            "peaks": [{"position": 467, "unit": "cm^-1", "assignment": "Al-O", "source": "image_and_text"}],
        }
    ]
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=evidence,
        spectra=spectra,
        samples=[],
        process_steps=[],
        link_types={"spectra_peak_to_parameter"},
        max_candidates_per_type=20,
    )
    links, unresolved = build_deterministic_links(candidates)
    assert any(link["source_type"] == "spectra_peak" and link["target_id"] == "param-ftir-467" for link in links)
    assert unresolved == []


def test_same_figure_without_peak_match_is_not_high_confidence_deterministic() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-ftir-467",
            "canonical_key": "ftir_peak_position_cm_1",
            "raw_name": "FTIR peak",
            "value": 467,
            "unit": "cm^-1",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": ["图2-2"],
            "linked_spectra_ids": ["图2-2"],
        }
    ]
    spectra = [
        {
            "figure_id": "图2-2",
            "figure_type": "ftir_spectrum",
            "technique": "FTIR",
            "peaks": [{"position": 700, "unit": "cm^-1", "assignment": "other", "source": "image"}],
        }
    ]
    candidates = build_link_candidates(
        paper,
        parameters,
        evidence=[],
        spectra=spectra,
        samples=[],
        process_steps=[],
        link_types={"spectra_peak_to_parameter"},
        max_candidates_per_type=20,
    )
    assert candidates == []
