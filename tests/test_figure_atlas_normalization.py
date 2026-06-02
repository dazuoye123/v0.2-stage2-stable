from __future__ import annotations

from alumina_sol_extractor.figure_atlas.normalization import (
    normalize_parameter_family,
    normalize_process_step_family,
    normalize_spectra_type,
)


def test_parameter_family_normalization_examples() -> None:
    assert normalize_parameter_family("pH") == "pH"
    assert normalize_parameter_family("calcination_temperature_C") == "calcination temperature"
    assert normalize_parameter_family("nmr_27Al_peak_position_ppm") == "NMR shift"
    assert normalize_parameter_family("ftir_peak_position_cm_1") == "FTIR peak"
    assert normalize_parameter_family("xrd_peak_position_2theta_deg") == "XRD peak"
    assert normalize_parameter_family("particle_size_nm") == "particle size"
    assert normalize_parameter_family("average_fiber_diameter_um") == "fiber diameter"


def test_spectra_type_normalization_examples() -> None:
    assert normalize_spectra_type("27Al MAS NMR") == "NMR"
    assert normalize_spectra_type("ftir_spectrum") == "FTIR"
    assert normalize_spectra_type("xrd_pattern") == "XRD"
    assert normalize_spectra_type("tg_dsc_curve") == "TG/DSC"
    assert normalize_spectra_type("SEM image") == "SEM/TEM microscopy"


def test_process_step_normalization_examples() -> None:
    assert normalize_process_step_family("hydrolysis") == "hydrolysis"
    assert normalize_process_step_family("aging") == "aging"
    assert normalize_process_step_family("electrospinning") == "spinning"
    assert normalize_process_step_family("calcination") == "calcination"
