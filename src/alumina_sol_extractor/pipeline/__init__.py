"""Pipeline entry points used by ``main.py``."""

from .stage1_pdf_to_markdown import Stage1Result, run_stage1_pdf_to_markdown
from .stage2_figure_pipeline import Stage2Result, run_stage2_figure_pipeline
from .stage3_dspy_pipeline import Stage3Result, run_stage3_dspy_pipeline

__all__ = [
    "Stage1Result",
    "Stage2Result",
    "Stage3Result",
    "run_stage1_pdf_to_markdown",
    "run_stage2_figure_pipeline",
    "run_stage3_dspy_pipeline",
]
