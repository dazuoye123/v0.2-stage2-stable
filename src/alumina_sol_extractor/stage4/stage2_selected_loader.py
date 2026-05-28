"""Load Stage2-selected figures for Stage4A without secondary re-filtering."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .io import read_jsonl


def load_stage2_selected_figures(paper_dir: Path) -> list[dict[str, Any]]:
    paper_dir = Path(paper_dir)
    figures_jsonl = paper_dir / "figures.jsonl"
    if figures_jsonl.exists():
        return _load_from_figures_jsonl(figures_jsonl, paper_dir)
    return _load_from_figures_for_vision_dir(paper_dir)


def _load_from_figures_jsonl(figures_jsonl: Path, paper_dir: Path) -> list[dict[str, Any]]:
    records = read_jsonl(figures_jsonl)
    selected: list[dict[str, Any]] = []
    for record in records:
        normalized = _normalize_stage2_selected_record(record, paper_dir, selection_source="figures_jsonl")
        if normalized is None:
            continue
        if not _record_is_stage2_selected(record, normalized, paper_dir):
            continue
        selected.append(normalized)
    return selected


def _load_from_figures_for_vision_dir(paper_dir: Path) -> list[dict[str, Any]]:
    figures_dir = paper_dir / "figures_for_vision"
    if not figures_dir.exists() or not figures_dir.is_dir():
        return []
    selected: list[dict[str, Any]] = []
    for image_path in sorted(figures_dir.iterdir()):
        if image_path.is_dir():
            continue
        selected.append(
            {
                "figure_id": _stable_fallback_figure_id(image_path),
                "image_path": str(image_path),
                "vision_image_path": str(image_path),
                "source_image_path": str(image_path),
                "caption": None,
                "stage2_figure_class": "unknown",
                "stage2_predicted_figure_type": None,
                "figure_label": None,
                "page_number": None,
                "subfigure_id": None,
                "reference_sentences": [],
                "context_before": None,
                "context_after": None,
                "nearby_text": None,
                "related_text": None,
                "ocr_text": None,
                "context_text": None,
                "description_text": None,
                "source_file": None,
                "source_pdf": None,
                "loader_warnings": ["figures_jsonl_missing_fallback_to_directory"],
                "selection_source": "figures_for_vision_directory",
                "send_to_vision_model": True,
                "keep": True,
            }
        )
    return selected


def _normalize_stage2_selected_record(
    record: dict[str, Any],
    paper_dir: Path,
    *,
    selection_source: str,
) -> dict[str, Any] | None:
    figure_id = str(record.get("figure_id") or "").strip() or None
    vision_image_path = _resolve_path(record.get("vision_image_path"), paper_dir)
    image_path = _resolve_path(record.get("image_path"), paper_dir)
    source_image_path = vision_image_path or image_path
    if not figure_id:
        fallback_source = source_image_path or record.get("figure_label") or record.get("caption") or record.get("image_path")
        figure_id = _stable_fallback_figure_id(fallback_source)

    reference_sentences = record.get("reference_sentences") or []
    if isinstance(reference_sentences, str):
        reference_sentences = [reference_sentences]
    elif not isinstance(reference_sentences, list):
        reference_sentences = []

    context_text = _first_text(
        record.get("context_text"),
        record.get("description_text"),
        record.get("ocr_text"),
        record.get("related_text"),
        record.get("nearby_text"),
    )
    loader_warnings: list[str] = []
    if not vision_image_path and image_path:
        loader_warnings.append("vision_image_path_missing_fallback_to_image_path")
    return {
        "figure_id": figure_id,
        "image_path": image_path,
        "vision_image_path": vision_image_path,
        "source_image_path": source_image_path,
        "caption": _first_text(record.get("caption"), record.get("raw_caption")),
        "stage2_figure_class": _first_text(record.get("stage2_figure_class"), record.get("figure_class"), record.get("figure_type"), "unknown"),
        "stage2_predicted_figure_type": _first_text(
            record.get("stage2_predicted_figure_type"),
            record.get("predicted_figure_type"),
            record.get("predicted_vision_type"),
        ),
        "figure_label": _first_text(record.get("figure_label"), record.get("label")),
        "page_number": record.get("page_number"),
        "subfigure_id": _first_text(record.get("subfigure_id"), record.get("subfigure_index")),
        "reference_sentences": [str(item).strip() for item in reference_sentences if str(item).strip()],
        "context_before": _first_text(record.get("context_before")),
        "context_after": _first_text(record.get("context_after")),
        "nearby_text": _first_text(record.get("nearby_text")),
        "related_text": _first_text(record.get("related_text")),
        "ocr_text": _first_text(record.get("ocr_text")),
        "context_text": context_text,
        "description_text": _first_text(record.get("description_text")),
        "source_file": _first_text(record.get("source_file")),
        "source_pdf": _first_text(record.get("source_pdf")),
        "loader_warnings": loader_warnings,
        "selection_source": selection_source,
        "send_to_vision_model": bool(record.get("send_to_vision_model")),
        "keep": bool(record.get("keep")),
        "raw_record": record,
    }


def _record_is_stage2_selected(record: dict[str, Any], normalized: dict[str, Any], paper_dir: Path) -> bool:
    if bool(record.get("send_to_vision_model")):
        return True
    if bool(record.get("vision_selected")):
        return True
    vision_image_path = str(normalized.get("vision_image_path") or "")
    if vision_image_path:
        if _path_under_directory(Path(vision_image_path), paper_dir / "figures_for_vision"):
            return True
        return True
    if bool(record.get("keep")) and _path_under_directory(Path(str(normalized.get("image_path") or "")), paper_dir / "figures_for_vision"):
        return True
    return False


def _resolve_path(value: Any, paper_dir: Path) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = paper_dir / path
    return str(path)


def _path_under_directory(path: Path, directory: Path) -> bool:
    if not str(path):
        return False
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except Exception:  # noqa: BLE001
        return False


def _stable_fallback_figure_id(source: Any) -> str:
    text = str(source or "").strip()
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"stage2_selected_{digest}"


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


__all__ = ["load_stage2_selected_figures"]
