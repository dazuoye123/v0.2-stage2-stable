from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dataset_fusion.link_aware_export import generate_link_aware_exports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export link-aware final dataset tables.")
    parser.add_argument("--final-dataset-dir", required=True)
    parser.add_argument("--paper-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--no-showcase", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    final_dataset_dir = Path(args.final_dataset_dir)
    if not final_dataset_dir.is_absolute():
        final_dataset_dir = PROJECT_ROOT / final_dataset_dir
    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir and not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    result = generate_link_aware_exports(
        final_dataset_dir,
        output_dir=output_dir,
        paper_id=args.paper_id,
        project_root=PROJECT_ROOT,
        include_showcase=not args.no_showcase,
    )
    print(
        json.dumps(
            {
                "paper_id": result["paper_id"],
                "output_dir": result["output_dir"],
                "summary": result["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
