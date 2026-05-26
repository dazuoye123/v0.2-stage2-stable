from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.stage3.process_steps_repair import (
    apply_process_steps_repair_to_paper,
    diagnose_process_steps_issue,
    repair_process_steps_records,
)


def test_diagnose_process_steps_issue_detects_process_steps_only_problem() -> None:
    cleaned = """# 2 实验过程
称取硝酸铝，加入去离子水，搅拌 2 h，煅烧 2 h。
"""
    steps = [
        {"action": "other", "description": "称取硝酸铝", "evidence_text": None},
        {"action": "other", "description": "加入去离子水", "evidence_text": None},
    ]
    diagnosis = diagnose_process_steps_issue(
        paper_id="demo_paper",
        cleaned_body_text=cleaned,
        process_steps=steps,
        data_points_count=12,
        evidence_objects_count=5,
    )
    assert diagnosis["issue_type"] == "process_steps_only"
    assert diagnosis["recommended_fix_type"] == "process_steps_repair"


def test_repair_backfills_evidence_and_uses_procedure_text() -> None:
    cleaned = """# 2 实验过程
将样品以 5 ℃/min 升温至 1000 ℃并保温 2 h。
"""
    steps = [{"action": "other", "description": "将样品以 5 ℃/min 升温至 1000 ℃并保温 2 h。", "evidence_text": ""}]
    repaired, log = repair_process_steps_records(cleaned_body_text=cleaned, process_steps=steps)
    assert repaired
    assert all(step.get("evidence_text") for step in repaired)
    assert any(step.get("temperature_value") == 1000.0 for step in repaired)
    assert any(step.get("heating_rate_value") == 5.0 for step in repaired)
    assert log["repair_used"] is True or log["after"]["process_steps_repaired_count"] >= 1


def test_repair_does_not_materialize_review_statements_and_can_manual_hold() -> None:
    cleaned = """# 1 研究进展
研究了材料性能。分析了结构。results show the trend.
"""
    repaired, log = repair_process_steps_records(cleaned_body_text=cleaned, process_steps=[])
    assert repaired == []
    assert log["manual_hold"] is True


def test_apply_process_steps_repair_updates_only_process_step_artifacts(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    stage3_dir = paper_dir / "stage3_twopass"
    text_dir = paper_dir / "stage3_text"
    stage3_dir.mkdir(parents=True)
    text_dir.mkdir(parents=True)

    (text_dir / "cleaned_body.md").write_text(
        "# 2 Experimental\nPVA was dissolved in water at 80 °C. The solution was stirred for 2 h and electrospun at 15 kV.\n",
        encoding="utf-8",
    )
    (stage3_dir / "process_steps.jsonl").write_text(
        json.dumps({"step_order": 1, "action": "other", "description": "PVA was dissolved in water at 80 °C.", "evidence_text": ""}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (stage3_dir / "data_points.jsonl").write_text(json.dumps({"raw_name": "good", "value": 1}, ensure_ascii=False) + "\n", encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text(json.dumps({"evidence_id": "ev-1", "figure_id": "Fig1"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text(json.dumps({"process_steps": [], "data_points": [{"raw_name": "good", "value": 1}]}, ensure_ascii=False), encoding="utf-8")
    (stage3_dir / "stage3_summary.json").write_text(json.dumps({"stage3_mode": "two-pass", "process_steps_count": 1}, ensure_ascii=False), encoding="utf-8")

    result = apply_process_steps_repair_to_paper(paper_output_dir=paper_dir, stage3_subdir="stage3_twopass")

    assert result["process_steps_count"] > 0
    assert (stage3_dir / "process_steps.before_C_repair.jsonl").exists()
    assert (stage3_dir / "process_steps_repair_log.json").exists()
    summary = json.loads((stage3_dir / "stage3_summary.json").read_text(encoding="utf-8"))
    assert "process_steps_repair_used" in summary
    assert "process_steps_other_action_ratio" in summary
    extraction = json.loads((stage3_dir / "paper_extraction.schema_v2.json").read_text(encoding="utf-8"))
    assert extraction["process_steps"]
    data_points = [json.loads(line) for line in (stage3_dir / "data_points.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert data_points == [{"raw_name": "good", "value": 1}]
