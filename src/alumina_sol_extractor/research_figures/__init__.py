"""Batch-level Stage3 + Stage4 research figure generation."""

"""Legacy research-figures compatibility package.

Prefer :mod:`alumina_sol_extractor.figure_atlas` for maintained batch-level
figure generation. This package remains to avoid breaking older scripts/tests
during the entrypoint cleanup.
"""

from .batch_runner import run_research_figures

__all__ = ["run_research_figures"]
