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
    (markdown_dir / "figure.png").write_bytes(b"png-bytes")

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
    (markdown_dir / "legacy.png").write_bytes(b"legacy-bytes")

    rewritten = rewrite_mineru_image_paths(
        markdown="![img](legacy.png)",
        markdown_dir=markdown_dir,
        project_root=tmp_path,
        paper_id="paper-legacy",
    )

    copied = tmp_path / "data" / "outputs" / "paper-legacy" / "figures_all" / "legacy.png"
    assert copied.exists()
    assert copied.as_posix() in rewritten


def test_build_mineru_cache_index_detects_candidate_variants(tmp_path: Path) -> None:
    mineru_raw_dir = tmp_path / "mineru_raw"
    (mineru_raw_dir / "paper_a").mkdir(parents=True)
    (mineru_raw_dir / "paper_a" / "raw_mineru.md").write_text("x", encoding="utf-8")
    (mineru_raw_dir / "mechanism" / "paper_b" / "extracted" / "bundle").mkdir(parents=True)
    (mineru_raw_dir / "mechanism" / "paper_b" / "extracted" / "bundle" / "full.md").write_text("x", encoding="utf-8")
    (mineru_raw_dir / "paper_c").mkdir(parents=True)
    (mineru_raw_dir / "paper_c" / "mineru_result.zip").write_bytes(b"zip")

    index = MODULE.build_mineru_cache_index(mineru_raw_dir)
    by_name = {item["folder_name"]: item for item in index}
    assert by_name["paper_a"]["has_raw_mineru_md"] is True
    assert by_name["paper_b"]["has_extracted_markdown"] is True
    assert by_name["paper_c"]["has_zip"] is True


def test_rebuild_matches_top_level_raw_cache_by_paper_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            _manifest_row(
                source_id="applications__001_demo",
                category="applications",
                paper_id_guess="001_demo",
                root=tmp_path,
            )
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "001_demo"
    raw_dir.mkdir(parents=True)
    (raw_dir / "img1.png").write_bytes(b"image-bytes")
    (raw_dir / "raw_mineru.md").write_text("![img](img1.png)\nAl2O3\n", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)

    row = result["rows"][0]
    output_md = tmp_path / "data" / "markdown" / "applications" / "001_demo.md"
    figures_all_dir = tmp_path / "data" / "outputs" / "applications" / "001_demo" / "figures_all"
    flat_dir = tmp_path / "data" / "outputs" / "001_demo" / "figures_all"
    assert row["status"] == "success"
    assert row["raw_dir_match_method"] == "exact_paper_id"
    assert Path(row["actual_raw_dir"]) == raw_dir.resolve()
    assert output_md.exists()
    assert (figures_all_dir / "img1.png").exists()
    assert not flat_dir.exists()


def test_rebuild_matches_category_aware_raw_cache_and_full_md(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            _manifest_row(
                source_id="mechanism__002_demo",
                category="mechanism",
                paper_id_guess="002_demo",
                root=tmp_path,
            )
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "mechanism" / "002_demo" / "extracted" / "bundle"
    raw_dir.mkdir(parents=True)
    (raw_dir / "img2.jpg").write_bytes(b"jpg-bytes")
    (raw_dir / "full.md").write_text("![img](img2.jpg)\n", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["raw_dir_match_method"] in {"exact_paper_id", "category_exact"}
    assert row["cache_has_extracted_markdown"] is True
    assert row["mineru_markdown_path"].endswith("full.md")
    assert (tmp_path / "data" / "outputs" / "mechanism" / "002_demo" / "figures_all" / "img2.jpg").exists()


def test_rebuild_matches_by_source_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    source_id = "rheology__source_folder"
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_manifest_row(source_id=source_id, category="rheology", paper_id_guess="paper-name", root=tmp_path)],
    )
    raw_dir = tmp_path / "mineru_raw" / source_id
    raw_dir.mkdir(parents=True)
    (raw_dir / "x.png").write_bytes(b"x")
    (raw_dir / "raw_mineru.md").write_text("![img](x.png)", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)
    assert result["rows"][0]["raw_dir_match_method"] == "exact_source_id"


def test_rebuild_can_use_category_exact_when_folder_name_is_ambiguous(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_manifest_row(source_id="mechanism__shared", category="mechanism", paper_id_guess="shared", root=tmp_path)],
    )
    top_level = tmp_path / "mineru_raw" / "shared"
    top_level.mkdir(parents=True)
    (top_level / "mineru_result.zip").write_bytes(b"zip-only")

    category_raw = tmp_path / "mineru_raw" / "mechanism" / "shared"
    category_raw.mkdir(parents=True)
    (category_raw / "x.png").write_bytes(b"x")
    (category_raw / "raw_mineru.md").write_text("![img](x.png)", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)
    assert result["rows"][0]["raw_dir_match_method"] == "category_exact"


def test_rebuild_matches_by_pdf_stem(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            _manifest_row(
                source_id="applications__no_match",
                category="applications",
                paper_id_guess="different-paper",
                pdf_path="G:/paper/Sorted_Database/Applications/pdf-stem-name.pdf",
                root=tmp_path,
            )
        ],
    )
    raw_dir = tmp_path / "mineru_raw" / "pdf-stem-name"
    raw_dir.mkdir(parents=True)
    (raw_dir / "x.png").write_bytes(b"x")
    (raw_dir / "raw_mineru.md").write_text("![img](x.png)", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)
    assert result["rows"][0]["raw_dir_match_method"] == "exact_pdf_stem"


