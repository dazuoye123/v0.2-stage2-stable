from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

RUBRIC_VERSION = "stage3_twopass_quality_v1"

SCIENTIFIC_FIGURE_CLASSES = {
    "xrd_pattern",
    "ftir_spectrum",
    "raman_spectrum",
    "thermal_analysis_plot",
    "microscopy_image",
    "mechanical_property_plot",
    "ferron_curve",
    "rheology_curve",
}

REVIEW_TITLE_MARKERS = (
    "review",
    "research progress",
    "progress paper",
    "literature review",
    "综述",
    "研究进展",
    "现状",
)

PROCEDURE_GOOD_MARKERS = (
    "实验部分",
    "实验材料",
    "实验方法",
    "实验过程",
    "制备方法",
    "制备过程",
    "样品制备",
    "溶胶制备",
    "前驱体制备",
    "纺丝",
    "静电纺丝",
    "干法纺丝",
    "热处理",
    "煅烧",
    "预烧结",
    "烧结",
    "测试与表征",
    "experimental",
    "experimental section",
    "materials and methods",
    "materials",
    "methods",
    "synthesis",
    "preparation",
    "sample preparation",
    "sol preparation",
    "precursor preparation",
    "electrospinning",
    "spinning",
    "calcination",
    "heat treatment",
    "sintering",
    "characterization",
)

PROCEDURE_BAD_MARKERS = (
    "绪论",
    "研究背景",
    "研究意义",
    "文献综述",
    "研究进展",
    "小结",
    "总结",
    "结论",
    "introduction",
    "background",
    "literature review",
    "conclusions",
    "summary",
)

GENERIC_PROCESS_MARKERS = (
    "研究了",
    "分析了",
    "讨论了",
    "表征了",
    "测试了性能",
    "results show",
    "it can be seen",
    "as shown in fig",
    "characterization was performed",
    "properties were investigated",
    "thermal evolution was studied",
)

ACTION_WORD_MARKERS = (
    "称取",
    "加入",
    "滴加",
    "溶解",
    "混合",
    "搅拌",
    "陈化",
    "老化",
    "水解",
    "缩聚",
    "调节ph",
    "过滤",
    "洗涤",
    "干燥",
    "纺丝",
    "静电纺丝",
    "干法纺丝",
    "离心甩丝",
    "预烧结",
    "煅烧",
    "升温",
    "保温",
    "烧结",
    "冷却",
    "浸渍",
    "负载",
    "还原",
    "weigh",
    "add",
    "dropwise add",
    "dissolve",
    "mix",
    "stir",
    "age",
    "hydrolyze",
    "reflux",
    "filter",
    "wash",
    "dry",
    "prepare",
    "synthesize",
    "spin",
    "electrospin",
    "calcine",
    "heat",
    "heat treat",
    "sinter",
    "cool",
    "impregnate",
    "load",
    "reduce",
)


