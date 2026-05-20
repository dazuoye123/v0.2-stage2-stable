from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


SOURCE_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "build_source_manifest.py"
SOURCE_SPEC = importlib.util.spec_from_file_location("build_source_manifest_script_for_supp", SOURCE_SCRIPT_PATH)
SOURCE_MODULE = importlib.util.module_from_spec(SOURCE_SPEC)
assert SOURCE_SPEC and SOURCE_SPEC.loader
SOURCE_SPEC.loader.exec_module(SOURCE_MODULE)

SUPP_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "build_supplementary_manifest.py"
SUPP_SPEC = importlib.util.spec_from_file_location("build_supplementary_manifest_script", SUPP_SCRIPT_PATH)
SUPP_MODULE = importlib.util.module_from_spec(SUPP_SPEC)
assert SUPP_SPEC and SUPP_SPEC.loader
SUPP_SPEC.loader.exec_module(SUPP_MODULE)

DOWNLOAD_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "download_supplementary_candidates.py"
DOWNLOAD_SPEC = importlib.util.spec_from_file_location("download_supplementary_candidates_script", DOWNLOAD_SCRIPT_PATH)
DOWNLOAD_MODULE = importlib.util.module_from_spec(DOWNLOAD_SPEC)
assert DOWNLOAD_SPEC and DOWNLOAD_SPEC.loader
DOWNLOAD_SPEC.loader.exec_module(DOWNLOAD_MODULE)


def test_build_supplementary_manifest_uses_simple_keyword_detection(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"
    supplementary_dir = tmp_path / "supplementary"

    cases = [
        {
            "paper_id": "paper-supp-info",
            "category": "fiber_process",
            "pdf_text": "Supplementary Information",
            "markdown_text": "# Paper\nSupplementary Information",
        },
        {
            "paper_id": "paper-supporting-info",
            "category": "applications",
            "pdf_text": "Supporting Information",
            "markdown_text": "# Paper\nSupporting Information",
        },
        {
            "paper_id": "paper-supp-material",
            "category": "mechanism",
            "pdf_text": "Supplementary Material",
            "markdown_text": "# Paper\nSupplementary Material",
        },
        {
            "paper_id": "paper-esi",
            "category": "rheology",
            "pdf_text": "ESI",
            "markdown_text": "# Paper\nESI",
        },
        {
            "paper_id": "paper-cn-material",
            "category": "fiber_process",
            "pdf_text": "\u8865\u5145\u6750\u6599",
            "markdown_text": "# Paper\n\u8865\u5145\u6750\u6599",
        },
        {
            "paper_id": "paper-cn-info",
            "category": "mechanism",
            "pdf_text": "\u8865\u5145\u4fe1\u606f",
            "markdown_text": "# Paper\n\u8865\u5145\u4fe1\u606f",
        },
        {
            "paper_id": "paper-appendix",
            "category": "applications",
            "pdf_text": "Appendix",
            "markdown_text": "# Paper\nAppendix",
        },
        {
            "paper_id": "paper-cn-appendix",
            "category": "rheology",
            "pdf_text": "\u9644\u5f55",
            "markdown_text": "# Paper\n\u9644\u5f55",
        },
        {
            "paper_id": "paper-available-online",
            "category": "fiber_process",
            "pdf_text": "available online",
            "markdown_text": "# Paper\navailable online",
        },
        {
            "paper_id": "paper-doi-only",
            "category": "mechanism",
            "pdf_text": "DOI 10.2000/abc456",
            "markdown_text": "# Paper\nDOI: 10.2000/abc456",
        },
        {
            "paper_id": "paper-url-only",
            "category": "applications",
            "pdf_text": "https://publisher.example.com/article/123",
            "markdown_text": "# Paper\nhttps://publisher.example.com/article/123",
        },
        {
            "paper_id": "paper-keyword-no-url",
            "category": "rheology",
            "pdf_text": "Supplementary Data",
            "markdown_text": "# Paper\nSupplementary Data",
        },
        {
            "paper_id": "paper-keyword-with-url",
            "category": "fiber_process",
            "pdf_text": "See Supporting Information https://example.com/files/s1.pdf",
            "markdown_text": "# Paper\nSee Supporting Information\nhttps://example.com/files/s1.pdf",
        },
    ]

    for case in cases:
        pdf_path = pdf_dir / case["category"] / f"{case['paper_id']}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text(case["pdf_text"], encoding="utf-8")
        markdown_path = markdown_dir / case["category"] / f"{case['paper_id']}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(case["markdown_text"], encoding="utf-8")

    source_result = SOURCE_MODULE.build_source_manifest(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        out_dir=out_dir,
        min_markdown_chars=5,
    )
    result = SUPP_MODULE.build_supplementary_manifest(
        source_manifest=source_result["csv_path"],
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        supplementary_dir=supplementary_dir,
        out_dir=out_dir,
    )

    rows_by_paper = {row["paper_id_guess"]: row for row in result["rows"]}

    assert rows_by_paper["paper-supp-info"]["supplementary_detected"] == "true"
    assert rows_by_paper["paper-supporting-info"]["supplementary_detected"] == "true"
    assert rows_by_paper["paper-supp-material"]["supplementary_detected"] == "true"
    assert rows_by_paper["paper-esi"]["supplementary_detected"] == "true"
    assert rows_by_paper["paper-cn-material"]["supplementary_detected"] == "true"
    assert rows_by_paper["paper-cn-info"]["supplementary_detected"] == "true"

    assert rows_by_paper["paper-appendix"]["supplementary_detected"] == "false"
    assert rows_by_paper["paper-cn-appendix"]["supplementary_detected"] == "false"
    assert rows_by_paper["paper-available-online"]["supplementary_detected"] == "false"
    assert rows_by_paper["paper-doi-only"]["supplementary_detected"] == "false"
    assert rows_by_paper["paper-url-only"]["supplementary_detected"] == "false"

    keyword_no_url = rows_by_paper["paper-keyword-no-url"]
    assert keyword_no_url["supplementary_detected"] == "true"
    assert keyword_no_url["needs_manual_download"] is True
    assert keyword_no_url["supplementary_url"] == ""
    assert keyword_no_url["download_status"] == "manual_required"

    keyword_with_url = rows_by_paper["paper-keyword-with-url"]
    assert keyword_with_url["supplementary_detected"] == "true"
    assert keyword_with_url["supplementary_url"] == "https://example.com/files/s1.pdf"
    assert keyword_with_url["needs_manual_download"] is False
    assert keyword_with_url["download_status"] == "not_attempted"

    summary = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
    assert summary["supplementary_detected_count"] == 8
    assert summary["no_supplementary_detected_count"] == 5
    assert summary["possible_supplementary_count"] == summary["supplementary_detected_count"]


def test_supplementary_manifest_normalizes_category_from_source_manifest(tmp_path: Path) -> None:
    source_manifest = tmp_path / "source_manifest.csv"
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    supplementary_dir = tmp_path / "supplementary"
    out_dir = tmp_path / "batch_manifest"
    pdf_path = pdf_dir / "Applications" / "001_app.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_text("Supplementary Information DOI 10.1000/abc123", encoding="utf-8")
    markdown_path = markdown_dir / "applications" / "001_app.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("Supporting Information", encoding="utf-8")

    with source_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "category",
                "paper_id_guess",
                "pdf_path",
                "markdown_expected_path",
                "markdown_actual_path",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_id": "applications__001_app",
                "category": "Applications",
                "paper_id_guess": "001_app",
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
            }
        )

    result = SUPP_MODULE.build_supplementary_manifest(
        source_manifest=source_manifest,
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        supplementary_dir=supplementary_dir,
        out_dir=out_dir,
    )

    row = result["rows"][0]
    assert row["category"] == "applications"
    assert row["markdown_path"].endswith(str(Path("applications") / "001_app.md"))


