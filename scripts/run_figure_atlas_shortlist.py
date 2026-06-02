from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alumina_sol_extractor.figure_atlas.shortlist import run_figure_atlas_shortlist


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a generated figure_atlas and build a shortlist package.")
    parser.add_argument("--atlas-dir", required=True, help="Existing figure_atlas directory to review.")
    parser.add_argument("--output-dir", default="", help="Output shortlist directory. Defaults to sibling figure_atlas_shortlist/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_figure_atlas_shortlist(
        atlas_dir=Path(args.atlas_dir),
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
