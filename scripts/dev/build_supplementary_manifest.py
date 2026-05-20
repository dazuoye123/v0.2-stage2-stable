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

from alumina_sol_extractor.utils.batch_categories import (
    BATCH_CATEGORY_PRIORITY,
    CANONICAL_BATCH_CATEGORIES,
    normalize_batch_category,
)

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
    "detection_hits",
    "evidence_strength",
    "strong_evidence_hits",
    "weak_evidence_hits",
    "notes",
]

STRONG_TEXT_PATTERNS = {
    "Supplementary Information": re.compile(r"\bsupplementary information\b", re.IGNORECASE),
    "Supporting Information": re.compile(r"\bsupporting information\b", re.IGNORECASE),
    "Supplementary Material": re.compile(r"\bsupplementary material\b", re.IGNORECASE),
    "Supplementary Materials": re.compile(r"\bsupplementary materials\b", re.IGNORECASE),
    "Electronic Supplementary Material": re.compile(r"\belectronic supplementary material\b", re.IGNORECASE),
    "Electronic Supporting Information": re.compile(r"\belectronic supporting information\b", re.IGNORECASE),
    "ESI": re.compile(r"\besi\b", re.IGNORECASE),
    "Supporting Data": re.compile(r"\bsupporting data\b", re.IGNORECASE),
    "Supplementary Data": re.compile(r"\bsupplementary data\b", re.IGNORECASE),
    "Supplementary File": re.compile(r"\bsupplementary file\b", re.IGNORECASE),
    "Supporting File": re.compile(r"\bsupporting file\b", re.IGNORECASE),
    "See Supplementary Information": re.compile(r"\bsee supplementary information\b", re.IGNORECASE),
    "See Supporting Information": re.compile(r"\bsee supporting information\b", re.IGNORECASE),
    "Available in the Supporting Information": re.compile(
        r"\bavailable in the supporting information\b",
        re.IGNORECASE,
    ),
    "Available in the Supplementary Information": re.compile(
        r"\bavailable in the supplementary information\b",
        re.IGNORECASE,
    ),
    "\u8865\u5145\u4fe1\u606f": re.compile("\u8865\u5145\u4fe1\u606f"),
    "\u8865\u5145\u6750\u6599": re.compile("\u8865\u5145\u6750\u6599"),
    "\u652f\u6301\u4fe1\u606f": re.compile("\u652f\u6301\u4fe1\u606f"),
    "\u7535\u5b50\u8865\u5145\u6750\u6599": re.compile("\u7535\u5b50\u8865\u5145\u6750\u6599"),
    "\u8be6\u89c1\u8865\u5145\u6750\u6599": re.compile("\u8be6\u89c1\u8865\u5145\u6750\u6599"),
    "\u89c1\u8865\u5145\u6750\u6599": re.compile("\u89c1\u8865\u5145\u6750\u6599"),
    "\u8865\u5145\u6570\u636e": re.compile("\u8865\u5145\u6570\u636e"),
}
WEAK_NOTE_PATTERNS = {
    "\u9644\u5f55": re.compile("\u9644\u5f55"),
    "Appendix": re.compile(r"\bappendix\b", re.IGNORECASE),
    "available online": re.compile(r"\bavailable online\b", re.IGNORECASE),
    "online version": re.compile(r"\bonline version\b", re.IGNORECASE),
}
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a keyword-based supplementary-information manifest without downloading files."
    )
    parser.add_argument(
        "--source-manifest",
        default=str(PROJECT_ROOT / "data" / "batch_manifest" / "source_manifest.csv"),
    )
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
    summary = _build_summary(
        rows,
        source_manifest=source_manifest,
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        supplementary_dir=supplementary_dir,
    )
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
    category = normalize_batch_category(source_row.get("category"))
    paper_id_guess = source_row.get("paper_id_guess") or ""
    main_pdf_path = Path(source_row.get("pdf_path") or pdf_dir / f"{paper_id_guess}.pdf")
    markdown_path = Path(
        source_row.get("markdown_actual_path")
        or source_row.get("markdown_expected_path")
        or markdown_dir / category / f"{paper_id_guess}.md"
    )

    markdown_text = _read_text_if_exists(markdown_path)
    pdf_text = _read_pdf_like_text(main_pdf_path)
    combined_text = "\n".join(part for part in [markdown_text, pdf_text] if part)

    detection_hits = _collect_detection_hits(combined_text)
    weak_notes = _collect_weak_notes(combined_text)
    doi = _extract_first_doi(combined_text)
    urls = _extract_urls(combined_text)
    local_files = _discover_local_supplementary_files(
        supplementary_dir,
        category=category,
        paper_id_guess=paper_id_guess,
    )

    supplementary_detected = "true" if detection_hits else "false"
    confidence = "high" if supplementary_detected == "true" else "low"
    evidence_strength = "strong" if supplementary_detected == "true" else "none"

    notes: list[str] = []
    detection_methods: list[str] = []
    supplementary_source = "unknown"
    supplementary_url = ""
    needs_manual_download = False
    download_status = "unavailable"

    if detection_hits:
        detection_methods.extend(_infer_detection_methods(markdown_text, pdf_text, detection_hits))
        if urls:
            supplementary_url = urls[0]
            supplementary_source = "markdown_link" if markdown_text else "pdf_link"
            needs_manual_download = False
            download_status = "not_attempted"
            notes.append("supplementary keyword detected with url")
        else:
            supplementary_source = "unknown"
            needs_manual_download = True
            download_status = "manual_required"
            notes.append("supplementary keyword detected without url")
    else:
        detection_methods.append("none")
        if weak_notes:
            notes.append("non-supplementary weak phrases present")
        if doi:
            notes.append(f"doi detected: {doi}")
        if urls:
            notes.append("general url present without supplementary keyword")

    if local_files:
        notes.append("local supplementary files present")

    title_guess = _guess_title(markdown_text, paper_id_guess)
    supplementary_file_type = _infer_file_type(
        local_files[0] if local_files else supplementary_url
    )

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
        "supplementary_source": supplementary_source,
        "supplementary_url": supplementary_url,
        "supplementary_file_type": supplementary_file_type,
        "supplementary_local_path": "; ".join(str(path) for path in local_files),
        "download_status": download_status,
        "needs_manual_download": needs_manual_download,
        "confidence": confidence,
        "detection_hits": "; ".join(_unique_preserve_order(detection_hits)),
        "evidence_strength": evidence_strength,
        "strong_evidence_hits": "; ".join(_unique_preserve_order(detection_hits)),
        "weak_evidence_hits": "",
        "notes": "; ".join(_unique_preserve_order(notes + weak_notes)),
    }


