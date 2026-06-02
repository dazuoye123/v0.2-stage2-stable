from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dspy_modules.settings import load_project_dotenv  # noqa: E402
from alumina_sol_extractor.stage4.extractor import Stage4VisionSpectraExtractor  # noqa: E402
from alumina_sol_extractor.stage4.io import write_json, write_jsonl  # noqa: E402
from alumina_sol_extractor.stage4.processed_index import merge_stage4_records_by_figure_id  # noqa: E402
from alumina_sol_extractor.stage4.validators import build_stage4_summary  # noqa: E402


DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "analysis_outputs_stage4a_audit" / "stage4a_missing_or_retry_manifest.csv"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
DEFAULT_SUMMARY_JSON = PROJECT_ROOT / "data" / "analysis_outputs_stage4a_audit" / "rerun_summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rerun or replay Stage4A figures from a coverage audit manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--outputs-dir", default=str(DEFAULT_OUTPUTS_DIR))
    parser.add_argument("--stage3-subdir", default="stage3_twopass")
    parser.add_argument("--stage4-subdir", default="stage4_vision_spectra_universal")
    parser.add_argument("--routing-mode", default="universal_compact")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--run-live", action="store_true", default=False)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--status-filter", default="")
    parser.add_argument("--force-nonretryable", action="store_true", default=False)
    parser.add_argument("--force-true-nonretryable", action="store_true", default=False)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--submit-delay-seconds", type=float, default=0.0)
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.run_live:
        args.dry_run = True
    result = execute_rerun_from_manifest(
        manifest_path=Path(args.manifest),
        outputs_dir=Path(args.outputs_dir),
        stage3_subdir=args.stage3_subdir,
        stage4_subdir=args.stage4_subdir,
        routing_mode=args.routing_mode,
        run_live=args.run_live,
        limit=args.limit,
        status_filter=_parse_status_filter(args.status_filter),
        force_nonretryable=args.force_nonretryable,
        force_true_nonretryable=args.force_true_nonretryable,
        workers=args.workers,
        submit_delay_seconds=args.submit_delay_seconds,
        summary_json=Path(args.summary_json),
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def execute_rerun_from_manifest(
    *,
    manifest_path: Path,
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
    run_live: bool,
    limit: int,
    status_filter: set[str] | None,
    force_nonretryable: bool = False,
    force_true_nonretryable: bool = False,
    workers: int = 1,
    submit_delay_seconds: float = 0.0,
    summary_json: Path = DEFAULT_SUMMARY_JSON,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    rows = _load_manifest_rows(manifest_path)
    skipped_missing_images = 0
    skipped_unreadable_images = 0
    filtered_rows = []
    for row in rows:
        if not _row_is_selected_for_rerun(
            row,
            status_filter=status_filter,
            force_nonretryable=force_nonretryable,
            force_true_nonretryable=force_true_nonretryable,
        ):
            continue
        if force_true_nonretryable:
            image_check = _resolve_rerun_image_for_row(row, outputs_dir=outputs_dir)
            if image_check["skip_reason"] == "missing_image":
                skipped_missing_images += 1
                continue
            if image_check["skip_reason"] == "unreadable_image":
                skipped_unreadable_images += 1
                continue
            row = dict(row)
            resolved_path = image_check.get("resolved_image_path")
            if resolved_path:
                row["resolved_image_path"] = resolved_path
        filtered_rows.append(row)
    if limit > 0:
        filtered_rows = filtered_rows[:limit]

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in filtered_rows:
        grouped[(row["category"], row["paper_id"])].append(row)

    normalized_workers = max(1, int(workers or 1))

    summary: dict[str, Any] = {
        "manifest_path": str(manifest_path),
        "selected_figure_count": len(filtered_rows),
        "selected_paper_count": len(grouped),
        "run_live": bool(run_live),
        "workers": normalized_workers,
        "submit_delay_seconds": float(submit_delay_seconds or 0.0),
        "status_filter": sorted(status_filter or []),
        "force_nonretryable": bool(force_nonretryable),
        "force_true_nonretryable": bool(force_true_nonretryable),
        "planned_by_status": dict(Counter(row.get("status") or "unknown" for row in filtered_rows)),
        "planned_by_action": dict(Counter(row.get("suggested_action") or "unknown" for row in filtered_rows)),
        "per_paper": [],
        "executed_papers": 0,
        "executed_figures": 0,
        "success_papers": 0,
        "failed_papers": 0,
        "success_figures": 0,
        "failed_figures": 0,
        "live_call_enabled": bool(run_live),
        "skipped_missing_images": skipped_missing_images,
        "skipped_unreadable_images": skipped_unreadable_images,
    }

    if run_live:
        load_project_dotenv(PROJECT_ROOT)

    paper_plans: list[dict[str, Any]] = []
    for (category, paper_id), paper_rows in sorted(grouped.items()):
        figure_ids = [row["figure_id"] for row in paper_rows if row.get("figure_id")]
        paper_plan = {
            "category": category,
            "paper_id": paper_id,
            "figure_count": len(figure_ids),
            "figure_ids": figure_ids,
            "statuses": sorted({row.get("status") or "unknown" for row in paper_rows}),
            "suggested_actions": sorted({row.get("suggested_action") or "unknown" for row in paper_rows}),
            "resolved_image_paths": {row.get("figure_id"): row.get("resolved_image_path") for row in paper_rows if row.get("resolved_image_path")},
            "summary": None,
            "error_message": None,
            "elapsed_seconds": 0.0,
        }
        summary["per_paper"].append(paper_plan)
        paper_plans.append({"plan": paper_plan, "rows": paper_rows})

    if run_live:
        if normalized_workers == 1:
            for paper_task in paper_plans:
                task_result = _execute_paper_rerun_task(
                    category=paper_task["plan"]["category"],
                    paper_id=paper_task["plan"]["paper_id"],
                    figure_rows=paper_task["rows"],
                    outputs_dir=outputs_dir,
                    stage3_subdir=stage3_subdir,
                    stage4_subdir=stage4_subdir,
                    routing_mode=routing_mode,
                )
                _apply_task_result(summary, paper_task["plan"], task_result)
        else:
            with ThreadPoolExecutor(max_workers=normalized_workers) as executor:
                future_to_task = {}
                for paper_task in paper_plans:
                    future = executor.submit(
                        _execute_paper_rerun_task,
                        category=paper_task["plan"]["category"],
                        paper_id=paper_task["plan"]["paper_id"],
                        figure_rows=paper_task["rows"],
                        outputs_dir=outputs_dir,
                        stage3_subdir=stage3_subdir,
                        stage4_subdir=stage4_subdir,
                        routing_mode=routing_mode,
                    )
                    future_to_task[future] = paper_task
                    if submit_delay_seconds > 0:
                        time.sleep(submit_delay_seconds)
                for future in as_completed(future_to_task):
                    paper_task = future_to_task[future]
                    try:
                        task_result = future.result()
                    except Exception as exc:  # pragma: no cover - defensive fallback
                        task_result = {
                            "ok": False,
                            "summary": None,
                            "error_message": str(exc),
                            "error_type": type(exc).__name__,
                            "traceback": traceback.format_exc(limit=5),
                            "elapsed_seconds": 0.0,
                        }
                    _apply_task_result(summary, paper_task["plan"], task_result)

    summary["elapsed_seconds"] = round(time.perf_counter() - started_at, 6)

    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"rows": filtered_rows, "summary": summary}


def _row_is_selected_for_rerun(
    row: dict[str, str],
    *,
    status_filter: set[str] | None,
    force_nonretryable: bool,
    force_true_nonretryable: bool,
) -> bool:
    status = str(row.get("status") or "").strip()
    retryable = _to_bool(row.get("retryable"))
    priority = str(row.get("priority") or "").strip()
    if status_filter and status not in status_filter:
        return False
    if force_true_nonretryable:
        return bool(str(row.get("resolved_image_path") or row.get("image_path") or "").strip())
    if force_nonretryable and status == "failed_nonretryable":
        return True
    return retryable or priority in {"P0", "P1", "P2", "P3"}


def _load_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_status_filter(value: str) -> set[str] | None:
    items = {item.strip() for item in str(value or "").split(",") if item.strip()}
    return items or None


def _to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _resolve_rerun_image_for_row(
    row: dict[str, str],
    *,
    outputs_dir: Path,
) -> dict[str, str | None]:
    candidate_paths = [
        str(row.get("resolved_image_path") or "").strip(),
        str(row.get("image_path") or "").strip(),
    ]
    seen: set[str] = set()
    for candidate in candidate_paths:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        resolved = _resolve_existing_path(candidate, outputs_dir=outputs_dir)
        if resolved is None:
            continue
        readable, error_message = _image_is_readable(resolved)
        if readable:
            return {"resolved_image_path": str(resolved), "skip_reason": None, "error_message": None}
        return {
            "resolved_image_path": str(resolved),
            "skip_reason": "unreadable_image",
            "error_message": error_message,
        }
    return {"resolved_image_path": None, "skip_reason": "missing_image", "error_message": None}


def _resolve_existing_path(path_value: str, *, outputs_dir: Path) -> Path | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    possibilities = []
    if candidate.is_absolute():
        possibilities.append(candidate)
    else:
        possibilities.extend([outputs_dir / candidate, PROJECT_ROOT / candidate, candidate])
    for option in possibilities:
        try:
            if option.exists() and option.is_file():
                return option
        except OSError:
            continue
    return None


def _image_is_readable(path: Path) -> tuple[bool, str | None]:
    try:
        if path.stat().st_size <= 0:
            return False, "empty_file"
    except OSError as exc:
        return False, str(exc)
    try:
        with Image.open(path) as image:
            image.verify()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _run_live_for_manifest_paper(
    *,
    category: str,
    paper_id: str,
    figure_rows: list[dict[str, str]],
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
) -> dict[str, Any]:
    paper_output_dir = outputs_dir / category / paper_id
    extractor = Stage4VisionSpectraExtractor(
        paper_id=paper_id,
        output_dir=paper_output_dir,
        dry_run=False,
        routing_mode=routing_mode,
        stage3_subdir=stage3_subdir,
        stage4_subdir=stage4_subdir,
        candidate_source="stage2-selected",
    )
    if not hasattr(extractor, "build_candidate_plan"):
        return extractor.run()
    plan = extractor.build_candidate_plan(create_stage4_dir=True)
    stage4_dir = plan["stage4_dir"]
    previous_extractions = plan["previous_extractions"]
    previous_raw_outputs = plan["previous_raw_outputs"]
    previous_failed_records = plan["previous_failed_records"]
    config_warnings = list(plan["config_warnings"])

    row_by_figure_id = {str(row.get("figure_id") or ""): row for row in figure_rows}
    candidates = []
    for candidate in plan["candidates"]:
        figure_id = str(candidate.get("figure_id") or "")
        if figure_id not in row_by_figure_id:
            continue
        row = row_by_figure_id[figure_id]
        resolved_image_path = str(row.get("resolved_image_path") or "").strip()
        updated = dict(candidate)
        if resolved_image_path:
            updated["source_image_path"] = resolved_image_path
            updated["vision_image_path"] = resolved_image_path
        updated["send_to_vlm"] = True
        updated["will_call_vlm"] = True
        updated["figure_processing_action"] = "new_live"
        updated["figure_processing_reason"] = row.get("reason") or row.get("status") or "manifest_requested_rerun"
        updated["rerun_reason"] = updated["figure_processing_reason"]
        updated["skip_reason"] = None
        candidates.append(updated)

    extractions, raw_outputs, failed_records, client_warnings = extractor._run_extractions(  # noqa: SLF001
        candidates,
        previous_extractions=previous_extractions,
        previous_raw_outputs=previous_raw_outputs,
    )
    config_warnings.extend(client_warnings)
    replaced_figure_ids = {
        str(candidate.get("figure_id") or "").strip()
        for candidate in candidates
        if candidate.get("figure_id")
    }
    final_extractions = merge_stage4_records_by_figure_id(
        previous_extractions,
        extractions,
        replaced_figure_ids=replaced_figure_ids,
    )
    final_raw_outputs = merge_stage4_records_by_figure_id(
        previous_raw_outputs,
        raw_outputs,
        replaced_figure_ids=replaced_figure_ids,
    )
    final_failed_records = merge_stage4_records_by_figure_id(
        previous_failed_records,
        failed_records,
        replaced_figure_ids=replaced_figure_ids,
    )
    summary = build_stage4_summary(
        candidates=[*plan["candidates"], *candidates],
        extractions=final_extractions,
        failed_records=final_failed_records,
        config_warnings=config_warnings,
    )
    write_jsonl(final_extractions, stage4_dir / "spectra_extractions.jsonl")
    write_jsonl(final_raw_outputs, stage4_dir / "raw_vlm_outputs.jsonl")
    write_jsonl(final_failed_records, stage4_dir / "spectra_failed_records.jsonl")
    write_json(stage4_dir / "stage4a_summary.json", summary)
    write_json(stage4_dir / "stage4_summary.json", summary)
    return summary


def _execute_paper_rerun_task(
    *,
    category: str,
    paper_id: str,
    figure_rows: list[dict[str, str]],
    outputs_dir: Path,
    stage3_subdir: str,
    stage4_subdir: str,
    routing_mode: str,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        result = _run_live_for_manifest_paper(
            category=category,
            paper_id=paper_id,
            figure_rows=figure_rows,
            outputs_dir=outputs_dir,
            stage3_subdir=stage3_subdir,
            stage4_subdir=stage4_subdir,
            routing_mode=routing_mode,
        )
        return {
            "ok": True,
            "summary": result,
            "error_message": None,
            "error_type": None,
            "traceback": None,
            "elapsed_seconds": round(time.perf_counter() - started_at, 6),
        }
    except Exception as exc:
        return {
            "ok": False,
            "summary": None,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(limit=5),
            "elapsed_seconds": round(time.perf_counter() - started_at, 6),
        }


def _apply_task_result(
    summary: dict[str, Any],
    paper_plan: dict[str, Any],
    task_result: dict[str, Any],
) -> None:
    figure_count = int(paper_plan.get("figure_count") or 0)
    summary["executed_papers"] += 1
    summary["executed_figures"] += figure_count
    paper_plan["summary"] = task_result.get("summary")
    paper_plan["error_message"] = task_result.get("error_message")
    paper_plan["elapsed_seconds"] = float(task_result.get("elapsed_seconds") or 0.0)
    if task_result.get("error_type"):
        paper_plan["error_type"] = task_result["error_type"]
    if task_result.get("traceback"):
        paper_plan["traceback"] = task_result["traceback"]

    if task_result.get("ok"):
        summary["success_papers"] += 1
        summary["success_figures"] += figure_count
    else:
        summary["failed_papers"] += 1
        summary["failed_figures"] += figure_count


if __name__ == "__main__":
    main()
