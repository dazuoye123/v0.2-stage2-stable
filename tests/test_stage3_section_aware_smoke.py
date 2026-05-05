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


def test_section_aware_smoke_uses_rule_based_selection_and_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    markdown_path = tmp_path / "paper.md"
    markdown_path.write_text(
        """# 纤维用铝溶胶前驱体的制备及表征

## 第二章 高 Al13 团簇含量铝溶胶的可控制备与表征
### 2.2 实验部分
反应温度、pH 和搅拌速率条件如下。
### 2.3 结果与讨论
图2.12 给出 27Al NMR 结果，图2.18 给出 FTIR，图2.19 给出 XRD。

## 第三章 分离研究
图3.7 给出标准曲线。
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"figure_id": "图2.12", "caption": "图2.12 27Al NMR 光谱", "reference_sentences": ["见图2.12"]}, ensure_ascii=False),
                json.dumps({"figure_id": "图3.7", "caption": "图3.7 第三章 NMR 标准曲线", "reference_sentences": ["见图3.7"]}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "vision_inputs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"figure_id": "图2.12", "figure_class": "nmr_spectrum"}, ensure_ascii=False),
                json.dumps({"figure_id": "图3.7", "figure_class": "nmr_quantification_plot"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "table_015.json").write_text(json.dumps([{"title": "第三章表格"}], ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(runner, "configure_dspy_lm", lambda settings: None)
    monkeypatch.setattr(runner, "ExtractPaperBasicInfoModule", lambda: _FakeModule({"author": "牛延强", "date": "2020-05-30"}))
    monkeypatch.setattr(runner, "ExtractGlobalConstantsModule", lambda: _FakeModule({"pH": 3.6, "nmr_27Al_peak_position_ppm": [0, 62.5]}))
    monkeypatch.setattr(runner, "ExtractExperimentSeriesModule", lambda: _FakeModule([{"series_id": "series-1", "series_name": "温度优化"}]))
    monkeypatch.setattr(
        runner,
        "ExtractDataPointsModule",
        lambda: _FakeModule([{"sample_id": "sample-1", "results": {"Al13_fraction_percent": 50}, "evidence_refs": ["图2.12"]}]),
    )
    monkeypatch.setattr(
        runner,
        "ExtractEvidenceObjectsModule",
        lambda: _FakeModule({"spectra": {"nmr": {"fact": "27Al NMR 证据", "evidence_source": "图2.12", "caption": "图2.12 27Al NMR 光谱"}}}),
    )

    summary = runner._run_live_stage3_extraction(
        project_root=project_root,
        dspy_settings={"enabled": True, "outputs": {}, "run_judge": False, "chunk_size": 2000},
        paper_id="niu_yanqiang_alumina_sol_ch2",
        cleaned_markdown_path=markdown_path,
        output_dir=output_dir,
        stage3_dir_name="stage3_dspy_smoke",
        summary_filename="stage3_smoke_summary.json",
        raw_outputs_filename="raw_dspy_outputs.jsonl",
        section_aware=True,
        section_method="rule",
        max_sections=3,
        section_keywords=["Al13", "NMR", "FTIR", "XRD", "pH"],
    )

    stage3_dir = output_dir / "stage3_dspy_smoke"
    selected_sections = (stage3_dir / "stage3_selected_sections.md").read_text(encoding="utf-8")
    evidence_scope = json.loads((stage3_dir / "stage3_evidence_scope.json").read_text(encoding="utf-8"))
    record = json.loads((stage3_dir / "paper_extraction.schema_v2.json").read_text(encoding="utf-8"))

    assert summary["schema_valid"] is True
    assert summary["evidence_object_count"] > 0
    assert "第二章 高 Al13 团簇含量铝溶胶的可控制备与表征" in selected_sections
    assert "第三章 分离研究" not in selected_sections
    assert evidence_scope["included_figure_ids"] == ["图2.12"]
    assert all(item.get("figure_id") != "图3.7" for item in record["evidence_objects"])
