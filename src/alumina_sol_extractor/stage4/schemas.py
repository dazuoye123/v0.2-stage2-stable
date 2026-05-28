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
    chemical_shift_ppm: float | None = None
    unit: str | None = None
    band_type: str | None = None
    intensity_level: str | None = None
    is_primary_peak: bool | None = None
    assignment: str | None = None
    functional_group: str | None = None
    phase_or_species: str | None = None
    species_assignment: str | None = None
    peak_width_type: str | None = None
    relative_intensity: float | None = None
    area: float | None = None
    source: str | None = None
    source_text: str | None = None
    conflict_warning: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_note: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ThermalEventRecord(Stage4BaseModel):
    event_type: str | None = None
    temperature_onset: float | None = None
    temperature_peak: float | None = None
    temperature_end: float | None = None
    temperature_unit: str | None = None
    mass_loss_percent: float | None = None
    residue_percent: float | None = None
    assignment: str | None = None
    source: str | None = None
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class FerronSpeciesRecord(Stage4BaseModel):
    species: str | None = None
    fraction_percent: float | None = None
    concentration: float | str | None = None
    source: str | None = None
    source_text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


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
    reference_ticks_visible: bool | None = None
    visible_peak_count_estimate: int | None = None
    reference_cards: list[str] = Field(default_factory=list)
    sample_name: str | None = None


class FerronCurveExtraction(BaseFigureExtraction):
    curve_type: str | None = None
    al_species: list[FerronSpeciesRecord] = Field(default_factory=list)
    species_quantification: dict[str, float | None] = Field(default_factory=dict)
    Ala_fraction_percent: float | None = None
    Alb_fraction_percent: float | None = None
    Alc_fraction_percent: float | None = None
    Al13_fraction_percent: float | None = None
    time_axis_unit: str | None = None
    fitted_parameters: dict[str, Any] = Field(default_factory=dict)
    equation: str | None = None
    r_squared: float | None = None
    method_summary: str | None = None
    sample_name: str | None = None


class ThermalAnalysisExtraction(BaseFigureExtraction):
    mass_loss_steps: list[dict[str, Any]] = Field(default_factory=list)
    thermal_events: list[ThermalEventRecord] = Field(default_factory=list)
    endothermic_peaks: list[PeakRecord] = Field(default_factory=list)
    exothermic_peaks: list[PeakRecord] = Field(default_factory=list)
    transition_temperatures: list[float] = Field(default_factory=list)
    residue_percent: float | None = None
    total_mass_loss_percent: float | None = None
    final_residue_percent: float | None = None
    atmosphere: str | None = None
    heating_rate: float | str | None = None


class MicroscopyExtraction(BaseFigureExtraction):
    morphology_summary: str | None = None
    object_identity: str | None = None
    view_type: str | None = None
    morphology_type: str | None = None
    surface_smoothness: str | None = None
    compactness: str | None = None
    fracture_type: str | None = None
    diameter_estimate: float | None = None
    diameter_unit: str | None = None
    diameter_range: str | None = None
    diameter_basis: str | None = None
    particle_size_estimate: float | None = None
    particle_size_range: str | None = None
    particle_size_unit: str | None = None
    particle_size_basis: str | None = None
    scale_bar: str | None = None
    estimated_particle_size: dict[str, Any] | None = None
    estimated_fiber_diameter: dict[str, Any] | None = None
    surface_features: list[str] = Field(default_factory=list)
    morphology_features: list[str] = Field(default_factory=list)
    image_quality_notes: list[str] = Field(default_factory=list)
    warning: str | None = None


class UnknownFigureExtraction(BaseFigureExtraction):
    likely_figure_type: str | None = None
    safe_observations: list[str] = Field(default_factory=list)
    why_uncertain: str | None = None
    raw_notes: str | None = None


class UniversalFigureExtraction(Stage4BaseModel):
    paper_id: str | None = None
    figure_id: str | None = None
    stage2_figure_class: str | None = None
    stage2_predicted_figure_type: str | None = None
    stage3_figure_type: str | None = None
    initial_figure_type: str | None = None
    actual_figure_type: str | None = None
    type_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    type_reason: str | None = None
    stage2_type_used_as_hint: bool | None = None
    type_mismatch: bool = False
    corrected_from_stage2_type: str | None = None
    needs_manual_review: bool = False
    routing_mode: str | None = None
    caption: str | None = None
    image_basename: str | None = None
    image_readability: str | None = None
    text_context_quality: str | None = None
    warnings: list[str] = Field(default_factory=list)
    conflict_warnings: list[str] = Field(default_factory=list)
    extraction: dict[str, Any] = Field(default_factory=dict)
