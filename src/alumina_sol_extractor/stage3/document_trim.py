"""Backward-compatible Stage 3 wrapper for markdown body trimming."""

from alumina_sol_extractor.markdown_processing.body_trim import (
    TrimResult,
    generate_cleaned_body_markdown,
    trim_markdown_body,
)

__all__ = ["TrimResult", "generate_cleaned_body_markdown", "trim_markdown_body"]
