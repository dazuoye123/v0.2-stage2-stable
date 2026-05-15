from __future__ import annotations

from pathlib import Path

from .body_trim import generate_cleaned_body_markdown


def ensure_cleaned_body_markdown(
    markdown_path: Path | str,
    paper_output_dir: Path | str,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Ensure Stage 3 body-trim artifacts exist without touching the source markdown."""

    markdown_path = Path(markdown_path)
    paper_output_dir = Path(paper_output_dir)
    stage3_text_dir = paper_output_dir / "stage3_text"
    cleaned_body_path = stage3_text_dir / "cleaned_body.md"
    report_path = stage3_text_dir / "markdown_trim_report.json"

    if force or not cleaned_body_path.exists() or not report_path.exists():
        generate_cleaned_body_markdown(markdown_path=markdown_path, paper_output_dir=paper_output_dir)

    return cleaned_body_path, report_path
