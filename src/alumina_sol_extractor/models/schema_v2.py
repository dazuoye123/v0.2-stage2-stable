"""Pydantic models for Stage 3 schema_v2 extraction records."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


JsonScalar = str | int | float | bool | None


class SchemaBaseModel(BaseModel):
    """Base model that accepts sparse literature extraction payloads."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class EvidenceRef(SchemaBaseModel):
    source_id: str | None = None
    page: int | None = None
    section: str | None = None
    figure_id: str | None = None
    table_id: str | None = None
    quote_or_context: str | None = None
    confidence: float | None = None


class ParameterRecord(SchemaBaseModel):
    canonical_key: str | None = None
    raw_name: str | None = None
    value: JsonScalar = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    raw_text: str | None = None
    normalization_note: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class PaperBasicInfo(SchemaBaseModel):
    paper_id: str | None = None
    source_file: str | None = None
    title: str | None = None
    translated_title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    document_type: str | None = None
    language: str | None = None
    is_review: bool | None = None
    material_system: str | None = None
    process_route: str | None = None
    research_object_form: str | None = None
    abstract_summary: str | None = None
    keywords: list[str] = Field(default_factory=list)


class RawMaterial(SchemaBaseModel):
    material_id: str | None = None
    role: str | None = None
    name: str | None = None
    formula_or_composition: str | None = None
    purity_or_grade: str | None = None
    supplier: str | None = None
    amount: JsonScalar = None
    amount_unit: str | None = None
    note: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class NominalCompositionItem(SchemaBaseModel):
    component: str | None = None
    value: JsonScalar = None
    unit: str | None = None
    basis: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class SharedProcessSummary(SchemaBaseModel):
    precursor_route_summary: str | None = None
    precursor_type: str | None = None
    forming_method: str | None = None
    heat_treatment_route_summary: str | None = None
    testing_summary: str | None = None


class SharedParameters(SchemaBaseModel):
    precursor_solution: dict[str, Any] = Field(default_factory=dict)
    forming: dict[str, Any] = Field(default_factory=dict)
    heat_treatment: dict[str, Any] = Field(default_factory=dict)
    product_structure: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)


class HeatTreatmentProgram(SchemaBaseModel):
    program_id: str | None = None
    stage_name: str | None = None
    start_temperature_C: float | None = None
    target_temperature_C: float | None = None
    heating_rate_C_min: float | None = None
    holding_time_h: float | None = None
    atmosphere: str | None = None
    cooling_method: str | None = None
    purpose: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class CharacterizationMethod(SchemaBaseModel):
    method: str | None = None
    sample_state: str | None = None
    instrument: str | None = None
    test_conditions: str | None = None
    measured_target: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class TGDSCEvent(SchemaBaseModel):
    event_id: str | None = None
    temperature_range_C: str | None = None
    mass_loss_wt_percent: float | None = None
    dsc_peak_temperature_C: float | None = None
    interpretation: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class SpectroscopicEvidence(SchemaBaseModel):
    evidence_id: str | None = None
    method: str | None = None
    peak_position: JsonScalar = None
    peak_unit: str | None = None
    assignment: str | None = None
    interpretation: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class MechanismNote(SchemaBaseModel):
    note_id: str | None = None
    claim: str | None = None
    basis_type: str | None = None
    confidence: float | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class GlobalObservations(SchemaBaseModel):
    tg_dsc_events: list[TGDSCEvent] = Field(default_factory=list)
    spectroscopic_evidence: list[SpectroscopicEvidence] = Field(default_factory=list)
    mechanism_notes: list[MechanismNote] = Field(default_factory=list)


