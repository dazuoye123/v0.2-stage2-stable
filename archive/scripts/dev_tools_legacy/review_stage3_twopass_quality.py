from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from alumina_sol_extractor.stage3.quality_grading import (
    aggregate_quality_review,
    evaluate_stage3_twopass_paper,
    render_quality_review_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Stage 3 two-pass outputs with the unified rubric.")
    parser.add_argument("--sample-csv", required=True, help="CSV containing category and paper_id columns.")
    parser.add_argument("--outputs-dir", default="data/outputs", help="Base outputs directory.")
    parser.add_argument("--output-csv", required=True, help="Destination CSV for per-paper review.")
    parser.add_argument("--output-json", required=True, help="Destination JSON summary.")
    parser.add_argument("--output-md", required=True, help="Destination Markdown report.")
    parser.add_argument("--title", default="Stage 3 Two-pass Quality Review", help="Markdown report title.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_csv = Path(args.sample_csv)
    outputs_dir = Path(args.outputs_dir)
    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    rows = list(csv.DictReader(sample_csv.open("r", encoding="utf-8-sig", newline="")))
    reviews = []
    for row in rows:
        category = row["category"]
        paper_id = row["paper_id"]
        paper_output_dir = outputs_dir / category / paper_id
        reviews.append(
            evaluate_stage3_twopass_paper(
                category=category,
                paper_id=paper_id,
                paper_output_dir=paper_output_dir,
                source_group=row.get("source_group", ""),
            )
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    if reviews:
        with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(reviews[0].keys()))
            writer.writeheader()
            writer.writerows(reviews)
    else:
        output_csv.write_text("", encoding="utf-8")

    summary = aggregate_quality_review(reviews)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(
        render_quality_review_markdown(title=args.title, summary=summary, rows=reviews),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
