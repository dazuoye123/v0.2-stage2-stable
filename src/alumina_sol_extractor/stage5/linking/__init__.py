"""Stage 5.5 candidate-constrained linking layer plus legacy figure matching exports."""

from .candidate_builder import build_deterministic_links, build_link_candidates, load_final_dataset_inputs
from .figure_context_matcher import FigureContextMatcher, match_figure_contexts
from .models import LinkCandidate, LinkRecord, LinkingSummary

__all__ = [
    "FigureContextMatcher",
    "LinkCandidate",
    "LinkRecord",
    "LinkingSummary",
    "build_link_candidates",
    "build_deterministic_links",
    "load_final_dataset_inputs",
    "match_figure_contexts",
]
