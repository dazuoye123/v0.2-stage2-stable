"""Re-parse Stage 4 raw VLM outputs without making new model calls."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.vision_spectra.reparse import reparse_stage4_vlm_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Reparse Stage 4 raw VLM outputs without new model calls.")
    parser.add_argument("--stage4-dir", required=True, help="Path to a stage4_vision_spectra directory.")
    parser.add_argument("--paper-id", default=None, help="Optional paper id for logging only.")
    args = parser.parse_args()

    stage4_dir = Path(args.stage4_dir)
    summary = reparse_stage4_vlm_outputs(stage4_dir)
    print(f"Reparsed Stage 4 outputs in {stage4_dir}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
