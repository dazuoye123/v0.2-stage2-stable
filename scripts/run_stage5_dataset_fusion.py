from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dataset_fusion.exporters import export_fusion_outputs
from alumina_sol_extractor.dataset_fusion.fusion import run_stage5_dataset_fusion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 5 dataset fusion.")
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--stage3-dir")
    parser.add_argument("--stage4-dir")
    parser.add_argument("--output-dataset-dir")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    stage3_dir = Path(args.stage3_dir) if args.stage3_dir else None
    if stage3_dir and not stage3_dir.is_absolute():
        stage3_dir = PROJECT_ROOT / stage3_dir
    stage4_dir = Path(args.stage4_dir) if args.stage4_dir else None
    if stage4_dir and not stage4_dir.is_absolute():
        stage4_dir = PROJECT_ROOT / stage4_dir
    output_dataset_dir = Path(args.output_dataset_dir) if args.output_dataset_dir else None
    if output_dataset_dir and not output_dataset_dir.is_absolute():
        output_dataset_dir = PROJECT_ROOT / output_dataset_dir

    bundle = run_stage5_dataset_fusion(
        paper_id=args.paper_id,
        output_dir=output_dir,
        stage3_dir=stage3_dir,
        stage4_dir=stage4_dir,
        output_dataset_dir=output_dataset_dir,
    )
    dataset_dir = Path(bundle["inputs"]["dirs"]["dataset_dir"])
    output_paths = export_fusion_outputs(bundle, dataset_dir)
    print(
        json.dumps(
            {
                "paper_id": args.paper_id,
                "dataset_dir": str(dataset_dir),
                "quality_summary": bundle["quality_summary"],
                "outputs": output_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