def evaluate_stage3_twopass_paper(
    *,
    category: str,
    paper_id: str,
    paper_output_dir: Path,
    source_group: str = "",
) -> dict[str, Any]:
    stage3_dir = paper_output_dir / "stage3_twopass"
    summary_path = stage3_dir / "stage3_summary.json"
    if not summary_path.exists():
        return _build_unreadable_result(
            category=category,
            paper_id=paper_id,
            source_group=source_group,
            stage3_summary_path=summary_path,
            main_problem="missing_stage3_summary",
        )

    try:
        summary = json.loads(_read_text(summary_path))
    except Exception:
        return _build_unreadable_result(
            category=category,
            paper_id=paper_id,
            source_group=source_group,
            stage3_summary_path=summary_path,
            main_problem="unreadable_stage3_summary",
        )

    if not isinstance(summary, dict):
        return _build_unreadable_result(
            category=category,
            paper_id=paper_id,
            source_group=source_group,
            stage3_summary_path=summary_path,
            main_problem="invalid_stage3_summary_payload",
        )

    process_steps = _read_jsonl(stage3_dir / "process_steps.jsonl")
    data_points = _read_jsonl(stage3_dir / "data_points.jsonl")
    evidence_objects = _read_jsonl(stage3_dir / "evidence_objects.jsonl")
    figures = _read_jsonl(paper_output_dir / "figures.jsonl")
    cleaned_body_text = _read_text(paper_output_dir / "stage3_text" / "cleaned_body.md")
    selected_sections_text = _read_text(stage3_dir / "stage3_selected_sections.md")
    cleaned_body_hint = str(summary.get("cleaned_body_path") or "").strip()
    markdown_text = _read_text(Path(cleaned_body_hint)) if cleaned_body_hint else ""
    if not markdown_text:
        data_dir = paper_output_dir.parents[2]
        markdown_text = _read_text(data_dir / "markdown" / category / f"{paper_id}.md")

    process_metrics = _compute_process_step_metrics(process_steps)
    data_metrics = _compute_data_point_metrics(data_points)
    evidence_metrics = _compute_evidence_metrics(evidence_objects)
    scientific_figure_count = sum(
        1
        for item in figures
        if str(item.get("figure_class") or "").strip() in SCIENTIFIC_FIGURE_CLASSES
    )
    cleaned_body_image_residue = _cleaned_body_has_image_residue(cleaned_body_text)
    raw_name_bug_count = _raw_name_bug_count(data_points)
    list_value_validation_error_count = sum(
        1 for item in data_points if isinstance(item.get("value"), list)
    )
    canonical_key_errors_count = int(summary.get("canonical_key_errors_count") or 0)
    rejected_parameter_records_count = int(summary.get("rejected_parameter_records_count") or 0)
    schema_valid = bool(summary.get("schema_valid", True))
    evidence_zero_with_scientific_figures = int(
        scientific_figure_count > 0 and len(evidence_objects) == 0
    )
    selected_good_heading_count, selected_bad_heading_count = _count_section_markers(
        selected_sections_text or markdown_text
    )
    review_like = _is_review_title(paper_id)

    hard_error_flags: list[str] = []
    warning_flags: list[str] = []
    if not schema_valid:
        hard_error_flags.append("schema_invalid")
    if raw_name_bug_count > 0:
        hard_error_flags.append("raw_name_key_value_bug")
    if list_value_validation_error_count > 0:
        hard_error_flags.append("list_value_validation_error")
    if canonical_key_errors_count > 0:
        hard_error_flags.append("canonical_key_errors_present")
    if rejected_parameter_records_count > 0:
        hard_error_flags.append("rejected_parameter_records_present")
    if evidence_zero_with_scientific_figures:
        hard_error_flags.append("scientific_figures_without_evidence")
    if cleaned_body_image_residue:
        hard_error_flags.append("cleaned_body_image_residue")
    if process_metrics["count"] == 0:
        hard_error_flags.append("process_steps_zero")

    if process_metrics["warning"]:
        warning_flags.append("process_steps_warning")
    if process_metrics["severe"]:
        warning_flags.append("severe_process_steps_warning")
    if data_metrics["source_missing_ratio"] > 0.6:
        warning_flags.append("data_point_source_support_sparse")
    if evidence_metrics["missing_figure_ratio"] > 0.5:
        warning_flags.append("evidence_link_sparse")
    if selected_bad_heading_count > selected_good_heading_count and selected_bad_heading_count >= 2:
        warning_flags.append("section_scope_warning")
    if review_like:
        warning_flags.append("review_like_title")

    data_points_grade = _grade_data_points(
        count=len(data_points),
        raw_name_bug_count=raw_name_bug_count,
        list_value_validation_error_count=list_value_validation_error_count,
        canonical_key_errors_count=canonical_key_errors_count,
        rejected_parameter_records_count=rejected_parameter_records_count,
        source_missing_ratio=data_metrics["source_missing_ratio"],
        supported_count=data_metrics["supported_count"],
    )
    evidence_grade = _grade_evidence(
        count=len(evidence_objects),
        missing_figure_ratio=evidence_metrics["missing_figure_ratio"],
        evidence_zero_with_scientific_figures=bool(evidence_zero_with_scientific_figures),
    )
    process_steps_grade = _grade_process_steps(process_metrics)
    section_selection_grade = (
        "C"
        if selected_bad_heading_count > selected_good_heading_count and selected_bad_heading_count >= 2
        else "B"
    )
    cleaned_body_grade = "A" if not cleaned_body_image_residue else "C"

    manual_hold = False
    main_problem = "strong_all_around"
    recommended_action = "usable_as_is"
    overall_grade = "A"

    if not schema_valid:
        overall_grade = "D"
        main_problem = "schema_invalid"
        recommended_action = "hold"
    elif review_like and process_steps_grade == "C" and data_points_grade in {"A", "B"} and evidence_grade in {"A", "B"}:
        overall_grade = "C"
        manual_hold = True
        main_problem = "review_or_no_experiment"
        recommended_action = "hold"
    elif data_points_grade == "C" or evidence_grade == "C":
        overall_grade = "C"
        main_problem = "core_module_issue"
        recommended_action = "rerun_after_fix"
    elif process_steps_grade == "C":
        overall_grade = "C"
        manual_hold = True
        main_problem = "process_steps_only"
        recommended_action = "hold"
    elif process_steps_grade == "B" or data_points_grade == "B" or evidence_grade == "B" or section_selection_grade == "C":
        overall_grade = "B"
        main_problem = "minor_review_needed"
        recommended_action = "usable_with_manual_review"

    usable_set_grade = "excluded_manual_hold" if manual_hold else overall_grade

    return {
        "rubric_version": RUBRIC_VERSION,
        "category": category,
        "paper_id": paper_id,
        "source_group": source_group,
        "stage3_mode": summary.get("stage3_mode", ""),
        "overall_grade": overall_grade,
        "manual_hold": manual_hold,
        "usable_set_grade": usable_set_grade,
        "data_points_grade": data_points_grade,
        "process_steps_grade": process_steps_grade,
        "evidence_grade": evidence_grade,
        "cleaned_body_grade": cleaned_body_grade,
        "section_selection_grade": section_selection_grade,
        "hard_error_flags": hard_error_flags,
        "warning_flags": warning_flags,
        "main_problem": main_problem,
        "recommended_action": recommended_action,
        "process_steps_count": process_metrics["count"],
        "other_action_ratio": process_metrics["other_ratio"],
        "missing_evidence_text_ratio": process_metrics["missing_ratio"],
        "canonical_key_errors_count": canonical_key_errors_count,
        "rejected_parameter_records_count": rejected_parameter_records_count,
        "raw_name_key_value_bug_count": raw_name_bug_count,
        "list_value_validation_error_count": list_value_validation_error_count,
        "evidence_zero_with_scientific_figures_count": evidence_zero_with_scientific_figures,
        "cleaned_body_image_residue_count": int(cleaned_body_image_residue),
        "data_point_count": len(data_points),
        "evidence_object_count": len(evidence_objects),
        "process_steps_warning": process_metrics["warning"],
        "severe_process_steps_warning": process_metrics["severe"],
        "average_other_action_ratio_component": process_metrics["other_ratio"],
        "average_missing_evidence_text_ratio_component": process_metrics["missing_ratio"],
        "process_steps_zero_count": int(process_metrics["count"] == 0),
        "data_point_source_missing_ratio": data_metrics["source_missing_ratio"],
        "evidence_missing_figure_ratio": evidence_metrics["missing_figure_ratio"],
        "selected_good_heading_count": selected_good_heading_count,
        "selected_bad_heading_count": selected_bad_heading_count,
        "schema_valid": schema_valid,
        "stage3_summary_path": str(summary_path),
    }


