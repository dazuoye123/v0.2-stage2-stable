from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "run_stage2_preprocess_batch.py"
SPEC = importlib.util.spec_from_file_location("run_stage2_preprocess_batch_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


MANIFEST_FIELDS = [
    "source_id",
    "category",
    "paper_id_guess",
    "pdf_path",
    "markdown_expected_path",
    "markdown_actual_path",
    "output_dir",
]


def test_stage2_batch_runner_filters_category_limit_and_ids(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
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
            "markdown_actual_path": "",
            "output_dir": str(outputs_dir / "001_alpha"),
        },
        {
            "source_id": "fiber_process__002_beta",
            "category": "fiber_process",
            "paper_id_guess": "002_beta",
            "pdf_path": str(pdf_dir / "fiber_process" / "002_beta.pdf"),
            "markdown_expected_path": str(markdown_dir / "fiber_process" / "002_beta.md"),
            "markdown_actual_path": "",
            "output_dir": str(outputs_dir / "002_beta"),
        },
        {
            "source_id": "mechanism__003_gamma",
            "category": "mechanism",
            "paper_id_guess": "003_gamma",
            "pdf_path": str(pdf_dir / "mechanism" / "003_gamma.pdf"),
            "markdown_expected_path": str(markdown_dir / "mechanism" / "003_gamma.md"),
            "markdown_actual_path": "",
            "output_dir": str(outputs_dir / "003_gamma"),
        },
    ]
    for row in rows:
        Path(row["pdf_path"]).write_text("fake pdf", encoding="utf-8")
        md_path = Path(row["markdown_expected_path"])
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text("fake markdown", encoding="utf-8")
    _write_manifest(manifest_path, rows)

    stage2_called = {"count": 0}

    def fail_if_called(*args, **kwargs):
        stage2_called["count"] += 1
        raise AssertionError("dry-run should not call Stage 2")

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", fail_if_called)

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        category="fiber_process",
        paper_ids=["001_alpha", "mechanism__003_gamma"],
        limit=1,
        dry_run=True,
    )

    assert stage2_called["count"] == 0
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["source_id"] == "fiber_process__001_alpha"
    assert row["status"] == "dry_run_planned"
    assert row["paper_output_dir"].endswith(str(Path("outputs") / "fiber_process" / "001_alpha"))
    assert row["image_link_normalized"] is False
    assert row["copied_legacy_figure_count"] == 0


def test_stage2_batch_runner_missing_markdown_and_skip_existing(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "applications"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    existing_md = markdown_dir / "applications" / "001_alpha.md"
    existing_md.parent.mkdir(parents=True, exist_ok=True)
    existing_md.write_text("ready markdown", encoding="utf-8")
    summary_path = outputs_dir / "applications" / "001_alpha" / "figure_stage2_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"raw_mineru_image_count": 3, "final_figure_record_count": 2}), encoding="utf-8")

    rows = [
        {
            "source_id": "applications__001_alpha",
            "category": "applications",
            "paper_id_guess": "001_alpha",
            "pdf_path": str(pdf_dir / "001_alpha.pdf"),
            "markdown_expected_path": str(existing_md),
            "markdown_actual_path": "",
            "output_dir": str(outputs_dir / "001_alpha"),
        },
        {
            "source_id": "applications__002_beta",
            "category": "applications",
            "paper_id_guess": "002_beta",
            "pdf_path": str(pdf_dir / "002_beta.pdf"),
            "markdown_expected_path": str(markdown_dir / "applications" / "002_beta.md"),
            "markdown_actual_path": "",
            "output_dir": str(outputs_dir / "002_beta"),
        },
    ]
    for row in rows:
        Path(row["pdf_path"]).write_text("fake pdf", encoding="utf-8")
    _write_manifest(manifest_path, rows)

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should skip stage2 call")))

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
    )

    statuses = {row["source_id"]: row for row in result["rows"]}
    assert statuses["applications__001_alpha"]["status"] == "skipped_existing"
    assert statuses["applications__001_alpha"]["raw_mineru_image_count"] == 3
    assert statuses["applications__001_alpha"]["figures_all_count"] == 2
    assert statuses["applications__002_beta"]["status"] == "missing_markdown"


