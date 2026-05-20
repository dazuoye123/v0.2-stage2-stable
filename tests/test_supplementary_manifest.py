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


def test_build_supplementary_manifest_detects_keywords_doi_and_local_files(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"
    supplementary_dir = tmp_path / "supplementary"
    paper_id = "paper-a"

    (pdf_dir / "fiber_process").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "fiber_process" / f"{paper_id}.pdf").write_text(
        "Supplementary Information available online. DOI 10.1000/xyz123. https://example.com/supplementary.pdf",
        encoding="utf-8",
    )
    (markdown_dir / "fiber_process").mkdir(parents=True, exist_ok=True)
    (markdown_dir / "fiber_process" / f"{paper_id}.md").write_text(
        "# Example Title\nSupporting Information and ESI are available online.\nDOI: 10.1000/xyz123",
        encoding="utf-8",
    )
    (supplementary_dir / "fiber_process" / paper_id).mkdir(parents=True, exist_ok=True)
    (supplementary_dir / "fiber_process" / paper_id / "table-s1.xlsx").write_text("fake", encoding="utf-8")

    source_result = SOURCE_MODULE.build_source_manifest(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        out_dir=out_dir,
        min_markdown_chars=20,
    )
    result = SUPP_MODULE.build_supplementary_manifest(
        source_manifest=source_result["csv_path"],
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        supplementary_dir=supplementary_dir,
        out_dir=out_dir,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"].startswith("fiber_process__")
    assert row["supplementary_detected"] == "true"
    assert "markdown_keyword" in row["detection_method"]
    assert "pdf_text_keyword" in row["detection_method"]
    assert row["doi"] == "10.1000/xyz123"
    assert "supplementary.pdf" in row["supplementary_url"]
    assert row["supplementary_local_path"].endswith("table-s1.xlsx")
    assert row["supplementary_file_type"] in {"pdf", "xlsx"}

    summary = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
    assert summary["possible_supplementary_count"] == 1
    assert summary["doi_detected_count"] == 1


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
