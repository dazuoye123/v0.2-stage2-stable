from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from alumina_sol_extractor.stage3.quality_grading import (
    RUBRIC_VERSION,
    aggregate_quality_review,
    evaluate_stage3_twopass_paper,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCRIPT = PROJECT_ROOT / "scripts" / "dev" / "review_stage3_twopass_quality.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _make_paper(tmp_path: Path, *, category: str = "fiber_process", paper_id: str = "paper1") -> Path:
    paper_dir = tmp_path / "data" / "outputs" / category / paper_id
    stage3_dir = paper_dir / "stage3_twopass"
    text_dir = paper_dir / "stage3_text"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    return paper_dir


def _write_common_summary(stage3_dir: Path, **overrides) -> None:
    payload = {
        "stage3_mode": "two-pass",
        "schema_valid": True,
        "canonical_key_errors_count": 0,
        "rejected_parameter_records_count": 0,
    }
    payload.update(overrides)
    (stage3_dir / "stage3_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_unified_grading_marks_strong_paper_as_a_even_without_source_text(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path)
    stage3_dir = paper_dir / "stage3_twopass"
    _write_common_summary(stage3_dir)
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [
            {
                "canonical_key": "calcination_temperature_C",
                "raw_name": "calcination temperature",
                "value": 1000,
                "unit": "C",
                "context": "calcined at 1000 C for 2 h",
                "evidence_refs": ["fig-xrd-1"],
            }
            for _ in range(6)
        ],
    )
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [
            {"action": "dissolve", "evidence_text": "PVA was dissolved in water at 80 C."},
            {"action": "stir", "evidence_text": "The solution was stirred for 2 h."},
            {"action": "electrospin", "evidence_text": "The solution was electrospun at 15 kV."},
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [
            {"evidence_id": "ev-1", "figure_id": "fig-xrd-1"},
            {"evidence_id": "ev-2", "figure_id": "fig-sem-1"},
            {"evidence_id": "ev-3", "figure_id": "fig-tg-1"},
        ],
    )
    _write_jsonl(
        paper_dir / "figures.jsonl",
        [
            {"figure_id": "fig-xrd-1", "figure_class": "xrd_pattern"},
            {"figure_id": "fig-sem-1", "figure_class": "microscopy_image"},
        ],
    )
    (paper_dir / "stage3_text" / "cleaned_body.md").write_text(
        "# Experimental\nPVA was dissolved in water at 80 C and stirred for 2 h before electrospinning.",
        encoding="utf-8",
    )
    review = evaluate_stage3_twopass_paper(
        category="fiber_process",
        paper_id="paper1",
        paper_output_dir=paper_dir,
    )
    assert review["rubric_version"] == RUBRIC_VERSION
    assert review["overall_grade"] == "A"
    assert review["data_points_grade"] == "A"


def test_unified_grading_marks_light_process_warning_as_b(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path)
    stage3_dir = paper_dir / "stage3_twopass"
    _write_common_summary(stage3_dir)
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [{"canonical_key": "ph_value", "raw_name": "pH", "value": 4, "unit": ""} for _ in range(8)],
    )
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [
            {"action": "other", "evidence_text": "The slurry was prepared."},
            {"action": "stir", "evidence_text": "The slurry was stirred for 2 h."},
            {"action": "dry", "evidence_text": "The gel was dried at 80 C."},
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [{"evidence_id": "ev-1", "figure_id": "fig-1"}, {"evidence_id": "ev-2", "figure_id": "fig-2"}],
    )
    _write_jsonl(paper_dir / "figures.jsonl", [{"figure_id": "fig-1", "figure_class": "xrd_pattern"}])
    review = evaluate_stage3_twopass_paper(
        category="fiber_process",
        paper_id="paper1",
        paper_output_dir=paper_dir,
    )
    assert review["overall_grade"] == "B"
    assert review["process_steps_grade"] == "B"


