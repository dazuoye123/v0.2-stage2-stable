from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402
from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 4 vision spectra dry-run or live smoke test.")
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-figures", type=int, default=10)
    parser.add_argument(
        "--figure-types",
        default="nmr_spectrum,ftir_spectrum,xrd_pattern,ferron_curve",
        help="Comma-separated normalized figure types to consider.",
    )
    parser.add_argument(
        "--figure-ids",
        default="",
        help="Comma-separated figure_id values to process exactly. If provided, these are filtered before max-figures.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not call the VLM; write prompt and placeholder outputs only.")
    parser.add_argument("--live", action="store_true", help="Call the configured VLM.")
    return parser.parse_args()


def main() -> None:
    load_project_dotenv(PROJECT_ROOT)
    args = parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    figure_types = {item.strip() for item in str(args.figure_types or "").split(",") if item.strip()}
    figure_ids = [item.strip() for item in str(args.figure_ids or "").split(",") if item.strip()]
    dry_run = not args.live
    if args.dry_run:
        dry_run = True

    extractor = Stage4VisionSpectraExtractor(
        paper_id=args.paper_id,
        output_dir=output_dir,
        max_figures=args.max_figures,
        allowed_figure_types=figure_types,
        figure_ids=figure_ids,
        dry_run=dry_run,
    )
    summary = extractor.run()
    print("Stage 4 vision spectra smoke test finished.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
