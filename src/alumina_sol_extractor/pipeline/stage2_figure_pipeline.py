"""Stage 2: tables + figures + classification + outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config import resolve_project_path
from alumina_sol_extractor.figures.figure_writer import save_figure_outputs
from alumina_sol_extractor.linking import match_figure_contexts
from alumina_sol_extractor.pdf.mineru_layout_parser import load_mineru_image_layout
from alumina_sol_extractor.utils.figure_utils import find_figures_in_markdown_any
from alumina_sol_extractor.utils.table_utils import extract_tables_from_markdown
from alumina_sol_extractor.vision.figure_filter import FigureFilter
from alumina_sol_extractor.vision.figure_fragment_merger import detect_and_merge_fragmented_figures


@dataclass(slots=True)
class Stage2Result:
    """Outputs produced by stage 2."""

    cleaned_markdown_path: Path
    output_dir: Path
    tables_dir: Path
    tables_count: int
    raw_mineru_image_count: int
    summary: dict[str, Any] = field(default_factory=dict)


def run_stage2_figure_pipeline(
    project_root: Path,
    settings: dict[str, Any],
    input_pdf: Path,
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
) -> Stage2Result:
    """Run table extraction and figure processing without changing behavior."""
    project_root = Path(project_root)
    output_dir = Path(output_dir)
    paths = settings.get("paths", {})
    figure_settings = settings.get("figures", {})
    output_schema = settings.get("outputs", {})

    table_markdown = cleaned_markdown_path.read_text(encoding="utf-8")
    table_processed_markdown, tables = extract_tables_from_markdown(
        markdown=table_markdown,
        project_root=project_root,
        paper_id=paper_id,
    )
    cleaned_markdown_path.write_text(table_processed_markdown, encoding="utf-8")
    final_markdown = cleaned_markdown_path.read_text(encoding="utf-8")
    raw_mineru_image_count = len(re.findall(r"!\[[^\]]*\]\([^\n]*\)", final_markdown))

    mineru_raw_dir = resolve_project_path(project_root, paths.get("mineru_raw_dir", "data/mineru_raw")) / paper_id
    mineru_layout = load_mineru_image_layout(mineru_raw_dir)
    figures = find_figures_in_markdown_any(
        markdown_text=final_markdown,
        markdown_path=cleaned_markdown_path,
        project_root=project_root,
        paper_id=paper_id,
        mineru_layout=mineru_layout,
    )
    figures = match_figure_contexts(final_markdown, figures)

    if figure_settings.get("enable_bbox_fragment_stitch", True):
        figures = detect_and_merge_fragmented_figures(
            figures=figures,
            markdown_text=final_markdown,
            output_dir=output_dir,
            paper_id=paper_id,
        )
        stitched_figures = [figure for figure in figures if figure.is_merged_figure]
        if stitched_figures:
            for figure in stitched_figures:
                figure.reference_sentences = []
                figure.description_text = None
            match_figure_contexts(final_markdown, stitched_figures)

    classifier_error = _run_resnet_if_enabled(figures, figure_settings)
    clip_error = _run_clip_if_enabled(figures, figure_settings)

    figures = FigureFilter(
        include_material_state_photos=figure_settings.get("include_material_state_photos", True),
        include_schematics_for_vision=figure_settings.get("include_schematics_for_vision", False),
        include_spinnability_photos_for_vision=figure_settings.get("include_spinnability_photos_for_vision", True),
    ).apply(figures)

    summary = save_figure_outputs(
        figures=figures,
        paper_output_dir=output_dir,
        raw_mineru_image_count=raw_mineru_image_count,
        paper_id=paper_id,
        output_schema=output_schema,
        include_material_state_photos=figure_settings.get("include_material_state_photos", True),
        include_schematics_for_vision=figure_settings.get("include_schematics_for_vision", False),
        include_spinnability_photos_for_vision=figure_settings.get("include_spinnability_photos_for_vision", True),
    )
    if classifier_error is not None:
        summary["figure_classifier"] = "unavailable"
    if clip_error is not None:
        summary["clip_prefilter"] = "unavailable"
    summary_path = output_dir / "figure_stage2_summary.json"
    summary_path.write_text(__import__("json").dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return Stage2Result(
        cleaned_markdown_path=cleaned_markdown_path,
        output_dir=output_dir,
        tables_dir=output_dir / "tables",
        tables_count=len(tables),
        raw_mineru_image_count=raw_mineru_image_count,
        summary=summary,
    )


def _run_resnet_if_enabled(figures: list, figure_settings: dict[str, Any]) -> Exception | None:
    if not figure_settings.get("run_resnet", True):
        return None
    try:
        from alumina_sol_extractor.vision.resnet_classifier import FigureClassifier

        classifier = FigureClassifier()
    except Exception as exc:
        return exc
    for figure in figures:
        try:
            figure.resnet_raw_class = classifier.predict(figure)
        except Exception as exc:
            figure.resnet_raw_class = None
            figure.keep_reason = (
                f"{figure.keep_reason}; classification failed: {exc}"
                if figure.keep_reason
                else f"classification failed: {exc}"
            )
    return None


def _run_clip_if_enabled(figures: list, figure_settings: dict[str, Any]) -> Exception | None:
    if not figure_settings.get("run_clip", True):
        return None
    try:
        from alumina_sol_extractor.vision.clip_prefilter import CLIPPrefilter

        clip_prefilter = CLIPPrefilter()
    except Exception as exc:
        return exc
    for figure in figures:
        try:
            result = clip_prefilter.predict(figure)
            figure.clip_label = result.clip_label
            figure.clip_score = result.clip_score
            figure.clip_decision = result.clip_decision
        except Exception:
            figure.clip_label = None
            figure.clip_score = None
            figure.clip_decision = "not_run"
    return None
