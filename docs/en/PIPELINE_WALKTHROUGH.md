# Pipeline Walkthrough

## End-to-end data flow

```text
PDF / Markdown
  -> Stage1 / Stage2 preprocessing
  -> Stage3 text extraction
  -> Stage4 figure and spectra extraction
  -> Stage5 fusion
  -> deterministic linking
  -> link-aware export
  -> batch final export
  -> figure_atlas
```

## Stage 3

- Reads: paper Markdown, cleaned text, procedure sections, and related metadata.
- Writes: parameters, samples, process steps, evidence objects, and Stage 3 summaries.
- Success indicator: `stage3_summary.json` plus populated JSONL outputs.
- Common warnings: evidence sparsity, missing procedure sections, partial parameter extraction.
- Rerun when: Stage 3 outputs are missing or clearly invalid.
- Do not rerun when: downstream-only docs or atlas work is the current task.

## Stage 4

- Reads:
  - Stage 2-selected figures from `figures.jsonl`
  - fallback `figures_for_vision/`
  - Stage 3 context
- Writes:
  - `spectra_extractions.jsonl`
  - `raw_vlm_outputs.jsonl`
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json`
- Success indicator:
  - expected figures processed or intentionally skipped
  - summary present
- Common warnings:
  - `missing_image_path`
  - fallback reuse
  - dry-run summary
- Rerun when:
  - live extraction has not actually happened
  - retryable failures remain
- Do not rerun when:
  - you only need Stage 5, batch export, or figure atlas from existing valid results

## Stage 5

- Reads:
  - Stage 3 outputs
  - Stage 4 spectra extractions when available
- Filters out:
  - dry-run spectra
  - failed records
  - raw-only records
- Writes:
  - `final_dataset/`
  - `stage5_summary.json`
  - deterministic linking outputs
  - per-paper link-aware export tables
- Success indicator:
  - `final_dataset/` populated
  - if linking enabled, `final_dataset/linking/` and `final_dataset/link_aware_exports/` exist
- Common warnings:
  - `dry_run_only_spectra`
  - `zero_evidence_links`
  - `zero_spectra_links`
  - `zero_process_step_links`

## Deterministic linking

- Reads:
  - Stage 5 fused parameters
  - evidence
  - spectra
  - samples
  - process steps
- Writes:
  - linking candidate and accepted link files
  - linking summary
- This stage should not fail just because one link family is empty.

## Link-aware export

- Reads:
  - `final_dataset/`
  - `final_dataset/linking/`
- Writes:
  - `final_dataset/link_aware_exports/`
- Typical use:
  - per-paper downstream analysis
  - later batch aggregation

## Batch final export

- Reads:
  - per-paper `final_dataset/link_aware_exports/`
- Writes:
  - `data/outputs/_batch_final_exports/`
- Success indicator:
  - aggregated CSV tables and JSON summary exist

## Figure atlas

- Reads only existing outputs:
  - batch final exports
  - Stage 4 per-paper spectra outputs
  - optional Stage 3 analysis directories
- Writes:
  - audit results
  - normalized source tables
  - per-figure source CSV / JSON
  - figure bundles
- Does not rerun Stage 3, Stage 4, or Stage 5.

## Validation checkpoints

### Stage 3 checkpoint

- Reads: Markdown
- Writes: Stage 3 JSON/JSONL
- Key files: `stage3_summary.json`, `parameters.jsonl`, `process_steps.jsonl`
- Success indicator: non-empty structured outputs

### Stage 4 checkpoint

- Reads: Stage 2-selected figures and Stage 3 context
- Writes: Stage 4 spectra outputs
- Key files: `spectra_extractions.jsonl`, `stage4a_summary.json`
- Success indicator: live or valid fallback spectra records where expected

### Stage 5 checkpoint

- Reads: Stage 3 + Stage 4
- Writes: `final_dataset/`
- Key files: `stage5_summary.json`, `parameters.jsonl`, `process_steps.jsonl`, `spectra.jsonl`
- Success indicator: Stage 5 outputs present, status not failed

### Linking checkpoint

- Reads: `final_dataset/`
- Writes: `final_dataset/linking/`
- Key files: `links.jsonl`, `linking_summary.json`
- Success indicator: outputs exist even if some link families remain empty

### Figure atlas checkpoint

- Reads: batch final export and existing stage outputs
- Writes: audit, normalized tables, figure bundles
- Key files: `figure_atlas_manifest.json`, `figure_index.csv`
- Success indicator: `core_inputs_ready=true` for generation or valid audit outputs for audit-only runs

