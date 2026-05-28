"""Prompt templates for Stage 4 vision spectra extraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    schema_name: str
    text: str


_COMMON_PREFIX = (
    "Return exactly one JSON object. Do not wrap JSON in markdown. Do not include prose outside JSON. "
    "You will receive an image and text context. "
    "Use the image as the primary source. Use caption and surrounding text as supporting context. "
    "If a value is visible in the image, mark source=image. "
    "If a value is not visually readable but is explicitly stated in text, mark source=text. "
    "If both support the same value, mark source=image_and_text. "
    "If you are only inferring from general knowledge, mark source=inferred and lower confidence. "
    "If image and text conflict, do not silently choose one; record conflict_warning. "
    "Do not fabricate. If a field is unclear, return null. "
    "Do not invent peaks or assignments not supported by image or text. "
    "Always include figure_id, figure_type, technique, confidence. "
    "All list fields must be JSON arrays. Never output null or a string for list fields. If no items exist, output []. "
    "warnings must always be a JSON array. conflict_warnings must always be a JSON array. If no warnings or conflicts exist, output []. "
    "peaks must be a JSON list. Numeric fields must be number or null. Never output numeric ranges as strings in numeric fields. "
    "Every extracted observation should include source, source_text, and confidence when applicable. "
    "For range-like or broad-band values such as 1000-1100 cm^-1, do not put the range string into a numeric field. "
    "Never convert range values to midpoint unless explicitly requested. "
    "Do not convert a range to a midpoint. Set the numeric position field to null, preserve the original range in source_text, describe it in assignment, "
    "and add warning range_peak_position_not_numeric if needed. "
    "Units must be explicit when present. "
    "If the figure cannot be read reliably, return low confidence and explain in warnings. "
    "Do not invent hidden peaks, hidden sizes, hidden phases, or unobservable morphology."
)


_UNIVERSAL_COMPACT_PROMPT = PromptTemplate(
    name="universal_compact_prompt",
    schema_name="UniversalCompactFigureExtraction",
    text=(
        "Return exactly one JSON object. Do not wrap JSON in markdown. Do not include prose outside JSON. "
        "You will receive an image plus text context. Use the image as the primary evidence. "
        "Stage2 figure_class is only a hint, not hard routing. Stage3 figure_type is only a hint, not hard routing. "
        "Stage2 predicted figure_type, if provided, is also only a hint. "
        "Caption and surrounding text may help, but image evidence comes first. "
        "First decide actual_figure_type from this closed set only: "
        "[xrd_pattern, ftir_spectrum, ir_spectrum, raman_spectrum, nmr_spectrum, tg_curve, dsc_curve, tg_dsc_curve, ferron_curve, sem_image, tem_image, microscopy, unknown, non_extractable]. "
        "If uncertain, set actual_figure_type=unknown. If the image is not a scientific extractable figure, use actual_figure_type=non_extractable. "
        "You must inspect the image content yourself. If Stage2 type disagrees with the image, correct it in actual_figure_type. "
        "If Stage2 type is unknown but the image or caption clearly indicates XRD, FTIR, Raman, NMR, TG, DSC, SEM, TEM, Ferron, or microscopy, assign the correct actual_figure_type. "
        "Do not fabricate peaks, phases, sizes, mass loss values, temperatures, residue, or morphology details that are not visible or explicitly supported by text. "
        "All list-like fields must be JSON arrays. If empty, output []. Numeric fields must be number or null. "
        "warnings must be []. conflict_warnings must be []. Do not output markdown. Output one JSON object only. "
        "For range-like peaks such as 1000-1100 cm^-1, do not convert the range to a midpoint. "
        "Set numeric position=null, preserve the range in source_text or note text, and keep the interpretation in assignment or notes. "
        "For XRD, do not treat reference tick marks as experimental peaks. "
        "For SEM, TEM, or microscopy, do not estimate diameter or particle size without a clear scale bar and measurable boundaries. "
        "If no reliable size can be measured, keep diameter_estimate and particle_size_estimate null and explain in image_quality_notes or warnings. "
        "Only populate fields relevant to actual_figure_type; keep unrelated fields null, [], or {}. "
        "The output JSON must follow this top-level structure: "
        "{"
        "\"paper_id\": null, "
        "\"figure_id\": null, "
        "\"stage2_figure_class\": null, "
        "\"stage2_predicted_figure_type\": null, "
        "\"stage3_figure_type\": null, "
        "\"actual_figure_type\": null, "
        "\"type_confidence\": null, "
        "\"type_reason\": null, "
        "\"stage2_type_used_as_hint\": true, "
        "\"type_mismatch\": false, "
        "\"corrected_from_stage2_type\": null, "
        "\"needs_manual_review\": false, "
        "\"image_basename\": null, "
        "\"image_readability\": null, "
        "\"text_context_quality\": null, "
        "\"conflict_warnings\": [], "
        "\"warnings\": [], "
        "\"extraction\": {"
        "\"figure_type\": null, "
        "\"technique\": null, "
        "\"sample_name\": null, "
        "\"peaks\": [], "
        "\"detected_phases\": [], "
        "\"phase_assignments\": [], "
        "\"crystallinity_trend\": null, "
        "\"reference_ticks_visible\": null, "
        "\"band_assignments\": [], "
        "\"trend_summary\": null, "
        "\"nucleus\": null, "
        "\"species_summary\": null, "
        "\"possible_species\": [], "
        "\"quantitative_values\": {}, "
        "\"reference_standard\": null, "
        "\"mass_loss_steps\": [], "
        "\"thermal_events\": [], "
        "\"endothermic_peaks\": [], "
        "\"exothermic_peaks\": [], "
        "\"transition_temperatures\": [], "
        "\"residue_percent\": null, "
        "\"total_mass_loss_percent\": null, "
        "\"final_residue_percent\": null, "
        "\"atmosphere\": null, "
        "\"heating_rate\": null, "
        "\"al_species\": [], "
        "\"species_quantification\": {}, "
        "\"Ala_fraction_percent\": null, "
        "\"Alb_fraction_percent\": null, "
        "\"Alc_fraction_percent\": null, "
        "\"Al13_fraction_percent\": null, "
        "\"equation\": null, "
        "\"r_squared\": null, "
        "\"method_summary\": null, "
        "\"morphology_summary\": null, "
        "\"object_identity\": null, "
        "\"view_type\": null, "
        "\"morphology_type\": null, "
        "\"surface_smoothness\": null, "
        "\"compactness\": null, "
        "\"fracture_type\": null, "
        "\"diameter_estimate\": null, "
        "\"diameter_range\": null, "
        "\"diameter_unit\": null, "
        "\"diameter_basis\": null, "
        "\"particle_size_estimate\": null, "
        "\"particle_size_range\": null, "
        "\"particle_size_unit\": null, "
        "\"particle_size_basis\": null, "
        "\"scale_bar\": null, "
        "\"morphology_features\": [], "
        "\"image_quality_notes\": [], "
        "\"likely_figure_type\": null, "
        "\"safe_observations\": [], "
        "\"why_uncertain\": null, "
        "\"raw_notes\": null"
        "}"
        "}."
    ),
)


_PROMPTS: dict[str, PromptTemplate] = {
    "nmr_spectrum": PromptTemplate(
        name="nmr_spectrum_prompt",
        schema_name="NMRExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on ppm peak positions, nucleus, possible Al species, "
            "peak areas or ratios when visible, and brief species summary. "
            "Focus on chemical shifts in ppm. Identify nucleus when visible or stated in text. "
            "Assign Al coordination species only when supported by text or common context. "
            "Mark broad or overlapped peaks using peak_width_type. Do not invent species assignments when unclear. "
            "Relative intensity may be qualitative. "
            "For each peak, provide position, unit, assignment, relative_intensity or area when available, "
            "species_assignment, peak_width_type, source, source_text, conflict_warning, warnings, and confidence."
        ),
    ),
    "ftir_spectrum": PromptTemplate(
        name="ftir_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 peak positions, broad band trends, and high-level band assignments. "
            "Do not infer hidden peaks. For each peak, provide source, source_text, conflict_warning, and confidence. "
            "For VibrationalSpectrumExtraction, peaks must be a JSON list. peak.position must be number or null. "
            "Do not output range strings in peak.position. If the peak is a broad band or range, set position=null, keep the range in source_text, "
            "keep the chemical interpretation in assignment, and add warning range_peak_position_not_numeric. "
            "Do not map 1000-1100 to 1050. "
            "For sharp clear peaks, use numeric position. For broad bands or range bands, use band_type=broad_band or range_band. "
            "Use intensity_level when visible. Assignment should be chemical and concise, such as Al-O-Si stretching, O-H stretching, or nitrate vibration. "
            "Do not over-extract noise."
        ),
    ),
    "ir_spectrum": PromptTemplate(
        name="ir_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 peak positions, broad band trends, and high-level band assignments. "
            "Do not infer hidden peaks. For each peak, provide source, source_text, conflict_warning, and confidence. "
            "For VibrationalSpectrumExtraction, peaks must be a JSON list. peak.position must be number or null. "
            "Do not output range strings in peak.position. If the peak is a broad band or range, set position=null, keep the range in source_text, "
            "keep the chemical interpretation in assignment, and add warning range_peak_position_not_numeric. "
            "Do not map 1000-1100 to 1050. "
            "For sharp clear peaks, use numeric position. For broad bands or range bands, use band_type=broad_band or range_band. "
            "Use intensity_level when visible. Assignment should be chemical and concise. Do not over-extract noise."
        ),
    ),
    "raman_spectrum": PromptTemplate(
        name="raman_spectrum_prompt",
        schema_name="VibrationalSpectrumExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on cm-1 Raman peak positions, relative intensity trends, and broad assignments. "
            "For each peak, provide source, source_text, conflict_warning, and confidence. "
            "For VibrationalSpectrumExtraction, peaks must be a JSON list. peak.position must be number or null. "
            "Do not output range strings in peak.position. If the peak is a broad band or range, set position=null, keep the range in source_text, "
            "keep the chemical interpretation in assignment, and add warning range_peak_position_not_numeric. "
            "Use band_type and intensity_level when visible. Preserve phase_or_species if stated. Do not over-extract noise."
        ),
    ),
    "xrd_pattern": PromptTemplate(
        name="xrd_pattern_prompt",
        schema_name="XRDExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on 2theta peak positions, detected phases, phase assignments, and crystallinity trend. "
            "For each peak, provide source, source_text, conflict_warning, warnings, intensity_level, is_primary_peak, and confidence. "
            "For XRDExtraction, detected_phases must be a JSON list of strings. phase_assignments must be a JSON list. "
            "If there is only one phase assignment, still output it as an array with one string item. "
            "Never output phase_assignments as a single string. peaks must be a JSON list. peak.position must be number or null. "
            "crystallinity_trend may be string or null. warnings must be [] if no warnings. conflict_warnings must be [] if no conflicts. "
            "Extract all visually resolvable peaks, not only the strongest peaks. Include weak peaks only if they are distinct from noise. "
            "Include shoulder peaks only if visually separable and mark intensity_level=shoulder with lower confidence. "
            "Sort peaks by increasing 2theta. Do not invent peaks hidden in noise. Positions read from image are approximate; use one decimal place when appropriate. "
            "Weak peaks should have lower confidence than strong peaks. Reference tick marks at the bottom are not experimental peaks. "
            "If reference tick marks are visible, set reference_ticks_visible=true. If phase names are stated in caption/text, include detected_phases and phase_assignments."
        ),
    ),
    "ferron_curve": PromptTemplate(
        name="ferron_curve_prompt",
        schema_name="FerronCurveExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on Ala/Alb/Alc or Al13 fractions, fitted parameters, and species quantification. "
            "Extract Ala/Alb/Alc/Al13 fractions only when visible or stated. If only trends are visible, output qualitative trend instead of fabricated numbers. "
            "Preserve fitted equation and R2 when visible. Do not infer fractions from curve shape without values."
        ),
    ),
    "tg_curve": PromptTemplate(
        name="tg_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on mass-loss steps, transition temperatures, residue percent, and thermal events. "
            "For TG, extract mass-loss steps and residue if visible or stated in text. "
            "Do not invent exact percentages from unclear plots. If values are stated in caption/text, mark source=text."
        ),
    ),
    "dsc_curve": PromptTemplate(
        name="dsc_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on endothermic or exothermic peaks, transition temperatures, and thermal events. "
            "For DSC/DTA, extract endothermic or exothermic peak temperatures. Do not invent exact temperatures from unclear plots."
        ),
    ),
    "tg_dsc_curve": PromptTemplate(
        name="tg_dsc_curve_prompt",
        schema_name="ThermalAnalysisExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on mass-loss steps, thermal peaks, transition temperatures, residue percent, and thermal events. "
            "For TG-DSC combined curves, separate TG events and DSC events if possible. Do not invent exact percentages from unclear plots."
        ),
    ),
    "sem_image": PromptTemplate(
        name="sem_image_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology, visible texture, and scale bar. "
            "Do not provide precise size if no clear scale bar exists. "
            "For MicroscopyExtraction, warnings must always be a JSON array and conflict_warnings must always be a JSON array. "
            "scale_bar should be a string like 200 nm or null unless the schema explicitly supports a dict. Never output warnings=null. "
            "Identify the main object in the image. Classify view_type and morphology_type. Describe morphology using fixed fields. "
            "Estimate diameter only when a scale bar is visible and object boundaries are clear. "
            "If image is a fracture surface, do not output fiber diameter unless directly measurable. "
            "If size comes from text only, set the corresponding basis=text. "
            "If no reliable measurement is possible, set diameter_estimate=null and diameter_basis=not_measurable. "
            "Never invent precise size. Always include scale_bar if visible. For low-quality images, add image_quality_notes and lower confidence."
        ),
    ),
    "tem_image": PromptTemplate(
        name="tem_image_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology, visible nanoscale features, and scale bar. "
            "Do not provide precise size if no clear scale bar exists. "
            "For MicroscopyExtraction, warnings must always be a JSON array and conflict_warnings must always be a JSON array. "
            "scale_bar should be a string like 200 nm or null unless the schema explicitly supports a dict. Never output warnings=null. "
            "Identify the main object in the image. Classify view_type and morphology_type. Describe morphology using fixed fields. "
            "Estimate diameter only when a scale bar is visible and object boundaries are clear. "
            "If no reliable measurement is possible, set diameter_estimate=null and diameter_basis=not_measurable. "
            "Never invent precise size. Always include scale_bar if visible. For low-quality images, add image_quality_notes and lower confidence."
        ),
    ),
    "microscopy": PromptTemplate(
        name="microscopy_prompt",
        schema_name="MicroscopyExtraction",
        text=(
            f"{_COMMON_PREFIX} Focus on morphology and visible scale information only. "
            "For MicroscopyExtraction, warnings must always be a JSON array and conflict_warnings must always be a JSON array. "
            "scale_bar should be a string like 200 nm or null unless the schema explicitly supports a dict. Never output warnings=null. "
            "Identify the main object in the image. Classify view_type and morphology_type. "
            "If no reliable measurement is possible, set diameter_estimate=null and diameter_basis=not_measurable."
        ),
    ),
    "unknown": PromptTemplate(
        name="unknown_figure_prompt",
        schema_name="UnknownFigureExtraction",
        text=(
            f"{_COMMON_PREFIX} If the figure type is unclear, do not force a specific schema. Preserve only safe high-level observations."
        ),
    ),
}


def get_prompt_for_figure_type(figure_type: str | None) -> PromptTemplate:
    key = (figure_type or "unknown").strip().lower()
    return _PROMPTS.get(key, _PROMPTS["unknown"])


def get_universal_compact_prompt() -> PromptTemplate:
    return _UNIVERSAL_COMPACT_PROMPT
