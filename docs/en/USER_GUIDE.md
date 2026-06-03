# User Guide

## Project overview

`alumina_sol_extractor` extracts structured research data from alumina sol and alumina fiber literature.

It combines:

- Stage 3 text extraction for samples, parameters, evidence, and process steps
- Stage 4 figure and spectra extraction
- Stage 5 fusion, deterministic linking, and link-aware export
- batch-level exports for cross-paper analysis
- figure atlas generation for QA, summary plots, and manuscript-ready starting points

## Recommended workflow

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

## Environment setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

Compatibility install:

```powershell
pip install -r requirements.txt
```

If you work with Chinese paths or long console output on Windows, prefer:

```powershell
$env:PYTHONIOENCODING='utf-8'
```

## Directory layout

```text
data/
  outputs/
  batch_validation/
  analysis_outputs_stage3_v2/
src/alumina_sol_extractor/
scripts/
docs/
tests/
archive/
```

- `src/` contains maintained runtime code.
- `scripts/` contains official CLI entrypoints.
- `archive/` stores historical helper implementations.
- `data/` contains local runtime inputs and outputs and should not be committed.

## Official entrypoints

### `scripts/run_full_pipeline.py`

- Purpose: orchestrate the maintained end-to-end pipeline.
- When to use: controlled top-level runs, dry-run planning, or small scoped re-entry.
- Reads: PDF, Markdown, Stage 3, Stage 4, and existing per-paper outputs depending on options.
- Writes: pipeline reports and optional downstream outputs.
- Model calls: possible if live Stage 3 / Stage 4 / linking options are enabled.
- Upstream reruns: possible, depending on flags.

### `scripts/run_stage4_batch.py`

- Purpose: run Stage 4 batch extraction.
- When to use: you already have per-paper outputs and want Stage 4 only.
- Reads: `data/outputs/{category}/{paper_id}/` plus Stage 3 context and Stage 2-selected figure metadata.
- Writes: `stage4_vision_spectra_universal/` and batch reports.
- Model calls: yes in live mode; no in default dry-run mode.

### `scripts/run_stage5_batch.py`

- Purpose: run Stage 5 fusion for many papers.
- When to use: Stage 3 and optional Stage 4 already exist.
- Reads: per-paper Stage 3 and Stage 4 outputs.
- Writes: `final_dataset/`, `linking/`, `link_aware_exports/`, and batch reports.
- Model calls: no for Stage 5 batch; deterministic linking and export only.

### `scripts/export_link_aware_dataset.py`

- Purpose: regenerate link-aware tables for one paper from an existing `final_dataset/`.
- When to use: export refresh without rerunning Stage 5 fusion.

### `scripts/export_batch_link_aware_dataset.py`

- Purpose: aggregate per-paper link-aware exports into batch-level CSV and JSON files.
- When to use: after many papers already contain `final_dataset/link_aware_exports/`.

### `scripts/run_figure_atlas.py`

- Purpose: generate audit tables and figure bundles from existing Stage 3 / Stage 4 / Stage 5 outputs.
- When to use: QA, summary plots, or manuscript preparation after extraction has already finished.
- Model calls: no.
- Upstream reruns: no.

## Full pipeline usage

```powershell
python .\scripts\run_full_pipeline.py `
  --pdf-dir ".\data\pdfs" `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "example_paper" `
  --export-link-aware
```

Important options:

- `--pdf-dir`
- `--markdown-dir`
- `--outputs-dir`
- `--paper-ids`
- `--max-papers`
- `--live-stage3`
- `--live-stage4`
- `--force-stage3`
- `--force-stage4`
- `--force-stage5`
- `--export-link-aware`
- `--dry-run`
- `--safe`

Legacy aliases:

- `--live-stage4a` -> `--live-stage4`
- `--force-stage4a` -> `--force-stage4`
- `--max-stage4a-papers` -> `--max-stage4-papers`
- `--max-stage4a-figures-per-paper` -> `--max-stage4-figures-per-paper`
- `--stage4a-figure-types` -> `--stage4-figure-types`

## Stage4 batch usage

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs" `
  --continue-on-error
```

Stage 4 uses:

- Stage 2-selected figures from `figures.jsonl`
- fallback `figures_for_vision/` if `figures.jsonl` is missing
- Stage 3 context from `stage3_twopass` by default

Default output directory:

- `stage4_vision_spectra_universal/`

## Stage5 batch usage

Live deterministic Stage 5 batch:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --skip-existing `
  --continue-on-error `
  --workers 1
```

Dry-run:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --dry-run `
  --limit 10
```

Only incomplete papers:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --only-incomplete `
  --skip-existing
```

## Batch link-aware export usage

```powershell
python .\scripts\export_batch_link_aware_dataset.py `
  --outputs-dir ".\data\outputs" `
  --output-dir ".\data\outputs\_batch_final_exports"
```

## Figure atlas usage

Audit only:

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --audit-only
```

Generate figures:

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures `
  --max-auto-figures 50
```

## How to interpret outputs

- `success`: the expected stage completed without blocking errors.
- `partial_success`: useful output was produced, but one or more non-fatal warnings remain.
- `failed`: the stage could not produce a valid output package.
- `warning`: non-fatal condition that still needs review.
- `dry_run_spectra_excluded`: dry-run spectra records were ignored on purpose.
- `zero_evidence_links`, `zero_spectra_links`, `zero_process_step_links`: linking coverage is empty for a family.
- `Unknown / Other`: values could not be normalized or classified more specifically.

## Common workflows

### I already have Stage 3 and Stage 4, only run Stage 5

Use `scripts/run_stage5_batch.py`.

### I only want to regenerate batch export

Use `scripts/export_batch_link_aware_dataset.py`.

### I only want to generate figures from existing results

Use `scripts/run_figure_atlas.py`.

### I want to check incomplete Stage 5 outputs

Use `scripts/run_stage5_batch.py --only-incomplete --dry-run`.

### I want to force rerun a small batch

Use `--force` carefully on Stage 5 batch. Do not use it unless you are sure overwriting `final_dataset/` is safe.

### I want to run audit only before plotting

Use `scripts/run_figure_atlas.py --audit-only`.

## What not to commit

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

