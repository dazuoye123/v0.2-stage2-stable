"""Export helpers for Stage 5 dataset fusion."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from alumina_sol_extractor.utils.jsonl import write_jsonl


def write_json(path: Path | str, payload: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown(path: Path | str, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_csv(path: Path | str, rows: list[dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _normalize_csv_value(row.get(key)) for key in fieldnames})
    return path


def write_parquet(path: Path | str, rows: list[dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Stage 5 parquet export requires pandas.") from exc
    frame = pd.DataFrame(rows)
    object_columns = [column for column in frame.columns if str(frame[column].dtype) == "object"]
    for column in object_columns:
        frame[column] = frame[column].apply(_normalize_parquet_value).astype("string")
    frame.to_parquet(path, index=False)
    return path


def export_fusion_outputs(bundle: dict[str, Any], dataset_dir: Path | str) -> dict[str, str]:
    dataset_dir = Path(dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "paper": str(write_json(dataset_dir / "paper.json", bundle["paper"])),
        "samples": str(write_jsonl(bundle["samples"], dataset_dir / "samples.jsonl")),
        "parameters": str(write_jsonl(bundle["parameters"], dataset_dir / "parameters.jsonl")),
        "evidence": str(write_jsonl(bundle["evidence"], dataset_dir / "evidence.jsonl")),
        "figures": str(write_jsonl(bundle["figures"], dataset_dir / "figures.jsonl")),
        "spectra": str(write_jsonl(bundle["spectra"], dataset_dir / "spectra.jsonl")),
        "quality_summary": str(write_json(dataset_dir / "quality_summary.json", bundle["quality_summary"])),
        "final_dataset_csv": str(write_csv(dataset_dir / "final_dataset.csv", bundle["final_dataset_rows"])),
        "final_dataset_parquet": str(write_parquet(dataset_dir / "final_dataset.parquet", bundle["final_dataset_rows"])),
        "fusion_report": str(write_markdown(dataset_dir / "fusion_report.md", bundle["fusion_report"])),
    }
    return output_paths


def _normalize_csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _normalize_parquet_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, default=str)
