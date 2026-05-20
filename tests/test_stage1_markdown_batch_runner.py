from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "run_stage1_markdown_batch.py"
SPEC = importlib.util.spec_from_file_location("run_stage1_markdown_batch_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


MANIFEST_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "markdown_expected_path",
    "markdown_status",
    "output_dir",
]


def test_stage1_batch_runner_filters_category_limit_and_ids_and_preserves_numbering(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs"
    (pdf_dir / "fiber_process").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "mechanism").mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "source_id": "fiber_process__001_alpha",
            "category": "fiber_process",
            "paper_id_guess": "001_alpha",
            "pdf_path": str(pdf_dir / "fiber_process" / "001_alpha.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "001_alpha.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "001_alpha"),
        },
        {
            "source_id": "fiber_process__002_beta",
            "category": "fiber_process",
            "paper_id_guess": "002_beta",
            "pdf_path": str(pdf_dir / "fiber_process" / "002_beta.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "002_beta.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "002_beta"),
        },
        {
            "source_id": "mechanism__003_gamma",
            "category": "mechanism",
            "paper_id_guess": "003_gamma",
            "pdf_path": str(pdf_dir / "mechanism" / "003_gamma.pdf"),
            "markdown_expected_path": str(markdown_dir / "mechanism" / "003_gamma.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "mechanism" / "003_gamma"),
        },
    ]
    for row in rows:
        Path(row["pdf_path"]).write_text("fake pdf", encoding="utf-8")
    _write_manifest(manifest_path, rows)

    stage1_called = {"count": 0}

    def fail_if_called(*args, **kwargs):
        stage1_called["count"] += 1
        raise AssertionError("dry-run should not call Stage 1")

    monkeypatch.setattr(MODULE, "run_stage1_pdf_to_markdown", fail_if_called)

    result = MODULE.run_stage1_markdown_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        report_dir=report_dir,
        category="fiber_process",
        paper_ids=["001_alpha", "mechanism__003_gamma"],
        limit=1,
        dry_run=True,
    )

    assert stage1_called["count"] == 0
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["source_id"] == "fiber_process__001_alpha"
    assert row["status"] == "dry_run_planned"
    assert row["markdown_path"].endswith(str(Path("fiber_process") / "001_alpha.md"))


def test_stage1_batch_runner_normalizes_manifest_category_filter(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "Applications"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "001_alpha.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": "applications__001_alpha",
                "category": "Applications",
                "paper_id_guess": "001_alpha",
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_dir / "applications" / "001_alpha.md"),
                "markdown_status": "not_generated",
                "output_dir": str(tmp_path / "outputs" / "applications" / "001_alpha"),
            }
        ],
    )

    monkeypatch.setattr(MODULE, "run_stage1_pdf_to_markdown", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not call Stage 1")))

    result = MODULE.run_stage1_markdown_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        report_dir=report_dir,
        category="applications",
        dry_run=True,
    )

    assert len(result["rows"]) == 1
    assert result["rows"][0]["category"] == "applications"
    assert result["rows"][0]["markdown_path"].endswith(str(Path("applications") / "001_alpha.md"))


def test_stage1_batch_runner_skips_existing_and_short_markdown_by_default(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "fiber_process"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    long_md = markdown_dir / "fiber_process" / "001_alpha.md"
    short_md = markdown_dir / "fiber_process" / "002_beta.md"
    long_md.parent.mkdir(parents=True, exist_ok=True)
    long_md.write_text("A" * 1500, encoding="utf-8")
    short_md.write_text("short", encoding="utf-8")

    rows = [
        {
            "source_id": "fiber_process__001_alpha",
            "category": "fiber_process",
            "paper_id_guess": "001_alpha",
            "pdf_path": str(pdf_dir / "001_alpha.pdf"),
            "markdown_expected_path": str(long_md),
            "markdown_status": "exists_ok",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "001_alpha"),
        },
        {
            "source_id": "fiber_process__002_beta",
            "category": "fiber_process",
            "paper_id_guess": "002_beta",
            "pdf_path": str(pdf_dir / "002_beta.pdf"),
            "markdown_expected_path": str(short_md),
            "markdown_status": "exists_too_short",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "002_beta"),
        },
    ]
    for row in rows:
        Path(row["pdf_path"]).write_text("fake pdf", encoding="utf-8")
    _write_manifest(manifest_path, rows)

    monkeypatch.setattr(MODULE, "run_stage1_pdf_to_markdown", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should skip existing markdown")))

    result = MODULE.run_stage1_markdown_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        report_dir=report_dir,
        min_markdown_chars=1000,
    )

    statuses = {row["source_id"]: row["status"] for row in result["rows"]}
    assert statuses["fiber_process__001_alpha"] == "skipped_existing"
    assert statuses["fiber_process__002_beta"] == "skipped_too_short_existing"


