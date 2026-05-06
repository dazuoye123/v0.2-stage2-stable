"""Prompt templates for Stage 4 vision spectra extraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    schema_name: str
    text: str


_COMMON_PREFIX = (
    "Output JSON only. You will receive an image and text context. "
    "Use the image as the primary source. Use caption and surrounding text as supporting context. "
    "If a value is visible in the image, mark source=image. "
    "If a value is not visually readable but is explicitly stated in text, mark source=text. "
    "If both support the same value, mark source=image_and_text. "
    "If you are only inferring from general knowledge, mark source=inferred and lower confidence. "
    "If image and text conflict, do not silently choose one; record conflict_warning. "
    "Do not fabricate. If a field is unclear, return null. "
    "Do not invent peaks or assignments not supported by image or text. "
    "Always include figure_id, figure_type, technique, confidence. "
    "peaks must be a JSON list. Numeric fields must be number or null. "
    "Units must be explicit when present. "
    "If the figure cannot be read reliably, return low confidence and explain in warnings."
)


_PROMPTS: dict[str, PromptTemplate] = {
    "nmr_spectrum": PromptTemplate(
        name="nmr_spectrum_prompt",
        schema_name="NMRExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on ppm peak positions, nucleus, possible Al species, "
            "peak areas or ratios when visible, and brief species summary. "
            "For each peak, provide position, unit, assignment, relative_intensity or area when available, "
            "source, source_text, conflict_warning, and confidence."
        ),
    ),
    "ftir_spectrum": PromptTemplate(
        name="ftir_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 peak positions, broad band trends, and high-level band assignments. "
            "Do not infer hidden peaks. For each peak, provide source, source_text, conflict_warning, and confidence."
        ),
    ),
    "ir_spectrum": PromptTemplate(
        name="ir_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 peak positions, broad band trends, and high-level band assignments. "
            "Do not infer hidden peaks. For each peak, provide source, source_text, conflict_warning, and confidence."
        ),
    ),
    "raman_spectrum": PromptTemplate(
        name="raman_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 Raman peak positions, relative intensity trends, and broad assignments. "
            "For each peak, provide source, source_text, conflict_warning, and confidence."
        ),
    ),
    "xrd_pattern": PromptTemplate(
        name="xrd_pattern_prompt",
        schema_name="XRDExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on 2theta peak positions, detected phases, phase assignments, and crystallinity trend. "
            "For each peak, provide source, source_text, conflict_warning, and confidence."
        ),
    ),
    "ferron_curve": PromptTemplate(
        name="ferron_curve_prompt",
        schema_name="FerronCurveExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on Ala/Alb/Alc or Al13 fractions, fitted parameters, and species quantification."
        ),
    ),
    "tg_curve": PromptTemplate(
        name="tg_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on mass-loss steps, transition temperatures, and residue percent."
        ),
    ),
    "dsc_curve": PromptTemplate(
        name="dsc_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on endothermic or exothermic peaks and transition temperatures."
        ),
    ),
    "tg_dsc_curve": PromptTemplate(
        name="tg_dsc_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on mass-loss steps, thermal peaks, transition temperatures, and residue percent."
        ),
    ),
    "sem_image": PromptTemplate(
        name="sem_image_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology, visible texture, and scale bar. "
            "Do not provide precise size if no clear scale bar exists."
        ),
    ),
    "tem_image": PromptTemplate(
        name="tem_image_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology, visible nanoscale features, and scale bar. "
            "Do not provide precise size if no clear scale bar exists."
        ),
    ),
    "microscopy": PromptTemplate(
        name="microscopy_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology and visible scale information only."
        ),
    ),
    "unknown": PromptTemplate(
        name="unknown_figure_prompt",
        schema_name="UnknownFigureExtraction",
        text=(
            f"{_COMMON_PREFIX} If the figure type is unclear, preserve only safe high-level observations."
        ),
    ),
}


def get_prompt_for_figure_type(figure_type: str | None) -> PromptTemplate:
    key = (figure_type or "unknown").strip().lower()
    return _PROMPTS.get(key, _PROMPTS["unknown"])
