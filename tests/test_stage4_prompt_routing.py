from __future__ import annotations

from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.routing import get_schema_for_figure_type, normalize_figure_type


def test_routing_normalizes_common_spectra_types() -> None:
    assert normalize_figure_type(None, "IR谱图") == "ftir_spectrum"
    assert normalize_figure_type(None, "27Al NMR spectrum") == "nmr_spectrum"
    assert normalize_figure_type(None, "XRD diffraction pattern") == "xrd_pattern"
    assert normalize_figure_type(None, "Al-Ferron curve") == "ferron_curve"
    assert normalize_figure_type(None, "Raman spectrum") == "raman_spectrum"


def test_prompt_and_schema_route_from_figure_type() -> None:
    prompt = get_prompt_for_figure_type("ftir_spectrum")
    schema_cls = get_schema_for_figure_type("ftir_spectrum")
    assert prompt.schema_name == "VibrationalSpectrumExtraction"
    assert schema_cls.__name__ == "VibrationalSpectrumExtraction"