class GlobalConstants(SchemaBaseModel):
    scope_note: str | None = None
    raw_materials: list[RawMaterial] = Field(default_factory=list)
    nominal_composition: list[NominalCompositionItem] = Field(default_factory=list)
    shared_process_summary: SharedProcessSummary | None = None
    shared_parameters: SharedParameters | None = None
    heat_treatment_programs: list[HeatTreatmentProgram] = Field(default_factory=list)
    characterization_methods: list[CharacterizationMethod] = Field(default_factory=list)
    global_observations: GlobalObservations | None = None
    additional_parameter_records: list[ParameterRecord] = Field(default_factory=list)
    extended_data: dict[str, Any] = Field(default_factory=dict)


class IndependentVariable(SchemaBaseModel):
    canonical_key: str | None = None
    display_name: str | None = None
    unit: str | None = None
    variable_type: str | None = None
    value_scope: str | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)


class SeriesConstants(SchemaBaseModel):
    raw_material_refs: list[str] = Field(default_factory=list)
    process_summary: str | None = None
    parameter_records: list[ParameterRecord] = Field(default_factory=list)
    heat_treatment_program_refs: list[str] = Field(default_factory=list)
    test_condition_summary: str | None = None
    extended_data: dict[str, Any] = Field(default_factory=dict)


class DataPoint(SchemaBaseModel):
    sample_id: str | None = None
    sample_label: str | None = None
    sample_role: str | None = None
    independent_variable_values: list[ParameterRecord] = Field(default_factory=list)
    process_parameters: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    qualitative_observations: list[str | dict[str, Any]] = Field(default_factory=list)
    additional_parameter_records: list[ParameterRecord] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)
    extended_data: dict[str, Any] = Field(default_factory=dict)


class ExperimentSeries(SchemaBaseModel):
    series_id: str | None = None
    series_name: str | None = None
    series_type: str | None = None
    research_question: str | None = None
    controlled_variable_keys: list[str] = Field(default_factory=list)
    independent_variables: list[IndependentVariable] = Field(default_factory=list)
    series_constants: SeriesConstants | None = None
    data_points: list[DataPoint] = Field(default_factory=list)
    relevant_source_sections: list[str] = Field(default_factory=list)
    relevant_figure_ids: list[str] = Field(default_factory=list)
    relevant_table_ids: list[str] = Field(default_factory=list)
    extended_data: dict[str, Any] = Field(default_factory=dict)


class EvidenceObject(SchemaBaseModel):
    evidence_id: str | None = None
    figure_id: str | None = None
    figure_type: str | None = None
    page: int | None = None
    caption: str | None = None
    panel_id: str | None = None
    panel_label: str | None = None
    curve_id: str | None = None
    object_id: str | None = None
    object_type: str | None = None
    object_label: str | None = None
    bbox: list[float] | None = None
    note: str | None = None
    extended_data: dict[str, Any] = Field(default_factory=dict)


class MultimodalExtraction(SchemaBaseModel):
    extraction_id: str | None = None
    source_figure_id: str | None = None
    source_panel_id: str | None = None
    extraction_type: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    evidence_refs: list[EvidenceRef | str] = Field(default_factory=list)
    extended_data: dict[str, Any] = Field(default_factory=dict)


class CrossModalLink(SchemaBaseModel):
    link_id: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    relation: str | None = None
    confidence: float | None = None
    note: str | None = None


class DataProvenance(SchemaBaseModel):
    source_pipeline: str | None = None
    extraction_time: str | None = None
    quality_flags: list[str] = Field(default_factory=list)
    normalization_log: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PaperExtractionRecord(SchemaBaseModel):
    schema_version: str = "2.0"
    paper_basic_info: PaperBasicInfo | None = None
    global_constants: GlobalConstants | None = None
    experiment_series: list[ExperimentSeries] = Field(default_factory=list)
    evidence_objects: list[EvidenceObject] = Field(default_factory=list)
    multimodal_extractions: list[MultimodalExtraction] = Field(default_factory=list)
    cross_modal_links: list[CrossModalLink] = Field(default_factory=list)
    data_provenance: DataProvenance | None = None


class PaperExtractionRecordList(RootModel[list[PaperExtractionRecord]]):
    """Convenience root model for files that store an array of records."""
