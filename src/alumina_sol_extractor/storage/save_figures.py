"""Compatibility storage helpers for figure metadata.

New code should prefer ``alumina_sol_extractor.figures.figure_writer`` and
``alumina_sol_extractor.utils.jsonl``. This module stays as a stable import
surface for existing scripts.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.utils.jsonl import write_jsonl


def save_figures_jsonl(figures: list[FigureInfo], output_path: Path) -> Path:
    """Save one FigureInfo object per JSONL line."""
    return write_jsonl((figure.model_dump() for figure in figures), output_path)


def copy_figures_for_vision(figures: list[FigureInfo], output_dir: Path) -> Path:
    """Copy selected images into figures_for_vision without deleting archive files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    for figure in figures:
        if figure.is_fragment or not figure.send_to_vision_model or not figure.image_path:
            continue
        source = Path(figure.image_path)
        if not source.exists():
            continue
        target = output_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        figure.vision_image_path = str(target.resolve())
    return output_dir
