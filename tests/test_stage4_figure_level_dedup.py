from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from alumina_sol_extractor.stage4.processed_index import (
    classify_stage4a_figure_processing_action,
    load_stage4a_processed_figure_index,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTINUE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "continue_stage4a_full_eligible_live.py"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def _load_continue_module():
    spec = importlib.util.spec_from_file_location("continue_stage4a_full_eligible_live_script", CONTINUE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_processed_index_marks_success_raw_replay_transient_and_missing_image(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra_universal"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 1, "dry_run_count": 0, "successful_extractions_count": 1, "failed_record_count": 3}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {
                "figure_id": "fig-success",
                "source_image_path": "img-success.png",
                "extraction_mode": "live",
            }
        ],
    )
    _write_jsonl(
        stage4_dir / "raw_vlm_outputs.jsonl",
        [
            {"figure_id": "fig-replay", "dry_run": False, "raw_response": "{\"ok\": true}"},
            {"figure_id": "fig-dry", "dry_run": True, "raw_response": None},
        ],
    )
    _write_jsonl(
        stage4_dir / "spectra_failed_records.jsonl",
        [
            {"figure_id": "fig-schema", "error_type": "schema_validation_failed", "error_message": "schema_validation_failed"},
            {"figure_id": "fig-timeout", "error_type": "read_timeout", "error_message": "Read timed out", "is_transient": True},
            {"figure_id": "fig-missing", "error_type": "missing_image_path", "error_message": "missing_image_path"},
        ],
    )

    index = load_stage4a_processed_figure_index(stage4_dir)

    assert index["successful_figure_ids"] == {"fig-success"}
    assert index["successful_image_paths"] == {"img-success.png"}
    assert index["raw_vlm_figure_ids"] == {"fig-replay"}
    assert index["schema_failed_figure_ids"] == {"fig-schema"}
    assert index["transient_failed_figure_ids"] == {"fig-timeout"}
    assert index["missing_image_path_figure_ids"] == {"fig-missing"}


def test_dry_run_only_summary_does_not_treat_extractions_as_live_success(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra_universal"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 0, "dry_run_count": 10, "successful_extractions_count": 0, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [{"figure_id": "fig-dry", "source_image_path": "img-dry.png", "extraction_mode": "dry_run"}],
    )

    index = load_stage4a_processed_figure_index(stage4_dir)

    assert index["successful_figure_ids"] == set()
    assert index["dry_run_only_figure_ids"] == {"fig-dry"}
    assert index["dry_run_only_summary"] is True


def test_classify_stage4a_figure_processing_action_prioritizes_success_then_replay_then_transient() -> None:
    processed_index = {
        "successful_figure_ids": {"fig-success"},
        "successful_image_paths": {"img-success.png"},
        "raw_vlm_figure_ids": {"fig-replay"},
        "failed_figure_ids": {"fig-schema", "fig-transient", "fig-missing"},
        "schema_failed_figure_ids": {"fig-schema"},
        "transient_failed_figure_ids": {"fig-transient"},
        "missing_image_path_figure_ids": {"fig-missing"},
        "blocked_failed_figure_ids": set(),
        "dry_run_only_figure_ids": set(),
    }

    assert classify_stage4a_figure_processing_action({"figure_id": "fig-success", "source_image_path": "img-success.png"}, processed_index) == (
        "skip_success",
        "already_successful_extraction",
    )
    assert classify_stage4a_figure_processing_action({"figure_id": "fig-replay", "source_image_path": "img-replay.png"}, processed_index) == (
        "replay_candidate",
        "raw_vlm_output_available",
    )
    assert classify_stage4a_figure_processing_action({"figure_id": "fig-schema", "source_image_path": "img-schema.png"}, processed_index) == (
        "replay_candidate",
        "schema_validation_failed",
    )
    assert classify_stage4a_figure_processing_action({"figure_id": "fig-transient", "source_image_path": "img-transient.png"}, processed_index) == (
        "rerun_transient",
        "transient_failure",
    )
    assert classify_stage4a_figure_processing_action({"figure_id": "fig-missing", "source_image_path": ""}, processed_index) == (
        "missing_image",
        "missing_image_path",
    )


def test_continue_script_audit_only_does_not_treat_032_dry_run_only_as_completed(tmp_path: Path, monkeypatch) -> None:
    module = _load_continue_module()
    project_root = tmp_path
    outputs_root = project_root / "data" / "outputs"
    reports_root = project_root / "data" / "batch_validation_reports"
    docs_root = project_root / "docs" / "refactor"
    selected_csv = reports_root / "stage4a_universal_full_eligible_selected_papers.csv"
    selected_csv.parent.mkdir(parents=True, exist_ok=True)
    docs_root.mkdir(parents=True, exist_ok=True)
    paper_id = "032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究"
    selected_csv.write_text(
        "category,paper_id,run_action\nfiber_process," + paper_id + ",run_live\n",
        encoding="utf-8",
    )
    paper_output_dir = outputs_root / "fiber_process" / paper_id
    stage3_dir = paper_output_dir / "stage3_twopass"
    stage4_dir = paper_output_dir / "stage4_vision_spectra_universal"
    image_path = paper_output_dir / "fig1.jpg"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"img")
    (paper_output_dir / "figures.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "caption": "FTIR spectrum", "image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (paper_output_dir / "vision_inputs.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "figure_class": "other", "vision_image_path": str(image_path)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"dry_run_count": 10, "live_count": 0, "successful_extractions_count": 0, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [{"figure_id": "fig-1", "extraction_mode": "dry_run"}])

    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module, "SELECTED_CSV", selected_csv)
    monkeypatch.setattr(module, "REMAINING_CSV", reports_root / "remaining.csv")
    monkeypatch.setattr(module, "COMPLETED_CSV", reports_root / "completed.csv")
    monkeypatch.setattr(module, "FAILED_CSV", reports_root / "failed.csv")
    monkeypatch.setattr(module, "REMAINING_TXT", reports_root / "remaining.txt")
    monkeypatch.setattr(module, "AUDIT_CSV", reports_root / "audit.csv")
    monkeypatch.setattr(module, "AUDIT_SUMMARY_JSON", reports_root / "audit_summary.json")
    monkeypatch.setattr(module, "AUDIT_MD", docs_root / "audit.md")
    monkeypatch.setattr(module, "STATUS_MD", docs_root / "status.md")
    monkeypatch.setattr(module, "CHUNK_ROOT", reports_root / "chunks")

    result = module.run_audit_only()

    assert result["rows"][0]["dry_run_only_summary"] is True
    assert result["rows"][0]["run_action"] == "defer_032"
    assert result["summary"]["remaining_figures_to_send_vlm"] == 1
