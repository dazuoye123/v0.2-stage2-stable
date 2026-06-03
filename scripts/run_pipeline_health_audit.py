from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.manuscript_figures.pipeline_health_audit import run_pipeline_health_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a static pipeline health audit over sampled papers without rerunning any stage.")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--batch-export-dir", default="data/outputs/_batch_final_exports")
    parser.add_argument("--figure-atlas-dir", default="data/batch_validation/20260602_212510/figure_atlas")
    parser.add_argument("--diagnosis-dir", default="data/batch_validation/20260602_212510/manuscript_figure_diagnosis")
    parser.add_argument("--manuscript-v2-dir", default="data/batch_validation/20260602_212510/manuscript_figures_nature_v2")
    parser.add_argument("--output-dir", default="data/batch_validation/20260602_212510/pipeline_health_audit")
    return parser.parse_args()


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_pipeline_health_audit(
        project_root=PROJECT_ROOT,
        outputs_dir=_resolve(args.outputs_dir),
        batch_export_dir=_resolve(args.batch_export_dir),
        figure_atlas_dir=_resolve(args.figure_atlas_dir),
        diagnosis_dir=_resolve(args.diagnosis_dir),
        manuscript_v2_dir=_resolve(args.manuscript_v2_dir),
        output_dir=_resolve(args.output_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