def test_supplementary_manifest_default_dry_run_only_targets_detected_urls(tmp_path: Path) -> None:
    manifest_path = tmp_path / "supplementary_manifest.csv"
    supplementary_dir = tmp_path / "supplementary"
    out_dir = tmp_path / "reports"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPP_MODULE.SUPPLEMENTARY_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "source_id": "fiber_process__paper_a",
                "category": "fiber_process",
                "paper_id_guess": "paper-a",
                "doi": "10.1000/xyz123",
                "title_guess": "Paper A",
                "main_pdf_path": "",
                "markdown_path": "",
                "supplementary_detected": "true",
                "detection_method": "markdown_keyword",
                "supplementary_source": "markdown_link",
                "supplementary_url": "https://example.com/supplementary.pdf",
                "supplementary_file_type": "pdf",
                "supplementary_local_path": "",
                "download_status": "not_attempted",
                "needs_manual_download": "false",
                "confidence": "high",
                "detection_hits": "Supplementary Information",
                "evidence_strength": "strong",
                "strong_evidence_hits": "Supplementary Information",
                "weak_evidence_hits": "",
                "notes": "",
            }
        )
        writer.writerow(
            {
                "source_id": "fiber_process__paper_b",
                "category": "fiber_process",
                "paper_id_guess": "paper-b",
                "doi": "10.1000/xyz124",
                "title_guess": "Paper B",
                "main_pdf_path": "",
                "markdown_path": "",
                "supplementary_detected": "false",
                "detection_method": "none",
                "supplementary_source": "unknown",
                "supplementary_url": "https://example.com/not-supplementary.pdf",
                "supplementary_file_type": "pdf",
                "supplementary_local_path": "",
                "download_status": "unavailable",
                "needs_manual_download": "false",
                "confidence": "low",
                "detection_hits": "",
                "evidence_strength": "none",
                "strong_evidence_hits": "",
                "weak_evidence_hits": "",
                "notes": "",
            }
        )

    result = DOWNLOAD_MODULE.download_supplementary_candidates(
        manifest=manifest_path,
        supplementary_dir=supplementary_dir,
        out_dir=out_dir,
        dry_run=True,
        manual_only=False,
    )

    assert result["summary"]["dry_run"] is True
    report_rows = result["rows"]
    assert len(report_rows) == 1
    assert report_rows[0]["source_id"] == "fiber_process__paper_a"
    assert report_rows[0]["action"] == "dry_run_candidate"
    assert Path(report_rows[0]["destination_path"]).exists() is False
    assert Path(result["report_path"]).exists()
    assert Path(result["summary_path"]).exists()
