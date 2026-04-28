"""Run one PDF through MinerU and save cleaned Markdown."""

from __future__ import annotations

import sys
import re
import json
from collections import Counter
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.pdf import MinerUPDFToMarkdown  # noqa: E402
from alumina_sol_extractor.pdf.mineru_layout_parser import load_mineru_image_layout  # noqa: E402
from alumina_sol_extractor.pdf.mineru_pdf_to_markdown import MinerUAPIError  # noqa: E402
from alumina_sol_extractor.linking import match_figure_contexts  # noqa: E402
from alumina_sol_extractor.storage import (  # noqa: E402
    copy_figures_for_vision,
    save_figures_jsonl,
)
from alumina_sol_extractor.utils.figure_utils import (  # noqa: E402
    find_figures_in_markdown_any,
)
from alumina_sol_extractor.utils.table_utils import (  # noqa: E402
    extract_tables_from_markdown,
)
from alumina_sol_extractor.vision.figure_fragment_merger import (  # noqa: E402
    detect_and_merge_fragmented_figures,
)
from alumina_sol_extractor.vision.figure_filter import (  # noqa: E402
    SIMPLIFIED_CLASSES,
    FigureFilter,
    is_false_candidate,
    is_review_candidate,
)


def load_settings(settings_path: Path) -> dict:
    """Load the YAML settings file."""
    if not settings_path.exists():
        raise FileNotFoundError(f"settings.yaml not found: {settings_path}")
    return yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}


