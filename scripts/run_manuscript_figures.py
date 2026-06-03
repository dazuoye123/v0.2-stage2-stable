from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.manuscript_figures import run_manuscript_figures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Nature-style manuscript figures from diagnosed source tables.")
    parser.add_argument("--diagnosis-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--nature-skills-dir")
    parser.add_argument("--support-tables-dir")
    parser.add_argument("--legacy-v1-source-dir")
    parser.add_argument("--figures", nargs="+", default=["Fig1", "Fig2", "Fig4"])
    parser.add_argument("--version-label", default="v2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_manuscript_figures(
        diagnosis_dir=_resolve(args.diagnosis_dir) or PROJECT_ROOT / "data" / "batch_validation" / "20260602_212510" / "manuscript_figure_diagnosis",
        output_dir=_resolve(args.output_dir) or PROJECT_ROOT / "data" / "batch_validation" / "20260602_212510" / "manuscript_figures_nature_v1",
        nature_skills_dir=_resolve(args.nature_skills_dir),
        support_tables_dir=_resolve(args.support_tables_dir),
        legacy_v1_source_dir=_resolve(args.legacy_v1_source_dir),
        figures=args.figures,
        version_label=args.version_label,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
