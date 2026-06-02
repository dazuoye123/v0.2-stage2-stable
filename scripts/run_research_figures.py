from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.research_figures import run_research_figures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate batch-level Stage3 + Stage4 research figures from existing outputs.")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--batch-output-dir", default="data/batch_validation")
    parser.add_argument("--manifest")
    parser.add_argument("--generate-figures", dest="generate_figures", action="store_true")
    parser.add_argument("--no-figures", dest="generate_figures", action="store_false")
    parser.set_defaults(generate_figures=True)
    parser.add_argument("--stage3-analysis-dir")
    parser.add_argument("--stage3-publication-dir")
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_research_figures(
        project_root=PROJECT_ROOT,
        outputs_dir=_resolve(args.outputs_dir) or PROJECT_ROOT / "data" / "outputs",
        batch_output_dir=_resolve(args.batch_output_dir) or PROJECT_ROOT / "data" / "batch_validation",
        stage3_analysis_dir=_resolve(args.stage3_analysis_dir),
        stage3_publication_dir=_resolve(args.stage3_publication_dir),
        manifest_path=_resolve(args.manifest),
        generate_figures=args.generate_figures,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