def _build_summary(
    rows: list[dict[str, Any]],
    *,
    source_manifest: Path,
    pdf_dir: Path,
    markdown_dir: Path,
    supplementary_dir: Path,
) -> dict[str, Any]:
    category_names = sorted({normalize_batch_category(row["category"]) for row in rows} | set(CANONICAL_BATCH_CATEGORIES))
    by_category: dict[str, dict[str, int]] = {}
    for category in category_names:
        category_rows = [row for row in rows if row["category"] == category]
        by_category[category] = _count_summary_fields(category_rows)

    recommended_list = _recommend_download_or_manual_check(rows)
    summary_counts = _count_summary_fields(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest),
        "pdf_dir": str(pdf_dir),
        "markdown_dir": str(markdown_dir),
        "supplementary_dir": str(supplementary_dir),
        "total_sources": len(rows),
        "supplementary_detected_count": summary_counts["supplementary_detected_count"],
        "no_supplementary_detected_count": summary_counts["no_supplementary_detected_count"],
        "needs_manual_download_count": summary_counts["needs_manual_download_count"],
        "with_supplementary_url_count": summary_counts["with_supplementary_url_count"],
        "doi_detected_count": summary_counts["doi_detected_count"],
        "possible_supplementary_count": summary_counts["supplementary_detected_count"],
        "by_category": by_category,
        "recommended_download_or_manual_check_list": recommended_list,
    }


