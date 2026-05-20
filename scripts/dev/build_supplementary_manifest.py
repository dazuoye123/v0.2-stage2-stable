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
    "evidence_strength",
    "strong_evidence_hits",
    "weak_evidence_hits",
    "needs_manual_review",
    "notes",
]

STRONG_TEXT_PATTERNS = {
    "supplementary information": re.compile(r"\bsupplementary information\b", re.IGNORECASE),
    "supporting information": re.compile(r"\bsupporting information\b", re.IGNORECASE),
    "supplementary material": re.compile(r"\bsupplementary material\b", re.IGNORECASE),
    "electronic supplementary material": re.compile(r"\belectronic supplementary material\b", re.IGNORECASE),
    "esi": re.compile(r"\besi\b", re.IGNORECASE),
    "supplementary data": re.compile(r"\bsupplementary data\b", re.IGNORECASE),
    "supplementary file": re.compile(r"\bsupplementary file\b", re.IGNORECASE),
    "supporting file": re.compile(r"\bsupporting file\b", re.IGNORECASE),
    "supporting data": re.compile(r"\bsupporting data\b", re.IGNORECASE),
    "supplementary materials are available": re.compile(
        r"\bsupplementary materials are available\b", re.IGNORECASE
    ),
    "supporting information is available": re.compile(
        r"\bsupporting information is available\b", re.IGNORECASE
    ),
    "available in the supporting information": re.compile(
        r"\bavailable in the supporting information\b", re.IGNORECASE
    ),
    "see supporting information": re.compile(r"\bsee supporting information\b", re.IGNORECASE),
    "see supplementary information": re.compile(r"\bsee supplementary information\b", re.IGNORECASE),
    "\u8865\u5145\u6750\u6599": re.compile("\u8865\u5145\u6750\u6599"),
    "\u652f\u6301\u4fe1\u606f": re.compile("\u652f\u6301\u4fe1\u606f"),
    "\u7535\u5b50\u8865\u5145\u6750\u6599": re.compile("\u7535\u5b50\u8865\u5145\u6750\u6599"),
    "\u8be6\u89c1\u8865\u5145\u6750\u6599": re.compile("\u8be6\u89c1\u8865\u5145\u6750\u6599"),
    "\u89c1\u8865\u5145\u6750\u6599": re.compile("\u89c1\u8865\u5145\u6750\u6599"),
}
WEAK_TEXT_PATTERNS = {
    "\u9644\u5f55": re.compile("\u9644\u5f55"),
    "appendix": re.compile(r"\bappendix\b", re.IGNORECASE),
    "available online": re.compile(r"\bavailable online\b", re.IGNORECASE),
    "online version": re.compile(r"\bonline version\b", re.IGNORECASE),
}
STRONG_URL_TOKENS = ("supplementary", "supporting", "suppinfo", "suppl", "esm", "si")
FILE_LIKE_SUFFIXES = {".pdf", ".docx", ".xlsx", ".zip", ".csv", ".xls", ".doc"}
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a supplementary-information detection manifest without downloading files."
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

    markdown_hits = _collect_text_hits(markdown_text)
    pdf_hits = _collect_text_hits(pdf_text)
    doi = _extract_first_doi(combined_text)
    urls = _extract_urls(combined_text)
    url_analysis = _classify_urls(urls)
    local_files = _discover_local_supplementary_files(
        supplementary_dir,
        category=category,
        paper_id_guess=paper_id_guess,
    )

    strong_hits: list[str] = []
    weak_hits: list[str] = []
    notes: list[str] = []
    detection_methods: list[str] = []
    supplementary_sources: list[str] = []

    if markdown_hits["strong"] or markdown_hits["weak"]:
        detection_methods.append("markdown_keyword")
    if pdf_hits["strong"] or pdf_hits["weak"]:
        detection_methods.append("pdf_text_keyword")

    if markdown_hits["strong"]:
        notes.append("strong supplementary signal found in markdown")
        strong_hits.extend(f"markdown:{hit}" for hit in markdown_hits["strong"])
    if pdf_hits["strong"]:
        notes.append("strong supplementary signal found in pdf-like text")
        strong_hits.extend(f"pdf:{hit}" for hit in pdf_hits["strong"])
    if markdown_hits["weak"]:
        notes.append("weak supplementary signal found in markdown")
        weak_hits.extend(f"markdown:{hit}" for hit in markdown_hits["weak"])
    if pdf_hits["weak"]:
        notes.append("weak supplementary signal found in pdf-like text")
        weak_hits.extend(f"pdf:{hit}" for hit in pdf_hits["weak"])

    if local_files:
        detection_methods.append("manual_hint")
        supplementary_sources.append("local_file")
        notes.append("local supplementary files present")
        strong_hits.append("local_file")

    if doi:
        detection_methods.append("doi_metadata")
        weak_hits.append(f"doi:{doi}")
        notes.append("doi detected")

    if url_analysis["all_urls"]:
        detection_methods.append("markdown_link" if markdown_text else "pdf_link")
        notes.append("url detected in source text")
    if url_analysis["strong_urls"]:
        strong_hits.extend(url_analysis["strong_hit_labels"])
        supplementary_sources.append("markdown_link" if markdown_text else "pdf_link")
        notes.append("strong supplementary url detected")
    elif url_analysis["all_urls"]:
        weak_hits.extend(url_analysis["weak_hit_labels"])
        supplementary_sources.append("publisher_page")
        notes.append("only weak/general urls detected")

    evidence_strength = _determine_evidence_strength(
        strong_hits=strong_hits,
        weak_hits=weak_hits,
    )
    supplementary_detected = "true" if evidence_strength == "strong" else "unknown"
    needs_manual_review = evidence_strength == "weak"
    confidence = _determine_confidence(
        evidence_strength=evidence_strength,
        has_strong_url=bool(url_analysis["strong_urls"]),
        has_local_files=bool(local_files),
        has_doi=bool(doi),
    )
    if not detection_methods:
        detection_methods.append("none")
    if not supplementary_sources:
        supplementary_sources.append("unknown")

    preferred_urls = url_analysis["strong_urls"] or url_analysis["all_urls"]
    supplementary_url = "; ".join(_unique_preserve_order(preferred_urls))
    supplementary_source = "; ".join(_unique_preserve_order(supplementary_sources))
    if not local_files and supplementary_source == "unknown" and doi:
        supplementary_source = "doi_page"

    download_status = "not_attempted"
    needs_manual_download = bool(not local_files and url_analysis["strong_urls"])
    if local_files:
        download_status = "downloaded"
        needs_manual_download = False
    elif evidence_strength == "weak" and doi:
        download_status = "manual_required"

    title_guess = _guess_title(markdown_text, paper_id_guess)
    supplementary_file_type = _infer_file_type(
        local_files[0] if local_files else preferred_urls[0] if preferred_urls else ""
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
        "evidence_strength": evidence_strength,
        "strong_evidence_hits": "; ".join(_unique_preserve_order(strong_hits)),
        "weak_evidence_hits": "; ".join(_unique_preserve_order(weak_hits)),
        "needs_manual_review": needs_manual_review,
        "notes": "; ".join(_unique_preserve_order(notes)),
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

    detection_counts = Counter()
    for row in rows:
        for item in _split_semi(row.get("detection_method", "")):
            detection_counts[item] += 1

    recommended_smoke = _recommend_supplementary_smoke(rows)
    summary_counts = _count_summary_fields(rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_manifest),
        "pdf_dir": str(pdf_dir),
        "markdown_dir": str(markdown_dir),
        "supplementary_dir": str(supplementary_dir),
        "total_sources": len(rows),
        "possible_supplementary_count": summary_counts["supplementary_detected_true"],
        "doi_detected_count": summary_counts["doi_detected"],
        "strong_evidence_count": summary_counts["strong_evidence_count"],
        "weak_only_count": summary_counts["weak_only_count"],
        "no_evidence_count": summary_counts["no_evidence_count"],
        "needs_manual_review_count": summary_counts["needs_manual_review_count"],
        "high_confidence_count": summary_counts["high_confidence_count"],
        "medium_confidence_count": summary_counts["medium_confidence_count"],
        "low_confidence_count": summary_counts["low_confidence_count"],
        "category_summary": by_category,
        "detection_method_counts": dict(detection_counts),
        "recommended_supplementary_smoke_10": recommended_smoke,
    }