def test_rebuild_matches_by_normalized_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_manifest_row(source_id="fiber_process__unused", category="fiber_process", paper_id_guess="Paper Name（测试）", root=tmp_path)],
    )
    raw_dir = tmp_path / "mineru_raw" / "paper_name_测试"
    raw_dir.mkdir(parents=True)
    (raw_dir / "x.png").write_bytes(b"x")
    (raw_dir / "raw_mineru.md").write_text("![img](x.png)", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)
    assert result["rows"][0]["raw_dir_match_method"] == "normalized_paper_id"


def test_rebuild_reports_missing_only_after_index_scan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_manifest_row(source_id="fiber_process__missing", category="fiber_process", paper_id_guess="missing", root=tmp_path)],
    )
    (tmp_path / "mineru_raw" / "other" / "raw_mineru.md").parent.mkdir(parents=True)
    (tmp_path / "mineru_raw" / "other" / "raw_mineru.md").write_text("x", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest)
    row = result["rows"][0]
    summary = result["summary"]
    assert row["status"] == "missing_mineru_raw"
    assert row["raw_dir_match_method"] == "not_found"
    assert summary["mineru_cache_candidate_count"] == 1
    assert summary["raw_dir_match_method_counts"]["not_found"] == 1
    assert summary["unmatched_sample"] == ["fiber_process__missing"]


def test_rebuild_dry_run_and_filters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            _manifest_row(source_id="fiber_process__001_ok", category="fiber_process", paper_id_guess="001_ok", root=tmp_path),
            _manifest_row(source_id="fiber_process__002_missing_raw", category="fiber_process", paper_id_guess="002_missing_raw", root=tmp_path),
            _manifest_row(source_id="applications__003_skip", category="applications", paper_id_guess="003_skip", root=tmp_path),
        ],
    )
    ok_raw_dir = tmp_path / "mineru_raw" / "001_ok"
    ok_raw_dir.mkdir(parents=True)
    (ok_raw_dir / "figure.png").write_bytes(b"png")
    (ok_raw_dir / "raw_mineru.md").write_text("![img](figure.png)", encoding="utf-8")

    result = _run_rebuild(tmp_path, manifest=manifest, category="fiber_process", limit=2, dry_run=True)
    statuses = {row["paper_id_guess"]: row["status"] for row in result["rows"]}
    assert statuses == {"001_ok": "dry_run_planned", "002_missing_raw": "missing_mineru_raw"}
    assert not (tmp_path / "data" / "markdown" / "fiber_process" / "001_ok.md").exists()


def test_rebuild_force_resets_category_figures_all_only_and_preserves_raw_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [_manifest_row(source_id="rheology__004_force", category="rheology", paper_id_guess="004_force", root=tmp_path)],
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

    result = _run_rebuild(tmp_path, manifest=manifest, force=True)
    row = result["rows"][0]
    assert row["status"] == "success"
    assert (raw_dir / "keep.txt").exists()
    assert not (figures_all_dir / "stale.png").exists()
    assert (figures_all_dir / "new.png").exists()


def test_rebuild_skips_existing_and_paper_id_filter_and_report_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    manifest = _write_manifest(
        tmp_path / "manifest.csv",
        [
            _manifest_row(source_id="applications__005_keep", category="applications", paper_id_guess="005_keep", root=tmp_path),
            _manifest_row(source_id="applications__006_skip", category="applications", paper_id_guess="006_skip", root=tmp_path),
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

    result = _run_rebuild(tmp_path, manifest=manifest, paper_ids=["applications__006_skip", "005_keep"])
    statuses = {row["paper_id_guess"]: row["status"] for row in result["rows"]}
    assert statuses["005_keep"] == "success"
    assert statuses["006_skip"] == "skipped_existing"
    report_row = next(row for row in result["rows"] if row["paper_id_guess"] == "005_keep")
    assert "expected_raw_dir" in report_row
    assert "actual_raw_dir" in report_row
    assert "raw_dir_match_method" in report_row

    summary = json.loads((tmp_path / "reports" / "rebuild_stage1_from_mineru_raw_summary.json").read_text(encoding="utf-8"))
    assert "mineru_cache_candidate_count" in summary
    assert "raw_dir_match_method_counts" in summary


def _run_rebuild(tmp_path: Path, **kwargs):
    return MODULE.rebuild_stage1_from_mineru_raw(
        manifest=kwargs.pop("manifest"),
        mineru_raw_dir=kwargs.pop("mineru_raw_dir", tmp_path / "mineru_raw"),
        markdown_dir=kwargs.pop("markdown_dir", tmp_path / "data" / "markdown"),
        outputs_dir=kwargs.pop("outputs_dir", tmp_path / "data" / "outputs"),
        report_dir=kwargs.pop("report_dir", tmp_path / "reports"),
        **kwargs,
    )


def _manifest_row(
    *,
    source_id: str,
    category: str,
    paper_id_guess: str,
    root: Path,
    pdf_path: str | None = None,
) -> dict[str, str]:
    return {
        "source_id": source_id,
        "category": category,
        "paper_id_guess": paper_id_guess,
        "pdf_path": pdf_path or f"G:/paper/Sorted_Database/{category}/{paper_id_guess}.pdf",
        "markdown_expected_path": str(root / "data" / "markdown" / category / f"{paper_id_guess}.md"),
    }


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_id", "category", "paper_id_guess", "pdf_path", "markdown_expected_path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path
