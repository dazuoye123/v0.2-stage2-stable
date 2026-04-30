from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.config import build_runtime_settings  # noqa: E402
from alumina_sol_extractor.dspy_modules import run_stage3_dspy_smoke_test  # noqa: E402
from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single-paper Stage 3 DSPy smoke test.")
    parser.add_argument("--paper-id", required=True, help="Paper identifier used in the output summary.")
    parser.add_argument(
        "--cleaned-markdown-path",
        required=True,
        help="Absolute or relative path to the cleaned markdown file for this paper.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Paper output directory containing Stage 2 files such as figures.jsonl and tables/.",
    )
    parser.add_argument(
        "--paper-text-limit-chars",
        type=int,
        default=4000,
        help="Truncate cleaned markdown to this many characters for a fast smoke test.",
    )
    parser.add_argument(
        "--max-experiment-series",
        type=int,
        default=1,
        help="Only keep the first N experiment series during smoke testing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cleaned_markdown_path = Path(args.cleaned_markdown_path)
    if not cleaned_markdown_path.is_absolute():
        cleaned_markdown_path = PROJECT_ROOT / cleaned_markdown_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if not cleaned_markdown_path.exists():
        raise SystemExit(f"Cleaned markdown not found: {cleaned_markdown_path}")

    load_project_dotenv(PROJECT_ROOT)
    settings = build_runtime_settings(PROJECT_ROOT, PROJECT_ROOT / "settings.yaml")
    settings.setdefault("dspy", {})
    settings["dspy"]["enabled"] = True
    settings.setdefault("stage3", {})
    settings["stage3"]["dry_run_validator"] = False

    try:
        summary = run_stage3_dspy_smoke_test(
            project_root=PROJECT_ROOT,
            settings=settings,
            paper_id=args.paper_id,
            cleaned_markdown_path=cleaned_markdown_path,
            output_dir=output_dir,
            paper_text_limit_chars=args.paper_text_limit_chars,
            max_experiment_series=args.max_experiment_series,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print("Stage 3 DSPy smoke test finished.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