def _count_summary_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "supplementary_detected_count": sum(1 for row in rows if row["supplementary_detected"] == "true"),
        "no_supplementary_detected_count": sum(1 for row in rows if row["supplementary_detected"] == "false"),
        "needs_manual_download_count": sum(1 for row in rows if _is_true(row["needs_manual_download"])),
        "with_supplementary_url_count": sum(1 for row in rows if row["supplementary_url"]),
        "doi_detected_count": sum(1 for row in rows if row["doi"]),
    }


def _build_run_groups(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Supplementary Run Groups",
        "",
        "Priority order: fiber_process > mechanism > rheology > applications",
        "",
    ]
    for category in BATCH_CATEGORY_PRIORITY:
        category_rows = [row for row in rows if row["category"] == category]
        detected_rows = [row for row in category_rows if row["supplementary_detected"] == "true"]
        no_detect_rows = [row for row in category_rows if row["supplementary_detected"] == "false"]
        lines.append(f"## {category}")
        lines.append(f"- total: {len(category_rows)}")
        lines.append(f"- supplementary_detected_count: {len(detected_rows)}")
        lines.append(f"- no_supplementary_detected_count: {len(no_detect_rows)}")
        lines.append("")
        lines.append("### Detected Supplementary Candidates")
        lines.extend(
            [
                f"- {row['source_id']} | url={'yes' if row['supplementary_url'] else 'no'} | manual_download={row['needs_manual_download']}"
                for row in detected_rows[:10]
            ]
            or ["- none"]
        )
        lines.append("")
        lines.append("### No Supplementary Keyword Detected")
        lines.append(f"- count: {len(no_detect_rows)}")
        lines.append("")
    lines.extend(
        [
            "## Recommended Download / Manual Check List",
            *(
                [
                    f"- {source_id}"
                    for source_id in summary.get("recommended_download_or_manual_check_list", [])
                ]
                or ["- none"]
            ),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _recommend_download_or_manual_check(rows: list[dict[str, Any]]) -> list[str]:
    detected_rows = [row for row in rows if row["supplementary_detected"] == "true"]
    detected_rows.sort(
        key=lambda row: (
            0 if row["supplementary_url"] else 1,
            0 if row["doi"] else 1,
            BATCH_CATEGORY_PRIORITY.index(row["category"]) if row["category"] in BATCH_CATEGORY_PRIORITY else 999,
            row["source_id"],
        )
    )
    return [row["source_id"] for row in detected_rows[:10]]


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


def _collect_detection_hits(text: str) -> list[str]:
    return [label for label, pattern in STRONG_TEXT_PATTERNS.items() if pattern.search(text)]


def _collect_weak_notes(text: str) -> list[str]:
    return [label for label, pattern in WEAK_NOTE_PATTERNS.items() if pattern.search(text)]


def _infer_detection_methods(markdown_text: str, pdf_text: str, detection_hits: list[str]) -> list[str]:
    methods: list[str] = []
    if any(pattern.search(markdown_text) for pattern in STRONG_TEXT_PATTERNS.values() if markdown_text):
        methods.append("markdown_keyword")
    if any(pattern.search(pdf_text) for pattern in STRONG_TEXT_PATTERNS.values() if pdf_text):
        methods.append("pdf_text_keyword")
    if not methods and detection_hits:
        methods.append("markdown_keyword" if markdown_text else "pdf_text_keyword")
    return methods or ["none"]


def _extract_first_doi(text: str) -> str:
    match = DOI_PATTERN.search(text)
    return match.group(0).rstrip(".,);") if match else ""


def _extract_urls(text: str) -> list[str]:
    return [match.rstrip(").,;") for match in URL_PATTERN.findall(text)]


def _discover_local_supplementary_files(
    supplementary_dir: Path,
    *,
    category: str,
    paper_id_guess: str,
) -> list[Path]:
    candidates = [
        supplementary_dir / category / paper_id_guess,
        supplementary_dir / paper_id_guess,
    ]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            files.extend(sorted(path for path in candidate.rglob("*") if path.is_file()))
    return files


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


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


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