def aggregate_quality_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(str(row.get("overall_grade") or "") for row in rows)
    usable_rows = [row for row in rows if not row.get("manual_hold")]
    usable_counts = Counter(str(row.get("overall_grade") or "") for row in usable_rows)
    return {
        "rubric_version": RUBRIC_VERSION,
        "tested_papers_count": total,
        "A_count": counts["A"],
        "B_count": counts["B"],
        "C_count": counts["C"],
        "D_count": counts["D"],
        "manual_hold_count": sum(1 for row in rows if row.get("manual_hold")),
        "usable_set_A_count": usable_counts["A"],
        "usable_set_B_count": usable_counts["B"],
        "usable_set_C_count": usable_counts["C"],
        "usable_set_D_count": usable_counts["D"],
        "raw_name_key_value_bug_count": sum(int(row.get("raw_name_key_value_bug_count") or 0) for row in rows),
        "list_value_validation_error_count": sum(
            int(row.get("list_value_validation_error_count") or 0) for row in rows
        ),
        "evidence_zero_with_scientific_figures_count": sum(
            int(row.get("evidence_zero_with_scientific_figures_count") or 0) for row in rows
        ),
        "cleaned_body_image_residue_count": sum(
            int(row.get("cleaned_body_image_residue_count") or 0) for row in rows
        ),
        "average_canonical_key_errors_count": _average(rows, "canonical_key_errors_count"),
        "average_rejected_parameter_records_count": _average(rows, "rejected_parameter_records_count"),
        "process_steps_warning_count": sum(1 for row in rows if row.get("process_steps_warning")),
        "average_other_action_ratio": _average(rows, "average_other_action_ratio_component"),
        "average_missing_evidence_text_ratio": _average(rows, "average_missing_evidence_text_ratio_component"),
        "process_steps_zero_count": sum(int(row.get("process_steps_zero_count") or 0) for row in rows),
        "severe_process_steps_warning_count": sum(
            1 for row in rows if row.get("severe_process_steps_warning")
        ),
        "source_text_warning_count": sum(
            1
            for row in rows
            if "data_point_source_support_sparse" in (row.get("warning_flags") or [])
        ),
    }


