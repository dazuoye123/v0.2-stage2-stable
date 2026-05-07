"""Run Stage 5.5 candidate-constrained linking on final_dataset outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.linking.candidate_builder import (
    DEFAULT_LINK_FAMILIES,
    build_deterministic_links,
    build_link_candidates,
    load_final_dataset_inputs,
)
from alumina_sol_extractor.linking.exporters import export_linking_outputs
from alumina_sol_extractor.linking.llm_linker import EvidenceSpectraParameterLinker
from alumina_sol_extractor.linking.report import render_linking_report
from alumina_sol_extractor.linking.validators import build_linking_summary, validate_llm_link_decisions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 5.5 evidence/spectra/parameter linking.")
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--final-dataset-dir", required=True)
    parser.add_argument("--max-candidates", type=int, default=100)
    parser.add_argument("--max-llm-candidates", type=int, default=20)
    parser.add_argument(
        "--link-types",
        default="spectra_peak_to_parameter,evidence_to_parameter,spectra_to_evidence,parameter_to_sample",
        help="Comma-separated candidate families.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = True if not args.live else False
    final_dataset_dir = Path(args.final_dataset_dir)
    linking_dir = final_dataset_dir / "linking"
    inputs = load_final_dataset_inputs(final_dataset_dir)
    link_types = {item.strip() for item in args.link_types.split(",") if item.strip()} or DEFAULT_LINK_FAMILIES

    candidates = build_link_candidates(
        inputs["paper"],
        inputs["parameters"],
        inputs["evidence"],
        inputs["spectra"],
        inputs["samples"],
        link_types=link_types,
        max_candidates_per_type=max(1, args.max_candidates),
    )
    deterministic_links, unmatched_candidates = build_deterministic_links(candidates)

    accepted_links = list(deterministic_links)
    rejected_links: list[dict] = []
    raw_llm_outputs: list[dict] = []
    invalid_source_id_count = 0
    invalid_target_id_count = 0

    if not dry_run:
        llm_candidates = [item for item in candidates if item.get("needs_llm")][: args.max_llm_candidates]
        linker = EvidenceSpectraParameterLinker(dry_run=False)
        decisions, raw_llm_outputs, parse_failures = linker.run(
            llm_candidates,
            paper_context=inputs["paper"],
            max_candidates_per_call=args.max_llm_candidates,
        )
        reviewed, rejected, unmatched, stats = validate_llm_link_decisions(
            llm_candidates,
            decisions,
            starting_index=len(accepted_links) + 1,
        )
        accepted_links.extend(reviewed)
        rejected_links.extend(rejected)
        unmatched_candidates.extend(unmatched)
        rejected_links.extend(parse_failures)
        invalid_source_id_count = stats["invalid_source_id_count"]
        invalid_target_id_count = stats["invalid_target_id_count"]

    summary = build_linking_summary(
        candidates=candidates,
        accepted_links=accepted_links,
        rejected_links=rejected_links,
        unmatched_candidates=unmatched_candidates,
        raw_llm_outputs=raw_llm_outputs,
        invalid_source_id_count=invalid_source_id_count,
        invalid_target_id_count=invalid_target_id_count,
    )
    report = render_linking_report(
        file_presence={
            "paper": (final_dataset_dir / "paper.json").exists(),
            "samples": (final_dataset_dir / "samples.jsonl").exists(),
            "parameters": (final_dataset_dir / "parameters.jsonl").exists(),
            "evidence": (final_dataset_dir / "evidence.jsonl").exists(),
            "spectra": (final_dataset_dir / "spectra.jsonl").exists(),
            "quality_summary": (final_dataset_dir / "quality_summary.json").exists(),
            "fusion_report": (final_dataset_dir / "fusion_report.md").exists(),
            "figures": (final_dataset_dir / "figures.jsonl").exists(),
        },
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=rejected_links,
        summary=summary,
    )
    outputs = export_linking_outputs(
        linking_dir,
        candidates=candidates,
        accepted_links=accepted_links,
        unmatched_candidates=unmatched_candidates,
        rejected_links=rejected_links,
        raw_llm_outputs=raw_llm_outputs,
        summary=summary,
        report=report,
    )
    print(
        json.dumps(
            {
                "paper_id": args.paper_id,
                "linking_dir": str(linking_dir),
                "summary": summary,
                "outputs": outputs,
                "mode": "dry_run" if dry_run else "live",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
