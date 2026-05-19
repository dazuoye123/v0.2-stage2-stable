from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.pipeline.resume_status import run_stage6b_batch_resume


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 6B batch resume pipeline.")
    parser.add_argument("--markdown-dir", required=True)
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--max-papers", type=int, default=5)
    parser.add_argument("--paper-ids", help="Comma-separated paper ids.")
    parser.add_argument("--safe", action="store_true", help="Safe mode: no LLM/VLM calls.")
    parser.add_argument("--live-stage3", action="store_true")
    parser.add_argument("--live-stage4a", action="store_true")
    parser.add_argument("--live-linking", action="store_true")
    parser.add_argument("--allow-stage2-refresh", action="store_true")
    parser.add_argument("--force-stage5", action="store_true")
    parser.add_argument("--force-linking", action="store_true")
    parser.add_argument("--dry-run-plan-only", action="store_true")
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _resolve_project_path(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    safe = args.safe or not any([args.live_stage3, args.live_stage4a, args.live_linking])
    markdown_dir = _resolve_project_path(args.markdown_dir)
    outputs_dir = _resolve_project_path(args.outputs_dir)
    output_dir = _resolve_project_path(args.output_dir)
    paper_ids = [item.strip() for item in (args.paper_ids or "").split(",") if item.strip()]

    result = run_stage6b_batch_resume(
        project_root=PROJECT_ROOT,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        max_papers=max(1, args.max_papers),
        paper_ids=paper_ids or None,
        safe=safe,
        live_stage3=args.live_stage3,
        live_stage4a=args.live_stage4a,
        live_linking=args.live_linking,
        allow_stage2_refresh=args.allow_stage2_refresh,
        force_stage5=args.force_stage5,
        force_linking=args.force_linking,
        dry_run_plan_only=args.dry_run_plan_only,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                "batch_output_dir": result["batch_output_dir"],
                "resume_summary": result["resume_summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
