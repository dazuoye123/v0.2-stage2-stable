# Stage 4A Universal Compact Prompt Design

## Goal

Design one compact VLM prompt that can:

1. infer `actual_figure_type`
2. fill the relevant extraction fields for that type
3. keep unrelated fields `null`, `[]`, or `{}`
4. let the program select the existing technique schema afterward

This design **does not** replace the current prompt routing yet. It only adds a new prompt candidate.

## Current Prompt Summary

The current Stage 4A prompt system is split by `figure_type`:

- `nmr_spectrum`
- `ftir_spectrum`
- `ir_spectrum`
- `raman_spectrum`
- `xrd_pattern`
- `ferron_curve`
- `tg_curve`
- `dsc_curve`
- `tg_dsc_curve`
- `sem_image`
- `tem_image`
- `microscopy`
- `unknown`

Common cross-cutting rules already enforced today:

- image-first reading
- caption/context are supporting hints
- JSON-only output
- no fabrication
- list fields must stay arrays
- broad/range peaks must not become midpoint numbers
- XRD reference ticks are not peaks
- SEM/TEM without a clear scale bar must not estimate diameter

## Universal Compact Prompt Draft

The new `universal_compact_prompt` is added in:

- `src/alumina_sol_extractor/stage4/prompt_templates.py`

It tells the model:

- Stage2 `figure_class` is only a hint, not hard routing
- Stage3 `figure_type` is only a hint, not hard routing
- the image is primary evidence
- if uncertain, use `actual_figure_type=unknown`
- do not fabricate invisible peaks/phases/sizes/mass-loss values/temperatures
- range peaks must not be converted to midpoint
- only the fields relevant to `actual_figure_type` should be filled
- everything else must stay `null`, `[]`, or `{}`
- output must be one JSON object only

The allowed `actual_figure_type` enum is:

- `xrd_pattern`
- `ftir_spectrum`
- `ir_spectrum`
- `raman_spectrum`
- `nmr_spectrum`
- `tg_curve`
- `dsc_curve`
- `tg_dsc_curve`
- `ferron_curve`
- `sem_image`
- `tem_image`
- `microscopy`
- `unknown`

## Why Key Rules Were Not Lost

The universal compact prompt keeps the most important safety rules from the existing per-technique prompts:

- broad/range peaks remain non-numeric in `position`
- `peaks`, `warnings`, and `conflict_warnings` remain arrays
- XRD reference ticks remain non-peak annotations
- microscopy size estimation still requires visible scale support
- uncertain type still falls back to `unknown`
- output remains strict JSON-only

## What Was Compressed

Instead of repeating long technique-specific prose, the compact prompt merges rules into short shared constraints:

- all spectra share the no-midpoint rule
- all extraction families share JSON-only and no-fabrication rules
- all microscopy families share the no-scale-bar-no-size rule
- all type routing now flows through `actual_figure_type` rather than pre-routing by Stage 2 / Stage 3 labels

This reduces prompt length while preserving the highest-signal constraints that matter for safe extraction.
