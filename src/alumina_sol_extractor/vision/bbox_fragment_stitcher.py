"""Stitch MinerU image fragments back together with bbox coordinates."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from alumina_sol_extractor.models.figure import FigureInfo


def stitch_fragments_by_bbox(
    fragment_figures: list[FigureInfo],
    output_path: Path,
    background_color: tuple[int, int, int] = (255, 255, 255),
    margin: int = 10,
) -> Path:
    """Paste fragment images onto a canvas according to MinerU pixel bboxes."""
    _validate_fragments(fragment_figures)
    boxes = [figure.bbox for figure in fragment_figures if figure.bbox]
    union_x0 = min(box[0] for box in boxes)
    union_y0 = min(box[1] for box in boxes)
    union_x1 = max(box[2] for box in boxes)
    union_y1 = max(box[3] for box in boxes)
    canvas_width = max(1, int(round(union_x1 - union_x0 + 2 * margin)))
    canvas_height = max(1, int(round(union_y1 - union_y0 + 2 * margin)))
    canvas = Image.new("RGB", (canvas_width, canvas_height), background_color)

    for figure in sorted(fragment_figures, key=lambda item: (item.bbox[1], item.bbox[0])):
        x0, y0, x1, y1 = figure.bbox
        bbox_width = max(1, int(round(x1 - x0)))
        bbox_height = max(1, int(round(y1 - y0)))
        paste_x = int(round(x0 - union_x0 + margin))
        paste_y = int(round(y0 - union_y0 + margin))
        with Image.open(figure.image_path) as image:
            resized = image.convert("RGB").resize((bbox_width, bbox_height), Image.Resampling.LANCZOS)
            canvas.paste(resized, (paste_x, paste_y))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=95)
    return output_path


def bbox_overlap_ratio(fragment_figures: list[FigureInfo]) -> float:
    """Return max pairwise overlap ratio relative to the smaller bbox."""
    boxes = [figure.bbox for figure in fragment_figures if figure.bbox]
    max_ratio = 0.0
    for index, box_a in enumerate(boxes):
        for box_b in boxes[index + 1 :]:
            intersection = _intersection_area(box_a, box_b)
            if intersection <= 0:
                continue
            smaller = min(_area(box_a), _area(box_b))
            if smaller > 0:
                max_ratio = max(max_ratio, intersection / smaller)
    return max_ratio


def canvas_blank_ratio(image_path: Path, background_color: tuple[int, int, int] = (255, 255, 255)) -> float:
    """Estimate blank ratio by counting pixels very close to the background."""
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        pixels = rgb.getdata()
        total = rgb.width * rgb.height
        if total == 0:
            return 1.0
        blank = 0
        br, bg, bb = background_color
        for red, green, blue in pixels:
            if abs(red - br) <= 6 and abs(green - bg) <= 6 and abs(blue - bb) <= 6:
                blank += 1
        return blank / total


def _validate_fragments(fragment_figures: list[FigureInfo]) -> None:
    if not fragment_figures:
        raise ValueError("fragment_figures is empty")
    page_indices = {figure.page_idx for figure in fragment_figures}
    if None in page_indices:
        raise ValueError("fragment missing page_idx")
    if len(page_indices) != 1:
        raise ValueError("fragments_not_on_same_page")
    for figure in fragment_figures:
        if not figure.image_path:
            raise ValueError("fragment missing image_path")
        if not Path(figure.image_path).exists():
            raise ValueError(f"fragment image not found: {figure.image_path}")
        if not figure.bbox or len(figure.bbox) != 4:
            raise ValueError("fragment missing bbox")


def _area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(box_a: list[float], box_b: list[float]) -> float:
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)
