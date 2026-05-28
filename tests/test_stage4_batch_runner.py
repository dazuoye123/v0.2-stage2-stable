from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "run_stage4a_batch.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_stage4a_batch_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage4_batch_runner_dry_run_uses_stage3_twopass_and_universal_subdir(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3_twopass"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (paper_output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "caption": "FTIR spectrum", "image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (paper_output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "figure_class": "other", "vision_image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_stage4a_batch(
        manifest=manifest,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        dry_run=True,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["stage4_dir"].endswith("stage4_vision_spectra_universal")
    assert row["routing_mode"] == "universal_compact"


def test_stage4_batch_runner_skip_existing(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3_twopass"
    stage4_dir = paper_output_dir / "stage4_vision_spectra_universal"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"dry_run_count": 1, "live_count": 0, "total_candidates": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_stage4a_batch(
        manifest=manifest,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        dry_run=True,
        skip_existing=True,
    )

    assert result["rows"][0]["status"] == "skipped_existing"


def test_stage4_batch_runner_live_not_blocked_by_dry_run_summary(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3_twopass"
    stage4_dir = paper_output_dir / "stage4_vision_spectra_universal"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"dry_run_count": 1, "live_count": 0, "total_candidates": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (paper_output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "caption": "FTIR spectrum", "image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (paper_output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "figure_class": "other", "vision_image_path": "fig1.jpg"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_stage4a_batch(
        manifest=manifest,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        dry_run=False,
        skip_existing=True,
    )

    assert result["rows"][0]["status"] == "success"


def test_is_live_successful_stage4_summary_requires_live_count_zero_failed_and_successful_extractions() -> None:
    module = _load_script_module()
    assert module._is_live_successful_stage4_summary(
        {"live_count": 1, "failed_record_count": 0, "successful_extractions_count": 1}
    ) is True
    assert module._is_live_successful_stage4_summary(
        {"live_count": 3, "failed_record_count": 0}
    ) is True
    assert module._is_live_successful_stage4_summary(
        {"live_count": 0, "failed_record_count": 0, "successful_extractions_count": 1}
    ) is False
    assert module._is_live_successful_stage4_summary(
        {"live_count": 1, "failed_record_count": 1, "successful_extractions_count": 1}
    ) is False
    assert module._is_live_successful_stage4_summary(
        {"live_count": 1, "failed_record_count": 0, "successful_extractions_count": 0}
    ) is False


def test_is_dry_run_only_stage4_summary_detects_non_live_placeholder() -> None:
    module = _load_script_module()
    assert module._is_dry_run_only_stage4_summary({"dry_run_count": 10, "live_count": 0}) is True
    assert module._is_dry_run_only_stage4_summary({"dry_run_count": 10, "live_count": 1}) is False
