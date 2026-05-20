from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "build_source_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_source_manifest_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_build_source_manifest_scans_categories_and_avoids_name_collisions(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"

    for category in MODULE.KNOWN_CATEGORIES:
        (pdf_dir / category).mkdir(parents=True, exist_ok=True)

    same_name = "同名论文"
    (pdf_dir / "fiber_process" / f"{same_name}.pdf").write_text("fake pdf", encoding="utf-8")
    (pdf_dir / "mechanism" / f"{same_name}.pdf").write_text("fake pdf", encoding="utf-8")
    (pdf_dir / "applications" / "应用论文.pdf").write_text("fake pdf", encoding="utf-8")
    (pdf_dir / "rheology" / "流变论文.pdf").write_text("fake pdf", encoding="utf-8")

    (markdown_dir / "fiber_process").mkdir(parents=True, exist_ok=True)
    (markdown_dir / "fiber_process" / f"{same_name}.md").write_text("A" * 1500, encoding="utf-8")
    (markdown_dir / "applications").mkdir(parents=True, exist_ok=True)
    (markdown_dir / "applications" / "应用论文.md").write_text("short", encoding="utf-8")

    legacy_output_dir = outputs_dir / same_name
    (legacy_output_dir / "stage3_dspy_smoke").mkdir(parents=True, exist_ok=True)

    result = MODULE.build_source_manifest(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        out_dir=out_dir,
        min_markdown_chars=10,
    )

    rows = result["rows"]
    assert len(rows) == 4
    source_ids = {row["source_id"] for row in rows}
    normalized_suffix = MODULE._build_source_id("x", same_name).split("__", 1)[1]
    assert f"fiber_process__{normalized_suffix}" in source_ids
    assert f"mechanism__{normalized_suffix}" in source_ids

    fiber_row = next(row for row in rows if row["category"] == "fiber_process")
    assert fiber_row["markdown_expected_path"].endswith(f"markdown{os.sep}fiber_process{os.sep}{same_name}.md")
    assert fiber_row["markdown_status"] == "exists_ok"
    assert fiber_row["has_stage3"] is True
    assert fiber_row["output_dir_layout"] == "legacy_flat"

    app_row = next(row for row in rows if row["category"] == "applications")
    assert app_row["markdown_status"] == "exists_too_short"
    assert app_row["recommended_next_action"] == "inspect_markdown"

    rheology_row = next(row for row in rows if row["category"] == "rheology")
    assert rheology_row["markdown_status"] == "not_generated"
    assert rheology_row["recommended_next_action"] == "run_stage1_pdf_to_markdown"

    summary = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
    assert summary["category_summary"]["fiber_process"]["pdf_count"] == 1
    assert summary["category_summary"]["mechanism"]["pdf_count"] == 1
    assert summary["category_summary"]["rheology"]["pdf_count"] == 1
    assert summary["category_summary"]["applications"]["pdf_count"] == 1


def test_source_manifest_normalizes_category_aliases_and_paths(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"

    alias_cases = {
        "Applications": ("applications", "001_app"),
        "Fiber_Process": ("fiber_process", "002_fiber"),
        "FiberProcess": ("fiber_process", "003_fiber_alt"),
        "fiber-process": ("fiber_process", "004_fiber_dash"),
        "Mechanism": ("mechanism", "005_mech"),
        "Rheology": ("rheology", "006_rheo"),
        "UnknownFolder": ("uncategorized", "007_unknown"),
    }
    for folder_name, (_, paper_id) in alias_cases.items():
        (pdf_dir / folder_name).mkdir(parents=True, exist_ok=True)
        (pdf_dir / folder_name / f"{paper_id}.pdf").write_text("fake pdf", encoding="utf-8")

    result = MODULE.build_source_manifest(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        out_dir=out_dir,
        min_markdown_chars=100,
    )

    rows_by_paper = {row["paper_id_guess"]: row for row in result["rows"]}
    for folder_name, (expected_category, paper_id) in alias_cases.items():
        row = rows_by_paper[paper_id]
        assert row["category"] == expected_category, folder_name
        assert row["source_id"].startswith(f"{expected_category}__")
        if expected_category != "uncategorized":
            assert row["markdown_expected_path"].endswith(
                str(Path("markdown") / expected_category / f"{paper_id}.md")
            )
            assert row["output_dir"].endswith(
                str(Path("outputs") / expected_category / paper_id)
            )
        else:
            assert row["category"] == "uncategorized"


def test_source_manifest_writes_csv_and_run_groups(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    out_dir = tmp_path / "batch_manifest"
    (pdf_dir / "fiber_process").mkdir(parents=True, exist_ok=True)
    (pdf_dir / "fiber_process" / "paper-a.pdf").write_text("fake pdf", encoding="utf-8")

    result = MODULE.build_source_manifest(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        out_dir=out_dir,
        min_markdown_chars=100,
    )

    csv_path = Path(result["csv_path"])
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and rows[0]["category"] == "fiber_process"
    assert rows[0]["markdown_status"] == "not_generated"

    run_groups = Path(result["run_groups_path"]).read_text(encoding="utf-8")
    assert "Recommended Stage1 Smoke 10" in run_groups
    assert "fiber_process__paper_a" in run_groups
