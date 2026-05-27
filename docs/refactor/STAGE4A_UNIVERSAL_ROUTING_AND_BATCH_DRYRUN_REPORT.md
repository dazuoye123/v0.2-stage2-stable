# Stage4A Universal Routing And Batch Dry-Run Report

## Status

- VLM called: no
- Real Stage4A live run executed: no
- Routing mode added: `universal_compact`
- Backward-compatible mode preserved: `schema_specific`
- Stage 3 subdir supported: `stage3_twopass`
- New batch runner: `scripts/dev/run_stage4a_batch.py`

## Code changes

- Added `UniversalFigureExtraction` outer-shell schema in `src/alumina_sol_extractor/stage4/schemas.py`.
- Added posterior validation path `validate_universal_extraction_payload(...)` in `src/alumina_sol_extractor/stage4/extractor.py`.
- Added `routing_mode`, `stage3_subdir`, and `stage4_subdir` support to `Stage4VisionSpectraExtractor`.
- Added universal candidate rescue logic for `unknown/generic/photo/other` stage2 classes when caption/context still looks scientific.
- Added candidate metadata:
  - `initial_figure_type`
  - `candidate_risk_level`
  - `routing_reason`
- Added new per-paper aliases:
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json`
  - `stage4a_validation_report.md`

## Dry-run audit snapshot

Based on `data/batch_manifest/source_manifest.csv` with `stage3_subdir=stage3_twopass`:

- `manifest_total_count = 343`
- `completed_stage3_twopass_count = 278`
- `missing_stage3_twopass_count = 65`
- `papers_with_figures_count = 277`
- `total_figures_count = 4513`
- `candidate_count_universal_compact = 4513`
- `send_to_vision_model_count = 1801`
- `rescued_unknown_by_caption_count = 112`
- `high_risk_mismatch_figure_count = 220`

## Interpretation

- Universal routing meaningfully expands the candidate set beyond strict schema-specific routing for weakly typed figures.
- Caption/context rescue is active and already recovers `112` candidates that old hard routing would have dropped.
- The current high-risk mismatch pool is non-trivial (`220` figures), so a small live sample should be used before large-scale Stage4A execution.
- The dry-run suggests the current Stage 4A universal mainline would trigger about `1801` VLM calls if all currently completed Stage 3 two-pass outputs were processed.

## Tests added or updated

- `tests/test_stage4_universal_prompt.py`
- `tests/test_stage4_universal_routing.py`
- `tests/test_stage4_universal_validation.py`
- `tests/test_stage4_batch_runner.py`

## Validation results

- `python -m compileall .\src .\scripts .\tests` passed
- targeted Stage4 universal tests passed
- full `pytest` passed

## Recommendation

- It is now safe to move to a small live Stage4A sample such as `limit5` or `limit10`.
- Do not go straight to full corpus live VLM.
- Prioritize reviewing the `high_risk_mismatch_figures` list before scaling.
