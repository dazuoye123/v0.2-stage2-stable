"""Legacy wrapper for the official Stage5 batch runner.

Use ``scripts/run_stage5_batch.py`` for normal execution.
This compatibility shim remains so older tests, notes, and local commands do
not break during the entrypoint migration.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_stage5_batch import main, parse_args  # noqa: E402
from alumina_sol_extractor.stage5.batch_runner import (  # noqa: E402
    DEFAULT_CATEGORIES,
    build_failure_manifest,
    build_overall_summary,
    build_quality_issue_rows,
    build_run_report,
    discover_papers,
    discover_stage_dirs,
    filter_incomplete_papers,
    has_complete_stage5_outputs,
    missing_stage5_outputs,
    run_single_paper,
    run_stage5_batch,
    summarize_existing_outputs,
)


if __name__ == "__main__":
    raise SystemExit(main())
