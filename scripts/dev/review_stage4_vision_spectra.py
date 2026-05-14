from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.vision_spectra.io import read_json  # noqa: E402
from alumina_sol_extractor.vision_spectra.quality_review import (  # noqa: E402
    load_stage4_outputs,
    review_stage4_extractions,
    write_stage4_quality_review,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review existing Stage 4 vision spectra outputs.")
    parser.add_argument("--stage4-dir", required=True)
    parser.add_argument("--expected-peaks-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stage4_dir = Path(args.stage4_dir)
    if not stage4_dir.is_absolute():
        stage4_dir = PROJECT_ROOT / stage4_dir
    expected_peaks = None
    if args.expected_peaks_json:
        expected_path = Path(args.expected_peaks_json)
        if not expected_path.is_absolute():
            expected_path = PROJECT_ROOT / expected_path
        expected_peaks = read_json(expected_path, default={}) or {}

    outputs = load_stage4_outputs(stage4_dir)
    review_payload = review_stage4_extractions(outputs, expected_peaks=expected_peaks)

    output_md = Path(args.output_md) if args.output_md else stage4_dir / "stage4_quality_review.md"
    output_json = Path(args.output_json) if args.output_json else stage4_dir / "stage4_quality_review.json"
    if not output_md.is_absolute():
        output_md = PROJECT_ROOT / output_md
    if not output_json.is_absolute():
        output_json = PROJECT_ROOT / output_json
    write_stage4_quality_review(review_payload, output_md=output_md, output_json=output_json)
    print(json.dumps(review_payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
