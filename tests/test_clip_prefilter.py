from __future__ import annotations

import base64
import sys
import types
from io import BytesIO
from pathlib import Path

from PIL import Image

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision import clip_prefilter as module


def _png_bytes(mode: str = "RGB", size: tuple[int, int] = (32, 32)) -> bytes:
    image = Image.new(mode, size, color=128)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_prepare_clip_image_converts_to_rgb() -> None:
    image = Image.new("L", (100, 50), color=128)

    prepared = module.prepare_clip_image(image)

    assert prepared.mode == "RGB"


def test_prepare_clip_image_limits_max_side() -> None:
    image = Image.new("RGB", (3000, 1500), color="white")

    prepared = module.prepare_clip_image(image, max_side=1024)

    assert max(prepared.size) <= 1024


def test_prepare_clip_image_returns_detached_copy() -> None:
    image = Image.new("RGB", (100, 50), color="white")

    prepared = module.prepare_clip_image(image)

    assert prepared is not image


def test_load_clip_image_path_uses_prepare_clip_image(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(_png_bytes())
    called = {}

    def fake_prepare(image: Image.Image, max_side: int = 1024) -> Image.Image:
        called["size"] = image.size
        called["max_side"] = max_side
        return Image.new("RGB", (10, 10), color="red")

    monkeypatch.setattr(module, "prepare_clip_image", fake_prepare)

    loaded = module.load_clip_image(image_path)

    assert loaded.size == (10, 10)
    assert called["size"] == (32, 32)
    assert called["max_side"] == 1024


def test_load_clip_image_figureinfo_path_uses_prepare_clip_image(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(_png_bytes())
    called = {}

    def fake_prepare(image: Image.Image, max_side: int = 1024) -> Image.Image:
        called["mode"] = image.mode
        return Image.new("RGB", (8, 8), color="blue")

    monkeypatch.setattr(module, "prepare_clip_image", fake_prepare)
    figure = FigureInfo(paper_id="paper", image_path=str(image_path))

    loaded = module.load_clip_image(figure)

    assert loaded.size == (8, 8)
    assert called["mode"] == "RGB"


def test_load_clip_image_base64_uses_prepare_clip_image(monkeypatch) -> None:
    payload = base64.b64encode(_png_bytes()).decode("ascii")
    figure = FigureInfo(paper_id="paper", base64_data=payload)
    called = {}

    def fake_prepare(image: Image.Image, max_side: int = 1024) -> Image.Image:
        called["size"] = image.size
        return Image.new("RGB", (6, 6), color="green")

    monkeypatch.setattr(module, "prepare_clip_image", fake_prepare)

    loaded = module.load_clip_image(figure)

    assert loaded.size == (6, 6)
    assert called["size"] == (32, 32)


def test_clip_processor_uses_use_fast_false(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class FakeTensor:
        def to(self, _device):
            return self

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, model_name: str, use_fast: bool = True):
            calls.append((model_name, use_fast))
            return cls()

        def __call__(self, **kwargs):
            return {"pixel_values": FakeTensor(), "input_ids": FakeTensor()}

    class FakeModel:
        @classmethod
        def from_pretrained(cls, _model_name: str):
            return cls()

        def to(self, _device):
            return self

        def eval(self):
            return self

    class FakeNoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
        device=lambda name: name,
        no_grad=lambda: FakeNoGrad(),
    )
    fake_transformers = types.SimpleNamespace(CLIPModel=FakeModel, CLIPProcessor=FakeProcessor)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    instance = module.CLIPPrefilter()

    assert instance.processor is not None
    assert calls == [(module.CLIPPrefilter.model_name, False)]
