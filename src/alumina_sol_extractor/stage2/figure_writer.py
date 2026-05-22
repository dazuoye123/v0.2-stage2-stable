"""Centralized writing for stage-2 figure outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.stage2_summary import save_stage2_outputs
from alumina_sol_extractor.storage import copy_figures_for_vision
from alumina_sol_extractor.utils.jsonl import write_jsonl


def save_figure_outputs(
    figures: list[FigureInfo],
    paper_output_dir: Path,
    raw_mineru_image_count: int,
    paper_id: str | None = None,
    output_schema: dict[str, Any] | None = None,
    include_material_state_photos: bool | None = None,
    include_schematics_for_vision: bool | None = None,
    include_spinnability_photos_for_vision: bool | None = None,
) -> dict[str, Any]:
    """Write JSONL outputs, figures_for_vision, summary, and vision inputs."""
    paper_output_dir = Path(paper_output_dir)
    figures_for_vision_dir = copy_figures_for_vision(figures, paper_output_dir / "figures_for_vision")
    summary = save_stage2_outputs(
        figures=figures,
        paper_output_dir=paper_output_dir,
        raw_mineru_image_count=raw_mineru_image_count,
        include_material_state_photos=include_material_state_photos,
        include_schematics_for_vision=include_schematics_for_vision,
        include_spinnability_photos_for_vision=include_spinnability_photos_for_vision,
    )
    vision_fields = (
        (output_schema or {}).get("vision_inputs_fields")
        or [
            "paper_id",
            "figure_id",
            "subfigure_index",
            "subfigure_label",
            "image_path",
            "vision_image_path",
            "caption",
            "reference_sentences",
            "description_text",
            "figure_class",
            "resnet_raw_class",
            "clip_label",
            "clip_score",
            "clip_decision",
        ]
    )
    vision_inputs_path = paper_output_dir / "vision_inputs.jsonl"
    vision_records = []
    for figure in figures:
        if figure.is_fragment or not figure.send_to_vision_model:
            continue
        payload = figure.model_dump()
        vision_records.append({field: payload.get(field) for field in vision_fields})
    write_jsonl(vision_records, vision_inputs_path)
    if paper_id is not None:
        summary["paper_id"] = paper_id
    summary["vision_inputs_jsonl"] = str(vision_inputs_path)
    summary["figures_for_vision_dir"] = str(figures_for_vision_dir)
    summary_fields = (output_schema or {}).get("summary_fields") or []
    if summary_fields:
        summary = {field: summary.get(field) for field in summary_fields if field in summary}
        if paper_id is not None and "paper_id" not in summary:
            summary["paper_id"] = paper_id
        summary["vision_inputs_jsonl"] = str(vision_inputs_path)
    (paper_output_dir / "figure_stage2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
