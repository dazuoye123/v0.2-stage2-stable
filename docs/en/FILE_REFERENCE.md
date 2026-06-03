# File Reference

## `scripts/`

### `scripts/run_full_pipeline.py`

- Purpose: official top-level CLI.
- Reads: CLI arguments and project paths.
- Writes: batch reports and downstream outputs through orchestrator calls.
- Main function called: `alumina_sol_extractor.pipeline.orchestrator.run_full_pipeline_orchestrated`.
- Notes: keeps Stage 4 legacy aliases for compatibility.

### `scripts/run_stage4_batch.py`

- Purpose: official Stage 4 batch CLI.
- Reads: `data/outputs/{category}/{paper_id}` plus optional manifest and selected figure IDs.
- Writes: Stage 4 per-paper outputs and batch report files.
- Main function called: `alumina_sol_extractor.stage4.batch_runner.run_stage4_batch`.

### `scripts/run_stage5_batch.py`

- Purpose: official Stage 5 batch CLI.
- Reads: Stage 3 and Stage 4 per-paper outputs.
- Writes: `final_dataset/`, optional linking and link-aware exports, batch summary CSV/JSON/Markdown.
- Main function called: `alumina_sol_extractor.stage5.batch_runner.run_stage5_batch`.

### `scripts/export_link_aware_dataset.py`

- Purpose: regenerate one paper’s link-aware export from an existing `final_dataset/`.
- Main function called: `alumina_sol_extractor.dataset_fusion.link_aware_export.generate_link_aware_exports`.

### `scripts/export_batch_link_aware_dataset.py`

- Purpose: aggregate link-aware exports across many papers.
- Main function called: `alumina_sol_extractor.dataset_fusion.batch_link_aware_export.export_batch_link_aware_dataset`.

### `scripts/run_figure_atlas.py`

- Purpose: official figure atlas CLI.
- Main function called: `alumina_sol_extractor.figure_atlas.run_figure_atlas`.

### `scripts/run_research_figures.py`

- Legacy only.
- Prefer `scripts/run_figure_atlas.py`.

## `src/alumina_sol_extractor/pipeline/`

### `orchestrator.py`

- Official orchestration layer for the maintained full pipeline entry.
- Coordinates Stage 1 recovery, full pipeline resume calls, Stage 5-only reuse, and link-aware export summary writing.

### `full_pipeline_runner.py`

- Maintains the older full resume implementation and compatibility surface.
- Still contains legacy internal terminology such as `stage6c`, `stage4a`, and `stage55`.

### `resume_status.py`

- Discovers what already exists for each paper and which stages are pending.

### `stage1_pdf_to_markdown.py`

- Stage 1 wrapper for PDF-to-Markdown conversion.

### `stage2_figure_pipeline.py`

- Stage 2 orchestration helper for figure/table preparation.

## `src/alumina_sol_extractor/stage4/`

### `extractor.py`

- Core Stage 4 execution logic.
- Reads Stage 2-selected figure metadata and Stage 3 context.
- Writes:
  - `spectra_extractions.jsonl`
  - `raw_vlm_outputs.jsonl`
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json` (legacy file name, still emitted)

### `batch_runner.py`

- Official Stage 4 batch orchestration.
- Writes:
  - `stage4_batch_rows.jsonl`
  - `stage4_batch_summary.json`
  - `stage4_batch_report.md`

### `processed_index.py`

- Figure-level dedup, dry-run detection, replay classification, and retry classification.

### `routing.py`

- Stage 4 routing and figure-type handling.

### `prompt_templates.py`

- Stage 4 prompt templates.

### `schemas.py`

- Stage 4 structured output schemas.

### `normalization.py`

- Normalization of raw Stage 4 payloads.

### `validators.py`

- Validation helpers for Stage 4 outputs.

### `stage2_selected_loader.py`

- Loads Stage 2-selected figures from `figures.jsonl` or fallback `figures_for_vision/`.

### `stage4_context.py`

- Builds Stage 4 textual context from paper metadata and Stage 3 outputs.

### `stage4_failures.py`

- Failure and fallback helpers, including reuse of previous success when available.

### `io.py`

- JSON / JSONL read-write helpers for Stage 4.

### `quality_review.py`

- Stage 4 output review helper.

### `reparse.py`

- Reparse helper for existing raw Stage 4 outputs.
- Helper / maintenance path, not a primary user entrypoint.

### `vlm_client.py`

- Stage 4 model call wrapper.
- Only relevant when Stage 4 live mode is used.

## `src/alumina_sol_extractor/stage5/`

### `batch_runner.py`

- Official Stage 5 batch runner.
- Supports dry-run, `--skip-existing`, `--only-incomplete`, and optional linking/export.

### `dataset_fusion/`

- Stage 5 fusion logic and export utilities.
- Key files:
  - `fusion.py`
  - `loaders.py`
  - `exporters.py`
  - `link_aware_export.py`
  - `batch_link_aware_export.py`
  - `validators.py`
  - `report.py`

### `linking/`

- Deterministic linking and optional linking-related helpers.
- Key files:
  - `candidate_builder.py`
  - `models.py`
  - `validators.py`
  - `exporters.py`
  - `report.py`

## `src/alumina_sol_extractor/figure_atlas/`

### `runner.py`

- Main figure atlas runner.
- Only reads existing outputs.
- Does not rerun Stage 3, Stage 4, or Stage 5.

### `audit.py`

- Builds result inventory, availability matrices, and feasibility matrices.

### `loaders.py`

- Loads batch export and per-stage source tables.

### `normalization.py`

- Shared normalization helpers used by atlas tables and plotting prep.

### `table_builder.py`

- Stable external API: `build_normalized_tables(payload)`.
- Internally delegates to `figure_atlas/tables/`.

### `tables/*`

- Internal table builders for parameters, process steps, spectra, peaks, links, sample matrix, and category summary.

### `main_figures.py`, `stage3_figures.py`, `stage4_figures.py`, `stage5_figures.py`, `cross_stage_figures.py`, `qa_figures.py`, `auto_figures.py`

- Generate tier-specific figure bundles from normalized tables.

### `plot_utils.py`, `plot_style.py`

- Shared plotting helpers.

### `source_data.py`

- Writes per-figure source CSV and source JSON files.

## `archive/`

- Stores archived historical implementations.
- Not recommended as official runtime entrypoints.
- Current `scripts/dev/*` wrappers may execute implementations from here.

## `tests/`

- Stage 4 tests
- Stage 5 tests
- batch export tests
- figure atlas tests
- full pipeline tests
- compatibility tests for legacy wrappers

