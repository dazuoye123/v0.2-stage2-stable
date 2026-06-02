from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alumina_sol_extractor.dataset_fusion.exporters import write_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Stage 5 batch outputs for completeness/integrity.")
    parser.add_argument("--report-dir", default="data/analysis_outputs_stage5_batch")
    return parser.parse_args()


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _safe_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def check_stage5_batch_outputs(report_dir: Path) -> dict[str, Any]:
    paper_summary_path = report_dir / "stage5_batch_paper_summary.csv"
    rows: list[dict[str, Any]] = []
    with paper_summary_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    checks: list[dict[str, Any]] = []
    warning_count = 0
    error_count = 0
    for row in rows:
        paper_dir = Path(row["paper_dir"])
        dataset_dir = paper_dir / "final_dataset"
        export_dir = dataset_dir / "link_aware_exports"
        warnings: list[str] = []
        errors: list[str] = []
        status = row.get("status")
        process_steps_count = _safe_int(row.get("process_steps_count"))
        spectra_count_used = _safe_int(row.get("spectra_count_used"))
        evidence_objects_count = _safe_int(row.get("evidence_objects_count"))
        dry_run_excluded = _safe_int(row.get("stage4a_dry_run_excluded_count"))
        evidence_links_count = _safe_int(row.get("evidence_parameter_links_count"))
        spectra_links_count = _safe_int(row.get("spectra_parameter_links_count"))
        process_step_links_count = _safe_int(row.get("process_step_parameter_links_count"))

        required_success_files = [
            dataset_dir / "stage5_summary.json",
            export_dir / "final_parameters_linked.csv",
            export_dir / "sample_parameter_matrix.csv",
        ]
        if status == "success":
            for path in required_success_files:
                if not path.exists():
                    errors.append(f"missing_file:{path.name}")
            if process_steps_count > 0 and _count_csv_rows(export_dir / "process_steps_table.csv") == 0:
                errors.append("empty_process_steps_table")
            if spectra_count_used > 0 and not (export_dir / "spectra_parameter_links.csv").exists():
                warnings.append("missing_spectra_parameter_links_csv")
            if spectra_count_used > 0 and spectra_links_count == 0:
                warnings.append("zero_spectra_links")
            if evidence_objects_count > 0 and not (export_dir / "evidence_parameter_links.csv").exists():
                warnings.append("missing_evidence_parameter_links_csv")
            if evidence_objects_count > 0 and evidence_links_count == 0:
                warnings.append("zero_evidence_links")
            if process_steps_count > 0 and process_step_links_count == 0:
                warnings.append("zero_process_step_links")
        if dry_run_excluded > 0:
            warnings.append("dry_run_excluded_present")

        integrity_status = "ok"
        if errors:
            integrity_status = "error"
            error_count += 1
        elif warnings:
            integrity_status = "warning"
            warning_count += 1

        checks.append(
            {
                "category": row["category"],
                "paper_id": row["paper_id"],
                "status": status,
                "integrity_status": integrity_status,
                "warnings": "|".join(warnings),
                "errors": "|".join(errors),
            }
        )

    report_lines = [
        "# Stage 5 Batch Integrity Report",
        "",
        f"- papers_checked: {len(checks)}",
        f"- warnings: {warning_count}",
        f"- errors: {error_count}",
        "",
        "## 重点问题",
    ]
    issue_rows = [row for row in checks if row["integrity_status"] != "ok"]
    if issue_rows:
        for row in issue_rows[:50]:
            report_lines.append(
                f"- {row['category']}/{row['paper_id']}: {row['integrity_status']} | warnings={row['warnings'] or 'none'} | errors={row['errors'] or 'none'}"
            )
    else:
        report_lines.append("- 无")

    _write_csv(report_dir / "stage5_batch_integrity_check.csv", checks)
    write_markdown(report_dir / "stage5_batch_integrity_report.md", "\n".join(report_lines))
    return {
        "integrity_check_path": str(report_dir / "stage5_batch_integrity_check.csv"),
        "integrity_report_path": str(report_dir / "stage5_batch_integrity_report.md"),
        "warnings": warning_count,
        "errors": error_count,
    }


def main() -> int:
    args = parse_args()
    report_dir = _resolve_path(args.report_dir)
    result = check_stage5_batch_outputs(report_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
