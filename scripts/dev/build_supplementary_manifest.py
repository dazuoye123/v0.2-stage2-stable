from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


SUPPLEMENTARY_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "doi",
    "title_guess",
    "main_pdf_path",
    "markdown_path",
    "supplementary_detected",
    "detection_method",
    "supplementary_source",
    "supplementary_url",
    "supplementary_file_type",
    "supplementary_local_path",
    "download_status",
    "needs_manual_download",
    "confidence",
    "notes",
]
SUPPLEMENTARY_KEYWORDS = [
    "supplementary information",
    "supporting information",
    "supplementary material",
    "electronic supplementary material",
    "esi",
    "see supplementary",
    "available online",
    "附录",
    "补充材料",
    "支持信息",
    "电子补充材料",
]
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a supplementary-information detection manifest without downloading files.")
    parser.add_argument("--source-manifest", default=str(PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"))
    parser.add_argument("--pdf-dir", default=str(PROJECT_ROOT / "data" / "pdfs"))
    parser.add_argument("--markdown-dir", default=str(PROJECT_ROOT / "data" / "markdown"))
    parser.add_argument("--supplementary-dir", default=str(PROJECT_ROOT / "data" / "supplementary"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "data" / "batch_manifest"))
    return parser.parse_args()


def build_supplementary_manifest(
    *,
    source_manifest: Path | str,
    pdf_dir: Path | str,
    markdown_dir: Path | str,
    supplementary_dir: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    source_manifest = Path(source_manifest)
    pdf_dir = Path(pdf_dir)
    markdown_dir = Path(markdown_dir)
    supplementary_dir = Path(supplementary_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_rows = _load_source_manifest(source_manifest)
    rows = [
        _build_supplementary_row(
            source_row,
            pdf_dir=pdf_dir,
            markdown_dir=markdown_dir,
            supplementary_dir=supplementary_dir,
        )
        for source_row in source_rows
    ]
    summary = _build_summary(rows, source_manifest=source_manifest, pdf_dir=pdf_dir, markdown_dir=markdown_dir, supplementary_dir=supplementary_dir)
    run_groups_md = _build_run_groups(rows, summary)

    csv_path = out_dir / "supplementary_manifest.csv"
    json_path = out_dir / "supplementary_manifest.json"
    summary_path = out_dir / "supplementary_summary.json"
    run_groups_path = out_dir / "supplementary_run_groups.md"
    _write_csv(csv_path, rows, SUPPLEMENTARY_FIELDS)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    run_groups_path.write_text(run_groups_md, encoding="utf-8")

    return {
        "rows": rows,
        "summary": summary,
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "summary_path": str(summary_path),
        "run_groups_path": str(run_groups_path),
    }


def _load_source_manifest(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        return list(json.loads(path.read_text(encoding="utf-8")))
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_supplementary_row(
    source_row: dict[str, Any],
    *,
    pdf_dir: Path,
    markdown_dir: Path,
    supplementary_dir: Path,
) -> dict[str, Any]:
    category = source_row.get("category") or "uncategorized"
    paper_id_guess = source_row.get("paper_id_guess") or ""
    main_pdf_path = Path(source_row.get("pdf_path") or pdf_dir / f"{paper_id_guess}.pdf")
    markdown_path = Path(source_row.get("markdown_actual_path") or source_row.get("markdown_expected_path") or markdown_dir / f"{paper_id_guess}.md")

    markdown_text = _read_text_if_exists(markdown_path)
    pdf_text = _read_pdf_like_text(main_pdf_path)
    combined_text = "\n".join(part for part in [markdown_text, pdf_text] if part)

    markdown_keyword_hit = _has_keyword(markdown_text)
    pdf_keyword_hit = _has_keyword(pdf_text)
    doi = _extract_first_doi(combined_text)
    urls = _extract_urls(combined_text)
    supplementary_urls = [url for url in urls if _looks_like_supplementary_url(url)] or urls
    local_files = _discover_local_supplementary_files(supplementary_dir, category=category, paper_id_guess=paper_id_guess)

    detection_methods: list[str] = []
    supplementary_sources: list[str] = []
    notes: list[str] = []
    if markdown_keyword_hit:
        detection_methods.append("markdown_keyword")
        notes.append("supplementary keyword found in markdown")
    if pdf_keyword_hit:
        detection_methods.append("pdf_text_keyword")
        notes.append("supplementary keyword found in pdf-like text")
    if local_files:
        detection_methods.append("manual_hint")
        supplementary_sources.append("local_file")
        notes.append("local supplementary files present")
    if supplementary_urls:
        supplementary_sources.append("markdown_link" if markdown_text else "pdf_link")
        notes.append("possible supplementary URL found")

    supplementary_detected = "true" if (markdown_keyword_hit or pdf_keyword_hit or local_files or supplementary_urls) else "unknown"
    if not detection_methods:
        detection_methods.append("none")
    if not supplementary_sources:
        supplementary_sources.append("unknown")

    confidence = _determine_confidence(
        keyword_hit=markdown_keyword_hit or pdf_keyword_hit,
        has_doi=bool(doi),
        has_url=bool(supplementary_urls),
        has_local_files=bool(local_files),
    )
    download_status = "not_attempted"
    needs_manual_download = bool(not local_files and supplementary_urls)
    if local_files:
        download_status = "downloaded"
        needs_manual_download = False
    elif supplementary_detected == "unknown":
        download_status = "manual_required" if doi else "not_attempted"

    title_guess = _guess_title(markdown_text, paper_id_guess)
    supplementary_file_type = _infer_file_type(local_files[0] if local_files else supplementary_urls[0] if supplementary_urls else "")

    return {
        "source_id": source_row.get("source_id", ""),
        "category": category,
        "paper_id_guess": paper_id_guess,
        "doi": doi,
        "title_guess": title_guess,
        "main_pdf_path": str(main_pdf_path),
        "markdown_path": str(markdown_path) if markdown_path.exists() else "",
        "supplementary_detected": supplementary_detected,
        "detection_method": "; ".join(_unique_preserve_order(detection_methods)),
        "supplementary_source": "; ".join(_unique_preserve_order(supplementary_sources)),
        "supplementary_url": "; ".join(_unique_preserve_order(supplementary_urls)),
        "supplementary_file_type": supplementary_file_type,
        "supplementary_local_path": "; ".join(str(path) for path in local_files),
        "download_status": download_status,
        "needs_manual_download": needs_manual_download,
        "confidence": confidence,
        "notes": "; ".join(notes),
    }


def _build_summary(
    rows: list[dict[str, Any]],
    *,
    source_manifest: Path,
    pdf_dir: Path,
    markdown_dir: Path,
    supplementary_dir: Path,
) -> dict[str, Any]:
    by_category: dict[str, dict[str, int]] = {}
    for category in sorted({row["category"] for row in rows} | {"applications", "fiber_process", "mechanism", "rheology"}):
        category_rows = [row for row in rows if row["category"] == category]
        by_category[category] = {
            "total": len(category_rows),
            "supplementary_detected_true": sum(1 for row in category_rows if row["supplementary_detected"] == "true"),
            "supplementary_detected_unknown": sum(1 for row in category_rows if row["supplementary_detected"] == "unknown"),
            "doi_detected": sum(1 for row in category_rows if row["doi"]),
            "local_file_detected": sum(1 for row in category_rows if row["supplementary_local_path"]),
        }
    detection_counts = Counter()
    for row in rows:
        for item in _split_semi(row.get("detection_method", "")):
            detection_counts[item] += 1
    recommended_smoke = _recommend_supplementary_smoke(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest),
        "pdf_dir": str(pdf_dir),
        "markdown_dir": str(markdown_dir),
        "supplementary_dir": str(supplementary_dir),
        "total_sources": len(rows),
        "possible_supplementary_count": sum(1 for row in rows if row["supplementary_detected"] == "true"),
        "doi_detected_count": sum(1 for row in rows if row["doi"]),
        "category_summary": by_category,
        "detection_method_counts": dict(detection_counts),
        "recommended_supplementary_smoke_10": recommended_smoke,
    }


def _build_run_groups(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    smoke_lines = [f"- {source_id}" for source_id in summary.get("recommended_supplementary_smoke_10", [])] or ["- none"]
    lines = [
        "# Supplementary Run Groups",
        "",
        "Priority order: fiber_process > mechanism > rheology > applications",
        "",
    ]
    for category in ["fiber_process", "mechanism", "rheology", "applications", "uncategorized"]:
        category_rows = [row for row in rows if row["category"] == category]
        lines.append(f"## {category}")
        lines.append(f"- total: {len(category_rows)}")
        lines.append(f"- supplementary_detected_true: {sum(1 for row in category_rows if row['supplementary_detected'] == 'true')}")
        hits = [row["source_id"] for row in category_rows if row["supplementary_detected"] == "true"]
        lines.append(f"- possible_supplementary_hits: {', '.join(hits[:10]) or 'none'}")
        lines.append("")
    lines.extend(
        [
            "## Recommended Supplementary Smoke 10",
            *smoke_lines,
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _recommend_supplementary_smoke(rows: list[dict[str, Any]]) -> list[str]:
    ranked = sorted(
        rows,
        key=lambda row: (
            0 if row["category"] == "fiber_process" else 1 if row["category"] == "mechanism" else 2 if row["category"] == "rheology" else 3,
            0 if row["confidence"] == "high" else 1 if row["confidence"] == "medium" else 2,
            0 if row["detection_method"] != "none" else 1,
            row["source_id"],
        ),
    )
    picks = [
        row["source_id"]
        for row in ranked
        if row["detection_method"] != "none" or row["doi"]
    ]
    return picks[:10]


def _read_text_if_exists(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf_like_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        parts = [(page.extract_text() or "") for page in reader.pages[:5]]
        text = "\n".join(parts).strip()
        if text:
            return text
    except Exception:
        pass
    try:
        return path.read_bytes().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _has_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in SUPPLEMENTARY_KEYWORDS)


def _extract_first_doi(text: str) -> str:
    match = DOI_PATTERN.search(text)
    return match.group(0).rstrip(".,);") if match else ""


def _extract_urls(text: str) -> list[str]:
    return [match.rstrip(").,;") for match in URL_PATTERN.findall(text)]


def _looks_like_supplementary_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ["supp", "support", "esi", "supplementary", "appendix"])


def _discover_local_supplementary_files(supplementary_dir: Path, *, category: str, paper_id_guess: str) -> list[Path]:
    candidates = [
        supplementary_dir / category / paper_id_guess,
        supplementary_dir / paper_id_guess,
    ]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            files.extend(sorted(path for path in candidate.rglob("*") if path.is_file()))
    return files


def _determine_confidence(*, keyword_hit: bool, has_doi: bool, has_url: bool, has_local_files: bool) -> str:
    if has_local_files or (keyword_hit and has_url):
        return "high"
    if keyword_hit or has_doi or has_url:
        return "medium"
    return "low"


def _guess_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:200]
    return fallback


def _infer_file_type(path_or_url: str | Path) -> str:
    suffix = Path(str(path_or_url)).suffix.lower()
    if suffix in {".pdf", ".docx", ".xlsx", ".zip", ".csv", ".png", ".jpg", ".jpeg", ".html"}:
        return suffix.lstrip(".")
    return "unknown"


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _split_semi(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


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


def main() -> None:
    args = parse_args()
    result = build_supplementary_manifest(
        source_manifest=args.source_manifest,
        pdf_dir=args.pdf_dir,
        markdown_dir=args.markdown_dir,
        supplementary_dir=args.supplementary_dir,
        out_dir=args.out_dir,
    )
    print(json.dumps({"summary": result["summary"], "csv_path": result["csv_path"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
