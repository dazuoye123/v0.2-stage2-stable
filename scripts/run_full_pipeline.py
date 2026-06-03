from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dataset_fusion.batch_link_aware_export import export_batch_link_aware_dataset  # noqa: E402
from alumina_sol_extractor.dataset_fusion.link_aware_export import generate_link_aware_exports  # noqa: E402
from alumina_sol_extractor.pipeline.full_pipeline_runner import run_stage6c_full_resume  # noqa: E402
from alumina_sol_extractor.pipeline.orchestrator import (  # noqa: E402
    _run_stage5_and_linking_for_selected_papers,
    run_full_pipeline_orchestrated,
)
from alumina_sol_extractor.pipeline.stage1_pdf_to_markdown import run_stage1_pdf_to_markdown  # noqa: E402

_run_stage5_and_stage55_dry_run = _run_stage5_and_linking_for_selected_papers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the controlled full pipeline from Stage 1 through link-aware export.")
    parser.add_argument("--pdf-dir")
    parser.add_argument("--markdown-dir")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--paper-ids", default="")
    parser.add_argument("--max-papers", type=int, default=4)
    parser.add_argument("--auto-complete", action="store_true")
    parser.add_argument("--allow-stage1", action="store_true")
    parser.add_argument("--allow-stage2-refresh", action="store_true")
    parser.add_argument("--live-stage3", action="store_true")
    parser.add_argument("--live-stage4", "--live-stage4a", dest="live_stage4", action="store_true", help="Run Stage4 live. --live-stage4a is a legacy alias.")
    parser.add_argument("--live-linking", action="store_true")
    parser.add_argument("--force-stage3", action="store_true")
    parser.add_argument("--force-stage4", "--force-stage4a", dest="force_stage4", action="store_true", help="Force Stage4 rerun. --force-stage4a is a legacy alias.")
    parser.add_argument("--force-stage5", action="store_true")
    parser.add_argument("--force-linking", action="store_true")
    parser.add_argument("--export-link-aware", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--safe", action="store_true")
    parser.add_argument("--max-stage3-papers", type=int, default=2)
    parser.add_argument("--max-stage4-papers", "--max-stage4a-papers", dest="max_stage4_papers", type=int, default=2, help="Limit Stage4 papers. --max-stage4a-papers is a legacy alias.")
    parser.add_argument(
        "--max-stage4-figures-per-paper",
        "--max-stage4a-figures-per-paper",
        dest="max_stage4_figures_per_paper",
        type=int,
        default=0,
        help="Limit Stage4 figures per paper. --max-stage4a-figures-per-paper is a legacy alias.",
    )
    parser.add_argument("--max-total-model-calls", type=int, default=10)
    parser.add_argument(
        "--stage4-figure-types",
        "--stage4a-figure-types",
        dest="stage4_figure_types",
        default="ftir_spectrum,xrd_pattern,nmr_spectrum,raman_spectrum,ferron_curve,tg_curve,dsc_curve,tg_dsc_curve,sem_image,tem_image",
        help="Preferred Stage4 figure types. --stage4a-figure-types is a legacy alias.",
    )
    parser.add_argument("--stage4-figure-ids", default="")
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--stage4-subdir", default="stage4_vision_spectra_universal")
    parser.add_argument("--stage4-routing-mode", default="universal_compact")
    parser.add_argument("--stage4-candidate-source", default="stage2-selected")
    parser.add_argument("--no-showcase", "--skip-preview-showcase", dest="no_showcase", action="store_true")
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def run_full_pipeline(**kwargs):
    return run_full_pipeline_orchestrated(
        **kwargs,
        stage1_runner=run_stage1_pdf_to_markdown,
        full_pipeline_resume_runner=run_stage6c_full_resume,
        link_exporter=generate_link_aware_exports,
        batch_exporter=export_batch_link_aware_dataset,
        stage5_only_runner=_run_stage5_and_linking_for_selected_papers,
    )


def main() -> int:
    args = parse_args()
    result = run_full_pipeline(
        pdf_dir=_resolve(args.pdf_dir),
        markdown_dir=_resolve(args.markdown_dir),
        outputs_dir=_resolve(args.outputs_dir),
        paper_ids=_split_csv(args.paper_ids) or None,
        max_papers=max(1, args.max_papers),
        auto_complete=args.auto_complete,
        allow_stage1=args.allow_stage1,
        allow_stage2_refresh=args.allow_stage2_refresh,
        live_stage3=args.live_stage3,
        live_stage4=args.live_stage4,
        live_linking=args.live_linking,
        force_stage3=args.force_stage3,
        force_stage4=args.force_stage4,
        force_stage5=args.force_stage5,
        force_linking=args.force_linking,
        export_link_aware=args.export_link_aware,
        dry_run=args.dry_run,
        safe=args.safe,
        max_stage3_papers=max(0, args.max_stage3_papers),
        max_stage4_papers=max(0, args.max_stage4_papers),
        max_stage4_figures_per_paper=max(0, args.max_stage4_figures_per_paper),
        max_total_model_calls=max(0, args.max_total_model_calls),
        stage4_figure_types=_split_csv(args.stage4_figure_types),
        stage4_figure_ids=_split_csv(args.stage4_figure_ids) or None,
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        stage4_routing_mode=args.stage4_routing_mode,
        stage4_candidate_source=args.stage4_candidate_source,
        include_showcase=not args.no_showcase,
        output_dir=_resolve(args.output_dir),
    )
    print(
        json.dumps(
            {
                "paper_ids": result["paper_ids"],
                "run_summary": result["run_summary"],
                "run_report_path": result["run_report_path"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