def test_stage2_batch_runner_force_runs_and_ignores_legacy_flat_output_dir(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "fiber_process"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / "fiber_process" / "002_beta.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "![legacy](data/outputs/002_beta/figures_all/fig1.png)\n"
        "![legacy-abs](G:/paper/Al-gel-sol/alumina_sol_extractor/data/outputs/002_beta/figures_all/fig2.png)\n",
        # Keep a Windows absolute legacy path too because real markdown may contain backslashes.
        encoding="utf-8",
    )
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8")
        + "![legacy-win](G:\\paper\\Al-gel-sol\\alumina_sol_extractor\\data\\outputs\\002_beta\\figures_all\\fig3.png)\n",
        encoding="utf-8",
    )
    pdf_path = pdf_dir / "002_beta.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    legacy_figures_all = outputs_dir / "002_beta" / "figures_all"
    legacy_figures_all.mkdir(parents=True, exist_ok=True)
    (legacy_figures_all / "fig1.png").write_text("img1", encoding="utf-8")
    (legacy_figures_all / "fig2.png").write_text("img2", encoding="utf-8")
    (legacy_figures_all / "fig3.png").write_text("img3", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": "fiber_process__002_beta",
                "category": "fiber_process",
                "paper_id_guess": "002_beta",
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / "002_beta"),
            }
        ],
    )

    calls: list[tuple[Path, Path, dict]] = []
    monkeypatch.setattr(MODULE, "build_runtime_settings", lambda *args, **kwargs: {"paths": {}, "figures": {"run_resnet": True, "run_clip": True}})

    def fake_stage2(project_root: Path, settings: dict, input_pdf: Path, paper_id: str, cleaned_markdown_path: Path, output_dir: Path):
        calls.append((Path(cleaned_markdown_path), Path(output_dir), settings))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "figures_all").mkdir(parents=True, exist_ok=True)
        (output_dir / "figures_all" / "fig1.png").write_text("img", encoding="utf-8")
        (output_dir / "figures_all" / "fig2.png").write_text("img2", encoding="utf-8")
        (output_dir / "figures_all" / "fig3.png").write_text("img3", encoding="utf-8")
        (output_dir / "figures.jsonl").write_text(
            json.dumps({"image_path": str(output_dir / "figures_all" / "fig1.png")}) + "\n",
            encoding="utf-8",
        )
        (output_dir / "vision_inputs.jsonl").write_text(
            json.dumps({"vision_image_path": str(output_dir / "figures_for_vision" / "fig1.png")}) + "\n",
            encoding="utf-8",
        )
        (output_dir / "figure_stage2_summary.json").write_text(
            json.dumps({"raw_mineru_image_count": 4, "final_figure_record_count": 1}),
            encoding="utf-8",
        )
        return SimpleNamespace(raw_mineru_image_count=4, tables_count=2, summary={"final_figure_record_count": 1})

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", fake_stage2)

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        force=True,
        disable_vision_classifiers=True,
    )

    assert len(calls) == 1
    cleaned_markdown_path, output_dir, settings = calls[0]
    assert cleaned_markdown_path == markdown_path
    assert output_dir == outputs_dir / "fiber_process" / "002_beta"
    assert settings["paths"]["output_dir"] == str(outputs_dir / "fiber_process")
    assert settings["paths"]["mineru_raw_dir"] == str(Path(MODULE.PROJECT_ROOT) / "data" / "mineru_raw" / "fiber_process")
    assert settings["figures"]["run_resnet"] is False
    assert settings["figures"]["run_clip"] is False
    normalized_markdown = markdown_path.read_text(encoding="utf-8")
    assert "data/outputs/fiber_process/002_beta/figures_all/fig1.png" in normalized_markdown
    assert "G:/paper/Al-gel-sol/alumina_sol_extractor/data/outputs/fiber_process/002_beta/figures_all/fig2.png" in normalized_markdown
    assert "G:\\paper\\Al-gel-sol\\alumina_sol_extractor\\data\\outputs\\fiber_process\\002_beta\\figures_all\\fig3.png" in normalized_markdown
    assert "data/outputs/002_beta/figures_all/fig1.png" not in normalized_markdown
    assert (outputs_dir / "fiber_process" / "002_beta" / "figures_all" / "fig1.png").exists()
    assert (outputs_dir / "fiber_process" / "002_beta" / "figures_all" / "fig2.png").exists()
    assert (outputs_dir / "fiber_process" / "002_beta" / "figures_all" / "fig3.png").exists()
    for filename in ("figures.jsonl", "vision_inputs.jsonl"):
        output_file = outputs_dir / "fiber_process" / "002_beta" / filename
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["paper_output_dir"].endswith(str(Path("outputs") / "fiber_process" / "002_beta"))
    assert row["image_link_normalized"] is True
    assert row["image_link_replacement_count"] == 3
    assert row["copied_legacy_figure_count"] == 3
    assert row["legacy_figures_all_dir"].endswith(str(Path("outputs") / "002_beta" / "figures_all"))
    assert row["category_figures_all_dir"].endswith(str(Path("outputs") / "fiber_process" / "002_beta" / "figures_all"))


