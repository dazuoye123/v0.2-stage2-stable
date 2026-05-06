from __future__ import annotations

from pathlib import Path

import pytest

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_figure_id_selection_filters_exact_requested_ids() -> None:
    extractor = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=Path("."),
        figure_ids=["图2.18", "图2.19"],
    )
    candidates = extractor._select_candidates(
        figures=[
            {"figure_id": "图2.18", "caption": "图2.18 旋蒸后铝溶胶的IR谱图", "image_path": "fig18.jpg"},
            {"figure_id": "图2.19", "caption": "图2.19 铝溶胶的XRD图", "image_path": "fig19.jpg"},
            {"figure_id": "图2.12", "caption": "图2.12 Al-Ferron曲线", "image_path": "fig12.jpg"},
        ],
        vision_inputs=[
            {"figure_id": "图2.18", "figure_class": "ftir_spectrum", "vision_image_path": "vision18.jpg"},
            {"figure_id": "图2.19", "figure_class": "xrd_pattern", "vision_image_path": "vision19.jpg"},
            {"figure_id": "图2.12", "figure_class": "ferron_curve", "vision_image_path": "vision12.jpg"},
        ],
        evidence_objects=[],
    )
    assert [item["figure_id"] for item in candidates] == ["图2.18", "图2.19"]


def test_figure_id_selection_raises_clear_error_when_missing() -> None:
    extractor = Stage4VisionSpectraExtractor(
        paper_id="paper-1",
        output_dir=Path("."),
        figure_ids=["图2.18", "图2.19"],
    )
    with pytest.raises(ValueError, match="Requested figure_id\\(s\\) not found: 图2.19"):
        extractor._select_candidates(
            figures=[{"figure_id": "图2.18", "caption": "图2.18 旋蒸后铝溶胶的IR谱图", "image_path": "fig18.jpg"}],
            vision_inputs=[{"figure_id": "图2.18", "figure_class": "ftir_spectrum", "vision_image_path": "vision18.jpg"}],
            evidence_objects=[],
        )
