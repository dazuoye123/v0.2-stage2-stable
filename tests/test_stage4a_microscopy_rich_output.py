from __future__ import annotations

from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor
from alumina_sol_extractor.vision_spectra.prompt_templates import get_prompt_for_figure_type
from alumina_sol_extractor.vision_spectra.schemas import MicroscopyExtraction


def test_microscopy_prompt_mentions_object_identity_and_diameter_basis() -> None:
    prompt = get_prompt_for_figure_type("sem_image").text
    assert "Identify the main object in the image." in prompt
    assert "diameter_basis=not_measurable" in prompt
    assert "image_quality_notes" in prompt


def test_microscopy_schema_accepts_rich_structure_fields() -> None:
    record = MicroscopyExtraction(
        figure_id="fig-sem",
        object_identity="alumina fiber bundle",
        view_type="surface",
        morphology_type="fiber",
        surface_smoothness="rough",
        compactness="agglomerated",
        diameter_estimate=None,
        diameter_basis="not_measurable",
        scale_bar="500 nm",
        morphology_features=["porous surface", "entangled fibers"],
        image_quality_notes=["low contrast"],
    ).model_dump()
    assert record["object_identity"] == "alumina fiber bundle"
    assert record["view_type"] == "surface"
    assert record["morphology_type"] == "fiber"
    assert record["diameter_basis"] == "not_measurable"


def test_microscopy_range_size_moves_to_range_field() -> None:
    normalized, warnings = Stage4VisionSpectraExtractor._normalize_live_payload(
        {"diameter_estimate": "80-120", "warnings": None, "conflict_warnings": None},
        figure_type="sem_image",
        schema_name="MicroscopyExtraction",
    )
    assert normalized["diameter_estimate"] is None
    assert normalized["diameter_range"] == "80-120"
    assert normalized["diameter_basis"] == "not_measurable"
    assert "diameter_estimate_range_moved_to_diameter_range" in warnings
