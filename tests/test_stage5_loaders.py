from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dataset_fusion.loaders import load_paper_inputs, resolve_stage_dirs


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""), encoding="utf-8")


def test_loaders_handle_missing_stage4_without_crashing(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (stage3_dir / "paper_basic_info.json").write_text(json.dumps({"title": "paper"}, ensure_ascii=False), encoding="utf-8")
    _write_jsonl(stage3_dir / "data_points.jsonl", [])
    payload = load_paper_inputs(output_dir)
    assert payload["stage3"]["paper_basic_info"]["title"] == "paper"
    assert payload["stage4"]["spectra_extractions"] == []
    assert payload["file_presence"]["stage4"]["spectra_extractions"] is False


def test_resolve_stage_dirs_defaults_to_standard_layout(tmp_path: Path) -> None:
    resolved = resolve_stage_dirs(tmp_path / "paper-output")
    assert resolved["stage3_dir"].name == "stage3_dspy_smoke"
    assert resolved["stage4_dir"].name == "stage4_vision_spectra"
    assert resolved["dataset_dir"].name == "final_dataset"
