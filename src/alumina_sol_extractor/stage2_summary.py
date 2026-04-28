"""Summary helpers for second-stage figure processing."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.storage import save_figures_jsonl
from alumina_sol_extractor.vision.figure_filter import (
    SIMPLIFIED_CLASSES,
    is_false_candidate,
    is_review_candidate,
)


def save_stage2_outputs(
    figures: list[FigureInfo],
    paper_output_dir: Path,
    total_images: int,
    include_material_state_photos: bool | None = None,
    include_schematics_for_vision: bool | None = None,
    include_spinnability_photos_for_vision: bool | None = None,
) -> dict:
    """Save figures.jsonl, false candidates, and summary JSON."""
    paper_output_dir = Path(paper_output_dir)
    figures_jsonl = paper_output_dir / "figures.jsonl"
    false_candidates_jsonl = paper_output_dir / "figure_false_candidates.jsonl"
    review_candidates_jsonl = paper_output_dir / "figure_review_candidates.jsonl"
    summary_path = paper_output_dir / "figure_stage2_summary.json"

    false_candidates = [figure for figure in figures if is_false_candidate(figure)]
    review_candidates = [figure for figure in figures if is_review_candidate(figure)]
    save_figures_jsonl(figures, figures_jsonl)
    save_figures_jsonl(false_candidates, false_candidates_jsonl)
    save_figures_jsonl(review_candidates, review_candidates_jsonl)

    clip_counts = Counter(figure.clip_decision or "not_run" for figure in figures)
    class_counts = Counter(figure.figure_class for figure in figures)
    summary = {
        "total_images": total_images,
        "deduped_images": len(figures),
        "keep_for_archive_count": sum(1 for figure in figures if figure.keep_for_archive),
        "send_to_vision_model_count": sum(1 for figure in figures if figure.send_to_vision_model),
        "send_to_vision_model_false_count": sum(1 for figure in figures if not figure.send_to_vision_model),
        "clip_positive_count": clip_counts.get("positive", 0),
        "clip_negative_count": clip_counts.get("negative", 0),
        "clip_uncertain_count": clip_counts.get("uncertain", 0),
        "clip_not_run_count": clip_counts.get("not_run", 0),
        "unknown_figure_count": sum(1 for figure in figures if figure.figure_id.startswith("Unknown Figure")),
        "caption_none_count": sum(1 for figure in figures if not figure.caption),
        "pseudo_caption_count": sum(1 for figure in figures if figure.caption_source == "pseudo_caption"),
        "figure_class_counts": {name: class_counts.get(name, 0) for name in SIMPLIFIED_CLASSES},
        "false_candidate_count": len(false_candidates),
        "review_candidate_count": len(review_candidates),
        "figures_jsonl": str(figures_jsonl),
        "figure_false_candidates_jsonl": str(false_candidates_jsonl),
        "figure_review_candidates_jsonl": str(review_candidates_jsonl),
        "figures_all_dir": str(paper_output_dir / "figures_all"),
        "figures_for_vision_dir": str(paper_output_dir / "figures_for_vision"),
        "include_material_state_photos": include_material_state_photos,
        "include_schematics_for_vision": include_schematics_for_vision,
        "include_spinnability_photos_for_vision": include_spinnability_photos_for_vision,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
