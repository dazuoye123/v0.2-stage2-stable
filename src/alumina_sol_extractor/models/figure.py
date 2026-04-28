"""Figure metadata model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FigureInfo(BaseModel):
    paper_id: str
    figure_id: str = "Unknown Figure"
    figure_id_raw: str | None = None

    # Multiple images can share one caption, for example Fig.6 with A/B/C panels.
    subfigure_index: int | None = None
    subfigure_label: str | None = None

    alt_text: str = ""
    image_path: str | None = None
    vision_image_path: str | None = None
    image_url: str | None = None
    base64_data: str | None = None
    image_hash: str | None = None

    position: int = 0
    section_title: str | None = None

    # Raw trace context, useful for debugging.
    context_before: str = ""
    context_after: str = ""

    # Text intended for later vision-language model prompting.
    raw_caption: str | None = None
    caption: str | None = None
    caption_source: str | None = None
    caption_cleaned: bool = False
    caption_truncation_reason: str | None = None
    reference_sentences: list[str] = Field(default_factory=list)
    description_text: str | None = None

    # Original 28-way ResNet output.
    resnet_raw_class: str | None = None

    # Optional CLIP semantic prefilter result.
    clip_label: str | None = None
    clip_score: float | None = None
    clip_decision: str = "not_run"

    # Simplified scientific figure class.
    figure_class: str = "other"

    keyword_hits: list[str] = Field(default_factory=list)
    keep: bool = False
    keep_reason: str | None = None
    maybe_useful: bool = False
    keep_for_archive: bool = True
    send_to_vision_model: bool = False
    exclude_reason: str | None = None
    review_reason: str | None = None
