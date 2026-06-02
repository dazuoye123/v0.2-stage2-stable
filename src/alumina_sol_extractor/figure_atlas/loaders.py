from __future__ import annotations

from pathlib import Path
from typing import Any

from .stage3_loader import load_stage3_inputs
from .stage4_loader import load_stage4_inputs
from .stage5_loader import load_stage5_batch_exports


def load_all_inputs(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
) -> dict[str, Any]:
    return {
        "stage3": load_stage3_inputs(project_root=project_root, stage3_analysis_dir=stage3_analysis_dir, stage3_publication_dir=stage3_publication_dir),
        "stage4": load_stage4_inputs(outputs_dir),
        "stage5": load_stage5_batch_exports(batch_final_export_dir),
    }
