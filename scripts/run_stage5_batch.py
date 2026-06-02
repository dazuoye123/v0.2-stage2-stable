from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage5.batch_runner import DEFAULT_CATEGORIES, run_stage5_batch  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official Stage5 batch runner.")
    parser.add_argument("--outputs-dir", default="data/outputs")
    parser.add_argument("--report-dir", default="data/analysis_outputs_stage5_batch")
    parser.add_argument("--categories", nargs="*", default=DEFAULT_CATEGORIES)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--paper-filter")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--only-incomplete", action="store_true")
    parser.add_argument("--stage5-only", action="store_true")
    parser.add_argument("--with-linking", action="store_true")
    parser.add_argument("--no-linking", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    outputs_dir = _resolve_path(args.outputs_dir)
    report_dir = _resolve_path(args.report_dir)
    with_linking = False if args.no_linking or args.stage5_only else True
    if args.with_linking:
        with_linking = True
    result = run_stage5_batch(
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        categories=args.categories,
        limit=args.limit,
        paper_filter=args.paper_filter,
        force=args.force,
        skip_existing=(args.skip_existing or not args.force),
        only_incomplete=args.only_incomplete,
        with_linking=with_linking,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
        workers=max(1, args.workers),
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
