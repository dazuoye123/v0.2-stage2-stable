from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "run_stage3_batch.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_stage3_batch_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _FakeStage3Result:
    def __init__(self, output_dir: Path, summary: dict):
        self.output_dir = output_dir
        self.summary = summary


def test_stage3_batch_estimate_only_reports_cost_without_llm(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "# 2.2 实验部分\n![](figures_all/a.png)\n图2 相关测试结果图\n",
        encoding="utf-8",
    )
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )

    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        estimate_only=True,
        mode="two-pass",
        limit=1,
    )

    row = result["rows"][0]
    assert row["status"] == "estimate_only"
    assert row["stage3_mode"] == "two-pass"
    assert row["cleaned_body_char_count"] > 0
    assert row["estimated_llm_call_count"] == 2
    assert result["summary"]["total_estimated_llm_call_count"] == 2


def test_stage3_batch_two_pass_mode_records_summary(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )

    def fake_run_stage3(**kwargs):
        assert kwargs["mode"] == "two-pass"
        summary = {
            "stage3_mode": "two-pass",
            "stage3_dspy": "enabled",
            "cleaned_body_char_count": 1200,
            "paper_text_char_count": 900,
            "experiment_series_count": 1,
            "data_point_count": 2,
            "process_steps_count": 3,
            "evidence_object_count": 4,
            "llm_call_count": 2,
        }
        (stage3_dir / "stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        (stage3_dir / "stage3_procedure_sections.json").write_text("[]", encoding="utf-8")
        return _FakeStage3Result(stage3_dir, summary)

    monkeypatch.setattr(module, "run_stage3_dspy_pipeline", fake_run_stage3)

    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mode="two-pass",
        force=True,
        limit=1,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["stage3_mode"] == "two-pass"
    assert row["estimated_llm_call_count"] == 2


def test_stage3_batch_unified_mode_records_summary(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )

    def fake_run_stage3(**kwargs):
        assert kwargs["mode"] == "unified"
        summary = {
            "stage3_mode": "unified",
            "stage3_dspy": "enabled",
            "cleaned_body_char_count": 1200,
            "paper_text_char_count": 900,
            "experiment_series_count": 1,
            "data_point_count": 2,
            "process_steps_count": 3,
            "evidence_object_count": 4,
            "llm_call_count": 1,
        }
        (stage3_dir / "stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        (stage3_dir / "stage3_procedure_sections.json").write_text("[]", encoding="utf-8")
        return _FakeStage3Result(stage3_dir, summary)

    monkeypatch.setattr(module, "run_stage3_dspy_pipeline", fake_run_stage3)

    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mode="unified",
        force=True,
        limit=1,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["stage3_mode"] == "unified"
    assert row["estimated_llm_call_count"] == 1


def test_stage3_batch_full_mode_remains_default(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    paper_output_dir = outputs_dir / "fiber_process" / "paper1"
    stage3_dir = paper_output_dir / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )

    def fake_run_stage3(**kwargs):
        assert kwargs["mode"] == "full"
        summary = {
            "stage3_mode": "full",
            "stage3_dspy": "enabled",
            "cleaned_body_char_count": 1000,
            "paper_text_char_count": 1000,
            "experiment_series_count": 2,
            "data_point_count": 5,
            "process_steps_count": 4,
            "evidence_object_count": 3,
            "llm_call_count": 7,
        }
        (stage3_dir / "stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        (stage3_dir / "stage3_procedure_sections.json").write_text("[{}, {}]", encoding="utf-8")
        return _FakeStage3Result(stage3_dir, summary)

    monkeypatch.setattr(module, "run_stage3_dspy_pipeline", fake_run_stage3)

    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        force=True,
        limit=1,
    )

    row = result["rows"][0]
    assert row["status"] == "success"
    assert row["stage3_mode"] == "full"
    assert row["estimated_llm_call_count"] == 7


def test_stage3_batch_mode_aware_skip_does_not_skip_different_mode(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    stage3_dir = outputs_dir / "fiber_process" / "paper1" / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )
    (stage3_dir / "stage3_summary.json").write_text(
        json.dumps({"stage3_mode": "full", "schema_valid": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (stage3_dir / "stage3_procedure_sections.json").write_text("[]", encoding="utf-8")

    def fake_run_stage3(**kwargs):
        assert kwargs["mode"] == "two-pass"
        summary = {
            "stage3_mode": "two-pass",
            "stage3_dspy": "enabled",
            "cleaned_body_char_count": 500,
            "paper_text_char_count": 400,
            "experiment_series_count": 1,
            "data_point_count": 1,
            "process_steps_count": 1,
            "evidence_object_count": 1,
            "llm_call_count": 2,
        }
        (stage3_dir / "stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        return _FakeStage3Result(stage3_dir, summary)

    monkeypatch.setattr(module, "run_stage3_dspy_pipeline", fake_run_stage3)
    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mode="two-pass",
        limit=1,
    )

    assert result["rows"][0]["status"] == "success"
    assert result["rows"][0]["stage3_mode"] == "two-pass"


def test_stage3_batch_mode_aware_skip_skips_same_mode_valid_summary(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    stage3_dir = outputs_dir / "fiber_process" / "paper1" / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )
    (stage3_dir / "stage3_summary.json").write_text(
        json.dumps(
            {
                "stage3_mode": "two-pass",
                "schema_valid": True,
                "stage3_dspy": "enabled",
                "cleaned_body_char_count": 500,
                "paper_text_char_count": 400,
                "experiment_series_count": 2,
                "data_point_count": 3,
                "process_steps_count": 4,
                "evidence_object_count": 5,
                "llm_call_count": 2,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (stage3_dir / "stage3_procedure_sections.json").write_text("[{}, {}]", encoding="utf-8")

    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mode="two-pass",
        limit=1,
    )

    row = result["rows"][0]
    assert row["status"] == "skipped_existing"
    assert row["stage3_mode"] == "two-pass"
    assert row["llm_call_count"] == 2


def test_stage3_batch_damaged_summary_does_not_skip(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "source_manifest.csv"
    markdown_dir = tmp_path / "markdown"
    outputs_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    markdown_path = markdown_dir / "fiber_process" / "paper1.md"
    stage3_dir = outputs_dir / "fiber_process" / "paper1" / "stage3"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# 2.2 实验部分\n正文\n", encoding="utf-8")
    manifest.write_text(
        "source_id,category,paper_id_guess,markdown_expected_path\n"
        f"s1,fiber_process,paper1,{markdown_path}\n",
        encoding="utf-8",
    )
    (stage3_dir / "stage3_summary.json").write_text("{broken", encoding="utf-8")

    def fake_run_stage3(**kwargs):
        summary = {
            "stage3_mode": "two-pass",
            "stage3_dspy": "enabled",
            "cleaned_body_char_count": 500,
            "paper_text_char_count": 400,
            "experiment_series_count": 1,
            "data_point_count": 1,
            "process_steps_count": 1,
            "evidence_object_count": 1,
            "llm_call_count": 2,
        }
        (stage3_dir / "stage3_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        return _FakeStage3Result(stage3_dir, summary)

    monkeypatch.setattr(module, "run_stage3_dspy_pipeline", fake_run_stage3)
    result = module.run_stage3_batch(
        manifest=manifest,
        markdown_dir=markdown_dir,
        outputs_dir=outputs_dir,
        report_dir=report_dir,
        mode="two-pass",
        limit=1,
    )

    assert result["rows"][0]["status"] == "success"
