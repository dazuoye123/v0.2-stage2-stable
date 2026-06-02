from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.stage4.processed_index import (
    is_dry_run_extraction_record,
    is_fallback_success_extraction_record,
    is_live_success_extraction_record,
    load_stage4a_processed_figure_index,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def test_dry_run_only_records_do_not_become_successful_figure_ids(tmp_path: Path) -> None:
    stage4_dir = tmp_path / "stage4_vision_spectra_universal"
    stage4_dir.mkdir(parents=True, exist_ok=True)
    (stage4_dir / "stage4a_summary.json").write_text(
        json.dumps({"live_count": 0, "dry_run_count": 2, "successful_extractions_count": 0, "failed_record_count": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_jsonl(stage4_dir / "spectra_extractions.jsonl", [{"figure_id": "fig-1", "extraction_mode": "dry_run"}])
    _write_jsonl(stage4_dir / "raw_vlm_outputs.jsonl", [{"figure_id": "fig-1", "dry_run": True, "raw_response": None}])

    index = load_stage4a_processed_figure_index(stage4_dir)

    assert index["successful_figure_ids"] == set()
    assert index["dry_run_only_figure_ids"] == {"fig-1"}


def test_live_and_fallback_detection_are_separate() -> None:
    live_record = {"figure_id": "fig-live", "extraction_mode": "live", "parse_success": True}
    fallback_record = {"figure_id": "fig-fallback", "extraction_mode": "reused_previous_success"}
    summary = {"live_count": 1, "dry_run_count": 0}

    assert is_live_success_extraction_record(live_record, summary=summary) is True
    assert is_dry_run_extraction_record(live_record, summary=summary) is False
    assert is_fallback_success_extraction_record(fallback_record) is True
    assert is_live_success_extraction_record(fallback_record, summary=summary) is False


def test_summary_live_count_zero_only_blocks_unmarked_records() -> None:
    summary = {"live_count": 0, "dry_run_count": 3}
    unmarked_record = {"figure_id": "fig-1"}
    explicit_live_record = {"figure_id": "fig-2", "extraction_mode": "live", "parse_success": True}

    assert is_dry_run_extraction_record(unmarked_record, summary=summary) is True
    assert is_live_success_extraction_record(unmarked_record, summary=summary) is False
    assert is_live_success_extraction_record(explicit_live_record, summary=summary) is True
