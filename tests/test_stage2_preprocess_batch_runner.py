from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from alumina_sol_extractor.utils.figure_utils import find_figures_in_markdown_any


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
    assert row["legacy_image_link_detected"] is False
    assert row["image_link_normalized"] is False
    assert row["image_file_missing_count"] == 0


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
    paper_id = "002_beta_stage2norm_missing"
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "fiber_process"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / "fiber_process" / f"{paper_id}.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        f"![legacy](data/outputs/{paper_id}/figures_all/fig1.png)\n"
        f"![legacy-abs](G:/paper/Al-gel-sol/alumina_sol_extractor/data/outputs/{paper_id}/figures_all/fig2.png)\n"
        f"![legacy-win](G:\\paper\\Al-gel-sol\\alumina_sol_extractor\\data\\outputs\\{paper_id}\\figures_all\\fig3.png)\n",
        encoding="utf-8",
    )
    pdf_path = pdf_dir / f"{paper_id}.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": f"fiber_process__{paper_id}",
                "category": "fiber_process",
                "paper_id_guess": paper_id,
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / paper_id),
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
    assert output_dir == outputs_dir / "fiber_process" / paper_id
    assert settings["paths"]["output_dir"] == str(outputs_dir / "fiber_process")
    assert settings["paths"]["mineru_raw_dir"] == str(Path(MODULE.PROJECT_ROOT) / "data" / "mineru_raw" / "fiber_process")
    assert settings["figures"]["run_resnet"] is False
    assert settings["figures"]["run_clip"] is False
    normalized_markdown = markdown_path.read_text(encoding="utf-8")
    assert f"data/outputs/fiber_process/{paper_id}/figures_all/fig1.png" in normalized_markdown
    assert f"G:/paper/Al-gel-sol/alumina_sol_extractor/data/outputs/fiber_process/{paper_id}/figures_all/fig2.png" in normalized_markdown
    assert f"G:\\paper\\Al-gel-sol\\alumina_sol_extractor\\data\\outputs\\fiber_process\\{paper_id}\\figures_all\\fig3.png" in normalized_markdown
    assert f"data/outputs/{paper_id}/figures_all/fig1.png" not in normalized_markdown
    for filename in ("figures.jsonl", "vision_inputs.jsonl"):
        output_file = outputs_dir / "fiber_process" / paper_id / filename
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["paper_output_dir"].endswith(str(Path("outputs") / "fiber_process" / paper_id))
    assert row["legacy_image_link_detected"] is True
    assert row["image_link_normalized"] is True
    assert row["image_link_replacement_count"] == 3
    assert row["image_file_missing_count"] == 3
    assert row["legacy_figures_all_dir"].endswith(str(Path("outputs") / paper_id / "figures_all"))
    assert row["category_figures_all_dir"].endswith(str(Path("outputs") / "fiber_process" / paper_id / "figures_all"))


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
    assert "legacy_image_link_detected" in csv_rows[0]
    assert "image_link_normalized" in csv_rows[0]
    assert "image_link_replacement_count" in csv_rows[0]
    assert "image_file_missing_count" in csv_rows[0]


def test_stage2_batch_runner_dry_run_does_not_modify_markdown(tmp_path: Path, monkeypatch) -> None:
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
    assert row["legacy_image_link_detected"] is False
    assert row["image_link_normalized"] is False
    assert row["image_file_missing_count"] == 0
    assert markdown_path.read_text(encoding="utf-8") == original_markdown
    assert not (outputs_dir / "applications" / "009_gamma" / "figures_all" / "img.png").exists()


