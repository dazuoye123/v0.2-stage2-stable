"""Detect MinerU fragmented images and stitch them using MinerU bboxes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from alumina_sol_extractor.figures.figure_id import find_figure_id_pair
from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.bbox_fragment_stitcher import (
    bbox_overlap_ratio,
    canvas_blank_ratio,
    stitch_fragments_by_bbox,
)
IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^\n]*\)")
CAPTION_START_RE = re.compile(r"^\s*(?:\u56fe\s*\d|Fig\.?\s*S?\d|Figure\s*S?\d)", re.IGNORECASE)
PANEL_LABEL_RE = re.compile(r"^[A-Za-z0-9#_\-\s/+\u3000\uff08\uff09()：:，,;；]+$")
EXPLICIT_SUBFIGURE_RE = re.compile(
    r"(\([a-zA-Z0-9]\)|\uff08[a-zA-Z0-9]\uff09|\b[A-C]\b|"
    r"low magnification|high magnification|before|after|sample\s*\d+)",
    re.IGNORECASE,
)


@dataclass
class ImageShape:
    path: Path
    width: int
    height: int
    ratio: float
    abnormal: bool


def detect_and_merge_fragmented_figures(
    figures: list[FigureInfo],
    markdown_text: str,
    output_dir: Path,
    paper_id: str,
    pdf_path: Path | None = None,
) -> list[FigureInfo]:
    """Detect likely MinerU fragments and append bbox-stitched figures.

    ``pdf_path`` is accepted for backward compatibility but intentionally not
    used. This implementation never crops the original PDF and never stitches by
    Markdown order.
    """
    output_dir = Path(output_dir)
    merged_dir = output_dir / "figures_merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    sorted_figures = sorted(figures, key=lambda figure: figure.position)
    groups = _candidate_groups(sorted_figures, markdown_text)
    merged_figures: list[FigureInfo] = []
    merge_index = 1

    for group in groups:
        shapes = _load_group_shapes(group)
        if len(group) == 1:
            if shapes and shapes[0].abnormal:
                group[0].review_reason = group[0].review_reason or "possible_fragment_single_image"
            continue
        if not _should_consider_fragment_group(group, shapes):
            continue

        if not _all_have_bbox(group):
            _mark_review(group, "bbox_missing_for_fragment_group")
            continue
        if len({figure.page_idx for figure in group}) != 1:
            _mark_review(group, "fragments_not_on_same_page")
            continue
        if bbox_overlap_ratio(group) > 0.35:
            _mark_review(group, "bbox_overlap_abnormal")
            continue

        group_id = f"{paper_id}_fragment_group_{merge_index:03d}"
        confidence = _merge_confidence(group, shapes)
        first = group[0]
        caption = first.caption or _shared_caption(group)
        figure_id = _figure_id_from_caption(caption) or first.figure_id
        if not figure_id or figure_id.startswith("Unknown Figure"):
            figure_id = first.figure_id

        stitched_path = merged_dir / f"stitched_figure_{merge_index:03d}.jpg"
        try:
            stitch_fragments_by_bbox(group, stitched_path)
        except Exception as exc:
            _mark_review(group, f"stitched_image_abnormal: {exc}")
            continue
        if _stitched_image_is_abnormal(stitched_path):
            _mark_review(group, "stitched_image_abnormal")
            continue
        if canvas_blank_ratio(stitched_path) > 0.96:
            _mark_review(group, "stitched_image_too_sparse")
            continue

        for fragment_index, figure in enumerate(sorted(group, key=lambda item: (item.bbox[1], item.bbox[0])), start=1):
            figure.figure_id = figure_id
            figure.is_fragment = True
            figure.image_origin = "mineru_fragment"
            figure.fragment_group_id = group_id
            figure.fragment_index = fragment_index
            figure.fragment_merge_confidence = confidence
            figure.keep_for_archive = True
            figure.send_to_vision_model = False
            figure.keep = False
            figure.exclude_reason = "replaced_by_bbox_stitched_figure"
            figure.keep_reason = figure.exclude_reason

        merged = FigureInfo(
            paper_id=paper_id,
            figure_id=figure_id,
            figure_id_raw=first.figure_id_raw,
            alt_text=first.alt_text,
            image_path=str(stitched_path.resolve()),
            image_hash=_sha256_file(stitched_path),
            image_origin="stitched_from_bbox_fragments",
            position=first.position,
            section_title=first.section_title,
            page_idx=first.page_idx,
            page_number=first.page_number,
            bbox=_union_bbox(group),
            bbox_format="pixel",
            bbox_source=first.bbox_source,
            context_before=first.context_before,
            context_after=group[-1].context_after,
            raw_caption=first.raw_caption,
            caption=caption,
            caption_source=first.caption_source,
            caption_cleaned=first.caption_cleaned,
            caption_truncation_reason=first.caption_truncation_reason,
            reference_sentences=[],
            description_text=None,
            keep_for_archive=True,
            clip_decision="not_run",
            is_merged_figure=True,
            fragment_group_id=group_id,
            fragment_merge_confidence=confidence,
            source_fragment_ids=[_fragment_id(figure) for figure in group],
            source_fragment_paths=[figure.image_path for figure in group if figure.image_path],
            merged_image_path=str(stitched_path.resolve()),
            merge_mode="bbox_grid_stitch",
        )
        merged_figures.append(merged)
        merge_index += 1

    return sorted(figures + merged_figures, key=lambda figure: (figure.position, figure.is_merged_figure))


def _candidate_groups(figures: list[FigureInfo], markdown_text: str) -> list[list[FigureInfo]]:
    groups: list[list[FigureInfo]] = []
    current: list[FigureInfo] = []
    for figure in figures:
        if not figure.image_path or figure.is_fragment or figure.is_merged_figure:
            if current:
                groups.append(current)
                current = []
            continue
        if not current:
            current = [figure]
            continue
        previous = current[-1]
        if _can_be_same_fragment_group(previous, figure, markdown_text):
            current.append(figure)
        else:
            groups.append(current)
            current = [figure]
    if current:
        groups.append(current)
    return groups


def _can_be_same_fragment_group(previous: FigureInfo, current: FigureInfo, markdown_text: str) -> bool:
    if _shared_caption([previous]) != _shared_caption([current]):
        return False
    if not previous.caption:
        return False
    between = markdown_text[previous.position : current.position]
    between = IMAGE_MARKDOWN_RE.sub("", between)
    between = _compact_spaces(between)
    if not between:
        return True
    if CAPTION_START_RE.search(between):
        return False
    return len(between) <= 80 and bool(PANEL_LABEL_RE.fullmatch(between))


def _load_group_shapes(group: list[FigureInfo]) -> list[ImageShape]:
    shapes: list[ImageShape] = []
    for figure in group:
        if not figure.image_path:
            continue
        path = Path(figure.image_path)
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            continue
        ratio = width / max(height, 1)
        abnormal = ratio > 3.0 or height < 180
        shapes.append(ImageShape(path=path, width=width, height=height, ratio=ratio, abnormal=abnormal))
    return shapes


def _should_consider_fragment_group(group: list[FigureInfo], shapes: list[ImageShape]) -> bool:
    if len(group) < 3 or len(shapes) != len(group):
        return False
    abnormal_count = sum(1 for shape in shapes if shape.abnormal)
    has_strip_pattern = abnormal_count >= max(2, len(shapes) // 2)
    widths_close = _relative_span([shape.width for shape in shapes]) <= 0.12
    heights_close = _relative_span([shape.height for shape in shapes]) <= 0.35
    all_complete_panels = all(0.45 <= shape.ratio <= 2.5 and shape.height >= 180 for shape in shapes)
    caption = _shared_caption(group)
    explicit_subfigures = bool(EXPLICIT_SUBFIGURE_RE.search(caption))
    if explicit_subfigures and all_complete_panels:
        return False
    return has_strip_pattern or (len(group) >= 4 and widths_close and heights_close and max(shape.height for shape in shapes) < 260)


def _all_have_bbox(group: list[FigureInfo]) -> bool:
    return all(figure.page_idx is not None and figure.bbox and len(figure.bbox) == 4 for figure in group)


def _union_bbox(group: list[FigureInfo]) -> list[float] | None:
    boxes = [figure.bbox for figure in group if figure.bbox]
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _merge_confidence(group: list[FigureInfo], shapes: list[ImageShape]) -> float:
    score = 0.45
    score += min(len(group), 6) * 0.05
    score += sum(1 for shape in shapes if shape.abnormal) / max(len(shapes), 1) * 0.3
    if _relative_span([shape.width for shape in shapes]) <= 0.12:
        score += 0.1
    if _shared_caption(group):
        score += 0.05
    return min(round(score, 3), 0.99)


def _mark_review(group: list[FigureInfo], reason: str) -> None:
    for figure in group:
        figure.review_reason = figure.review_reason or reason


def _stitched_image_is_abnormal(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            return image.width < 20 or image.height < 20
    except Exception:
        return True


def _shared_caption(group: list[FigureInfo]) -> str:
    captions = [_compact_spaces(figure.caption or "") for figure in group if figure.caption]
    return captions[0] if captions and all(caption == captions[0] for caption in captions) else ""


def _figure_id_from_caption(caption: str | None) -> str | None:
    _, figure_id = find_figure_id_pair(caption or "")
    return figure_id


def _relative_span(values: list[int]) -> float:
    if not values:
        return 1.0
    max_value = max(values)
    if max_value == 0:
        return 0.0
    return (max_value - min(values)) / max_value


def _fragment_id(figure: FigureInfo) -> str:
    if figure.image_hash:
        return figure.image_hash
    return f"{figure.figure_id}:{figure.position}"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compact_spaces(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
