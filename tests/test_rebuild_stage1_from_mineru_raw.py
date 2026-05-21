from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

from alumina_sol_extractor.utils.figure_utils import rewrite_mineru_image_paths


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "rebuild_stage1_from_mineru_raw.py"
SPEC = importlib.util.spec_from_file_location("rebuild_stage1_from_mineru_raw_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_rewrite_mineru_image_paths_uses_explicit_figures_all_dir(tmp_path: Path) -> None:
    markdown_dir = tmp_path / "raw"
    markdown_dir.mkdir()
    source_image = markdown_dir / "figure.png"
    source_image.write_bytes(b"png-bytes")

    figures_all_dir = tmp_path / "data" / "outputs" / "applications" / "paper-1" / "figures_all"
    rewritten = rewrite_mineru_image_paths(
        markdown="![img](figure.png)",
        markdown_dir=markdown_dir,
        project_root=tmp_path,
        paper_id="paper-1",
        figures_all_dir=figures_all_dir,
    )

    copied = figures_all_dir / "figure.png"
    assert copied.exists()
    assert copied.as_posix() in rewritten
    assert not (tmp_path / "data" / "outputs" / "paper-1" / "figures_all" / "figure.png").exists()


def test_rewrite_mineru_image_paths_keeps_legacy_default(tmp_path: Path) -> None:
    markdown_dir = tmp_path / "raw"
    markdown_dir.mkdir()
    source_image = markdown_dir / "legacy.png"
    source_image.write_bytes(b"legacy-bytes")

    rewritten = rewrite_mineru_image_paths(
        markdown="![img](legacy.png)",
        markdown_dir=markdown_dir,
        project_root=tmp_path,
        paper_id="paper-legacy",
    )

    copied = tmp_path / "data" / "outputs" / "paper-legacy" / "figures_all" / "legacy.png"
    assert copied.exists()
    assert copied.as_posix() in rewritten


def test_rebuild_from_raw_mineru_md_writes_category_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            {
                "source_id": "applications__001_demo",
                "category": "applications",
                "paper_id_guess": "001_demo",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "applications" / "001_demo.md"),
            }
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "001_demo"
    raw_dir.mkdir(parents=True)
    source_image = raw_dir / "img1.png"
    source_image.write_bytes(b"image-bytes")
    (raw_dir / "raw_mineru.md").write_text("![img](img1.png)\nAl2O3\n", encoding="utf-8")

    result = MODULE.rebuild_stage1_from_mineru_raw(
        manifest=manifest,
        mineru_raw_dir=tmp_path / "mineru_raw",
        markdown_dir=tmp_path / "data" / "markdown",
        outputs_dir=tmp_path / "data" / "outputs",
        report_dir=tmp_path / "reports",
    )

    row = result["rows"][0]
    output_md = tmp_path / "data" / "markdown" / "applications" / "001_demo.md"
    figures_all_dir = tmp_path / "data" / "outputs" / "applications" / "001_demo" / "figures_all"
    flat_dir = tmp_path / "data" / "outputs" / "001_demo" / "figures_all"
    assert row["status"] == "success"
    assert output_md.exists()
    assert figures_all_dir.exists()
    assert (figures_all_dir / "img1.png").exists()
    assert not flat_dir.exists()
    written_markdown = output_md.read_text(encoding="utf-8")
    assert "Al2O3" in written_markdown
    assert figures_all_dir.as_posix() in written_markdown
    assert (tmp_path / "reports" / "rebuild_stage1_from_mineru_raw_report.csv").exists()
    assert (tmp_path / "reports" / "rebuild_stage1_from_mineru_raw_report.md").exists()
    assert (tmp_path / "reports" / "rebuild_stage1_from_mineru_raw_summary.json").exists()


