"""Pydantic models for Stage 5 fused dataset outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaperRecord(BaseModel):
    paper_id: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | int | None = None
    source_file: str | None = None
    material_system: str | None = None
    process_route: str | None = None
    keywords: list[str] = Field(default_factory=list)
    abstract: str | None = None


class EvidenceRecord(BaseModel):
    evidence_id: str | None = None
    figure_id: str | None = None
    table_id: str | None = None
    evidence_type: str | None = None
    figure_type: str | None = None
    caption: str | None = None
    fact_summary: list[str] = Field(default_factory=list)
    detailed_observation: str | None = None
    source_section: str | None = None
    confidence: float | None = None


class SpectraRecord(BaseModel):
    figure_id: str | None = None
    figure_type: str | None = None
    schema_name: str | None = None
    technique: str | None = None
    extraction_mode: str | None = None
    peaks: list[dict[str, Any]] = Field(default_factory=list)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    confidence: float | None = None
    warning_codes: list[str] = Field(default_factory=list)
    quality_review_assessment: str | None = None
    conflict_warnings: list[str] = Field(default_factory=list)


class ParameterRow(BaseModel):
    parameter_id: str
    paper_id: str | None = None
    sample_id: str | None = None
    series_id: str | None = None
    canonical_key: str | None = None
    raw_name: str | None = None
    value: Any = None
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    source_scope: str | None = None
    evidence_refs: list[Any] = Field(default_factory=list)
    confidence: float | None = None
    normalization_note: str | None = None
    quality_flags: list[str] = Field(default_factory=list)


class SampleRecord(BaseModel):
    sample_id: str | None = None
    sample_name: str | None = None
    material_type: str | None = None
    process_context: str | None = None
    linked_parameters: list[str] = Field(default_factory=list)
    linked_evidence: list[str] = Field(default_factory=list)
    linked_spectra: list[str] = Field(default_factory=list)

