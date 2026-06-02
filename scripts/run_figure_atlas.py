from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.figure_atlas import run_figure_atlas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage3/Stage4/Stage5 figure atlas from existing outputs.")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--batch-final-export-dir", required=True)
    parser.add_argument("--stage3-analysis-dir")
    parser.add_argument("--stage3-publication-dir")
    parser.add_argument("--batch-output-dir", default="data/batch_validation")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--generate-figures", dest="generate_figures", action="store_true")
    parser.add_argument("--skip-auto-figures", action="store_true")
    parser.add_argument("--max-auto-figures", type=int, default=50)
    parser.add_argument("--delete-old-research-figures-code", action="store_true")
    parser.add_argument("--dry-run-delete-old-code", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.set_defaults(generate_figures=True)
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_figure_atlas(
        project_root=PROJECT_ROOT,
        outputs_dir=_resolve(args.outputs_dir) or PROJECT_ROOT / "data" / "outputs",
        batch_final_export_dir=_resolve(args.batch_final_export_dir) or PROJECT_ROOT / "data" / "outputs" / "_batch_final_exports",
        batch_output_dir=_resolve(args.batch_output_dir) or PROJECT_ROOT / "data" / "batch_validation",
        stage3_analysis_dir=_resolve(args.stage3_analysis_dir),
        stage3_publication_dir=_resolve(args.stage3_publication_dir),
        audit_only=args.audit_only,
        generate_figures=args.generate_figures,
        skip_auto_figures=args.skip_auto_figures,
        max_auto_figures=args.max_auto_figures,
        delete_old_research_figures_code=args.delete_old_research_figures_code,
        dry_run_delete_old_code=args.dry_run_delete_old_code,
        continue_on_error=args.continue_on_error,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