def _count_summary_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "supplementary_detected_true": sum(1 for row in rows if row["supplementary_detected"] == "true"),
        "supplementary_detected_unknown": sum(1 for row in rows if row["supplementary_detected"] == "unknown"),
        "doi_detected": sum(1 for row in rows if row["doi"]),
        "local_file_detected": sum(1 for row in rows if row["supplementary_local_path"]),
        "strong_evidence_count": sum(1 for row in rows if row["evidence_strength"] == "strong"),
        "weak_only_count": sum(1 for row in rows if row["evidence_strength"] == "weak"),
        "no_evidence_count": sum(1 for row in rows if row["evidence_strength"] == "none"),
        "needs_manual_review_count": sum(1 for row in rows if _is_true(row["needs_manual_review"])),
        "high_confidence_count": sum(1 for row in rows if row["confidence"] == "high"),
        "medium_confidence_count": sum(1 for row in rows if row["confidence"] == "medium"),
        "low_confidence_count": sum(1 for row in rows if row["confidence"] == "low"),
    }


def _build_run_groups(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    smoke_lines = [f"- {source_id}" for source_id in summary.get("recommended_supplementary_smoke_10", [])] or ["- none"]
    lines = [
        "# Supplementary Run Groups",
        "",
        "Priority order: fiber_process > mechanism > rheology > applications",
        "",
    ]
    for category in BATCH_CATEGORY_PRIORITY:
        category_rows = [row for row in rows if row["category"] == category]
        strong_hits = [row["source_id"] for row in category_rows if row["evidence_strength"] == "strong"]
        weak_hits = [row["source_id"] for row in category_rows if row["evidence_strength"] == "weak"]
        no_hits = [row["source_id"] for row in category_rows if row["evidence_strength"] == "none"]
        lines.append(f"## {category}")
        lines.append(f"- total: {len(category_rows)}")
        lines.append(f"- strong_evidence_count: {len(strong_hits)}")
        lines.append(f"- weak_only_count: {len(weak_hits)}")
        lines.append(f"- no_evidence_count: {len(no_hits)}")
        lines.append("")
        lines.append("### Strong Supplementary Candidates")
        lines.extend([f"- {source_id}" for source_id in strong_hits[:10]] or ["- none"])
        lines.append("")
        lines.append("### Weak / Manual Review Candidates")
        lines.extend([f"- {source_id}" for source_id in weak_hits[:10]] or ["- none"])
        lines.append("")
        lines.append("### No Evidence")
        lines.extend([f"- {source_id}" for source_id in no_hits[:10]] or ["- none"])
        lines.append("")
    lines.extend(
        [
            "## Recommended Supplementary Smoke 10",
            *smoke_lines,
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _recommend_supplementary_smoke(rows: list[dict[str, Any]]) -> list[str]:
    category_buckets: dict[str, list[dict[str, Any]]] = {}
    for category in BATCH_CATEGORY_PRIORITY:
        category_rows = [row for row in rows if row["category"] == category and row["evidence_strength"] == "strong"]
        category_buckets[category] = sorted(
            category_rows,
            key=lambda row: (
                0 if _has_strong_url(row) else 1,
                0 if row["doi"] else 1,
                0 if row["confidence"] == "high" else 1,
                row["source_id"],
            ),
        )

    picks: list[str] = []
    while len(picks) < 10:
        added = False
        for category in BATCH_CATEGORY_PRIORITY:
            bucket = category_buckets.get(category) or []
            if not bucket:
                continue
            picks.append(bucket.pop(0)["source_id"])
            added = True
            if len(picks) >= 10:
                break
        if not added:
            break
    return picks


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


def _collect_text_hits(text: str) -> dict[str, list[str]]:
    strong_hits = [label for label, pattern in STRONG_TEXT_PATTERNS.items() if pattern.search(text)]
    weak_hits = [label for label, pattern in WEAK_TEXT_PATTERNS.items() if pattern.search(text)]
    return {"strong": strong_hits, "weak": weak_hits}


def _extract_first_doi(text: str) -> str:
    match = DOI_PATTERN.search(text)
    return match.group(0).rstrip(".,);") if match else ""


def _extract_urls(text: str) -> list[str]:
    return [match.rstrip(").,;") for match in URL_PATTERN.findall(text)]


def _classify_urls(urls: list[str]) -> dict[str, list[str]]:
    strong_urls: list[str] = []
    strong_hit_labels: list[str] = []
    weak_hit_labels: list[str] = []
    for url in urls:
        if _looks_like_strong_supplementary_url(url):
            strong_urls.append(url)
            strong_hit_labels.append(f"url:{url}")
        else:
            weak_hit_labels.append(f"url:{url}")
    return {
        "all_urls": _unique_preserve_order(urls),
        "strong_urls": _unique_preserve_order(strong_urls),
        "strong_hit_labels": _unique_preserve_order(strong_hit_labels),
        "weak_hit_labels": _unique_preserve_order(weak_hit_labels),
    }


def _looks_like_strong_supplementary_url(url: str) -> bool:
    lowered = url.lower()
    if any(token in lowered for token in STRONG_URL_TOKENS):
        return True
    return Path(lowered.split("?", 1)[0]).suffix in FILE_LIKE_SUFFIXES and any(
        token in lowered for token in STRONG_URL_TOKENS
    )


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


def _determine_evidence_strength(*, strong_hits: list[str], weak_hits: list[str]) -> str:
    if strong_hits:
        return "strong"
    if weak_hits:
        return "weak"
    return "none"


def _determine_confidence(
    *,
    evidence_strength: str,
    has_strong_url: bool,
    has_local_files: bool,
    has_doi: bool,
) -> str:
    if evidence_strength == "strong":
        if has_strong_url or has_local_files:
            return "high"
        return "medium"
    if evidence_strength == "weak":
        return "medium" if has_doi else "low"
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


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _has_strong_url(row: dict[str, Any]) -> bool:
    return any(hit.startswith("url:") for hit in _split_semi(str(row.get("strong_evidence_hits", ""))))


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
