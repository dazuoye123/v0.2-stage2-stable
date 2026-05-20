from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


REPORT_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "supplementary_url",
    "confidence",
    "needs_manual_download",
    "action",
    "status",
    "destination_path",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run-first downloader for detected supplementary candidates with URLs.")
    parser.add_argument("--manifest", default=str(PROJECT_ROOT / "data" / "batch_manifest" / "supplementary_manifest.csv"))
    parser.add_argument("--supplementary-dir", default=str(PROJECT_ROOT / "data" / "supplementary"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "data" / "batch_validation_reports"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    parser.add_argument("--execute", dest="dry_run", action="store_false")
    parser.add_argument("--manual-only", action="store_true")
    return parser.parse_args()


def download_supplementary_candidates(
    *,
    manifest: Path | str,
    supplementary_dir: Path | str,
    out_dir: Path | str,
    limit: int = 0,
    dry_run: bool = True,
    manual_only: bool = False,
) -> dict[str, Any]:
    manifest = Path(manifest)
    supplementary_dir = Path(supplementary_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_csv(manifest)
    candidates = [
        row
        for row in rows
        if _as_bool(row.get("supplementary_detected")) and row.get("supplementary_url")
    ]
    if manual_only:
        candidates = [row for row in candidates if _as_bool(row.get("needs_manual_download"))]
    if limit > 0:
        candidates = candidates[:limit]

    report_rows: list[dict[str, Any]] = []
    for row in candidates:
        destination_path = supplementary_dir / row.get("category", "uncategorized") / row.get("paper_id_guess", "") / Path(row["supplementary_url"]).name
        action = "dry_run_candidate" if dry_run else "download"
        status = "not_attempted"
        error = ""
        if not dry_run:
            if destination_path.exists():
                status = "downloaded"
                action = "skip_existing"
            else:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    urllib.request.urlretrieve(row["supplementary_url"], destination_path)
                    status = "downloaded"
                except (urllib.error.URLError, ValueError, OSError) as exc:
                    status = "failed"
                    error = str(exc)
        report_rows.append(
            {
                "source_id": row.get("source_id", ""),
                "category": row.get("category", ""),
                "paper_id_guess": row.get("paper_id_guess", ""),
                "supplementary_url": row.get("supplementary_url", ""),
                "confidence": row.get("confidence", ""),
                "needs_manual_download": row.get("needs_manual_download", ""),
                "action": action,
                "status": status,
                "destination_path": str(destination_path),
                "error": error,
            }
        )

    report_path = out_dir / "supplementary_download_report.csv"
    summary_path = out_dir / "supplementary_download_summary.json"
    _write_csv(report_path, report_rows, REPORT_FIELDS)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest),
        "dry_run": dry_run,
        "manual_only": manual_only,
        "candidate_count": len(candidates),
        "downloaded_count": sum(1 for row in report_rows if row["status"] == "downloaded"),
        "failed_count": sum(1 for row in report_rows if row["status"] == "failed"),
        "report_path": str(report_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"rows": report_rows, "summary": summary, "report_path": str(report_path), "summary_path": str(summary_path)}


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def main() -> None:
    args = parse_args()
    result = download_supplementary_candidates(
        manifest=args.manifest,
        supplementary_dir=args.supplementary_dir,
        out_dir=args.out_dir,
        limit=args.limit,
        dry_run=args.dry_run,
        manual_only=args.manual_only,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
