from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor


def test_candidate_selection_prefers_stage3_type_then_stage2_class() -> None:
    extractor = Stage4VisionSpectraExtractor(paper_id="paper-1", output_dir=Path("."))
    candidates = extractor._select_candidates(
        figures=[{"figure_id": "图2.18", "caption": "IR谱图", "image_path": "fig18.jpg"}],
        vision_inputs=[{"figure_id": "图2.18", "figure_class": "ftir_spectrum", "vision_image_path": "vision18.jpg"}],
        evidence_objects=[{"evidence_id": "图2.18", "figure_id": "图2.18", "figure_type": "ftir_spectrum"}],
    )
    assert candidates[0]["figure_type"] == "ftir_spectrum"
    assert candidates[0]["send_to_vlm"] is True


def test_candidate_selection_can_fallback_to_caption_without_stage2_class() -> None:
    extractor = Stage4VisionSpectraExtractor(paper_id="paper-1", output_dir=Path("."))
    candidates = extractor._select_candidates(
        figures=[{"figure_id": "图2.19", "caption": "XRD衍射图", "image_path": "fig19.jpg"}],
        vision_inputs=[],
        evidence_objects=[],
    )
    assert candidates[0]["figure_type"] == "xrd_pattern"
