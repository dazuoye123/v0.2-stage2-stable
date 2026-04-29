# Ontology Cleanup Report

## Scope
- Cleaned obvious mojibake in `configs/ontology.yaml`.
- Preserved all existing `canonical_key` names from the stage3 seed.
- Added alumina-sol-specific canonical keys needed for nitrate/aluminum hydrolysis and 27Al-NMR workflows.

## What Was Cleaned
- Replaced garbled category labels with readable Chinese labels.
- Rebuilt parameter records into a consistent shape:
  - `canonical_key`
  - `category`
  - `standard_unit`
  - `zh_name`
  - `en_name`
  - `aliases_zh`
  - `aliases_en`
  - `is_core_statistical_field`
  - `description`
- Deduplicated alias lists while preserving seed ordering where possible.
- For legacy fields whose original Chinese text could not be recovered confidently from the seed file, replaced mojibake with readable English fallback labels instead of inventing uncertain Chinese terms.

## Duplicate Alias Merges
- Removed case-insensitive duplicate aliases during rewrite.
- Unified the ontology alias field names to `aliases_zh` and `aliases_en`.
- Loader compatibility is retained for legacy `zh_aliases` / `en_aliases` readers in Python.

## Canonical Keys Kept Unchanged
- All 72 seed `canonical_key` values were preserved verbatim.
- No legacy ceramic-fiber key was deleted.
- Existing overlapping fields such as `nmr_chemical_shift_ppm` and `nmr_27Al_peak_position_ppm` were both retained.

## Newly Added Alumina-Sol Keys
- Concentration and ratio keys: `Al_concentration_mol_L`, `Al_to_AlN_molar_ratio`, `water_to_aluminum_molar_ratio`, `nitrate_to_aluminum_molar_ratio`, `acid_to_aluminum_molar_ratio`, `base_to_aluminum_molar_ratio`
- Precursor/source keys: `aluminum_source`, `nitrate_source`, `acid_type`, `base_type`, `peptizing_agent`, `chelating_agent`
- Process keys: `hydrolysis_temperature_C`, `hydrolysis_time_h`, `peptization_temperature_C`, `peptization_time_h`, `stirring_speed_rpm`
- Spectroscopy/speciation keys: `Al13_fraction_percent`, `Al30_fraction_percent`, `monomeric_aluminum_fraction_percent`, `polymeric_aluminum_fraction_percent`, `octahedral_aluminum_fraction_percent`, `tetrahedral_aluminum_fraction_percent`, `pentahedral_aluminum_fraction_percent`, `nmr_27Al_peak_position_ppm`, `nmr_27Al_peak_area`, `raman_peak_position_cm_1`
- Sol-property keys: `sol_stability_time_h`, `sol_stability_time_d`, `sol_transparency`, `spinnability`, `fiber_forming_ability`

## Keys Left Intentionally Conservative
- `Al_to_AlN_molar_ratio` was kept exactly as requested even though the name may later deserve a domain review.
- Long-tail production keys such as `continuous_length_m` and `spinning_duration_h` were left intact and not renamed.
- Polymer additive keys (`pva_content_wt_percent`, `pvp_content_wt_percent`, `peo_content_wt_percent`) were cleaned conservatively without changing canonical naming.
- Some long-tail legacy fields now use English fallback in `zh_name` / `aliases_zh` because the original seed text was already unrecoverable mojibake.

## Suggested Manual Follow-Up
- Review whether `Al_to_AlN_molar_ratio` should remain the long-term canonical name or be superseded by a clearer nitrate-specific key.
- Review whether `nmr_chemical_shift_ppm` and `nmr_27Al_peak_position_ppm` should eventually be merged or explicitly separated by scope.
- Review whether `sol_stability_time_h` and `sol_stability_time_d` should be normalized to one storage field plus provenance instead of two parallel canonical keys.
