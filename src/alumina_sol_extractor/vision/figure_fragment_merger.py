"""Detect and merge MinerU fragmented figure images.

MinerU sometimes exports one figure as several consecutive strip images. This
module keeps the original fragments for archive, marks them as not suitable for
vision-model input, and creates one merged FigureInfo for downstream taxonomy.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

from alumina_sol_extractor.models.figure import FigureInfo


FIGURE_ID_RE = re.compile(
    r"(?P<zh>图\s*(?P<zh_num>\d+(?:[.\-]\d+)*))|"
    r"(?P<fig>\bFig\.?\s*(?P<fig_num>S?\d+(?:[.\-]\d+)*))|"
    r"(?P<figure>\bFigure\s*(?P<figure_num>S?\d+(?:[.\-]\d+)*))",
    re.IGNORECASE,
)
IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^\n]*\)")
CAPTION_START_RE = re.compile(r"^\s*(?:图\s*\d|Fig\.?\s*S?\d|Figure\s*S?\d)", re.IGNORECASE)
PANEL_LABEL_RE = re.compile(r"^[A-Za-z0-9#_\-\s/（）()：:，,;；]+$")
EXPLICIT_SUBFIGURE_RE = re.compile(
    r"(\([a-zA-Z0-9]\)|（[a-zA-Z0-9]）|\b[A-C]\b|"
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
) -> list[FigureInfo]:
    """Detect consecutive strip fragments and append merged figures.

    Original MinerU fragments remain in the returned list with
    ``is_fragment=True``. Merged figures are appended and marked with
    ``image_origin='merged_from_fragments'``.
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
        if not _should_merge_group(group, shapes):
            continue

        group_id = f"{paper_id}_fragment_group_{merge_index:03d}"
        confidence = _merge_confidence(group, shapes)
        first = group[0]
        caption = first.caption or _shared_caption(group)
        figure_id = _figure_id_from_caption(caption) or first.figure_id
        if not figure_id or figure_id.startswith("Unknown Figure"):
            figure_id = first.figure_id
        for fragment_index, figure in enumerate(group, start=1):
            figure.figure_id = figure_id
            figure.is_fragment = True
            figure.image_origin = "mineru_fragment"
            figure.fragment_group_id = group_id
            figure.fragment_index = fragment_index
            figure.fragment_merge_confidence = confidence
            figure.keep_for_archive = True
            figure.send_to_vision_model = False
            figure.keep = False
            figure.exclude_reason = "merged_fragment"
            figure.keep_reason = "merged_fragment"

        merged_path = merged_dir / f"merged_figure_{merge_index:03d}.jpg"
        _merge_images_vertically([shape.path for shape in shapes], merged_path)

        merged = FigureInfo(
            paper_id=paper_id,
            figure_id=figure_id,
            figure_id_raw=first.figure_id_raw,
            subfigure_index=None,
            subfigure_label=None,
            alt_text=first.alt_text,
            image_path=str(merged_path.resolve()),
            image_hash=_sha256_file(merged_path),
            image_origin="merged_from_fragments",
            position=first.position,
            section_title=first.section_title,
            context_before=first.context_before,
            context_after=group[-1].context_after,
            raw_caption=first.raw_caption,
            caption=caption,
            caption_source=first.caption_source,
            caption_cleaned=first.caption_cleaned,
            caption_truncation_reason=first.caption_truncation_reason,
            reference_sentences=list(first.reference_sentences),
            description_text=first.description_text,
            keep_for_archive=True,
            clip_decision="not_run",
            is_merged_figure=True,
            fragment_group_id=group_id,
            fragment_merge_confidence=confidence,
            source_fragment_ids=[_fragment_id(figure) for figure in group],
            source_fragment_paths=[figure.image_path for figure in group if figure.image_path],
            merged_image_path=str(merged_path.resolve()),
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
    if len(between) <= 80 and PANEL_LABEL_RE.fullmatch(between):
        return True
    return False


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


def _should_merge_group(group: list[FigureInfo], shapes: list[ImageShape]) -> bool:
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


def _merge_confidence(group: list[FigureInfo], shapes: list[ImageShape]) -> float:
    score = 0.45
    score += min(len(group), 6) * 0.05
    score += sum(1 for shape in shapes if shape.abnormal) / max(len(shapes), 1) * 0.3
    if _relative_span([shape.width for shape in shapes]) <= 0.12:
        score += 0.1
    if _shared_caption(group):
        score += 0.05
    return min(round(score, 3), 0.99)


def _merge_images_vertically(paths: list[Path], output_path: Path) -> None:
    images = [_trim_large_white_border(Image.open(path).convert("RGB")) for path in paths]
    max_width = max(image.width for image in images)
    total_height = sum(image.height for image in images)
    canvas = Image.new("RGB", (max_width, total_height), "white")
    y_offset = 0
    for image in images:
        x_offset = (max_width - image.width) // 2
        canvas.paste(image, (x_offset, y_offset))
        y_offset += image.height
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=95)
    for image in images:
        image.close()


def _trim_large_white_border(image: Image.Image) -> Image.Image:
    white = Image.new(image.mode, image.size, "white")
    diff = ImageChops.difference(image, white)
    bbox = diff.getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    x_margin = min(left, image.width - right)
    y_margin = min(top, image.height - bottom)
    if x_margin < 8 and y_margin < 8:
        return image
    cropped = image.crop((left, top, right, bottom))
    return ImageOps.expand(cropped, border=2, fill="white")


def _shared_caption(group: list[FigureInfo]) -> str:
    captions = [_compact_spaces(figure.caption or "") for figure in group if figure.caption]
    return captions[0] if captions and all(caption == captions[0] for caption in captions) else ""


def _figure_id_from_caption(caption: str | None) -> str | None:
    match = FIGURE_ID_RE.search(caption or "")
    if not match:
        return None
    if match.group("zh"):
        return f"图{match.group('zh_num')}"
    if match.group("fig"):
        return f"Fig.{match.group('fig_num')}"
    return f"Figure {match.group('figure_num')}"


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
