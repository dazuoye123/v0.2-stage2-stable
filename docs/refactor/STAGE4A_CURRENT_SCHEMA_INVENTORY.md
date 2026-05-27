# Stage 4A Current Schema Inventory

| schema_name | main_fields | list_fields | numeric_fields | source/evidence fields | warnings fields |
|---|---|---|---|---|---|
| `BaseFigureExtraction` | `paper_id`, `figure_id`, `figure_type`, `technique`, `caption`, `confidence`, `raw_notes`, `image_readability`, `text_context_quality` | `warnings`, `used_context_sources`, `conflict_warnings` | `confidence` | `source_image_path`, `input_context_summary` | `warnings`, `conflict_warnings` |
| `PeakRecord` | `position`, `chemical_shift_ppm`, `assignment`, `functional_group`, `phase_or_species`, `species_assignment`, `peak_width_type`, `evidence_note` | `warnings` | `position`, `chemical_shift_ppm`, `relative_intensity`, `area`, `confidence` | `source`, `source_text`, `conflict_warning` | `warnings`, `conflict_warning` |
| `ThermalEventRecord` | `event_type`, `assignment` | `warnings` | `temperature_onset`, `temperature_peak`, `temperature_end`, `mass_loss_percent`, `residue_percent`, `confidence` | `source`, `source_text` | `warnings` |
| `FerronSpeciesRecord` | `species`, `concentration` | none | `fraction_percent`, `confidence` | `source`, `source_text` | none |
| `NMRExtraction` | `nucleus`, `species_summary`, `sample_name`, `reference_standard` | `peaks`, `possible_species` | inherited `confidence` | inherited base context + per-peak source fields | inherited base warnings + per-peak warnings |
| `VibrationalSpectrumExtraction` | `spectrum_type`, `sample_name`, `trend_summary` | `peaks`, `band_assignments` | inherited `confidence` | inherited base context + per-peak source fields | inherited base warnings + per-peak warnings |
| `XRDExtraction` | `crystallinity_trend`, `reference_ticks_visible`, `visible_peak_count_estimate`, `sample_name` | `peaks`, `phase_assignments`, `detected_phases`, `reference_cards` | `visible_peak_count_estimate`, inherited `confidence` | inherited base context + per-peak source fields | inherited base warnings + per-peak warnings |
| `FerronCurveExtraction` | `curve_type`, `equation`, `r_squared`, `method_summary`, `sample_name` | `al_species` | `Ala_fraction_percent`, `Alb_fraction_percent`, `Alc_fraction_percent`, `Al13_fraction_percent`, `r_squared`, inherited `confidence` | inherited base context + per-species source fields | inherited base warnings |
| `ThermalAnalysisExtraction` | `residue_percent`, `total_mass_loss_percent`, `final_residue_percent`, `atmosphere`, `heating_rate` | `mass_loss_steps`, `thermal_events`, `endothermic_peaks`, `exothermic_peaks`, `transition_temperatures` | `residue_percent`, `total_mass_loss_percent`, `final_residue_percent`, inherited `confidence` | inherited base context + per-event/per-peak source fields | inherited base warnings + event/peak warnings |
| `MicroscopyExtraction` | `morphology_summary`, `object_identity`, `view_type`, `morphology_type`, `surface_smoothness`, `compactness`, `fracture_type`, `diameter_basis`, `particle_size_basis`, `scale_bar`, `warning` | `surface_features`, `morphology_features`, `image_quality_notes` | `diameter_estimate`, `particle_size_estimate`, inherited `confidence` | inherited base context | inherited base warnings + `image_quality_notes` |
| `UnknownFigureExtraction` | `likely_figure_type`, `why_uncertain`, `raw_notes` | `safe_observations` | inherited `confidence` | inherited base context | inherited base warnings |

## Minimal Technique-Specific Fields Worth Preserving

### XRD

- `peaks`
- `detected_phases`
- `phase_assignments`
- `crystallinity_trend`
- `reference_ticks_visible`
- `sample_name`

### FTIR / IR / Raman

- `peaks`
- `band_assignments`
- `trend_summary`
- `sample_name`

### NMR

- `nucleus`
- `peaks`
- `species_summary`
- `possible_species`
- `quantitative_values`
- `sample_name`
- `reference_standard`

### TG / DSC / TG-DSC

- `mass_loss_steps`
- `thermal_events`
- `endothermic_peaks`
- `exothermic_peaks`
- `transition_temperatures`
- `residue_percent`
- `total_mass_loss_percent`
- `final_residue_percent`
- `atmosphere`
- `heating_rate`

### Ferron

- `al_species`
- `species_quantification`
- `Ala_fraction_percent`
- `Alb_fraction_percent`
- `Alc_fraction_percent`
- `Al13_fraction_percent`
- `equation`
- `r_squared`
- `method_summary`
- `sample_name`

### SEM / TEM / Microscopy

- `morphology_summary`
- `object_identity`
- `view_type`
- `morphology_type`
- `surface_smoothness`
- `compactness`
- `fracture_type`
- `diameter_estimate`
- `diameter_range`
- `diameter_unit`
- `diameter_basis`
- `particle_size_estimate`
- `particle_size_range`
- `particle_size_unit`
- `particle_size_basis`
- `scale_bar`
- `morphology_features`
- `image_quality_notes`

### Unknown

- `likely_figure_type`
- `safe_observations`
- `why_uncertain`
- `raw_notes`
