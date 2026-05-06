"""Stage 4 vision-spectra extraction helpers."""

from .extractor import Stage4VisionSpectraExtractor
from .routing import get_schema_for_figure_type, normalize_figure_type, should_process_figure
from .schemas import (
    BaseFigureExtraction,
    FerronCurveExtraction,
    MicroscopyExtraction,
    NMRExtraction,
    PeakRecord,
    ThermalAnalysisExtraction,
    UnknownFigureExtraction,
    VibrationalSpectrumExtraction,
    XRDExtraction,
)

__all__ = [
    "BaseFigureExtraction",
    "FerronCurveExtraction",
    "MicroscopyExtraction",
    "NMRExtraction",
    "PeakRecord",
    "Stage4VisionSpectraExtractor",
    "ThermalAnalysisExtraction",
    "UnknownFigureExtraction",
    "VibrationalSpectrumExtraction",
    "XRDExtraction",
    "get_schema_for_figure_type",
    "normalize_figure_type",
    "should_process_figure",
]
