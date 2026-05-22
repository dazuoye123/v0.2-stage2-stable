"""Pydantic models for Stage 5.5 linking."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LinkCandidate(BaseModel):
    candidate_id: str
    paper_id: str | None = None
    source_type: str
    source_id: str
    source_text: str | None = None
    source_value: float | int | str | None = None
    source_unit: str | None = None
    source_figure_id: str | None = None
    target_type: str
    target_id: str
    target_text: str | None = None
    target_value: float | int | str | None = None
    target_unit: str | None = None
    target_figure_id: str | None = None
    candidate_reason: str | None = None
    deterministic_score: float = 0.0
    needs_llm: bool = False
    candidate_status: str = "candidate"


class LinkRecord(BaseModel):
    link_id: str
    paper_id: str | None = None
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    link_type: str
    confidence: str
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reasoning: str | None = None
    evidence_text: str | None = None
    validation_status: str = "accepted"
    validation_warnings: list[str] = Field(default_factory=list)
    created_by: str = "deterministic"


class LinkingSummary(BaseModel):
    total_candidates: int = 0
    deterministic_links: int = 0
    llm_reviewed_candidates: int = 0
    accepted_links: int = 0
    rejected_links: int = 0
    unmatched_candidates: int = 0
    invalid_source_id_count: int = 0
    invalid_target_id_count: int = 0
    by_link_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    warning_count: int = 0
