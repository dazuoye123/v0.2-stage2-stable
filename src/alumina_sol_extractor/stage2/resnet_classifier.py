"""ResNet-152 DocFigure classifier.

This is a lightweight adaptation of LeMaterial's ResNet classifier. It only
classifies whole figures. There is no Florence, DINO, or subfigure splitting.
"""

from __future__ import annotations

import base64
from io import BytesIO

import requests
import torch
import torch.nn as nn
from huggingface_hub import hf_hub_download
from PIL import Image
from torchvision import models, transforms

from alumina_sol_extractor.models.figure import FigureInfo


FIGURE_CATEGORIES: list[str] = [
    "3D objects",
    "Algorithm",
    "Area chart",
    "Bar plots",
    "Block diagram",
    "Box plot",
    "Bubble Chart",
    "Confusion matrix",
    "Contour plot",
    "Flow chart",
    "Geographic map",
    "Graph plots",
    "Heat map",
    "Histogram",
    "Mask",
    "Medical images",
    "Natural images",
    "Pareto charts",
    "Pie chart",
    "Polar plot",
    "Radar chart",
    "Scatter plot",
    "Sketches",
    "Surface plot",
    "Tables",
    "Tree Diagram",
    "Vector plot",
    "Venn Diagram",
]


class ResNetDocFigureModel(nn.Module):
    """ResNet-152 with a 28-class document-figure head."""

    def __init__(self, num_classes: int = 28):
        super().__init__()
        self.resnet = models.resnet152(weights=None)
        num_features = self.resnet.fc.in_features
        self.resnet.fc = nn.Linear(num_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.resnet(x)


def load_figure_image(figure: FigureInfo) -> Image.Image:
    """Load a FigureInfo image from image_path, base64_data, or image_url."""
    if figure.image_path:
        return Image.open(figure.image_path).convert("RGB")

    if figure.base64_data:
        data = figure.base64_data
        if data.startswith("data:") and "," in data:
            data = data.split(",", 1)[1]
        return Image.open(BytesIO(base64.b64decode(data))).convert("RGB")

    if figure.image_url:
        response = requests.get(figure.image_url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")

    raise ValueError(f"Figure has no loadable image source: {figure.figure_id}")


class FigureClassifier:
    """Predict document-figure classes with a HuggingFace ResNet checkpoint."""

    repo_id = "sehaba95/ResNet-152-DocFigure"
    filename = "pytorch_model.bin"

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.labels = FIGURE_CATEGORIES
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BILINEAR),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )
        self.model = self._load_model().to(self.device).eval()

    def _load_model(self) -> ResNetDocFigureModel:
        try:
            model_path = hf_hub_download(repo_id=self.repo_id, filename=self.filename)
            state_dict = torch.load(model_path, map_location="cpu", weights_only=False)
            model = ResNetDocFigureModel(num_classes=len(self.labels))
            model.load_state_dict(state_dict)
            return model
        except Exception as exc:
            raise RuntimeError(
                "Failed to load ResNet DocFigure model from HuggingFace. "
                "Figure extraction will continue with keyword filtering only. "
                f"repo_id={self.repo_id}, filename={self.filename}, error={exc}"
            ) from exc

    def predict(self, image_or_figure: Image.Image | FigureInfo) -> str:
        """Predict a class for a PIL image or FigureInfo."""
        if isinstance(image_or_figure, FigureInfo):
            image = load_figure_image(image_or_figure)
        elif isinstance(image_or_figure, Image.Image):
            image = image_or_figure.convert("RGB")
        else:
            raise TypeError(f"Unsupported image input: {type(image_or_figure)}")

        tensor = self.transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.model(tensor)
        prediction = int(torch.argmax(outputs, dim=1).item())
        return self.labels[prediction]
