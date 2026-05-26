from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from alumina_sol_extractor.utils.jsonl import write_jsonl

from .procedure_sections import select_procedure_sections
from alumina_sol_extractor.dspy_modules.runner import (
    _build_rule_based_process_steps_v3,
    _count_process_step_repairs,
    _count_process_step_warnings,
    _extract_procedure_text,
    _fallback_process_steps_are_better,
    _normalize_process_steps_payload,
    _process_steps_are_too_generic,
    _process_steps_missing_evidence_ratio,
    _process_steps_other_action_ratio,
)

REVIEW_LIKE_TOKENS = (
    "研究进展",
    "文献综述",
    "综述",
    "浅谈",
    "review",
    "research progress",
    "literature review",
)


def process_steps_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
    process_steps_count = len(steps)
    return {
        "process_steps_count": process_steps_count,
        "other_action_ratio": _process_steps_other_action_ratio(steps),
        "missing_evidence_text_ratio": _process_steps_missing_evidence_ratio(steps),
        "process_steps_warning_count": _count_process_step_warnings(steps),
        "process_steps_repaired_count": _count_process_step_repairs(steps),
    }


def diagnose_process_steps_issue(
    *,
    paper_id: str,
    cleaned_body_text: str,
    process_steps: list[dict[str, Any]],
    data_points_count: int,
    evidence_objects_count: int,
) -> dict[str, Any]:
    metrics = process_steps_metrics(process_steps)
    selected_sections, selected_text = select_procedure_sections(cleaned_body_text)
    selected_titles = [str(item.get("title") or "") for item in selected_sections if item.get("selected_for_process_steps")]
    selected_blob = " ".join(selected_titles).lower()
    review_like = any(token in paper_id.lower() for token in REVIEW_LIKE_TOKENS) or any(
        token in selected_blob for token in REVIEW_LIKE_TOKENS
    )
    english_heavy = _looks_english_heavy(cleaned_body_text)
    has_procedure_signal = bool(selected_text.strip() or _extract_procedure_text(cleaned_body_text).strip())

    if data_points_count <= 0 or evidence_objects_count <= 0:
        issue_type = "real_core_failure"
    elif not has_procedure_signal:
        issue_type = "procedure_scope_error"
    elif english_heavy and metrics["process_steps_count"] <= 2:
        issue_type = "english_procedure_weak"
    elif review_like and metrics["other_action_ratio"] >= 0.5:
        issue_type = "insufficient_source"
    else:
        issue_type = "process_steps_only"

    if issue_type == "procedure_scope_error":
        recommended_fix_type = "procedure_section_selection"
    elif issue_type == "english_procedure_weak":
        recommended_fix_type = "english_procedure_fallback"
    elif issue_type == "insufficient_source":
        recommended_fix_type = "manual_hold_or_process_steps_only_llm"
    elif issue_type == "real_core_failure":
        recommended_fix_type = "hold"
    else:
        recommended_fix_type = "process_steps_repair"

    return {
        **metrics,
        "issue_type": issue_type,
        "review_like": review_like,
        "english_heavy": english_heavy,
        "selected_titles": selected_titles,
        "selected_procedure_text": selected_text,
        "recommended_fix_type": recommended_fix_type,
    }