def test_stage2_batch_runner_supports_uncategorized_category_output(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "UnknownFolder"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / "uncategorized" / "011_misc.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("markdown", encoding="utf-8")
    pdf_path = pdf_dir / "011_misc.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": "uncategorized__011_misc",
                "category": "uncategorized",
                "paper_id_guess": "011_misc",
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / "011_misc"),
            }
        ],
    )

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not call Stage 2")))

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        dry_run=True,
    )

    row = result["rows"][0]
    assert row["category"] == "uncategorized"
    assert row["paper_output_dir"].endswith(str(Path("outputs") / "uncategorized" / "011_misc"))
    assert not row["paper_output_dir"].endswith(str(Path("outputs") / "011_misc"))


def test_stage2_batch_runner_continues_after_failures_and_writes_reports(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "rheology"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for paper_id in ("100_fail", "101_ok"):
        pdf_path = pdf_dir / f"{paper_id}.pdf"
        pdf_path.write_text("fake pdf", encoding="utf-8")
        markdown_path = markdown_dir / "rheology" / f"{paper_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text("markdown", encoding="utf-8")
        rows.append(
            {
                "source_id": f"rheology__{paper_id}",
                "category": "rheology",
                "paper_id_guess": paper_id,
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / paper_id),
            }
        )
    _write_manifest(manifest_path, rows)

    monkeypatch.setattr(MODULE, "build_runtime_settings", lambda *args, **kwargs: {"paths": {}, "figures": {}})

    def fake_stage2(project_root: Path, settings: dict, input_pdf: Path, paper_id: str, cleaned_markdown_path: Path, output_dir: Path):
        if paper_id == "100_fail":
            raise RuntimeError("simulated stage2 failure")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "tables").mkdir(parents=True, exist_ok=True)
        (output_dir / "tables" / "table1.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (output_dir / "figures.jsonl").write_text(json.dumps({"image_path": "ok"}) + "\n", encoding="utf-8")
        (output_dir / "vision_inputs.jsonl").write_text(json.dumps({"vision_image_path": "ok"}) + "\n", encoding="utf-8")
        (output_dir / "figure_stage2_summary.json").write_text(
            json.dumps({"raw_mineru_image_count": 5, "final_figure_record_count": 3}),
            encoding="utf-8",
        )
        return SimpleNamespace(raw_mineru_image_count=5, tables_count=1, summary={"final_figure_record_count": 3})

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", fake_stage2)

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        continue_on_error=True,
    )

    statuses = {row["source_id"]: row for row in result["rows"]}
    assert statuses["rheology__100_fail"]["status"] == "failed"
    assert statuses["rheology__101_ok"]["status"] == "success"

    report_csv = Path(result["report_csv_path"])
    report_md = Path(result["report_md_path"])
    summary_json = Path(result["summary_json_path"])
    assert report_csv.exists()
    assert report_md.exists()
    assert summary_json.exists()

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["failed_count"] == 1
    assert summary["success_count"] == 1
    assert summary["by_category"]["rheology"]["failed_count"] == 1
    assert summary["by_category"]["rheology"]["success_count"] == 1

    with report_csv.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 2
    assert "image_link_normalized" in csv_rows[0]
    assert "image_link_replacement_count" in csv_rows[0]
    assert "copied_legacy_figure_count" in csv_rows[0]


def test_stage2_batch_runner_dry_run_does_not_modify_markdown_or_copy_images(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "applications"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / "applications" / "009_gamma.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    original_markdown = "![legacy](data/outputs/009_gamma/figures_all/img.png)\n"
    markdown_path.write_text(original_markdown, encoding="utf-8")
    pdf_path = pdf_dir / "009_gamma.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    legacy_figures_all = outputs_dir / "009_gamma" / "figures_all"
    legacy_figures_all.mkdir(parents=True, exist_ok=True)
    (legacy_figures_all / "img.png").write_text("legacy", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": "applications__009_gamma",
                "category": "applications",
                "paper_id_guess": "009_gamma",
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / "009_gamma"),
            }
        ],
    )

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not call Stage 2")))

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        dry_run=True,
    )

    row = result["rows"][0]
    assert row["status"] == "dry_run_planned"
    assert row["image_link_normalized"] is False
    assert row["copied_legacy_figure_count"] == 0
    assert markdown_path.read_text(encoding="utf-8") == original_markdown
    assert not (outputs_dir / "applications" / "009_gamma" / "figures_all" / "img.png").exists()


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