def resolve_project_path(path_value: str | Path) -> Path:
    """Resolve paths in settings.yaml relative to the project root."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main() -> None:
    settings = load_settings(PROJECT_ROOT / "settings.yaml")
    paths = settings.get("paths", {})
    mineru = settings.get("mineru", {})
    chemistry = settings.get("chemistry_normalization", {})
    figure_settings = settings.get("figures", {})

    input_pdf = resolve_project_path(paths.get("input_pdf", "data/pdfs/example.pdf"))
    if not input_pdf.exists():
        print(f"Input PDF not found: {input_pdf}")
        print("Put a test PDF at data/pdfs/example.pdf or edit settings.yaml.")
        raise SystemExit(1)

    paper_id = input_pdf.stem
    markdown_output_dir = resolve_project_path(
        paths.get("markdown_output_dir", "data/markdown")
    )
    output_md = markdown_output_dir / f"{paper_id}.md"

    try:
        converter = MinerUPDFToMarkdown(
            project_root=PROJECT_ROOT,
            mineru_raw_dir=paths.get("mineru_raw_dir", "data/mineru_raw"),
            markdown_output_dir=paths.get("markdown_output_dir", "data/markdown"),
            output_dir=paths.get("output_dir", "data/outputs"),
            api_key_env=mineru.get("api_key_env", "MINERU_API_KEY"),
            base_url_env=mineru.get("base_url_env", "MINERU_BASE_URL"),
            poll_interval_seconds=mineru.get("poll_interval_seconds", 3),
            max_wait_seconds=mineru.get("max_wait_seconds", 600),
            save_raw=mineru.get("save_raw", True),
            save_cleaned=mineru.get("save_cleaned", True),
            chemistry_enabled=chemistry.get("enabled", True),
            unicode_subscript=chemistry.get("unicode_subscript", False),
        )
        cleaned_md = converter.convert_file(input_pdf=input_pdf, output_md=output_md)
    except MinerUAPIError as exc:
        print(f"MinerU conversion failed: {exc}")
        raise SystemExit(2) from exc

    table_markdown = cleaned_md.read_text(encoding="utf-8")
    table_processed_markdown, tables = extract_tables_from_markdown(
        markdown=table_markdown,
        project_root=PROJECT_ROOT,
        paper_id=paper_id,
    )
    cleaned_md.write_text(table_processed_markdown, encoding="utf-8")
    tables_dir = PROJECT_ROOT / "data" / "outputs" / paper_id / "tables"

    final_markdown = cleaned_md.read_text(encoding="utf-8")
    raw_mineru_image_count = len(re.findall(r"!\[[^\]]*\]\([^\n]*\)", final_markdown))
    mineru_raw_dir = resolve_project_path(paths.get("mineru_raw_dir", "data/mineru_raw")) / paper_id
    mineru_layout = load_mineru_image_layout(mineru_raw_dir)
    figures = find_figures_in_markdown_any(
        markdown_text=final_markdown,
        markdown_path=cleaned_md,
        project_root=PROJECT_ROOT,
        paper_id=paper_id,
        mineru_layout=mineru_layout,
    )
    figures = match_figure_contexts(final_markdown, figures)
    output_dir = PROJECT_ROOT / "data" / "outputs" / paper_id
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

    classifier = None
    classifier_error = None
    try:
        from alumina_sol_extractor.vision.resnet_classifier import FigureClassifier

        classifier = FigureClassifier()
    except Exception as exc:
        classifier_error = exc
        print(f"ResNet classifier unavailable; using keyword filtering only. {exc}")

    if classifier is not None:
        for figure in figures:
            try:
                figure.resnet_raw_class = classifier.predict(figure)
            except Exception as exc:
                figure.resnet_raw_class = None
                if figure.keep_reason:
                    figure.keep_reason += f"; classification failed: {exc}"
                else:
                    figure.keep_reason = f"classification failed: {exc}"

    clip_prefilter = None
    clip_error = None
    try:
        from alumina_sol_extractor.vision.clip_prefilter import CLIPPrefilter

        clip_prefilter = CLIPPrefilter()
    except Exception as exc:
        clip_error = exc
        print(f"CLIP prefilter unavailable; continuing without CLIP. {exc}")

    if clip_prefilter is not None:
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

    figures = FigureFilter(
        include_material_state_photos=figure_settings.get(
            "include_material_state_photos", True
        ),
        include_schematics_for_vision=figure_settings.get(
            "include_schematics_for_vision", False
        ),
        include_spinnability_photos_for_vision=figure_settings.get(
            "include_spinnability_photos_for_vision", True
        ),
    ).apply(figures)
    figures_jsonl = output_dir / "figures.jsonl"
    figures_all_dir = output_dir / "figures_all"
    figures_for_vision_dir = output_dir / "figures_for_vision"
    copy_figures_for_vision(figures, figures_for_vision_dir)
    save_figures_jsonl(figures, figures_jsonl)
    false_candidates = [figure for figure in figures if is_false_candidate(figure)]
    false_candidates_jsonl = output_dir / "figure_false_candidates.jsonl"
    save_figures_jsonl(false_candidates, false_candidates_jsonl)
    review_candidates = [figure for figure in figures if is_review_candidate(figure)]
    review_candidates_jsonl = output_dir / "figure_review_candidates.jsonl"
    save_figures_jsonl(review_candidates, review_candidates_jsonl)
    archive_count = sum(1 for figure in figures if figure.keep_for_archive)
    vision_count = sum(1 for figure in figures if figure.send_to_vision_model)
    vision_false_count = len(figures) - vision_count
    logo_or_front_matter_count = sum(
        1
        for figure in figures
        if figure.figure_class == "logo_or_icon"
        or figure.exclude_reason == "unknown_without_caption"
    )
    unknown_figure_count = sum(
        1 for figure in figures if figure.figure_id.startswith("Unknown Figure")
    )
    caption_none_count = sum(1 for figure in figures if not figure.caption)
    pseudo_caption_count = sum(1 for figure in figures if figure.caption_source == "pseudo_caption")
    fragment_count = sum(1 for figure in figures if figure.is_fragment)
    merged_figure_count = sum(1 for figure in figures if figure.is_merged_figure)
    bbox_attached_count = sum(1 for figure in figures if figure.bbox)
    bbox_missing_count = sum(1 for figure in figures if not figure.bbox)
    bbox_stitched_figure_count = sum(1 for figure in figures if figure.image_origin == "stitched_from_bbox_fragments")
    merge_mode_counts = Counter(figure.merge_mode or "none" for figure in figures)
    clip_counts = Counter(figure.clip_decision or "not_run" for figure in figures)
    class_counts = {
        name: sum(1 for figure in figures if figure.figure_class == name)
        for name in SIMPLIFIED_CLASSES
    }
    summary = {
        "paper_id": paper_id,
        "raw_mineru_image_count": raw_mineru_image_count,
        "final_figure_record_count": len(figures),
        "total_images": raw_mineru_image_count,
        "deduped_images": len(figures),
        "keep_for_archive_count": archive_count,
        "send_to_vision_model_count": vision_count,
        "send_to_vision_model_false_count": vision_false_count,
        "clip_positive_count": clip_counts.get("positive", 0),
        "clip_negative_count": clip_counts.get("negative", 0),
        "clip_uncertain_count": clip_counts.get("uncertain", 0),
        "clip_not_run_count": clip_counts.get("not_run", 0),
        "unknown_figure_count": unknown_figure_count,
        "caption_none_count": caption_none_count,
        "pseudo_caption_count": pseudo_caption_count,
        "fragment_count": fragment_count,
        "fragment_group_count": len({figure.fragment_group_id for figure in figures if figure.fragment_group_id}),
        "fragment_image_count": fragment_count,
        "merged_figure_count": merged_figure_count,
        "bbox_attached_count": bbox_attached_count,
        "bbox_missing_count": bbox_missing_count,
        "bbox_stitched_figure_count": bbox_stitched_figure_count,
        "merge_mode_counts": dict(sorted(merge_mode_counts.items())),
        "figure_class_counts": class_counts,
        "false_candidate_count": len(false_candidates),
        "review_candidate_count": len(review_candidates),
        "figures_jsonl": str(figures_jsonl),
        "figure_false_candidates_jsonl": str(false_candidates_jsonl),
        "figure_review_candidates_jsonl": str(review_candidates_jsonl),
        "figures_all_dir": str(figures_all_dir),
        "figures_for_vision_dir": str(figures_for_vision_dir),
        "figures_merged_dir": str(output_dir / "figures_merged"),
        "include_material_state_photos": figure_settings.get("include_material_state_photos", True),
        "include_schematics_for_vision": figure_settings.get("include_schematics_for_vision", False),
        "include_spinnability_photos_for_vision": figure_settings.get("include_spinnability_photos_for_vision", True),
    }
    summary_path = output_dir / "figure_stage2_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("MinerU PDF to Markdown finished.")
    print(f"cleaned_markdown: {cleaned_md}")
    print(f"tables_dir: {tables_dir}")
    print(f"tables_count: {len(tables)}")
    print(f"raw_mineru_image_count: {raw_mineru_image_count}")
    print(f"final_figure_record_count: {len(figures)}")
    print(f"keep_for_archive_count: {archive_count}")
    print(f"send_to_vision_model_count: {vision_count}")
    print(f"send_to_vision_model_false_count: {vision_false_count}")
    print(f"logo_or_front_matter_count: {logo_or_front_matter_count}")
    print(f"unknown_figure_count: {unknown_figure_count}")
    print(f"caption_none_count: {caption_none_count}")
    print(f"pseudo_caption_count: {pseudo_caption_count}")
    print(f"fragment_count: {fragment_count}")
    print(f"fragment_group_count: {len({figure.fragment_group_id for figure in figures if figure.fragment_group_id})}")
    print(f"fragment_image_count: {fragment_count}")
    print(f"merged_figure_count: {merged_figure_count}")
    print(f"bbox_attached_count: {bbox_attached_count}")
    print(f"bbox_missing_count: {bbox_missing_count}")
    print(f"bbox_stitched_figure_count: {bbox_stitched_figure_count}")
    print("clip_decision_counts:")
    for clip_decision, count in sorted(clip_counts.items()):
        print(f"  {clip_decision}: {count}")
    print("figure_class_counts:")
    for class_name, count in class_counts.items():
        print(f"  {class_name}: {count}")
    print(f"false_candidate_count: {len(false_candidates)}")
    print(f"review_candidate_count: {len(review_candidates)}")
    print(f"figures_jsonl: {figures_jsonl}")
    print(f"figure_false_candidates_jsonl: {false_candidates_jsonl}")
    print(f"figure_review_candidates_jsonl: {review_candidates_jsonl}")
    print(f"figure_stage2_summary: {summary_path}")
    print(f"figures_all_dir: {figures_all_dir}")
    print(f"figures_for_vision_dir: {figures_for_vision_dir}")
    if classifier_error is not None:
        print("figure_classifier: unavailable")
    if clip_error is not None:
        print("clip_prefilter: unavailable")
    for key, value in converter.last_outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
