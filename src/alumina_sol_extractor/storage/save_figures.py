"""Save figure metadata."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from alumina_sol_extractor.models.figure import FigureInfo


def save_figures_jsonl(figures: list[FigureInfo], output_path: Path) -> Path:
    """Save one FigureInfo object per JSONL line."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_obj:
        for figure in figures:
            file_obj.write(json.dumps(figure.model_dump(), ensure_ascii=False) + "\n")
    return output_path


def copy_figures_for_vision(figures: list[FigureInfo], output_dir: Path) -> Path:
    """Copy selected images into figures_for_vision without deleting archive files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    for figure in figures:
        if not figure.send_to_vision_model or not figure.image_path:
            continue
        source = Path(figure.image_path)
        if not source.exists():
            continue
        target = output_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        figure.vision_image_path = str(target.resolve())
    return output_dir
