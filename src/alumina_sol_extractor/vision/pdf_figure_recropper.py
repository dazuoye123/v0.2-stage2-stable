"""Recrop fragmented figures from the original PDF page using MinerU bboxes."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from alumina_sol_extractor.models.figure import FigureInfo


def recrop_fragment_group_by_bbox(
    pdf_path: Path,
    page_idx: int,
    fragment_figures: list[FigureInfo],
    output_path: Path,
    margin_ratio: float = 0.02,
) -> Path:
    """Render one PDF page and crop the union bbox of all fragments."""
    if not fragment_figures:
        raise ValueError("fragment_figures is empty")
    if any(figure.page_idx != page_idx for figure in fragment_figures):
        raise ValueError("All fragments must be on the same page_idx")
    if any(not figure.bbox for figure in fragment_figures):
        raise ValueError("All fragments must have bbox")

    import fitz  # PyMuPDF, imported lazily so tests can run without PDF rendering.

    pdf_path = Path(pdf_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        page_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        boxes = [
            _bbox_to_render_pixels(figure.bbox, figure.bbox_format, pix.width, pix.height)
            for figure in fragment_figures
            if figure.bbox
        ]
        x0 = min(box[0] for box in boxes)
        y0 = min(box[1] for box in boxes)
        x1 = max(box[2] for box in boxes)
        y1 = max(box[3] for box in boxes)
        margin = int(max(x1 - x0, y1 - y0) * margin_ratio)
        crop_box = (
            max(0, int(x0 - margin)),
            max(0, int(y0 - margin)),
            min(pix.width, int(x1 + margin)),
            min(pix.height, int(y1 + margin)),
        )
        page_image.crop(crop_box).save(output_path, format="JPEG", quality=95)
    finally:
        doc.close()
    return output_path


def infer_fragment_layout_from_bboxes(fragments: list[FigureInfo]) -> str:
    """Infer spatial arrangement from MinerU bboxes."""
    boxes = [figure.bbox for figure in fragments if figure.bbox]
    if len(boxes) != len(fragments) or len(boxes) < 2:
        return "unknown"
    centers = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in boxes]
    widths = [abs(box[2] - box[0]) for box in boxes]
    heights = [abs(box[3] - box[1]) for box in boxes]
    avg_width = sum(widths) / len(widths)
    avg_height = sum(heights) / len(heights)
    x_values = [center[0] for center in centers]
    y_values = [center[1] for center in centers]
    x_clusters = _cluster_values(x_values, tolerance=max(avg_width * 0.45, 20))
    y_clusters = _cluster_values(y_values, tolerance=max(avg_height * 0.45, 20))

    if len(x_clusters) == 1 and _is_monotonic(y_values):
        return "vertical"
    if len(y_clusters) == 1 and _is_monotonic(x_values):
        return "horizontal"
    if len(x_clusters) >= 2 and len(y_clusters) >= 2:
        return "grid"
    if len(x_clusters) >= 2 or len(y_clusters) >= 2:
        return "scattered"
    return "unknown"


def _bbox_to_render_pixels(
    bbox: list[float],
    bbox_format: str | None,
    page_width: int,
    page_height: int,
) -> tuple[float, float, float, float]:
    if bbox_format == "normalized" or all(0 <= float(value) <= 1 for value in bbox):
        return (
            bbox[0] * page_width,
            bbox[1] * page_height,
            bbox[2] * page_width,
            bbox[3] * page_height,
        )
    x0, y0, x1, y1 = bbox
    max_x = max(x0, x1)
    max_y = max(y0, y1)
    scale = 1.0
    if max_x > page_width or max_y > page_height:
        scale = min(page_width / max_x if max_x else 1.0, page_height / max_y if max_y else 1.0)
    return x0 * scale, y0 * scale, x1 * scale, y1 * scale


def _cluster_values(values: list[float], tolerance: float) -> list[list[float]]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or abs(value - (sum(clusters[-1]) / len(clusters[-1]))) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return clusters


def _is_monotonic(values: list[float]) -> bool:
    return values == sorted(values) or values == sorted(values, reverse=True)
