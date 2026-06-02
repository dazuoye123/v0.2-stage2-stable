from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "audit_stage4a_coverage.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("audit_stage4a_coverage_script", SCRIPT_PATH)
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


def _write_minimal_paper(tmp_path: Path, *, paper_id: str = "paper1", figure_id: str = "fig-1") -> tuple[Path, Path, Path]:
    outputs_dir = tmp_path / "outputs"
    paper_dir = outputs_dir / "fiber_process" / paper_id
    stage3_dir = paper_dir / "stage3_twopass"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    figures_dir = paper_dir / "figures_for_vision"
    image_path = figures_dir / "fig1.png"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"img")
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (paper_dir / "figures.jsonl").write_text(
        json.dumps(
            {
                "figure_id": figure_id,
                "vision_image_path": str(image_path),
                "image_path": str(image_path),
                "caption": "FTIR spectrum",
                "figure_class": "unknown",
                "send_to_vision_model": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process," + paper_id + "\n", encoding="utf-8")
    return manifest, outputs_dir, stage4_dir


def test_dry_run_only_is_detected_and_added_to_manifest(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest, outputs_dir, stage4_dir = _write_minimal_paper(tmp_path)
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 0, "dry_run_count": 1, "successful_extractions_count": 0, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(stage4_dir / "raw_vlm_outputs.jsonl", [{"figure_id": "fig-1", "dry_run": True, "raw_response": None}])
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [{"figure_id": "fig-1", "extraction_mode": "dry_run"}])

    audit_dir = tmp_path / "audit"
    result = module.run_audit(manifest_path=manifest, outputs_dir=outputs_dir, audit_dir=audit_dir)

    assert result["consistency"]["dry_run_only_total"] == 1
    manifest_rows = list(module.csv.DictReader((audit_dir / "stage4a_missing_or_retry_manifest.csv").open("r", encoding="utf-8")))
    assert manifest_rows[0]["status"] == "dry_run_only"


def test_live_success_wins_even_with_dry_run_history(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest, outputs_dir, stage4_dir = _write_minimal_paper(tmp_path)
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 1, "dry_run_count": 1, "successful_extractions_count": 1, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(
        stage4_dir / "raw_vlm_outputs.jsonl",
        [
            {"figure_id": "fig-1", "dry_run": True, "raw_response": None},
            {"figure_id": "fig-1", "dry_run": False, "raw_response": "{\"figure_id\":\"fig-1\"}"},
        ],
    )
    _write_jsonl(
        stage4_dir / "spectra_extractions.jsonl",
        [
            {"figure_id": "fig-1", "extraction_mode": "dry_run"},
            {"figure_id": "fig-1", "extraction_mode": "live", "parse_success": True},
        ],
    )

    result = module.run_audit(manifest_path=manifest, outputs_dir=outputs_dir, audit_dir=tmp_path / "audit")

    assert result["consistency"]["success_live_total"] == 1
    assert result["consistency"]["dry_run_only_total"] == 0


def test_fallback_and_failed_statuses_are_separated(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    outputs_dir = tmp_path / "outputs"
    rows = ["source_id,category,paper_id_guess"]
    for index, paper_id in enumerate(["paper_fallback", "paper_retry", "paper_nonretry"], start=1):
        rows.append(f"s{index},fiber_process,{paper_id}")
        _write_minimal_paper(tmp_path, paper_id=paper_id)
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")

    fallback_dir = outputs_dir / "fiber_process" / "paper_fallback" / "stage4_vision_spectra_universal"
    (fallback_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 0, "dry_run_count": 0, "successful_extractions_count": 1, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(fallback_dir / "spectra_extractions.jsonl", [{"figure_id": "fig-1", "extraction_mode": "reused_previous_success"}])

    retry_dir = outputs_dir / "fiber_process" / "paper_retry" / "stage4_vision_spectra_universal"
    (retry_dir / "stage4a_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    _write_jsonl(
        retry_dir / "spectra_failed_records.jsonl",
        [{"figure_id": "fig-1", "error_type": "read_timeout", "error_message": "Read timed out", "is_transient": True}],
    )

    nonretry_dir = outputs_dir / "fiber_process" / "paper_nonretry" / "stage4_vision_spectra_universal"
    (nonretry_dir / "stage4a_summary.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    _write_jsonl(
        nonretry_dir / "spectra_failed_records.jsonl",
        [{"figure_id": "fig-1", "error_type": "missing_image_path", "error_message": "missing_image_path"}],
    )

    result = module.run_audit(manifest_path=manifest, outputs_dir=outputs_dir, audit_dir=tmp_path / "audit")

    assert result["consistency"]["success_reused_previous_total"] == 1
    assert result["consistency"]["failed_retryable_total"] == 1
    assert result["consistency"]["failed_nonretryable_total"] == 1
