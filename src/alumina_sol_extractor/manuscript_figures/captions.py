from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import write_markdown


def build_caption(
    *,
    figure_id: str,
    title: str,
    scientific_question: str,
    expected_claim: str,
    panel_descriptions: list[str],
    source_tables: list[str],
    filtering_and_normalization: list[str],
    limitations: list[str],
) -> str:
    lines = [
        f"# {figure_id} {title}",
        "",
        "## Scientific question",
        scientific_question,
        "",
        "## Main claim",
        expected_claim,
        "",
        "## Panel descriptions",
    ]
    for text in panel_descriptions:
        lines.append(text)
    lines.extend(["", "## Data source"])
    for item in source_tables:
        lines.append(f"- {item}")
    lines.extend(["", "## Filtering and normalization"])
    for item in filtering_and_normalization:
        lines.append(f"- {item}")
    lines.extend(["", "## Limitations"])
    for item in limitations:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_caption(path: Path, text: str) -> Path:
    return write_markdown(path, text)
