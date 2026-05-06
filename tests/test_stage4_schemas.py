from __future__ import annotations

from alumina_sol_extractor.vision_spectra.schemas import (
    FerronCurveExtraction,
    MicroscopyExtraction,
    NMRExtraction,
    PeakRecord,
    ThermalAnalysisExtraction,
    UnknownFigureExtraction,
    VibrationalSpectrumExtraction,
    XRDExtraction,
)


def test_stage4_schema_models_accept_sparse_payloads() -> None:
    models = [
        NMRExtraction(figure_id="fig1"),
        VibrationalSpectrumExtraction(figure_id="fig2"),
        XRDExtraction(figure_id="fig3"),
        FerronCurveExtraction(figure_id="fig4"),
        ThermalAnalysisExtraction(figure_id="fig5"),
        MicroscopyExtraction(figure_id="fig6"),
        UnknownFigureExtraction(figure_id="fig7"),
    ]
    for model in models:
        dumped = model.model_dump()
        assert dumped["figure_id"].startswith("fig")


def test_peak_record_confidence_and_fields() -> None:
    peak = PeakRecord(position=62.5, unit="ppm", confidence=0.8)
    assert peak.model_dump()["position"] == 62.5
