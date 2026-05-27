# Stage4A Universal Routing Implementation Audit

## Current extractor audit

- `Stage4VisionSpectraExtractor.run()` still writes into a configurable Stage 4 subdir and now defaults to the legacy `stage4_vision_spectra`.
- Candidate construction happens in `Stage4VisionSpectraExtractor._select_candidates()`.
- `stage3_figure_type` is derived from `evidence_objects.jsonl`, `stage2_figure_class` from `vision_inputs.jsonl` / `figures.jsonl`, and `initial_figure_type` is normalized from those hints plus caption text.
- Old schema-specific routing is preserved:
  - prompt template comes from `get_prompt_for_figure_type(initial_figure_type)`
  - schema class comes from `get_schema_for_figure_type(initial_figure_type)`
  - `unknown` is skipped by `should_process_figure()`
- New universal routing is added:
  - prompt template comes from `get_universal_compact_prompt()`
  - pre-VLM routing no longer hard-locks the schema from `stage2_figure_class`
  - post-VLM validation uses `actual_figure_type`

## Current schema/parse flow

- Raw VLM text is parsed with `parse_json_payload()`.
- Schema-specific mode still follows:
  1. parse JSON
  2. normalize payload with `_normalize_live_payload(...)`
  3. validate with the per-type schema
- Universal mode now follows:
  1. parse JSON
  2. validate outer shell with `UniversalFigureExtraction`
  3. normalize `actual_figure_type`
  4. if `actual_figure_type` is unknown or low-confidence, validate with `UnknownFigureExtraction`
  5. otherwise validate `extraction` with the schema chosen from `actual_figure_type`
  6. merge routing metadata back into the final extraction record

## Failure handling

- Previous-success fallback is unchanged for transient `VLMRequestError`.
- Universal schema validation failure no longer crashes the paper:
  - failed record is written
  - raw universal payload is preserved in `raw_vlm_outputs.jsonl`
  - warning `schema_validation_failed` is attached

## Output files

- Per-paper Stage 4 output now supports configurable subdir via `stage4_subdir`.
- Legacy outputs remain:
  - `spectra_extractions.jsonl`
  - `failed_records.jsonl`
  - `stage4_summary.json`
- New aliases for universal batch/dry-run are also written:
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json`
  - `stage4a_validation_report.md`

## Stage 3 input path audit

- Legacy hardcoded Stage 3 input path was `stage3_dspy_smoke`.
- Extractor now supports `stage3_subdir`, so new Stage 4A dry-run / batch can read:
  - `stage3_twopass/evidence_objects.jsonl`
  - `stage3_twopass/paper_extraction.schema_v2.json`
- Missing `paper_extraction.schema_v2.json` is non-fatal and produces a warning.
