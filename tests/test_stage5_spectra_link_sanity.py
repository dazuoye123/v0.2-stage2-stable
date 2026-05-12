from __future__ import annotations

from alumina_sol_extractor.linking.candidate_builder import build_deterministic_links, build_link_candidates


def test_xrd_approximate_peak_match_is_medium_confidence() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-xrd-25.5",
            "canonical_key": "xrd_peak_position_2theta_deg",
            "raw_name": "xrd peak",
            "value": 25.5,
            "unit": "2theta_deg",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": ["Fig.3"],
            "linked_spectra_ids": ["Fig.3"],
        }
    ]
    spectra = [
        {
            "figure_id": "Fig.3",
            "figure_type": "xrd_pattern",
            "technique": "XRD",
            "peaks": [{"position": 25.8, "unit": "2theta_deg", "source": "image_and_text"}],
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
    links, _ = build_deterministic_links(candidates)

    match = next(link for link in links if link["target_id"] == "param-xrd-25.5")
    assert match["confidence"] == "medium"
    assert "approximate" in str(match["reasoning"])


def test_ftir_peak_is_not_linked_to_process_temperature() -> None:
    paper = {"paper_id": "paper-1"}
    parameters = [
        {
            "parameter_id": "param-temp",
            "canonical_key": "calcination_temperature_C",
            "raw_name": "calcination temperature",
            "value": 600,
            "unit": "C",
            "sample_id": None,
            "evidence_refs": [],
            "linked_figure_ids": ["Fig.5"],
            "linked_spectra_ids": ["Fig.5"],
        }
    ]
    spectra = [
        {
            "figure_id": "Fig.5",
            "figure_type": "ftir_spectrum",
            "technique": "FTIR",
            "peaks": [{"position": 467, "unit": "cm^-1", "source": "image_and_text"}],
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


def test_xrd_peak_is_not_linked_to_viscosity_parameter() -> None:
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
            "linked_figure_ids": ["Fig.3"],
            "linked_spectra_ids": ["Fig.3"],
        }
    ]
    spectra = [
        {
            "figure_id": "Fig.3",
            "figure_type": "xrd_pattern",
            "technique": "XRD",
            "peaks": [{"position": 25.8, "unit": "2theta_deg", "source": "image_and_text"}],
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
