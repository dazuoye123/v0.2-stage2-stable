"""Pydantic schemas for Stage 4 vision spectra extraction."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Stage4BaseModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class BaseFigureExtraction(Stage4BaseModel):
    paper_id: str | None = None
    figure_id: str | None = None
    figure_type: str | None = None
    technique: str | None = None
    source_image_path: str | None = None
    caption: str | None = None
    extraction_model: str | None = None
    extraction_mode: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    raw_notes: str | None = None
    input_context_summary: str | None = None
    used_context_sources: list[str] = Field(default_factory=list)
    image_readability: str | None = None
    text_context_quality: str | None = None
    conflict_warnings: list[str] = Field(default_factory=list)


class PeakRecord(Stage4BaseModel):
    position: float | None = None
    unit: str | None = None
    assignment: str | None = None
    relative_intensity: float | None = None
    area: float | None = None
    source: str | None = None
    source_text: str | None = None
    conflict_warning: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_note: str | None = None


class NMRExtraction(BaseFigureExtraction):
    nucleus: str | None = None
    x_axis_unit: str | None = "ppm"
    peaks: list[PeakRecord] = Field(default_factory=list)
    species_summary: str | None = None
    possible_species: list[str] = Field(default_factory=list)
    quantitative_values: dict[str, float | int | str | None] = Field(default_factory=dict)
    sample_name: str | None = None
    reference_standard: str | None = None


class VibrationalSpectrumExtraction(BaseFigureExtraction):
    spectrum_type: str | None = None
    x_axis_unit: str | None = "cm-1"
    peaks: list[PeakRecord] = Field(default_factory=list)
    band_assignments: list[str] = Field(default_factory=list)
    sample_name: str | None = None
    trend_summary: str | None = None


class XRDExtraction(BaseFigureExtraction):
    x_axis_unit: str | None = "2theta_deg"
    peaks: list[PeakRecord] = Field(default_factory=list)
    phase_assignments: list[str] = Field(default_factory=list)
    detected_phases: list[str] = Field(default_factory=list)
    crystallinity_trend: str | None = None
    reference_cards: list[str] = Field(default_factory=list)
    sample_name: str | None = None


class FerronCurveExtraction(BaseFigureExtraction):
    curve_type: str | None = None
    species_quantification: dict[str, float | None] = Field(default_factory=dict)
    Ala_fraction_percent: float | None = None
    Alb_fraction_percent: float | None = None
    Alc_fraction_percent: float | None = None
    Al13_fraction_percent: float | None = None
    time_axis_unit: str | None = None
    fitted_parameters: dict[str, Any] = Field(default_factory=dict)
    sample_name: str | None = None


class ThermalAnalysisExtraction(BaseFigureExtraction):
    mass_loss_steps: list[dict[str, Any]] = Field(default_factory=list)
    endothermic_peaks: list[PeakRecord] = Field(default_factory=list)
    exothermic_peaks: list[PeakRecord] = Field(default_factory=list)
    transition_temperatures: list[float] = Field(default_factory=list)
    residue_percent: float | None = None


class MicroscopyExtraction(BaseFigureExtraction):
    morphology_summary: str | None = None
    scale_bar: str | None = None
    estimated_particle_size: dict[str, Any] | None = None
    estimated_fiber_diameter: dict[str, Any] | None = None
    surface_features: list[str] = Field(default_factory=list)
    warning: str | None = None


class UnknownFigureExtraction(BaseFigureExtraction):
    raw_notes: str | None = None
