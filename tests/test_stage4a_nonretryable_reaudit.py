from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "audit_stage4a_nonretryable_details.py"
RERUN_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "rerun_stage4a_from_manifest.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(path)


def test_schema_failed_readable_image_becomes_force_retry_candidate(tmp_path: Path) -> None:
    module = _load_module(AUDIT_SCRIPT_PATH, "audit_stage4a_nonretryable_details_script")
    image_path = tmp_path / "img.png"
    _write_image(image_path)
    result = module.classify_nonretryable_candidate(
        original_error_type="schema_validation_failed",
        original_error_message="1 validation error for MicroscopyExtraction",
        image_check={
            "resolved_image_path": str(image_path),
            "image_exists": True,
            "image_size_bytes": image_path.stat().st_size,
            "image_readable": True,
            "image_error": "",
        },
        has_raw_real=True,
        has_extraction_live=False,
        has_failed=True,
        duplicate_or_inconsistent=False,
    )

    assert result["force_retry_candidate"] is True
    assert result["new_retry_reason"] == "schema_or_parse_error_with_readable_image"


def test_missing_image_that_cannot_be_resolved_stays_true_nonretryable(tmp_path: Path) -> None:
    module = _load_module(AUDIT_SCRIPT_PATH, "audit_stage4a_nonretryable_details_script")
    image_check = module.inspect_image_reference(
        image_path="missing.png",
        paper_dir=tmp_path / "paper",
        outputs_dir=tmp_path / "outputs",
        project_root=tmp_path,
    )
    result = module.classify_nonretryable_candidate(
        original_error_type="missing_image_path",
        original_error_message="missing_image_path",
        image_check=image_check,
        has_raw_real=False,
        has_extraction_live=False,
        has_failed=True,
        duplicate_or_inconsistent=False,
    )

    assert result["true_nonretryable"] is True
    assert result["new_retry_reason"] == "image_missing_now"


def test_missing_image_history_becomes_force_retry_when_path_now_resolvable(tmp_path: Path) -> None:
    module = _load_module(AUDIT_SCRIPT_PATH, "audit_stage4a_nonretryable_details_script")
    paper_dir = tmp_path / "paper"
    image_path = paper_dir / "figures_for_vision" / "img.png"
    _write_image(image_path)
    image_check = module.inspect_image_reference(
        image_path=str(image_path),
        paper_dir=paper_dir,
        outputs_dir=tmp_path / "outputs",
        project_root=tmp_path,
    )
    result = module.classify_nonretryable_candidate(
        original_error_type="missing_image_path",
        original_error_message="missing_image_path",
        image_check=image_check,
        has_raw_real=False,
        has_extraction_live=False,
        has_failed=True,
        duplicate_or_inconsistent=False,
    )

    assert result["force_retry_candidate"] is True
    assert result["new_retry_reason"] == "path_now_resolvable"


def test_force_retry_manifest_prefers_resolved_image_path(tmp_path: Path) -> None:
    audit_module = _load_module(AUDIT_SCRIPT_PATH, "audit_stage4a_nonretryable_details_script")
    image_path = tmp_path / "outputs" / "fiber_process" / "paper1" / "figures_for_vision" / "img.png"
    _write_image(image_path)
    coverage_csv = tmp_path / "coverage.csv"
    error_csv = tmp_path / "errors.csv"
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper1"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        stage4_dir / "spectra_failed_records.jsonl",
        [{"figure_id": "fig-1", "error_type": "missing_image_path", "error_message": "missing_image_path"}],
    )
    coverage_csv.write_text(
        "category,paper_id,figure_id,image_path,status,has_raw_real,has_extraction_live,has_failed,duplicate_or_inconsistent,error_type,error_message\n"
        f"fiber_process,paper1,fig-1,{image_path},failed_nonretryable,False,False,True,False,missing_image_path,missing_image_path\n",
        encoding="utf-8",
    )
    error_csv.write_text("status,error_type,error_message,count\n", encoding="utf-8")

    result = audit_module.run_nonretryable_reaudit(
        coverage_csv=coverage_csv,
        error_summary_csv=error_csv,
        outputs_dir=outputs_dir,
        audit_dir=tmp_path / "audit",
    )
    rows = list(audit_module.csv.DictReader((result["force_retry_csv"]).open("r", encoding="utf-8")))

    assert rows[0]["resolved_image_path"] == str(image_path)


def test_rerun_script_defaults_to_dry_run_and_force_nonretryable_selection(tmp_path: Path) -> None:
    module = _load_module(RERUN_SCRIPT_PATH, "rerun_stage4a_from_manifest_script")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img.png,resolved.png,failed_nonretryable,path_now_resolvable,force_rerun_with_resolved_path,False,P2\n",
        encoding="utf-8",
    )
    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter={"failed_nonretryable"},
        force_nonretryable=True,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["live_call_enabled"] is False
    assert result["summary"]["per_paper"][0]["resolved_image_paths"]["fig-1"] == "resolved.png"