def render_quality_review_markdown(
    *,
    title: str,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    extra_lines: list[str] | None = None,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- rubric_version = {summary.get('rubric_version')}",
        f"- tested_papers_count = {summary.get('tested_papers_count')}",
        f"- A = {summary.get('A_count')}",
        f"- B = {summary.get('B_count')}",
        f"- C = {summary.get('C_count')}",
        f"- D = {summary.get('D_count')}",
        f"- manual_hold = {summary.get('manual_hold_count')}",
        f"- usable_set_A = {summary.get('usable_set_A_count')}",
        f"- usable_set_B = {summary.get('usable_set_B_count')}",
        f"- usable_set_C = {summary.get('usable_set_C_count')}",
        f"- usable_set_D = {summary.get('usable_set_D_count')}",
        f"- raw_name_key_value_bug_count = {summary.get('raw_name_key_value_bug_count')}",
        f"- list_value_validation_error_count = {summary.get('list_value_validation_error_count')}",
        f"- evidence_zero_with_scientific_figures_count = {summary.get('evidence_zero_with_scientific_figures_count')}",
        f"- cleaned_body_image_residue_count = {summary.get('cleaned_body_image_residue_count')}",
        f"- average_canonical_key_errors_count = {summary.get('average_canonical_key_errors_count')}",
        f"- average_rejected_parameter_records_count = {summary.get('average_rejected_parameter_records_count')}",
        f"- process_steps_warning_count = {summary.get('process_steps_warning_count')}",
        f"- source_text_warning_count = {summary.get('source_text_warning_count')}",
        f"- average_other_action_ratio = {summary.get('average_other_action_ratio')}",
        f"- average_missing_evidence_text_ratio = {summary.get('average_missing_evidence_text_ratio')}",
        f"- process_steps_zero_count = {summary.get('process_steps_zero_count')}",
        f"- severe_process_steps_warning_count = {summary.get('severe_process_steps_warning_count')}",
        "",
    ]
    if extra_lines:
        lines.extend(extra_lines)
        lines.append("")

    top_c = [row for row in rows if row.get("overall_grade") == "C"][:20]
    if top_c:
        lines.append("## C Papers")
        lines.append("")
        for row in top_c:
            lines.append(
                f"- {row.get('paper_id')} ({row.get('category')}): "
                f"main_problem={row.get('main_problem')}, "
                f"recommended_action={row.get('recommended_action')}, "
                f"manual_hold={row.get('manual_hold')}"
            )
        lines.append("")
    return "\n".join(lines)


def _build_unreadable_result(
    *,
    category: str,
    paper_id: str,
    source_group: str,
    stage3_summary_path: Path,
    main_problem: str,
) -> dict[str, Any]:
    return {
        "rubric_version": RUBRIC_VERSION,
        "category": category,
        "paper_id": paper_id,
        "source_group": source_group,
        "stage3_mode": "",
        "overall_grade": "D",
        "manual_hold": False,
        "usable_set_grade": "D",
        "data_points_grade": "D",
        "process_steps_grade": "D",
        "evidence_grade": "D",
        "cleaned_body_grade": "D",
        "section_selection_grade": "D",
        "hard_error_flags": [main_problem],
        "warning_flags": [],
        "main_problem": main_problem,
        "recommended_action": "hold",
        "process_steps_count": 0,
        "other_action_ratio": 1.0,
        "missing_evidence_text_ratio": 1.0,
        "canonical_key_errors_count": 0,
        "rejected_parameter_records_count": 0,
        "raw_name_key_value_bug_count": 0,
        "list_value_validation_error_count": 0,
        "evidence_zero_with_scientific_figures_count": 0,
        "cleaned_body_image_residue_count": 0,
        "data_point_count": 0,
        "evidence_object_count": 0,
        "process_steps_warning": True,
        "severe_process_steps_warning": True,
        "average_other_action_ratio_component": 1.0,
        "average_missing_evidence_text_ratio_component": 1.0,
        "process_steps_zero_count": 1,
        "data_point_source_missing_ratio": 1.0,
        "evidence_missing_figure_ratio": 1.0,
        "selected_good_heading_count": 0,
        "selected_bad_heading_count": 0,
        "schema_valid": False,
        "stage3_summary_path": str(stage3_summary_path),
    }