def test_stage2_batch_runner_does_not_copy_legacy_figures_and_only_reports_missing_images(tmp_path: Path, monkeypatch) -> None:
    paper_id = "010_delta_stage2norm_missing"
    manifest_path = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs" / "mechanism"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_dir / "mechanism" / f"{paper_id}.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(f"![legacy](data/outputs/{paper_id}/figures_all/fig.png)\n", encoding="utf-8")
    pdf_path = pdf_dir / f"{paper_id}.pdf"
    pdf_path.write_text("fake pdf", encoding="utf-8")
    legacy_figures_all = outputs_dir / paper_id / "figures_all"
    legacy_figures_all.mkdir(parents=True, exist_ok=True)
    (legacy_figures_all / "fig.png").write_text("legacy-image", encoding="utf-8")
    _write_manifest(
        manifest_path,
        [
            {
                "source_id": f"mechanism__{paper_id}",
                "category": "mechanism",
                "paper_id_guess": paper_id,
                "pdf_path": str(pdf_path),
                "markdown_expected_path": str(markdown_path),
                "markdown_actual_path": "",
                "output_dir": str(outputs_dir / paper_id),
            }
        ],
    )

    monkeypatch.setattr(MODULE, "build_runtime_settings", lambda *args, **kwargs: {"paths": {}, "figures": {"run_resnet": True, "run_clip": True}})

    def fake_stage2(project_root: Path, settings: dict, input_pdf: Path, paper_id: str, cleaned_markdown_path: Path, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "figures.jsonl").write_text(
            json.dumps({"image_path": str(output_dir / "figures_all" / "fig.png")}) + "\n",
            encoding="utf-8",
        )
        (output_dir / "vision_inputs.jsonl").write_text(
            json.dumps({"vision_image_path": str(output_dir / "figures_for_vision" / "fig.png")}) + "\n",
            encoding="utf-8",
        )
        (output_dir / "figure_stage2_summary.json").write_text(
            json.dumps({"raw_mineru_image_count": 1, "final_figure_record_count": 1}),
            encoding="utf-8",
        )
        return SimpleNamespace(raw_mineru_image_count=1, tables_count=0, summary={"final_figure_record_count": 1})

    monkeypatch.setattr(MODULE, "run_stage2_figure_pipeline", fake_stage2)

    result = MODULE.run_stage2_preprocess_batch(
        manifest=manifest_path,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        force=True,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["legacy_image_link_detected"] is True
    assert row["image_link_normalized"] is True
    assert row["image_link_replacement_count"] == 1
    assert row["image_file_missing_count"] == 1
    assert markdown_path.read_text(encoding="utf-8") == f"![legacy](data/outputs/mechanism/{paper_id}/figures_all/fig.png)\n"
    assert not (outputs_dir / "mechanism" / paper_id / "figures_all" / "fig.png").exists()
    assert (outputs_dir / paper_id / "figures_all" / "fig.png").exists()


def test_find_figures_in_markdown_any_uses_explicit_category_aware_figures_dir(tmp_path: Path) -> None:
    project_root = tmp_path
    markdown_path = project_root / "data" / "markdown" / "fiber_process" / "paper1.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("![img](data/outputs/paper1/figures_all/figure_a.png)\n", encoding="utf-8")

    category_figures_all_dir = project_root / "data" / "outputs" / "fiber_process" / "paper1" / "figures_all"
    category_figures_all_dir.mkdir(parents=True, exist_ok=True)
    (category_figures_all_dir / "figure_a.png").write_bytes(b"fake-png")

    figures = find_figures_in_markdown_any(
        markdown_text=markdown_path.read_text(encoding="utf-8"),
        markdown_path=markdown_path,
        project_root=project_root,
        paper_id="paper1",
        figures_all_dir=category_figures_all_dir,
    )

    assert len(figures) == 1
    assert Path(figures[0].image_path) == category_figures_all_dir / "figure_a.png"
    assert not (project_root / "data" / "outputs" / "paper1").exists()


def test_stage2_pipeline_passes_category_aware_tables_and_figures_dirs(tmp_path: Path, monkeypatch) -> None:
    from alumina_sol_extractor.pipeline import stage2_figure_pipeline as stage2_module

    project_root = tmp_path
    cleaned_markdown_path = project_root / "data" / "markdown" / "fiber_process" / "paper1.md"
    cleaned_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_markdown_path.write_text("![img](data/outputs/paper1/figures_all/figure_a.png)\n", encoding="utf-8")
    pdf_path = project_root / "pdfs" / "paper1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_text("fake pdf", encoding="utf-8")
    output_dir = project_root / "data" / "outputs" / "fiber_process" / "paper1"

    captured: dict[str, object] = {}

    def fake_extract_tables_from_markdown(markdown: str, project_root: Path, paper_id: str, preview_rows: int = 8, tables_dir: Path | None = None):
        captured["tables_dir"] = Path(tables_dir)
        return markdown, []

    def fake_load_mineru_image_layout(path: Path):
        captured["layout_dir"] = Path(path)
        return {"figure_a.png": {"bbox": [1, 2, 3, 4]}}

    def fake_find_figures_in_markdown_any(
        markdown_text: str,
        markdown_path: Path,
        project_root: Path,
        paper_id: str,
        mineru_layout=None,
        figures_all_dir: Path | None = None,
    ):
        captured["figures_all_dir"] = Path(figures_all_dir)
        captured["mineru_layout"] = mineru_layout
        return []

    def fake_match_figure_contexts(markdown_text: str, figures: list):
        return figures

    def fake_detect_and_merge_fragmented_figures(figures: list, paper_id: str, output_dir: Path, **kwargs):
        return figures

    def fake_save_figure_outputs(**kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "figures.jsonl").write_text(json.dumps({"image_path": str(output_dir / "figures_all" / "figure_a.png")}) + "\n", encoding="utf-8")
        (output_dir / "vision_inputs.jsonl").write_text(json.dumps({"image_path": str(output_dir / "figures_all" / "figure_a.png"), "vision_image_path": str(output_dir / "figures_for_vision" / "figure_a.png")}) + "\n", encoding="utf-8")
        summary = {
            "raw_mineru_image_count": 1,
            "final_figure_record_count": 0,
            "clip_not_run_count": 1,
            "bbox_attached_count": 1,
            "bbox_missing_count": 0,
            "standard_caption_count": 1,
            "pseudo_caption_count": 0,
            "caption_none_count": 0,
        }
        (output_dir / "figure_stage2_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary

    monkeypatch.setattr(stage2_module, "extract_tables_from_markdown", fake_extract_tables_from_markdown)
    monkeypatch.setattr(stage2_module, "load_mineru_image_layout", fake_load_mineru_image_layout)
    monkeypatch.setattr(stage2_module, "find_figures_in_markdown_any", fake_find_figures_in_markdown_any)
    monkeypatch.setattr(stage2_module, "match_figure_contexts", fake_match_figure_contexts)
    monkeypatch.setattr(stage2_module, "detect_and_merge_fragmented_figures", fake_detect_and_merge_fragmented_figures)
    monkeypatch.setattr(stage2_module, "save_figure_outputs", fake_save_figure_outputs)

    result = stage2_module.run_stage2_figure_pipeline(
        project_root=project_root,
        settings={
            "paths": {"mineru_raw_dir": str(project_root / "data" / "mineru_raw" / "fiber_process")},
            "figures": {"run_resnet": False, "run_clip": False},
            "outputs": {},
        },
        input_pdf=pdf_path,
        paper_id="paper1",
        cleaned_markdown_path=cleaned_markdown_path,
        output_dir=output_dir,
    )

    assert captured["tables_dir"] == output_dir / "tables"
    assert captured["figures_all_dir"] == output_dir / "figures_all"
    assert captured["layout_dir"] == project_root / "data" / "mineru_raw" / "fiber_process" / "paper1"
    assert captured["mineru_layout"] == {"figure_a.png": {"bbox": [1, 2, 3, 4]}}
    assert result.tables_dir == output_dir / "tables"
    assert result.output_dir == output_dir
    assert result.summary["mineru_layout_dir"] == str(project_root / "data" / "mineru_raw" / "fiber_process" / "paper1")
    assert result.summary["mineru_layout_found"] is True
    assert result.summary["mineru_layout_image_count"] == 1
    assert result.summary["mineru_layout_warning"] is None
    assert result.summary["bbox_attached_count"] == 1
    assert result.summary["bbox_missing_count"] == 0
    assert result.summary["standard_caption_count"] == 1
    assert result.summary["pseudo_caption_count"] == 0
    assert result.summary["caption_none_count"] == 0
    assert not (project_root / "data" / "outputs" / "paper1").exists()

    figures_rows = [json.loads(line) for line in (output_dir / "figures.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert figures_rows[0]["image_path"] == str(output_dir / "figures_all" / "figure_a.png")

    vision_rows = [json.loads(line) for line in (output_dir / "vision_inputs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert vision_rows[0]["image_path"] == str(output_dir / "figures_all" / "figure_a.png")
    assert vision_rows[0]["vision_image_path"] == str(output_dir / "figures_for_vision" / "figure_a.png")


def test_stage2_pipeline_does_not_fallback_to_flat_mineru_layout(tmp_path: Path, monkeypatch) -> None:
    from alumina_sol_extractor.pipeline import stage2_figure_pipeline as stage2_module

    project_root = tmp_path
    cleaned_markdown_path = project_root / "data" / "markdown" / "fiber_process" / "paper1.md"
    cleaned_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_markdown_path.write_text("![img](data/outputs/fiber_process/paper1/figures_all/figure_a.png)\n", encoding="utf-8")
    pdf_path = project_root / "pdfs" / "paper1.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_text("fake pdf", encoding="utf-8")
    output_dir = project_root / "data" / "outputs" / "fiber_process" / "paper1"
    flat_only_layout_dir = project_root / "data" / "mineru_raw" / "paper1"
    flat_only_layout_dir.mkdir(parents=True, exist_ok=True)
    (flat_only_layout_dir / "content_list.json").write_text("[]", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_extract_tables_from_markdown(markdown: str, project_root: Path, paper_id: str, preview_rows: int = 8, tables_dir: Path | None = None):
        return markdown, []

    def fake_load_mineru_image_layout(path: Path):
        captured["layout_dir"] = Path(path)
        return {}

    def fake_find_figures_in_markdown_any(
        markdown_text: str,
        markdown_path: Path,
        project_root: Path,
        paper_id: str,
        mineru_layout=None,
        figures_all_dir: Path | None = None,
    ):
        captured["mineru_layout"] = mineru_layout
        return []

    def fake_match_figure_contexts(markdown_text: str, figures: list):
        return figures

    def fake_detect_and_merge_fragmented_figures(figures: list, paper_id: str, output_dir: Path, **kwargs):
        return figures

    def fake_save_figure_outputs(**kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "raw_mineru_image_count": 1,
            "final_figure_record_count": 0,
            "clip_not_run_count": 1,
            "bbox_attached_count": 0,
            "bbox_missing_count": 1,
            "standard_caption_count": 0,
            "pseudo_caption_count": 0,
            "caption_none_count": 1,
        }
        (output_dir / "figure_stage2_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return summary

    monkeypatch.setattr(stage2_module, "extract_tables_from_markdown", fake_extract_tables_from_markdown)
    monkeypatch.setattr(stage2_module, "load_mineru_image_layout", fake_load_mineru_image_layout)
    monkeypatch.setattr(stage2_module, "find_figures_in_markdown_any", fake_find_figures_in_markdown_any)
    monkeypatch.setattr(stage2_module, "match_figure_contexts", fake_match_figure_contexts)
    monkeypatch.setattr(stage2_module, "detect_and_merge_fragmented_figures", fake_detect_and_merge_fragmented_figures)
    monkeypatch.setattr(stage2_module, "save_figure_outputs", fake_save_figure_outputs)

    result = stage2_module.run_stage2_figure_pipeline(
        project_root=project_root,
        settings={
            "paths": {"mineru_raw_dir": str(project_root / "data" / "mineru_raw" / "fiber_process")},
            "figures": {"run_resnet": False, "run_clip": False},
            "outputs": {},
        },
        input_pdf=pdf_path,
        paper_id="paper1",
        cleaned_markdown_path=cleaned_markdown_path,
        output_dir=output_dir,
    )

    assert captured["layout_dir"] == project_root / "data" / "mineru_raw" / "fiber_process" / "paper1"
    assert captured["mineru_layout"] == {}
    assert result.summary["mineru_layout_dir"] == str(project_root / "data" / "mineru_raw" / "fiber_process" / "paper1")
    assert result.summary["mineru_layout_found"] is False
    assert result.summary["mineru_layout_image_count"] == 0
    assert result.summary["mineru_layout_warning"] == "missing_category_mineru_layout"
    assert not (project_root / "data" / "outputs" / "paper1").exists()


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
