from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.figure_atlas.manuscript_diagnosis import run_manuscript_figure_diagnosis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manuscript figure diagnosis from existing figure_atlas outputs.")
    parser.add_argument("--atlas-dir", required=True)
    parser.add_argument("--shortlist-dir", required=True)
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_manuscript_figure_diagnosis(
        atlas_dir=_resolve(args.atlas_dir) or PROJECT_ROOT / "data" / "batch_validation" / "20260602_212510" / "figure_atlas",
        shortlist_dir=_resolve(args.shortlist_dir) or PROJECT_ROOT / "data" / "batch_validation" / "20260602_212510" / "figure_atlas_shortlist",
        output_dir=_resolve(args.output_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