def test_stage1_batch_runner_force_retries_and_continues_after_failures(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "fiber_process"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    existing_md = markdown_dir / "fiber_process" / "001_alpha.md"
    existing_md.parent.mkdir(parents=True, exist_ok=True)
    existing_md.write_text("old", encoding="utf-8")

    rows = [
        {
            "source_id": "fiber_process__001_alpha",
            "category": "fiber_process",
            "paper_id_guess": "001_alpha",
            "pdf_path": str(pdf_dir / "001_alpha.pdf"),
            "markdown_expected_path": str(existing_md),
            "markdown_status": "exists_too_short",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "001_alpha"),
        },
        {
            "source_id": "fiber_process__002_beta",
            "category": "fiber_process",
            "paper_id_guess": "002_beta",
            "pdf_path": str(pdf_dir / "002_beta.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "002_beta.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "002_beta"),
        },
        {
            "source_id": "fiber_process__003_missing",
            "category": "fiber_process",
            "paper_id_guess": "003_missing",
            "pdf_path": str(pdf_dir / "003_missing.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "003_missing.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "003_missing"),
        },
        {
            "source_id": "fiber_process__004_gamma",
            "category": "fiber_process",
            "paper_id_guess": "004_gamma",
            "pdf_path": str(pdf_dir / "004_gamma.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "004_gamma.md"),
            "markdown_status": "not_generated",
            "output_dir": str(tmp_path / "outputs" / "fiber_process" / "004_gamma"),
        },
    ]
    for row in rows:
        if "003_missing" not in row["source_id"]:
            Path(row["pdf_path"]).write_text("fake pdf", encoding="utf-8")
    _write_manifest(manifest_path, rows)

    monkeypatch.setattr(MODULE, "build_runtime_settings", lambda *args, **kwargs: {"paths": {}})
    calls: list[str] = []

    def fake_stage1(project_root: Path, settings: dict) -> SimpleNamespace:
        input_pdf = Path(settings["paths"]["input_pdf"])
        calls.append(input_pdf.stem)
        if input_pdf.stem == "002_beta":
            raise RuntimeError("simulated stage1 failure")
        output_dir = Path(settings["paths"]["markdown_output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        cleaned_path = output_dir / f"{input_pdf.stem}.md"
        cleaned_path.write_text(f"markdown for {input_pdf.stem}", encoding="utf-8")
        return SimpleNamespace(
            cleaned_markdown_path=cleaned_path,
            output_dir=Path(settings["paths"]["output_dir"]) / input_pdf.stem,
            converter_outputs={},
        )

    monkeypatch.setattr(MODULE, "run_stage1_pdf_to_markdown", fake_stage1)

    result = MODULE.run_stage1_markdown_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        report_dir=report_dir,
        force=True,
        continue_on_error=True,
    )

    statuses = {row["source_id"]: row for row in result["rows"]}
    assert calls == ["001_alpha", "002_beta", "004_gamma"]
    assert statuses["fiber_process__001_alpha"]["status"] == "success"
    assert statuses["fiber_process__001_alpha"]["overwritten"] is True
    assert statuses["fiber_process__002_beta"]["status"] == "failed"
    assert statuses["fiber_process__003_missing"]["status"] == "missing_pdf"
    assert statuses["fiber_process__004_gamma"]["status"] == "success"
    assert (markdown_dir / "fiber_process" / "004_gamma.md").exists()


def test_stage1_batch_runner_writes_reports_and_summary(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "mechanism"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "010_theta.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")

    row = {
        "source_id": "mechanism__010_theta",
        "category": "mechanism",
        "paper_id_guess": "010_theta",
        "pdf_path": str(pdf_path),
        "markdown_expected_path": str(markdown_dir / "mechanism" / "010_theta.md"),
        "markdown_status": "not_generated",
        "output_dir": str(tmp_path / "outputs" / "mechanism" / "010_theta"),
    }
    _write_manifest(manifest_path, [row])

    monkeypatch.setattr(MODULE, "build_runtime_settings", lambda *args, **kwargs: {"paths": {}})
    monkeypatch.setattr(
        MODULE,
        "run_stage1_pdf_to_markdown",
        lambda project_root, settings: _fake_stage1_success(settings),
    )

    result = MODULE.run_stage1_markdown_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        report_dir=report_dir,
    )

    report_csv = Path(result["report_csv_path"])
    report_md = Path(result["report_md_path"])
    summary_json = Path(result["summary_json_path"])
    assert report_csv.exists()
    assert report_md.exists()
    assert summary_json.exists()

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["success_count"] == 1
    assert summary["by_category"]["mechanism"]["success_count"] == 1
    assert "build_supplementary_manifest" in report_md.read_text(encoding="utf-8")

    with report_csv.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["status"] == "success"


def test_stage1_batch_runner_missing_manifest_has_clear_error(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing.csv"
    try:
        MODULE.run_stage1_markdown_batch(manifest=missing_manifest)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")

    assert "build_source_manifest.py" in message
    assert "Sorted_Database" in message


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _fake_stage1_success(settings: dict) -> SimpleNamespace:
    input_pdf = Path(settings["paths"]["input_pdf"])
    output_dir = Path(settings["paths"]["markdown_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = output_dir / f"{input_pdf.stem}.md"
    cleaned_path.write_text("A" * 1200, encoding="utf-8")
    return SimpleNamespace(
        cleaned_markdown_path=cleaned_path,
        output_dir=Path(settings["paths"]["output_dir"]) / input_pdf.stem,
        converter_outputs={},
    )