def test_rebuild_uses_full_md_fallback_under_extracted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            {
                "source_id": "mechanism__002_demo",
                "category": "mechanism",
                "paper_id_guess": "002_demo",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "mechanism" / "002_demo.md"),
            }
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "002_demo" / "extracted" / "bundle"
    raw_dir.mkdir(parents=True)
    source_image = raw_dir / "img2.jpg"
    source_image.write_bytes(b"jpg-bytes")
    (raw_dir / "full.md").write_text("![img](img2.jpg)\n", encoding="utf-8")

    result = MODULE.rebuild_stage1_from_mineru_raw(
        manifest=manifest,
        mineru_raw_dir=tmp_path / "mineru_raw",
        markdown_dir=tmp_path / "data" / "markdown",
        outputs_dir=tmp_path / "data" / "outputs",
        report_dir=tmp_path / "reports",
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["mineru_markdown_path"].endswith("full.md")
    assert (tmp_path / "data" / "outputs" / "mechanism" / "002_demo" / "figures_all" / "img2.jpg").exists()


def test_rebuild_dry_run_and_missing_statuses_and_filters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            {
                "source_id": "fiber_process__001_ok",
                "category": "fiber_process",
                "paper_id_guess": "001_ok",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "fiber_process" / "001_ok.md"),
            },
            {
                "source_id": "fiber_process__002_missing_raw",
                "category": "fiber_process",
                "paper_id_guess": "002_missing_raw",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "fiber_process" / "002_missing_raw.md"),
            },
            {
                "source_id": "applications__003_missing_md",
                "category": "applications",
                "paper_id_guess": "003_missing_md",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "applications" / "003_missing_md.md"),
            },
        ],
    )
    ok_raw_dir = tmp_path / "mineru_raw" / "001_ok"
    ok_raw_dir.mkdir(parents=True)
    (ok_raw_dir / "figure.png").write_bytes(b"png")
    (ok_raw_dir / "raw_mineru.md").write_text("![img](figure.png)", encoding="utf-8")
    (tmp_path / "mineru_raw" / "003_missing_md").mkdir(parents=True)

    result = MODULE.rebuild_stage1_from_mineru_raw(
        manifest=manifest,
        mineru_raw_dir=tmp_path / "mineru_raw",
        markdown_dir=tmp_path / "data" / "markdown",
        outputs_dir=tmp_path / "data" / "outputs",
        report_dir=tmp_path / "reports",
        category="fiber_process",
        limit=2,
        dry_run=True,
    )

    statuses = {row["paper_id_guess"]: row["status"] for row in result["rows"]}
    assert statuses == {
        "001_ok": "dry_run_planned",
        "002_missing_raw": "missing_mineru_raw",
    }
    assert not (tmp_path / "data" / "markdown" / "fiber_process" / "001_ok.md").exists()
    summary = json.loads((tmp_path / "reports" / "rebuild_stage1_from_mineru_raw_summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run_count"] == 1
    assert summary["missing_mineru_raw_count"] == 1


def test_rebuild_force_resets_category_figures_all_only_and_preserves_raw_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            {
                "source_id": "rheology__004_force",
                "category": "rheology",
                "paper_id_guess": "004_force",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "rheology" / "004_force.md"),
            }
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "004_force"
    raw_dir.mkdir(parents=True)
    (raw_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (raw_dir / "new.png").write_bytes(b"new-image")
    (raw_dir / "raw_mineru.md").write_text("![img](new.png)", encoding="utf-8")

    output_md = tmp_path / "data" / "markdown" / "rheology" / "004_force.md"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("old", encoding="utf-8")
    figures_all_dir = tmp_path / "data" / "outputs" / "rheology" / "004_force" / "figures_all"
    figures_all_dir.mkdir(parents=True, exist_ok=True)
    (figures_all_dir / "stale.png").write_bytes(b"stale")

    result = MODULE.rebuild_stage1_from_mineru_raw(
        manifest=manifest,
        mineru_raw_dir=tmp_path / "mineru_raw",
        markdown_dir=tmp_path / "data" / "markdown",
        outputs_dir=tmp_path / "data" / "outputs",
        report_dir=tmp_path / "reports",
        force=True,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert (raw_dir / "keep.txt").exists()
    assert not (figures_all_dir / "stale.png").exists()
    assert (figures_all_dir / "new.png").exists()


def test_rebuild_skips_existing_and_paper_id_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            {
                "source_id": "applications__005_keep",
                "category": "applications",
                "paper_id_guess": "005_keep",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "applications" / "005_keep.md"),
            },
            {
                "source_id": "applications__006_skip",
                "category": "applications",
                "paper_id_guess": "006_skip",
                "markdown_expected_path": str(tmp_path / "data" / "markdown" / "applications" / "006_skip.md"),
            },
        ],
    )

    keep_raw_dir = tmp_path / "mineru_raw" / "005_keep"
    keep_raw_dir.mkdir(parents=True)
    (keep_raw_dir / "keep.png").write_bytes(b"keep")
    (keep_raw_dir / "raw_mineru.md").write_text("![img](keep.png)", encoding="utf-8")

    skip_md = tmp_path / "data" / "markdown" / "applications" / "006_skip.md"
    skip_md.parent.mkdir(parents=True, exist_ok=True)
    skip_md.write_text("existing", encoding="utf-8")
    skip_figures = tmp_path / "data" / "outputs" / "applications" / "006_skip" / "figures_all"
    skip_figures.mkdir(parents=True, exist_ok=True)
    (skip_figures / "existing.png").write_bytes(b"existing")
    skip_raw_dir = tmp_path / "mineru_raw" / "006_skip"
    skip_raw_dir.mkdir(parents=True)
    (skip_raw_dir / "skip.png").write_bytes(b"skip")
    (skip_raw_dir / "raw_mineru.md").write_text("![img](skip.png)", encoding="utf-8")

    result = MODULE.rebuild_stage1_from_mineru_raw(
        manifest=manifest,
        mineru_raw_dir=tmp_path / "mineru_raw",
        markdown_dir=tmp_path / "data" / "markdown",
        outputs_dir=tmp_path / "data" / "outputs",
        report_dir=tmp_path / "reports",
        paper_ids=["applications__006_skip", "005_keep"],
    )

    statuses = {row["paper_id_guess"]: row["status"] for row in result["rows"]}
    assert statuses["005_keep"] == "success"
    assert statuses["006_skip"] == "skipped_existing"


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_id", "category", "paper_id_guess", "markdown_expected_path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path
