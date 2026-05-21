"""CLIP semantic prefilter for extracted figures.

This module borrows the useful idea from the old ``cleanpicwithCLIP.py`` script:
compare each image against positive and negative text prompts. It never deletes
images. It only writes ``clip_label``, ``clip_score``, and ``clip_decision`` to
``FigureInfo`` so the later filter can make a combined decision.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageFile, ImageOps

from alumina_sol_extractor.models.figure import FigureInfo


POSITIVE_PROMPTS = [
    "a scientific graph or plot",
    "a spectrum plot",
    "an NMR spectrum",
    "an XRD diffraction pattern",
    "an FTIR spectrum",
    "a Raman spectrum",
    "a thermal analysis curve",
    "a rheology curve",
    "a particle size distribution plot",
    "a zeta potential plot",
    "an electron microscope image",
    "a SEM image",
    "a TEM image",
    "a photograph of material",
    "a laboratory sample photograph",
]

NEGATIVE_PROMPTS = [
    "a publisher logo",
    "a school logo",
    "a small icon or symbol",
    "a mathematical formula",
    "a single equation",
    "text sentences",
    "a table with text and numbers",
    "a barcode or qr code",
    "a cover page image",
    "a decorative image",
]


@dataclass
class CLIPResult:
    clip_label: str
    clip_score: float
    clip_decision: str


class CLIPPrefilter:
    """Small wrapper around ``openai/clip-vit-base-patch32``."""

    model_name = "openai/clip-vit-base-patch32"

    def __init__(self) -> None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch
        except Exception as exc:
            raise RuntimeError(
                "CLIP prefilter requires transformers and torch. Install them with "
                "`pip install transformers torch` or keep running without CLIP."
            ) from exc

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = CLIPProcessor.from_pretrained(self.model_name, use_fast=False)
        self.model = CLIPModel.from_pretrained(self.model_name).to(self.device).eval()
        self.prompts = POSITIVE_PROMPTS + NEGATIVE_PROMPTS
        self.positive_count = len(POSITIVE_PROMPTS)

    def predict(self, image_or_figure: str | Path | Image.Image | FigureInfo) -> CLIPResult:
        """Return the best prompt label, score, and positive/negative decision."""
        image = load_clip_image(image_or_figure)
        inputs = self.processor(
            text=self.prompts,
            images=image,
            return_tensors="pt",
            padding=True,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0].detach().cpu()

        best_index = int(self.torch.argmax(probs).item())
        best_label = self.prompts[best_index]
        best_score = float(probs[best_index].item())
        positive_score = float(probs[: self.positive_count].max().item())
        negative_score = float(probs[self.positive_count :].max().item())

        if positive_score >= negative_score * 1.05:
            decision = "positive"
        elif negative_score >= positive_score * 1.05:
            decision = "negative"
        else:
            decision = "uncertain"

        return CLIPResult(
            clip_label=best_label,
            clip_score=best_score,
            clip_decision=decision,
        )

    def apply(self, figures: list[FigureInfo]) -> list[FigureInfo]:
        """Attach CLIP results to each loadable figure."""
        for figure in figures:
            try:
                result = self.predict(figure)
            except Exception:
                figure.clip_label = None
                figure.clip_score = None
                figure.clip_decision = "not_run"
                continue
            figure.clip_label = result.clip_label
            figure.clip_score = result.clip_score
            figure.clip_decision = result.clip_decision
        return figures


def prepare_clip_image(image: Image.Image, max_side: int = 1024) -> Image.Image:
    """Normalize CLIP input images with a conservative, crash-resistant path."""
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side))
    return image.copy()


def load_clip_image(image_or_figure: str | Path | Image.Image | FigureInfo) -> Image.Image:
    """Load an image from path, PIL, or FigureInfo."""
    if isinstance(image_or_figure, Image.Image):
        return prepare_clip_image(image_or_figure)
    if isinstance(image_or_figure, (str, Path)):
        return prepare_clip_image(Image.open(image_or_figure))
    if isinstance(image_or_figure, FigureInfo):
        if image_or_figure.image_path:
            return prepare_clip_image(Image.open(image_or_figure.image_path))
        if image_or_figure.base64_data:
            data = image_or_figure.base64_data
            if data.startswith("data:") and "," in data:
                data = data.split(",", 1)[1]
            return prepare_clip_image(Image.open(BytesIO(base64.b64decode(data))))
        if image_or_figure.image_url:
            response = requests.get(image_or_figure.image_url, timeout=30)
            response.raise_for_status()
            return prepare_clip_image(Image.open(BytesIO(response.content)))
    raise ValueError("No loadable image source for CLIP prefilter.")