def _compute_process_step_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
    if not steps:
        return {
            "count": 0,
            "other_ratio": 1.0,
            "missing_ratio": 1.0,
            "warning": True,
            "severe": True,
        }
    other = 0
    missing = 0
    supported = 0
    generic = 0
    heading_like = 0
    for step in steps:
        action = str(step.get("action") or "").strip().lower()
        if action == "other":
            other += 1
        evidence_text = str(step.get("evidence_text") or "").strip()
        description = str(step.get("description") or "").strip()
        source = evidence_text or description
        lowered = source.lower()
        if not evidence_text:
            missing += 1
        if source.startswith("#") or source.startswith("|"):
            heading_like += 1
        if any(marker in lowered for marker in GENERIC_PROCESS_MARKERS):
            generic += 1
        if any(marker in lowered for marker in ACTION_WORD_MARKERS) or action not in {"", "other"}:
            supported += 1
    count = len(steps)
    other_ratio = round(other / count, 4)
    missing_ratio = round(missing / count, 4)
    support_ratio = supported / count
    severe = (
        count == 0
        or (other_ratio >= 0.7 and missing_ratio >= 0.7)
        or (heading_like / count) >= 0.25
        or support_ratio < 0.35
    )
    warning = severe or other_ratio >= 0.3 or missing_ratio >= 0.5 or (generic / count) >= 0.25
    return {
        "count": count,
        "other_ratio": other_ratio,
        "missing_ratio": missing_ratio,
        "warning": warning,
        "severe": severe,
    }


def _compute_data_point_metrics(data_points: list[dict[str, Any]]) -> dict[str, Any]:
    if not data_points:
        return {"source_missing_ratio": 1.0, "supported_count": 0}
    supported = 0
    missing = 0
    for point in data_points:
        source_text = str(point.get("source_text") or point.get("evidence_text") or "").strip()
        context = str(point.get("context") or point.get("source_context") or "").strip()
        evidence_refs = point.get("evidence_refs") or point.get("evidence_ref") or point.get("evidence_id")
        if source_text or context or evidence_refs:
            supported += 1
        else:
            missing += 1
    return {
        "source_missing_ratio": round(missing / len(data_points), 4),
        "supported_count": supported,
    }


def _compute_evidence_metrics(evidence_objects: list[dict[str, Any]]) -> dict[str, Any]:
    if not evidence_objects:
        return {"missing_figure_ratio": 1.0}
    missing = 0
    for item in evidence_objects:
        if not str(item.get("figure_id") or item.get("table_id") or "").strip():
            missing += 1
    return {"missing_figure_ratio": round(missing / len(evidence_objects), 4)}


def _grade_data_points(
    *,
    count: int,
    raw_name_bug_count: int,
    list_value_validation_error_count: int,
    canonical_key_errors_count: int,
    rejected_parameter_records_count: int,
    source_missing_ratio: float,
    supported_count: int,
) -> str:
    if (
        raw_name_bug_count > 0
        or list_value_validation_error_count > 0
        or canonical_key_errors_count > 0
        or rejected_parameter_records_count > 0
        or count == 0
    ):
        return "C"
    if count < 5:
        return "B"
    if source_missing_ratio > 0.8:
        return "B"
    if source_missing_ratio > 0.6:
        return "B"
    return "A"


def _grade_evidence(
    *,
    count: int,
    missing_figure_ratio: float,
    evidence_zero_with_scientific_figures: bool,
) -> str:
    if evidence_zero_with_scientific_figures or count == 0:
        return "C"
    if count < 3 or missing_figure_ratio > 0.5:
        return "B"
    return "A"


def _grade_process_steps(process_metrics: dict[str, Any]) -> str:
    if process_metrics["severe"]:
        return "C"
    if process_metrics["warning"]:
        return "B"
    return "A"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _cleaned_body_has_image_residue(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("![", "<img", "figures_all/", "figures_for_vision/", ".png)", ".jpg)", ".jpeg)", ".webp)")
    )


def _raw_name_bug_count(data_points: list[dict[str, Any]]) -> int:
    bad_names = {"key", "value", "unit", "context", "evidence_ref", "evidence_id"}
    return sum(
        1
        for item in data_points
        if str(item.get("raw_name") or "").strip().lower() in bad_names
    )


def _is_review_title(paper_id: str) -> bool:
    lowered = paper_id.lower()
    return any(marker in lowered for marker in REVIEW_TITLE_MARKERS)


def _count_section_markers(text: str) -> tuple[int, int]:
    lowered = text.lower()
    good = sum(1 for marker in PROCEDURE_GOOD_MARKERS if marker.lower() in lowered)
    bad = sum(1 for marker in PROCEDURE_BAD_MARKERS if marker.lower() in lowered)
    return good, bad


def _average(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row.get(field) or 0) for row in rows) / len(rows), 4)
