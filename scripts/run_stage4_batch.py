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
from alumina_sol_extractor.stage4.batch_runner import (  # noqa: E402
    DEFAULT_CANDIDATE_SOURCE,
    DEFAULT_ROUTING_MODE,
    DEFAULT_STAGE3_SUBDIR,
    DEFAULT_STAGE4_SUBDIR,
    run_stage4_batch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official Stage4 batch runner.")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--force-stage4", action="store_true")
    parser.add_argument("--stage4-figure-ids", default="")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--stage3-subdir", default=DEFAULT_STAGE3_SUBDIR)
    parser.add_argument("--stage4-subdir", default=DEFAULT_STAGE4_SUBDIR)
    parser.add_argument("--stage4-routing-mode", default=DEFAULT_ROUTING_MODE)
    parser.add_argument("--candidate-source", default=DEFAULT_CANDIDATE_SOURCE)
    parser.add_argument("--max-figures-per-paper", type=int, default=0)
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def main() -> int:
    args = parse_args()
    if args.live:
        load_project_dotenv(PROJECT_ROOT)
    result = run_stage4_batch(
        outputs_dir=_resolve(args.outputs_dir) or PROJECT_ROOT / "data" / "outputs",
        manifest=_resolve(args.manifest) if args.manifest else None,
        paper_ids=_split_csv(args.paper_ids) or None,
        category=args.category or None,
        limit=max(0, args.limit),
        dry_run=not args.live,
        force_stage4=args.force_stage4,
        stage4_figure_ids=_split_csv(args.stage4_figure_ids) or None,
        continue_on_error=args.continue_on_error,
        output_dir=_resolve(args.output_dir),
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        routing_mode=args.stage4_routing_mode,
        candidate_source=args.candidate_source,
        max_figures_per_paper=max(0, args.max_figures_per_paper),
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
