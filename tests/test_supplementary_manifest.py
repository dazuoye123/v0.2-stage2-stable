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


def test_build_supplementary_manifest_classifies_strong_and_weak_evidence(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"
    supplementary_dir = tmp_path / "supplementary"

    cases = [
        {
            "paper_id": "paper-strong-en",
            "category": "fiber_process",
            "pdf_text": "Supplementary Information available online. DOI 10.1000/xyz123.",
            "markdown_text": "# Strong EN\nSupporting Information is available.\nhttps://example.com/supplementary.pdf",
            "local_file": "",
        },
        {
            "paper_id": "paper-strong-zh",
            "category": "mechanism",
            "pdf_text": "\u8be6\u89c1\u8865\u5145\u6750\u6599",
            "markdown_text": "# Strong ZH\n\u8865\u5145\u6750\u6599",
            "local_file": "",
        },
        {
            "paper_id": "paper-weak-appendix",
            "category": "rheology",
            "pdf_text": "\u9644\u5f55",
            "markdown_text": "# Weak Appendix\n\u9644\u5f55",
            "local_file": "",
        },
        {
            "paper_id": "paper-weak-online",
            "category": "applications",
            "pdf_text": "available online",
            "markdown_text": "# Weak Online\navailable online",
            "local_file": "",
        },
        {
            "paper_id": "paper-doi-only",
            "category": "fiber_process",
            "pdf_text": "DOI 10.2000/abc456",
            "markdown_text": "# DOI Only\nDOI: 10.2000/abc456",
            "local_file": "",
        },
        {
            "paper_id": "paper-url-strong",
            "category": "mechanism",
            "pdf_text": "https://example.org/supporting-data.zip",
            "markdown_text": "# Strong URL\nhttps://example.org/supporting-data.zip",
            "local_file": "",
        },
        {
            "paper_id": "paper-url-weak",
            "category": "applications",
            "pdf_text": "https://publisher.example.com/article/123",
            "markdown_text": "# Weak URL\nhttps://publisher.example.com/article/123",
            "local_file": "",
        },
        {
            "paper_id": "paper-local-file",
            "category": "rheology",
            "pdf_text": "",
            "markdown_text": "# Local File\n",
            "local_file": "table-s1.xlsx",
        },
    ]

    for case in cases:
        pdf_path = pdf_dir / case["category"] / f"{case['paper_id']}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text(case["pdf_text"], encoding="utf-8")
        markdown_path = markdown_dir / case["category"] / f"{case['paper_id']}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(case["markdown_text"], encoding="utf-8")
        if case["local_file"]:
            local_dir = supplementary_dir / case["category"] / case["paper_id"]
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / case["local_file"]).write_text("fake", encoding="utf-8")

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

    strong_en = rows_by_paper["paper-strong-en"]
    assert strong_en["supplementary_detected"] == "true"
    assert strong_en["evidence_strength"] == "strong"
    assert "markdown:supporting information" in strong_en["strong_evidence_hits"]
    assert "url:https://example.com/supplementary.pdf" in strong_en["strong_evidence_hits"]

    strong_zh = rows_by_paper["paper-strong-zh"]
    assert strong_zh["supplementary_detected"] == "true"
    assert strong_zh["evidence_strength"] == "strong"
    assert "\u8865\u5145\u6750\u6599" in strong_zh["strong_evidence_hits"]

    weak_appendix = rows_by_paper["paper-weak-appendix"]
    assert weak_appendix["supplementary_detected"] == "unknown"
    assert weak_appendix["evidence_strength"] == "weak"
    assert "\u9644\u5f55" in weak_appendix["weak_evidence_hits"]
    assert str(weak_appendix["needs_manual_review"]).lower() == "true"

    weak_online = rows_by_paper["paper-weak-online"]
    assert weak_online["supplementary_detected"] == "unknown"
    assert weak_online["evidence_strength"] == "weak"
    assert "available online" in weak_online["weak_evidence_hits"]

    doi_only = rows_by_paper["paper-doi-only"]
    assert doi_only["supplementary_detected"] == "unknown"
    assert doi_only["evidence_strength"] == "weak"
    assert "doi:10.2000/abc456" in doi_only["weak_evidence_hits"]

    strong_url = rows_by_paper["paper-url-strong"]
    assert strong_url["supplementary_detected"] == "true"
    assert strong_url["evidence_strength"] == "strong"
    assert "supporting-data.zip" in strong_url["supplementary_url"]

    weak_url = rows_by_paper["paper-url-weak"]
    assert weak_url["supplementary_detected"] == "unknown"
    assert weak_url["evidence_strength"] == "weak"
    assert weak_url["supplementary_url"] == "https://publisher.example.com/article/123"

    local_file = rows_by_paper["paper-local-file"]
    assert local_file["supplementary_detected"] == "true"
    assert local_file["evidence_strength"] == "strong"
    assert local_file["supplementary_local_path"].endswith("table-s1.xlsx")
    assert local_file["confidence"] == "high"

    summary = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
    assert summary["strong_evidence_count"] == 4
    assert summary["weak_only_count"] == 4
    assert summary["no_evidence_count"] == 0
    assert summary["needs_manual_review_count"] == 4


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
    markdown_path.write_text("Supporting Information available online", encoding="utf-8")

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


def test_supplementary_manifest_default_dry_run_does_not_download(tmp_path: Path) -> None:
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
                "needs_manual_download": "true",
                "confidence": "high",
                "evidence_strength": "strong",
                "strong_evidence_hits": "url:https://example.com/supplementary.pdf",
                "weak_evidence_hits": "",
                "needs_manual_review": "false",
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
    assert report_rows[0]["action"] == "dry_run_candidate"
    assert Path(report_rows[0]["destination_path"]).exists() is False
    assert Path(result["report_path"]).exists()
    assert Path(result["summary_path"]).exists()
