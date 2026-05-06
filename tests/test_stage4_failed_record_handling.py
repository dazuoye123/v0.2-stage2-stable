from __future__ import annotations

import json
from pathlib import Path

import pytest

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor
from alumina_sol_extractor.vision_spectra.vlm_client import VLMRequest, VisionLanguageModelClient


class FakeLiveClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract(self, request: VLMRequest) -> dict[str, object]:
        self.calls.append(request.image_path)
        if request.image_path.endswith("fig18.jpg"):
            return {
                "dry_run": False,
                "model": "fake-vlm",
                "image_path": request.image_path,
                "prompt": request.prompt,
                "response_text": '{"figure_id":"图2.18","figure_type":"ftir_spectrum","spectrum_type":"FTIR","peaks":[],"confidence":0.72}',
                "response_payload": {"choices": [{"message": {"content": "ok"}}]},
            }
        return {
            "dry_run": False,
            "model": "fake-vlm",
            "image_path": request.image_path,
            "prompt": request.prompt,
            "response_text": "not json at all",
            "response_payload": {"choices": [{"message": {"content": "not json at all"}}]},
        }


def test_run_writes_failed_records_without_crashing(tmp_path: Path) -> None:
    output_dir = tmp_path / "paper-output"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = [
        {"figure_id": "图2.18", "caption": "图2.18 旋蒸后铝溶胶的IR谱图", "image_path": "fig18.jpg"},
        {"figure_id": "图2.19", "caption": "图2.19 铝溶胶的XRD图", "image_path": "fig19.jpg"},
    ]
    vision_inputs = [
        {"figure_id": "图2.18", "figure_class": "ftir_spectrum", "vision_image_path": "fig18.jpg"},
        {"figure_id": "图2.19", "figure_class": "xrd_pattern", "vision_image_path": "fig19.jpg"},
    ]
    stage3_dir = output_dir / "stage3_dspy_smoke"
    stage3_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in figures) + "\n", encoding="utf-8")
    (output_dir / "vision_inputs.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in vision_inputs) + "\n", encoding="utf-8")
    (stage3_dir / "evidence_objects.jsonl").write_text("", encoding="utf-8")
    (stage3_dir / "paper_extraction.schema_v2.json").write_text("{}", encoding="utf-8")

    client = FakeLiveClient()
    summary = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=output_dir,
        figure_ids=["图2.18", "图2.19"],
        max_figures=2,
        allowed_figure_types={"ftir_spectrum", "xrd_pattern"},
        dry_run=False,
        client=client,
    ).run()

    assert summary["live_count"] == 1
    assert summary["failed_record_count"] == 1
    failed_path = output_dir / "stage4_vision_spectra" / "failed_records.jsonl"
    assert failed_path.exists()
    failed_text = failed_path.read_text(encoding="utf-8")
    assert "图2.19" in failed_text
    raw_text = (output_dir / "stage4_vision_spectra" / "raw_vlm_outputs.jsonl").read_text(encoding="utf-8")
    assert "not json at all" in raw_text


def test_live_mode_without_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "fig18.jpg"
    image_path.write_bytes(b"fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    client = VisionLanguageModelClient(dry_run=False, api_key=None, base_url="https://example.com", model_name="fake")
    with pytest.raises(RuntimeError, match="requires OPENAI_API_KEY or DASHSCOPE_API_KEY"):
        client.extract(VLMRequest(image_path=str(image_path), prompt="{}"))
