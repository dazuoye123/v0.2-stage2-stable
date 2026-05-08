from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import export_batch_link_aware_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export batch link-aware dataset tables.")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = export_batch_link_aware_dataset(
        _resolve(args.outputs_dir),
        output_dir=_resolve(args.output_dir),
        paper_ids=[item.strip() for item in args.paper_ids.split(",") if item.strip()] or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
