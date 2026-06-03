from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from PIL import Image

from .style import configure_style


def verify_outputs(bundle: dict[str, str]) -> dict[str, Any]:
    result = {
        "png_openable": False,
        "svg_nonempty": False,
        "pdf_nonempty": False,
        "source_data_exists": False,
        "figure_data_exists": False,
        "caption_exists": False,
    }
    png = Path(bundle["output_png"])
    svg = Path(bundle["output_svg"])
    pdf = Path(bundle["output_pdf"])
    source = Path(bundle["source_data_csv"])
    figure_data = Path(bundle["figure_data_json"])
    caption = Path(bundle["caption_md"])
    if png.exists():
        with Image.open(png) as image:
            image.verify()
        result["png_openable"] = True
    result["svg_nonempty"] = svg.exists() and svg.stat().st_size > 0
    result["pdf_nonempty"] = pdf.exists() and pdf.stat().st_size > 0
    result["source_data_exists"] = source.exists()
    result["figure_data_exists"] = figure_data.exists()
    result["caption_exists"] = caption.exists()
    return result


def write_qc_png(path: Path, *, figure_id: str, checks: dict[str, Any], notes: list[str]) -> Path:
    configure_style()
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    ax.axis("off")
    lines = [f"{figure_id} QC"]
    lines.extend([f"- {key}: {value}" for key, value in checks.items()])
    lines.extend([f"- note: {note}" for note in notes[:4]])
    ax.text(0.02, 0.98, "\n".join(lines), ha="left", va="top", fontsize=7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path
