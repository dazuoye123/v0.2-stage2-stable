# Stage 4A Current Prompt Inventory

## Common Prefix

`_COMMON_PREFIX` currently enforces these shared rules:

- Return exactly one JSON object, with no markdown wrapper or extra prose.
- Use the image as the primary source; caption/context are supporting hints.
- Encode source as `image`, `text`, `image_and_text`, or `inferred`.
- Do not silently resolve image/text conflicts; record `conflict_warning`.
- Do not fabricate unclear values.
- Always include `figure_id`, `figure_type`, `technique`, and `confidence`.
- All list fields must be JSON arrays, including `warnings`, `conflict_warnings`, and `peaks`.
- Numeric fields must be number or `null`.
- Range peaks such as `1000-1100 cm^-1` must not be converted to a midpoint.
- If range-like, use `position = null`, preserve the range in `source_text`, and warn as needed.
- Units must be explicit when present.
- If the figure is hard to read, lower confidence and explain in warnings.
- Do not invent hidden peaks, hidden sizes, hidden phases, or unobservable morphology.

## Prompt Table

| figure_type | prompt_name | schema_name | current_prompt_summary | required_outputs | special_rules |
|---|---|---|---|---|---|
| `nmr_spectrum` | `nmr_spectrum_prompt` | `NMRExtraction` | Extract ppm shifts, nucleus, species, peak areas/ratios when visible, and concise species summary. | `nucleus`, `peaks`, `species_summary`, `possible_species`, `quantitative_values`, `sample_name`, `reference_standard` | Broad/overlapped peaks use `peak_width_type`; do not invent species assignments. |
| `ftir_spectrum` | `ftir_spectrum_prompt` | `VibrationalSpectrumExtraction` | Extract cm^-1 peaks, broad band trends, and concise band assignments. | `peaks`, `band_assignments`, `sample_name`, `trend_summary` | Range peaks stay as ranges in `source_text`, not midpoint; `peak.position` must be number or `null`. |
| `ir_spectrum` | `ir_spectrum_prompt` | `VibrationalSpectrumExtraction` | Same family as FTIR, focused on wavenumber peaks and concise assignments. | `peaks`, `band_assignments`, `sample_name`, `trend_summary` | Same no-midpoint rule for range bands; do not over-extract noise. |
| `raman_spectrum` | `raman_spectrum_prompt` | `VibrationalSpectrumExtraction` | Extract Raman peak positions, relative intensity trends, and broad assignments. | `peaks`, `band_assignments`, `sample_name`, `trend_summary` | Preserve `phase_or_species` only when supported; range peaks remain non-numeric. |
| `xrd_pattern` | `xrd_pattern_prompt` | `XRDExtraction` | Extract 2theta peaks, phases, phase assignments, and crystallinity trend. | `peaks`, `detected_phases`, `phase_assignments`, `crystallinity_trend`, `reference_ticks_visible`, `sample_name` | Reference tick marks are not experimental peaks; sort peaks by increasing 2theta; do not invent hidden peaks. |
| `ferron_curve` | `ferron_curve_prompt` | `FerronCurveExtraction` | Extract Ala/Alb/Alc or Al13 fractions, fitted parameters, and species quantification. | `al_species`, `species_quantification`, `Ala_fraction_percent`, `Alb_fraction_percent`, `Alc_fraction_percent`, `Al13_fraction_percent`, `equation`, `r_squared`, `method_summary`, `sample_name` | Do not infer fractions only from curve shape; preserve fitted equation/R² only if visible. |
| `tg_curve` | `tg_curve_prompt` | `ThermalAnalysisExtraction` | Extract mass-loss steps, transition temperatures, residue, and thermal events. | `mass_loss_steps`, `thermal_events`, `residue_percent`, `total_mass_loss_percent`, `final_residue_percent`, `atmosphere`, `heating_rate` | Do not invent exact percentages from unclear plots. |
| `dsc_curve` | `dsc_curve_prompt` | `ThermalAnalysisExtraction` | Extract endothermic/exothermic peaks and transition temperatures. | `thermal_events`, `endothermic_peaks`, `exothermic_peaks`, `transition_temperatures`, `atmosphere`, `heating_rate` | Do not invent exact temperatures from unclear plots. |
| `tg_dsc_curve` | `tg_dsc_curve_prompt` | `ThermalAnalysisExtraction` | Combined thermal plot extraction, separating TG and DSC events where possible. | `mass_loss_steps`, `thermal_events`, `endothermic_peaks`, `exothermic_peaks`, `transition_temperatures`, `residue_percent`, `total_mass_loss_percent`, `final_residue_percent`, `atmosphere`, `heating_rate` | Separate TG and DSC evidence when possible; do not fabricate percentages. |
| `sem_image` | `sem_image_prompt` | `MicroscopyExtraction` | Extract morphology, texture, visible scale information, and measurable size only when justified. | `morphology_summary`, `object_identity`, `view_type`, `morphology_type`, `surface_smoothness`, `compactness`, `fracture_type`, `diameter_estimate`, `diameter_range`, `diameter_unit`, `diameter_basis`, `particle_size_estimate`, `particle_size_range`, `particle_size_unit`, `particle_size_basis`, `scale_bar`, `morphology_features`, `image_quality_notes` | No clear scale bar means no reliable diameter; fracture surface should not imply fiber diameter. |
| `tem_image` | `tem_image_prompt` | `MicroscopyExtraction` | Same family as SEM but focused on nanoscale visible features. | Same as `sem_image` | No clear scale bar means no reliable size estimate. |
| `microscopy` | `microscopy_prompt` | `MicroscopyExtraction` | Generic microscopy fallback with morphology and scale-only extraction. | Same as `sem_image` / `tem_image` | If not measurable, keep size fields `null` and basis `not_measurable`. |
| `unknown` | `unknown_figure_prompt` | `UnknownFigureExtraction` | Preserve only safe high-level observations when type is unclear. | `likely_figure_type`, `safe_observations`, `why_uncertain`, `raw_notes` | Do not force a specific technique or schema detail. |

## Important Rules Preserved Across Current Prompts

- Range peaks such as `1000-1100 cm^-1` must not be converted to midpoint values.
- `position` fields must be number or `null`.
- `peaks` must always be arrays.
- `warnings` and `conflict_warnings` must always be arrays.
- SEM/TEM without a clear scale bar must not estimate diameter.
- XRD reference tick marks are not experimental peaks.
- Do not fabricate peaks, phases, sizes, mass loss values, or temperatures.
