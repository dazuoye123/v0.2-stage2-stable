"""Stage 3: optional ontology/schema_v2 DSPy extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alumina_sol_extractor.dspy_modules.runner import run_stage3_dspy_schema_extraction


@dataclass(slots=True)
class Stage3Result:
    """Outputs produced by stage 3 DSPy extraction."""

    output_dir: Path
    summary: dict[str, Any] = field(default_factory=dict)


def run_stage3_dspy_pipeline(
    project_root: Path,
    settings: dict[str, Any],
    paper_id: str,
    cleaned_markdown_path: Path,
    output_dir: Path,
    *,
    mode: str = "full",
    max_experiment_series: int | None = None,
    stage3_subdir: str = "stage3",
) -> Stage3Result:
    """Run optional Stage 3 without affecting Stage 1/2 defaults."""
    summary = run_stage3_dspy_schema_extraction(
        project_root=project_root,
        settings=settings,
        paper_id=paper_id,
        cleaned_markdown_path=cleaned_markdown_path,
        output_dir=output_dir,
        mode=mode,
        max_experiment_series=max_experiment_series,
        stage3_subdir=stage3_subdir,
    )
    return Stage3Result(output_dir=Path(output_dir) / stage3_subdir, summary=summary)
