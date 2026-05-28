from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "run_stage4a_stage2_selected_batch.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_stage4a_stage2_selected_batch_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_audit_only_uses_stage2_selected_figures_and_dedup(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_dir / "stage3_twopass"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    figures_for_vision = paper_dir / "figures_for_vision"
    image_path = figures_for_vision / "fig1.png"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    figures_for_vision.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"img")
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (paper_dir / "figures.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-1",
                "vision_image_path": str(image_path),
                "caption": "FTIR spectrum",
                "figure_class": "unknown",
                "send_to_vision_model": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 1, "failed_record_count": 0, "successful_extractions_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage4_dir / "spectra_extractions.jsonl").write_text(
        json.dumps({"figure_id": "fig-1", "source_image_path": str(image_path), "extraction_mode": "live"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_audit_only(
        rows=module._load_manifest_rows(manifest),
        outputs_dir=outputs_dir,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        candidate_source="stage2-selected",
        max_figures_per_paper=0,
        defer_large_papers=True,
    )

    assert result["summary"]["total_stage2_selected_figures"] == 1
    assert result["summary"]["already_live_success_figures"] == 1
    assert result["summary"]["new_live_candidate_figures"] == 0
    assert result["summary"]["duplicate_vlm_prevented_count"] == 1


def test_review_only_reports_zero_midpoint_and_scale_bar_errors(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_dir / "stage3_twopass"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 1, "failed_record_count": 0, "successful_extractions_count": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage4_dir / "spectra_extractions.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-1",
                "figure_type": "unknown",
                "actual_figure_type": "unknown",
                "type_mismatch": False,
                "peaks": [{"position": None, "source_text": "1000–1100 cm^-1"}],
                "scale_bar": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (stage4_dir / "spectra_failed_records.jsonl").write_text("", encoding="utf-8")
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_review_only(
        rows=module._load_manifest_rows(manifest),
        outputs_dir=outputs_dir,
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
    )

    assert result["summary"]["range_peak_midpoint_error_count"] == 0
    assert result["summary"]["sem_tem_unscaled_diameter_error_count"] == 0