def repair_process_steps_records(
    *,
    cleaned_body_text: str,
    process_steps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = _normalize_process_steps_payload(process_steps)
    before = process_steps_metrics(normalized)

    procedure_sections, procedure_text = select_procedure_sections(cleaned_body_text)
    procedure_text = procedure_text.strip() or _extract_procedure_text(cleaned_body_text)
    fallback_steps = _build_rule_based_process_steps_v3(procedure_text) if procedure_text else []

    repair_used = False
    repair_reason = "kept_existing_steps"
    repaired = normalized

    if not normalized:
        repaired = fallback_steps
        repair_used = bool(fallback_steps)
        repair_reason = "empty_steps_used_fallback" if fallback_steps else "manual_hold_no_steps"
    elif _process_steps_are_too_generic(normalized) and fallback_steps:
        if _fallback_process_steps_are_better(normalized, fallback_steps):
            repaired = fallback_steps
            repair_used = True
            repair_reason = "replaced_generic_steps_with_fallback"
    elif fallback_steps and _fallback_process_steps_are_better(normalized, fallback_steps):
        repaired = fallback_steps
        repair_used = True
        repair_reason = "fallback_stronger_than_existing"

    after = process_steps_metrics(repaired)
    manual_hold = not repaired or (
        after["other_action_ratio"] >= 0.8 and after["missing_evidence_text_ratio"] >= 0.8
    )
    repair_log = {
        "selected_procedure_sections": procedure_sections,
        "selected_procedure_text_char_count": len(procedure_text or ""),
        "before": before,
        "after": after,
        "repair_used": repair_used,
        "repair_reason": repair_reason,
        "manual_hold": manual_hold,
    }
    return repaired, repair_log


def apply_process_steps_repair_to_paper(
    *,
    paper_output_dir: Path,
    stage3_subdir: str = "stage3_twopass",
) -> dict[str, Any]:
    stage3_dir = paper_output_dir / stage3_subdir
    stage3_text_dir = paper_output_dir / "stage3_text"
    cleaned_body_path = stage3_text_dir / "cleaned_body.md"
    process_steps_path = stage3_dir / "process_steps.jsonl"
    summary_path = stage3_dir / "stage3_summary.json"
    extraction_path = stage3_dir / "paper_extraction.schema_v2.json"

    cleaned_body_text = cleaned_body_path.read_text(encoding="utf-8", errors="ignore")
    backup_path = stage3_dir / "process_steps.before_C_repair.jsonl"
    process_steps = _read_jsonl(backup_path) if backup_path.exists() else _read_jsonl(process_steps_path)
    repaired_steps, repair_log = repair_process_steps_records(
        cleaned_body_text=cleaned_body_text,
        process_steps=process_steps,
    )

    if not backup_path.exists():
        write_jsonl(process_steps, backup_path)
    write_jsonl(repaired_steps, process_steps_path)

    (stage3_dir / "process_steps_repair_log.json").write_text(
        json.dumps(repair_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    procedure_sections = repair_log["selected_procedure_sections"]
    (stage3_dir / "stage3_procedure_sections.json").write_text(
        json.dumps(procedure_sections, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    selected_text = "\n\n".join(
        str(item.get("text_preview") or "")
        for item in procedure_sections
        if item.get("selected_for_process_steps")
    ).strip()
    (stage3_dir / "stage3_selected_sections.md").write_text(selected_text, encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    after = repair_log["after"]
    summary.update(
        {
            "process_steps_count": len(repaired_steps),
            "process_steps_repair_used": bool(repair_log["repair_used"]),
            "process_steps_repair_count": int(after["process_steps_repaired_count"]),
            "process_steps_manual_hold_count": 1 if repair_log["manual_hold"] else 0,
            "process_steps_other_action_ratio": float(after["other_action_ratio"]),
            "process_steps_missing_evidence_ratio": float(after["missing_evidence_text_ratio"]),
            "process_steps_warning_count": int(after["process_steps_warning_count"]),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if extraction_path.exists():
        extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
        extraction["process_steps"] = repaired_steps
        extraction_path.write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "repair_log_path": str(stage3_dir / "process_steps_repair_log.json"),
        "backup_path": str(backup_path),
        "process_steps_count": len(repaired_steps),
        "process_steps_other_action_ratio": after["other_action_ratio"],
        "process_steps_missing_evidence_ratio": after["missing_evidence_text_ratio"],
        "process_steps_warning_count": after["process_steps_warning_count"],
        "process_steps_manual_hold_count": 1 if repair_log["manual_hold"] else 0,
        "process_steps_repair_used": bool(repair_log["repair_used"]),
        "issue_type": diagnose_process_steps_issue(
            paper_id=paper_output_dir.name,
            cleaned_body_text=cleaned_body_text,
            process_steps=repaired_steps,
            data_points_count=_count_jsonl(stage3_dir / "data_points.jsonl"),
            evidence_objects_count=_count_jsonl(stage3_dir / "evidence_objects.jsonl"),
        )["issue_type"],
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _count_jsonl(path: Path) -> int:
    return len(_read_jsonl(path))


def _looks_english_heavy(text: str) -> bool:
    ascii_letters = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return ascii_letters > chinese
