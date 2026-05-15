from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.dspy_modules import runner


class _FakeResult:
    def __init__(self, payload):
        self.payload = payload
        self.error = None
        self.raw_output = json.dumps(payload, ensure_ascii=False)


class _FakeModule:
    def __init__(self, payload):
        self.payload = payload

    def run(self, **kwargs):
        return _FakeResult(self.payload)


def test_long_thesis_uses_cleaned_body_and_section_aware_without_mechanical_truncation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    intro = ("# 绪论\n" + ("背景介绍。\n" * 9000))
    methods = """# 2.2 实验部分
# 2.2.2 初始铝溶胶的制备
称取一定量九水合硝酸铝和铝粉，加入去离子水。加热至 70 ℃ 保温 1 h，再升温至 90 ℃ 保温 5.5 h，冷却后得到铝溶胶。"""
    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text(intro + "\n" + methods + "\n# 参考文献\n[1] demo", encoding="utf-8")

    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.jsonl").write_text("", encoding="utf-8")
    (output_dir / "vision_inputs.jsonl").write_text("", encoding="utf-8")
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(runner, "configure_dspy_lm", lambda settings: None)
    monkeypatch.setattr(runner, "ExtractPaperBasicInfoModule", lambda: _FakeModule({"title": "demo"}))
    monkeypatch.setattr(runner, "ExtractGlobalConstantsModule", lambda: _FakeModule({}))
    monkeypatch.setattr(runner, "ExtractExperimentSeriesModule", lambda: _FakeModule([]))
    monkeypatch.setattr(runner, "ExtractDataPointsModule", lambda: _FakeModule([]))
    monkeypatch.setattr(runner, "ExtractProcessStepsModule", lambda: _FakeModule([]))
    monkeypatch.setattr(runner, "ExtractEvidenceObjectsModule", lambda: _FakeModule([]))

    summary = runner._run_live_stage3_extraction(
        project_root=Path(__file__).resolve().parents[1],
        dspy_settings={"enabled": True, "outputs": {}, "run_judge": False, "chunk_size": 2000},
        paper_id="paper-1",
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
        stage3_dir_name="stage3_dspy_smoke",
        summary_filename="stage3_smoke_summary.json",
        raw_outputs_filename="raw_dspy_outputs.jsonl",
        paper_text_limit_chars=None,
        section_aware=False,
        section_method="rule",
        max_sections=4,
        section_keywords=["实验", "制备", "XRD"],
    )

    stage3_dir = output_dir / "stage3_dspy_smoke"
    selected_sections = (stage3_dir / "stage3_selected_sections.md").read_text(encoding="utf-8")
    procedure_sections = json.loads((stage3_dir / "stage3_procedure_sections.json").read_text(encoding="utf-8"))
    process_steps = [
        json.loads(line)
        for line in (stage3_dir / "process_steps.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert summary["stage3_input_mode"] == "section_aware"
    assert "2.2.2 初始铝溶胶的制备" in selected_sections
    assert any(item.get("selected_for_process_steps") for item in procedure_sections)
    assert len(process_steps) > 0
