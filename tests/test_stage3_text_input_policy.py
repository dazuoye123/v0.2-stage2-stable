from __future__ import annotations

import inspect
import importlib.util
from pathlib import Path

from alumina_sol_extractor.batch_validation import full_resume
from alumina_sol_extractor.dspy_modules import runner


def test_stage3_smoke_runner_default_text_limit_is_none() -> None:
    signature = inspect.signature(runner.run_stage3_dspy_smoke_test)
    assert signature.parameters["paper_text_limit_chars"].default is None


def test_stage3_live_resume_no_longer_forces_5000_char_limit(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_runtime_settings(*args, **kwargs):
        return {"dspy": {}, "stage3": {}}

    def fake_run_stage3_dspy_smoke_test(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text("# 2.2.2 初始铝溶胶的制备\n正文", encoding="utf-8")

    monkeypatch.setattr(full_resume, "build_runtime_settings", fake_build_runtime_settings)
    monkeypatch.setattr(full_resume, "run_stage3_dspy_smoke_test", fake_run_stage3_dspy_smoke_test)

    full_resume._run_stage3_live(
        project_root=tmp_path,
        paper_id="paper-1",
        markdown_path=markdown_path,
        output_dir=tmp_path / "output",
    )

    assert captured["paper_text_limit_chars"] is None
    assert captured["section_aware"] is False


def test_stage3_smoke_cli_no_longer_mentions_4000_char_default() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_stage3_dspy_smoke_test.py"
    spec = importlib.util.spec_from_file_location("run_stage3_dspy_smoke_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.parse_args
    assert callable(parser)
    help_text = script_path.read_text(encoding="utf-8")
    assert "Defaults to 4000 in full-text mode" not in help_text
