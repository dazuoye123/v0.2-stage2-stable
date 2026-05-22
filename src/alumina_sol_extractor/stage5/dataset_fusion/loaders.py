"""Load Stage 3 and Stage 4 outputs for dataset fusion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def resolve_stage_dirs(
    output_dir: Path | str,
    *,
    stage3_dir: Path | str | None = None,
    stage4_dir: Path | str | None = None,
    output_dataset_dir: Path | str | None = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    return {
        "output_dir": output_dir,
        "stage3_dir": Path(stage3_dir) if stage3_dir else output_dir / "stage3_dspy_smoke",
        "stage4_dir": Path(stage4_dir) if stage4_dir else output_dir / "stage4_vision_spectra",
        "dataset_dir": Path(output_dataset_dir) if output_dataset_dir else output_dir / "final_dataset",
    }


def load_paper_inputs(
    output_dir: Path | str,
    *,
    stage3_dir: Path | str | None = None,
    stage4_dir: Path | str | None = None,
    output_dataset_dir: Path | str | None = None,
) -> dict[str, Any]:
    dirs = resolve_stage_dirs(
        output_dir,
        stage3_dir=stage3_dir,
        stage4_dir=stage4_dir,
        output_dataset_dir=output_dataset_dir,
    )
    stage3_dir_path = dirs["stage3_dir"]
    stage4_dir_path = dirs["stage4_dir"]
    stage3_files = {
        "paper_basic_info": stage3_dir_path / "paper_basic_info.json",
        "global_constants": stage3_dir_path / "global_constants.json",
        "experiment_series": stage3_dir_path / "experiment_series.jsonl",
        "data_points": stage3_dir_path / "data_points.jsonl",
        "process_steps": stage3_dir_path / "process_steps.jsonl",
        "evidence_objects": stage3_dir_path / "evidence_objects.jsonl",
        "paper_extraction": stage3_dir_path / "paper_extraction.schema_v2.json",
        "stage3_summary": stage3_dir_path / "stage3_smoke_summary.json",
        "stage3_validation_report": stage3_dir_path / "stage3_validation_report.md",
    }
    stage4_files = {
        "spectra_extractions": stage4_dir_path / "spectra_extractions.jsonl",
        "stage4_summary": stage4_dir_path / "stage4_summary.json",
        "stage4_quality_review": stage4_dir_path / "stage4_quality_review.json",
        "stage4_quality_review_md": stage4_dir_path / "stage4_quality_review.md",
    }
    payload = {
        "dirs": dirs,
        "file_index": {
            "stage3": {name: str(path) for name, path in stage3_files.items()},
            "stage4": {name: str(path) for name, path in stage4_files.items()},
        },
        "file_presence": {
            "stage3": {name: path.exists() for name, path in stage3_files.items()},
            "stage4": {name: path.exists() for name, path in stage4_files.items()},
        },
        "stage3": {
            "paper_basic_info": read_json(stage3_files["paper_basic_info"], default={}) or {},
            "global_constants": read_json(stage3_files["global_constants"], default={}) or {},
            "experiment_series": read_jsonl(stage3_files["experiment_series"]),
            "data_points": read_jsonl(stage3_files["data_points"]),
            "process_steps": read_jsonl(stage3_files["process_steps"]),
            "evidence_objects": read_jsonl(stage3_files["evidence_objects"]),
            "paper_extraction": read_json(stage3_files["paper_extraction"], default={}) or {},
            "summary": read_json(stage3_files["stage3_summary"], default={}) or {},
            "validation_report": stage3_files["stage3_validation_report"].read_text(encoding="utf-8")
            if stage3_files["stage3_validation_report"].exists()
            else "",
        },
        "stage4": {
            "spectra_extractions": read_jsonl(stage4_files["spectra_extractions"]),
            "summary": read_json(stage4_files["stage4_summary"], default={}) or {},
            "quality_review": read_json(stage4_files["stage4_quality_review"], default={}) or {},
            "quality_review_md": stage4_files["stage4_quality_review_md"].read_text(encoding="utf-8")
            if stage4_files["stage4_quality_review_md"].exists()
            else "",
        },
    }
    return payload
