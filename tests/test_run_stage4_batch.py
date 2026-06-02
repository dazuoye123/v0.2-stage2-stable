from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_stage4_batch.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_stage4_batch_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_run_stage4_batch_defaults_to_stage3_twopass_and_universal_subdir(tmp_path: Path) -> None:
    module = _load_script_module()
    outputs_dir = tmp_path / "outputs"
    manifest = tmp_path / "source_manifest.csv"
    paper_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_dir / "stage3_twopass"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"schema_valid": True}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_stage4_batch(
        outputs_dir=outputs_dir,
        manifest=manifest,
        dry_run=True,
    )

    row = result["rows"][0]
    assert row["stage3_dir"].endswith("stage3_twopass")
    assert row["stage4_dir"].endswith("stage4_vision_spectra_universal")


def test_run_stage4_batch_live_skip_existing_uses_live_success_not_dry_run_only(tmp_path: Path) -> None:
    module = _load_script_module()
    outputs_dir = tmp_path / "outputs"
    manifest = tmp_path / "source_manifest.csv"
    paper_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_dir / "stage3_twopass"
    stage4_dir = paper_dir / "stage4_vision_spectra_universal"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"schema_valid": True}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"dry_run_count": 3, "live_count": 0, "successful_extractions_count": 1, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest.write_text("source_id,category,paper_id_guess\ns1,fiber_process,paper1\n", encoding="utf-8")

    result = module.run_stage4_batch(
        outputs_dir=outputs_dir,
        manifest=manifest,
        dry_run=False,
        continue_on_error=True,
    )

    assert result["rows"][0]["status"] != "skipped_existing"


def test_parse_args_supports_stage4_aliases(monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_stage4_batch.py",
            "--outputs-dir",
            "tmp",
            "--live",
            "--stage4-routing-mode",
            "universal_compact",
        ],
    )
    args = module.parse_args()
    assert args.live is True
    assert args.stage4_routing_mode == "universal_compact"
