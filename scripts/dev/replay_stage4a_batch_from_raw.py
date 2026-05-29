from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor, validate_universal_extraction_payload  # noqa: E402
from alumina_sol_extractor.stage4.io import parse_json_payload, read_json, read_jsonl, write_json, write_jsonl  # noqa: E402
from alumina_sol_extractor.stage4.validators import build_stage4_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Stage4A universal raw outputs without calling VLM.")
    parser.add_argument("--batch-report")
    parser.add_argument("--selected-papers-csv")
    parser.add_argument("--outputs-dir", default=str(PROJECT_ROOT / "data" / "outputs"))
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--stage4-subdir", default="stage4_vision_spectra_universal")
    parser.add_argument("--routing-mode", default="universal_compact")
    parser.add_argument("--report-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--backup-dir-name", default="_backup_before_replay")
    return parser.parse_args()


def _load_batch_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_selected_rows(path: Path, *, outputs_dir: Path, stage3_subdir: str, stage4_subdir: str, routing_mode: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        selected_rows = list(csv.DictReader(handle))
    rows: list[dict[str, str]] = []
    for row in selected_rows:
        category = row["category"]
        paper_id = row["paper_id"]
        paper_output_dir = outputs_dir / category / paper_id
        rows.append(
            {
                "category": category,
                "paper_id_guess": paper_id,
                "paper_output_dir": str(paper_output_dir),
                "stage3_dir": str(paper_output_dir / stage3_subdir),
                "stage4_dir": str(paper_output_dir / stage4_subdir),
                "routing_mode": routing_mode,
            }
        )
    return rows


def _latest_raw_by_figure_id(raw_outputs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in raw_outputs:
        figure_id = str(record.get("figure_id") or "")
        if not figure_id:
            continue
        if record.get("raw_response"):
            latest[figure_id] = record
        elif figure_id not in latest:
            latest[figure_id] = record
    return latest


def _write_stage4a_validation_report(stage4_dir: Path, summary: dict[str, Any], *, routing_mode: str) -> None:
    lines = [
        "# Stage4A Validation Report",
        "",
        f"- routing_mode: {routing_mode}",
        f"- total_candidates: {summary.get('total_candidates', 0)}",
        f"- processed_count: {summary.get('processed_count', 0)}",
        f"- skipped_count: {summary.get('skipped_count', 0)}",
        f"- rescued_unknown_by_caption_count: {summary.get('rescued_unknown_by_caption_count', 0)}",
        f"- hard_failed_record_count: {summary.get('hard_failed_record_count', 0)}",
        "",
        "## Routing Reasons",
        "",
    ]
    for key, value in (summary.get("routing_reason_distribution") or {}).items():
        lines.append(f"- {key}: {value}")
    (stage4_dir / "stage4a_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _backup_file(path: Path, backup_dir: Path) -> str | None:
    if not path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / path.name
    shutil.copy2(path, target)
    return str(target)


def _existing_previous_extractions(stage4_dir: Path) -> list[dict[str, Any]]:
    extractions = read_jsonl(stage4_dir / "spectra_extractions.jsonl")
    by_figure: dict[str, dict[str, Any]] = {}
    for record in extractions:
        figure_id = str(record.get("figure_id") or "")
        if figure_id:
            by_figure[figure_id] = record
    return list(by_figure.values())


def replay_batch(
    *,
    batch_report: Path | None,
    selected_papers_csv: Path | None,
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    report_csv: Path,
    summary_json: Path,
    report_md: Path,
    materialize: bool,
    backup_dir_name: str,
) -> dict[str, Any]:
    if selected_papers_csv:
        rows = _load_selected_rows(
            selected_papers_csv,
            outputs_dir=outputs_dir,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
        )
    elif batch_report:
        rows = _load_batch_rows(batch_report)
    else:
        raise ValueError("Either --batch-report or --selected-papers-csv must be provided.")
    replay_rows: list[dict[str, Any]] = []
    total_old_success = 0
    total_old_failed = 0
    total_new_success = 0
    total_new_failed = 0
    backed_up_files: list[str] = []

    for row in rows:
        stage4_dir = Path(row["stage4_dir"])
        paper_output_dir = Path(row["paper_output_dir"])
        paper_id = row["paper_id_guess"]
        category = row["category"]

        old_success = len(read_jsonl(stage4_dir / "spectra_extractions.jsonl"))
        old_failed = len(read_jsonl(stage4_dir / "spectra_failed_records.jsonl"))
        total_old_success += old_success
        total_old_failed += old_failed

        extractor = Stage4VisionSpectraExtractor(
            paper_id=paper_id,
            output_dir=paper_output_dir,
            dry_run=True,
            routing_mode=row.get("routing_mode") or "universal_compact",
            stage3_subdir=Path(row["stage3_dir"]).name,
            stage4_subdir=stage4_dir.name,
        )
        figures = read_jsonl(paper_output_dir / "figures.jsonl")
        vision_inputs = read_jsonl(paper_output_dir / "vision_inputs.jsonl")
        evidence_objects = read_jsonl(Path(row["stage3_dir"]) / "evidence_objects.jsonl")
        stage3_schema = read_json(Path(row["stage3_dir"]) / "paper_extraction.schema_v2.json", default={}) or {}
        candidates = extractor._select_candidates(
            figures=figures,
            vision_inputs=vision_inputs,
            evidence_objects=evidence_objects,
            stage3_schema=stage3_schema,
        )

        raw_outputs = read_jsonl(stage4_dir / "raw_vlm_outputs.jsonl")
        latest_raw = _latest_raw_by_figure_id(raw_outputs)
        previous_extractions = {str(item.get("figure_id") or ""): item for item in _existing_previous_extractions(stage4_dir)}

        new_extractions: list[dict[str, Any]] = []
        new_failed: list[dict[str, Any]] = []
        used_raw_count = 0
        reused_previous_count = 0
        skipped_missing_raw = 0

        for candidate in candidates:
            if not candidate.get("send_to_vlm"):
                continue
            figure_id = str(candidate.get("figure_id") or "")
            raw_record = latest_raw.get(figure_id)
            if raw_record and raw_record.get("raw_response"):
                used_raw_count += 1
                parsed = parse_json_payload(str(raw_record.get("raw_response") or ""))
                parsed.setdefault("paper_id", paper_id)
                parsed.setdefault("figure_id", figure_id)
                parsed.setdefault("source_image_path", candidate.get("source_image_path"))
                parsed.setdefault("caption", candidate.get("caption"))
                parsed.setdefault("extraction_mode", "live")
                parsed.setdefault("extraction_model", (raw_record.get("response_payload") or {}).get("model"))
                result = validate_universal_extraction_payload(parsed, candidate)
                if result.get("ok"):
                    new_extractions.append(result["record"])
                else:
                    new_failed.append(
                        {
                            "figure_id": figure_id,
                            "figure_type": candidate.get("figure_type"),
                            "actual_figure_type": result.get("actual_figure_type"),
                            "schema_name": result.get("schema_name"),
                            "error_type": "schema_validation_failed",
                            "error_message": str(result.get("error_message") or "schema_validation_failed"),
                            "warnings": result.get("warnings", []),
                            "final_status": "failed",
                        }
                    )
                continue

            previous = previous_extractions.get(figure_id)
            if previous:
                reused_previous_count += 1
                new_extractions.append(previous)
            else:
                skipped_missing_raw += 1
                new_failed.append(
                    {
                        "figure_id": figure_id,
                        "figure_type": candidate.get("figure_type"),
                        "error_type": "missing_raw_response_for_replay",
                        "error_message": "missing_raw_response_for_replay",
                        "final_status": "failed",
                    }
                )

        summary = build_stage4_summary(candidates=candidates, extractions=new_extractions, failed_records=new_failed)

        if materialize:
            backup_dir = stage4_dir / backup_dir_name
            for filename in (
                "spectra_extractions.jsonl",
                "spectra_failed_records.jsonl",
                "stage4a_summary.json",
                "stage4a_validation_report.md",
            ):
                backed = _backup_file(stage4_dir / filename, backup_dir)
                if backed:
                    backed_up_files.append(backed)
            write_jsonl(new_extractions, stage4_dir / "spectra_extractions.jsonl")
            write_jsonl(new_failed, stage4_dir / "spectra_failed_records.jsonl")
            write_json(stage4_dir / "stage4a_summary.json", summary)
            _write_stage4a_validation_report(stage4_dir, summary, routing_mode=row.get("routing_mode") or "universal_compact")

        total_new_success += len(new_extractions)
        total_new_failed += len(new_failed)
        replay_rows.append(
            {
                "category": category,
                "paper_id": paper_id,
                "old_successful_extractions": old_success,
                "old_failed_records": old_failed,
                "new_successful_extractions": len(new_extractions),
                "new_failed_records": len(new_failed),
                "used_raw_response_count": used_raw_count,
                "reused_previous_success_count": reused_previous_count,
                "skipped_missing_raw_count": skipped_missing_raw,
                "schema_validation_failed_count": sum(1 for item in new_failed if item.get("error_type") == "schema_validation_failed"),
            }
        )

    summary = {
        "paper_count": len(replay_rows),
        "old_successful_extractions": total_old_success,
        "old_failed_records": total_old_failed,
        "new_successful_extractions": total_new_success,
        "new_failed_records": total_new_failed,
        "schema_validation_failed_count_after": sum(row["schema_validation_failed_count"] for row in replay_rows),
        "materialized": materialize,
        "backed_up_file_count": len(backed_up_files),
        "backup_files": backed_up_files,
    }

    report_csv.parent.mkdir(parents=True, exist_ok=True)
    with report_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(replay_rows[0].keys()) if replay_rows else [
            "category",
            "paper_id",
            "old_successful_extractions",
            "old_failed_records",
            "new_successful_extractions",
            "new_failed_records",
            "used_raw_response_count",
            "reused_previous_success_count",
            "skipped_missing_raw_count",
            "schema_validation_failed_count",
        ])
        writer.writeheader()
        writer.writerows(replay_rows)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Stage4A Universal Replay Report",
        "",
        f"- paper_count: {summary['paper_count']}",
        f"- old_successful_extractions: {summary['old_successful_extractions']}",
        f"- old_failed_records: {summary['old_failed_records']}",
        f"- new_successful_extractions: {summary['new_successful_extractions']}",
        f"- new_failed_records: {summary['new_failed_records']}",
        f"- schema_validation_failed_count_after: {summary['schema_validation_failed_count_after']}",
        f"- materialized: {summary['materialized']}",
        f"- backed_up_file_count: {summary['backed_up_file_count']}",
        "",
    ]
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    replay_batch(
        batch_report=Path(args.batch_report) if args.batch_report else None,
        selected_papers_csv=Path(args.selected_papers_csv) if args.selected_papers_csv else None,
        outputs_dir=Path(args.outputs_dir),
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        routing_mode=args.routing_mode,
        report_csv=Path(args.report_csv),
        summary_json=Path(args.summary_json),
        report_md=Path(args.report_md),
        materialize=args.materialize,
        backup_dir_name=args.backup_dir_name,
    )


if __name__ == "__main__":
    main()
