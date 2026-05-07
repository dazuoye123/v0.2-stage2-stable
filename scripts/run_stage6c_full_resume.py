from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.batch_validation.full_resume import run_stage6c_full_resume


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 6C controlled full resume.")
    parser.add_argument("--markdown-dir", required=True)
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--max-papers", type=int, default=4)
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--auto-complete", action="store_true")
    parser.add_argument("--allow-stage2-refresh", action="store_true")
    parser.add_argument("--live-stage3", action="store_true")
    parser.add_argument("--live-stage4a", action="store_true")
    parser.add_argument("--live-linking", action="store_true")
    parser.add_argument("--force-stage3", action="store_true")
    parser.add_argument("--force-stage4a", action="store_true")
    parser.add_argument("--force-stage5", action="store_true")
    parser.add_argument("--force-linking", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--dry-run-plan-only", action="store_true")
    parser.add_argument("--max-stage4a-figures-per-paper", type=int, default=4)
    parser.add_argument("--max-stage3-papers", type=int, default=2)
    parser.add_argument("--max-stage4a-papers", type=int, default=2)
    parser.add_argument("--max-total-model-calls", type=int, default=10)
    parser.add_argument(
        "--stage4a-figure-types",
        default="ftir_spectrum,xrd_pattern,nmr_spectrum,raman_spectrum,ferron_curve,tg_curve,dsc_curve,tg_dsc_curve,sem_image,tem_image",
    )
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    result = run_stage6c_full_resume(
        project_root=PROJECT_ROOT,
        markdown_dir=_resolve(args.markdown_dir),
        outputs_dir=_resolve(args.outputs_dir),
        max_papers=max(1, args.max_papers),
        paper_ids=[item.strip() for item in args.paper_ids.split(",") if item.strip()] or None,
        auto_complete=args.auto_complete,
        allow_stage2_refresh=args.allow_stage2_refresh,
        live_stage3=args.live_stage3,
        live_stage4a=args.live_stage4a,
        live_linking=args.live_linking,
        force_stage3=args.force_stage3,
        force_stage4a=args.force_stage4a,
        force_stage5=args.force_stage5,
        force_linking=args.force_linking,
        stop_on_error=args.stop_on_error,
        dry_run_plan_only=args.dry_run_plan_only,
        max_stage4a_figures_per_paper=max(1, args.max_stage4a_figures_per_paper),
        max_stage3_papers=max(0, args.max_stage3_papers),
        max_stage4a_papers=max(0, args.max_stage4a_papers),
        max_total_model_calls=max(0, args.max_total_model_calls),
        stage4a_figure_types=[item.strip() for item in args.stage4a_figure_types.split(",") if item.strip()],
        output_dir=_resolve(args.output_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
