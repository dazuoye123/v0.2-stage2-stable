"""Stage 1: MinerU PDF -> cleaned Markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alumina_sol_extractor.config import resolve_project_path
from alumina_sol_extractor.pdf import MinerUPDFToMarkdown


@dataclass(slots=True)
class Stage1Result:
    """Outputs produced by stage 1."""

    input_pdf: Path
    paper_id: str
    cleaned_markdown_path: Path
    output_dir: Path
    converter_outputs: dict[str, Any] = field(default_factory=dict)


def run_stage1_pdf_to_markdown(project_root: Path, settings: dict[str, Any]) -> Stage1Result:
    """Convert one PDF into cleaned Markdown using the current MinerU config."""
    project_root = Path(project_root)
    paths = settings.get("paths", {})
    mineru = settings.get("mineru", {})
    chemistry = settings.get("chemistry_normalization", {})

    input_pdf = resolve_project_path(project_root, paths.get("input_pdf", "data/pdfs/example.pdf"))
    paper_id = input_pdf.stem
    markdown_output_dir = resolve_project_path(
        project_root,
        paths.get("markdown_output_dir", "data/markdown"),
    )
    output_md = markdown_output_dir / f"{paper_id}.md"
    output_dir = resolve_project_path(project_root, paths.get("output_dir", "data/outputs")) / paper_id

    converter = MinerUPDFToMarkdown(
        project_root=project_root,
        mineru_raw_dir=paths.get("mineru_raw_dir", "data/mineru_raw"),
        markdown_output_dir=paths.get("markdown_output_dir", "data/markdown"),
        output_dir=paths.get("output_dir", "data/outputs"),
        api_key_env=mineru.get("api_key_env", "MINERU_API_KEY"),
        base_url_env=mineru.get("base_url_env", "MINERU_BASE_URL"),
        poll_interval_seconds=mineru.get("poll_interval_seconds", 3),
        max_wait_seconds=mineru.get("max_wait_seconds", 600),
        save_raw=mineru.get("save_raw", True),
        save_cleaned=mineru.get("save_cleaned", True),
        chemistry_enabled=chemistry.get("enabled", True),
        unicode_subscript=chemistry.get("unicode_subscript", False),
    )
    cleaned_md = converter.convert_file(input_pdf=input_pdf, output_md=output_md)
    return Stage1Result(
        input_pdf=input_pdf,
        paper_id=paper_id,
        cleaned_markdown_path=cleaned_md,
        output_dir=output_dir,
        converter_outputs=dict(converter.last_outputs),
    )
