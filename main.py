"""Thin entry point for the lightweight alumina sol extraction pipeline."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.config import build_runtime_settings, resolve_project_path  # noqa: E402
from alumina_sol_extractor.pdf.mineru_pdf_to_markdown import MinerUAPIError  # noqa: E402
from alumina_sol_extractor.pipeline import (  # noqa: E402
    run_stage1_pdf_to_markdown,
    run_stage2_figure_pipeline,
    run_stage3_dspy_pipeline,
)


def main() -> None:
    """Run stage 1 and stage 2 while keeping settings.yaml as the main entry."""
    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    input_pdf = resolve_project_path(
        PROJECT_ROOT,
        settings.get("paths", {}).get("input_pdf", "data/pdfs/example.pdf"),
    )
    if not input_pdf.exists():
        print(f"Input PDF not found: {input_pdf}")
        print("Put a test PDF at data/pdfs/example.pdf or edit settings.yaml.")
        raise SystemExit(1)

    try:
        stage1 = run_stage1_pdf_to_markdown(PROJECT_ROOT, settings)
    except MinerUAPIError as exc:
        print(f"MinerU conversion failed: {exc}")
        raise SystemExit(2) from exc

    stage2 = run_stage2_figure_pipeline(
        project_root=PROJECT_ROOT,
        settings=settings,
        input_pdf=stage1.input_pdf,
        paper_id=stage1.paper_id,
        cleaned_markdown_path=stage1.cleaned_markdown_path,
        output_dir=stage1.output_dir,
    )

    print("MinerU PDF to Markdown finished.")
    print(f"cleaned_markdown: {stage1.cleaned_markdown_path}")
    print(f"tables_dir: {stage2.tables_dir}")
    print(f"tables_count: {stage2.tables_count}")
    for key, value in stage2.summary.items():
        print(f"{key}: {value}")
    if settings.get("dspy", {}).get("enabled", False):
        stage3 = run_stage3_dspy_pipeline(
            project_root=PROJECT_ROOT,
            settings=settings,
            paper_id=stage1.paper_id,
            cleaned_markdown_path=stage1.cleaned_markdown_path,
            output_dir=stage1.output_dir,
        )
        for key, value in stage3.summary.items():
            print(f"{key}: {value}")
    for key, value in stage1.converter_outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