def test_unified_grading_marks_severe_process_failure_as_c(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path)
    stage3_dir = paper_dir / "stage3_twopass"
    _write_common_summary(stage3_dir)
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [{"canonical_key": "viscosity_mPa_s", "raw_name": "viscosity", "value": 500, "unit": "mPa s"} for _ in range(8)],
    )
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [
            {"action": "other", "evidence_text": ""},
            {"action": "other", "evidence_text": ""},
            {"action": "other", "evidence_text": ""},
        ],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [{"evidence_id": "ev-1", "figure_id": "fig-1"}, {"evidence_id": "ev-2", "figure_id": "fig-2"}],
    )
    _write_jsonl(paper_dir / "figures.jsonl", [{"figure_id": "fig-1", "figure_class": "xrd_pattern"}])
    review = evaluate_stage3_twopass_paper(
        category="fiber_process",
        paper_id="paper1",
        paper_output_dir=paper_dir,
    )
    assert review["overall_grade"] == "C"
    assert review["manual_hold"] is True


def test_unified_grading_marks_unreadable_summary_as_d(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path)
    stage3_dir = paper_dir / "stage3_twopass"
    (stage3_dir / "stage3_summary.json").write_text("{bad json", encoding="utf-8")
    review = evaluate_stage3_twopass_paper(
        category="fiber_process",
        paper_id="paper1",
        paper_output_dir=paper_dir,
    )
    assert review["overall_grade"] == "D"


def test_unified_grading_marks_review_like_paper_as_manual_hold(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path, paper_id="review_paper")
    stage3_dir = paper_dir / "stage3_twopass"
    _write_common_summary(stage3_dir)
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [{"canonical_key": "temperature_C", "raw_name": "temperature", "value": 1000, "unit": "C"} for _ in range(8)],
    )
    _write_jsonl(
        stage3_dir / "process_steps.jsonl",
        [{"action": "other", "evidence_text": ""} for _ in range(3)],
    )
    _write_jsonl(
        stage3_dir / "evidence_objects.jsonl",
        [{"evidence_id": "ev-1", "figure_id": "fig-1"} for _ in range(4)],
    )
    _write_jsonl(paper_dir / "figures.jsonl", [{"figure_id": "fig-1", "figure_class": "xrd_pattern"}])
    review = evaluate_stage3_twopass_paper(
        category="fiber_process",
        paper_id="123_Research progress review paper",
        paper_output_dir=paper_dir,
    )
    assert review["manual_hold"] is True
    assert review["overall_grade"] == "C"


def test_unified_grading_is_deterministic(tmp_path: Path) -> None:
    paper_dir = _make_paper(tmp_path)
    stage3_dir = paper_dir / "stage3_twopass"
    _write_common_summary(stage3_dir)
    _write_jsonl(
        stage3_dir / "data_points.jsonl",
        [
            {
                "canonical_key": "temperature_C",
                "raw_name": "temperature",
                "value": 1000,
                "unit": "C",
                "source_text": "calcined at 1000 C",
            }
            for _ in range(6)
        ],
    )
    _write_jsonl(stage3_dir / "process_steps.jsonl", [{"action": "stir", "evidence_text": "stirred for 2 h"}])
    _write_jsonl(stage3_dir / "evidence_objects.jsonl", [{"evidence_id": "ev-1", "figure_id": "fig-1"} for _ in range(3)])
    _write_jsonl(paper_dir / "figures.jsonl", [{"figure_id": "fig-1", "figure_class": "xrd_pattern"}])
    first = evaluate_stage3_twopass_paper(category="fiber_process", paper_id="paper1", paper_output_dir=paper_dir)
    second = evaluate_stage3_twopass_paper(category="fiber_process", paper_id="paper1", paper_output_dir=paper_dir)
    assert first == second
    summary = aggregate_quality_review([first, second])
    assert summary["A_count"] == 2


def test_review_script_uses_unified_evaluator() -> None:
    script_text = REVIEW_SCRIPT.read_text(encoding="utf-8")
    assert "evaluate_stage3_twopass_paper" in script_text
    assert "aggregate_quality_review" in script_text
