from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.manuscript_figures.semantic_repair_validation import run_semantic_repair_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate semantic-repair batch exports for figure/manuscript use.")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--batch-export-dir", default="data/outputs/_batch_final_exports_semantic_v1")
    parser.add_argument("--validation-dir", required=True)
    return parser.parse_args()


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_semantic_repair_validation(
        project_root=PROJECT_ROOT,
        outputs_dir=_resolve(args.outputs_dir),
        batch_final_export_dir=_resolve(args.batch_export_dir),
        validation_dir=_resolve(args.validation_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
