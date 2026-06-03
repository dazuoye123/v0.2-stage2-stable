# alumina_sol_extractor

Structured literature extraction pipeline for alumina sol and alumina fiber papers.

## Project overview

This repository converts PDF or Markdown literature into structured research data for downstream analysis.

The maintained pipeline covers:

- Stage 1 and Stage 2 preprocessing
- Stage 3 text extraction
- Stage 4 figure and spectra extraction
- Stage 5 fusion, linking, and link-aware export
- batch-level final exports
- figure atlas generation from existing results

## Official entrypoints

Use these scripts for normal operation:

- `python scripts/run_full_pipeline.py`
- `python scripts/run_stage4_batch.py`
- `python scripts/run_stage5_batch.py`
- `python scripts/export_link_aware_dataset.py`
- `python scripts/export_batch_link_aware_dataset.py`
- `python scripts/run_figure_atlas.py`

Legacy tools remain in the repository for compatibility, but they are not the recommended entrypoints for new work.

## Quick start

Install the package in an isolated environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

Compatibility install:

```bash
pip install -r requirements.txt
```

Example commands:

```bash
python scripts/run_stage4_batch.py --outputs-dir .\data\outputs
python scripts/run_stage5_batch.py --outputs-dir .\data\outputs --report-dir .\data\analysis_outputs_stage5_batch --with-linking --skip-existing
python scripts/export_batch_link_aware_dataset.py --outputs-dir .\data\outputs --output-dir .\data\outputs\_batch_final_exports
python scripts/run_figure_atlas.py --outputs-dir .\data\outputs --batch-final-export-dir .\data\outputs\_batch_final_exports --batch-output-dir .\data\batch_validation --audit-only
```

## Output locations

Common output locations:

- per-paper outputs: `data/outputs/{category}/{paper_id}/`
- Stage 5 batch reports: `data/analysis_outputs_stage5_batch/`
- batch link-aware exports: `data/outputs/_batch_final_exports/`
- figure atlas runs: `data/batch_validation/{timestamp}/figure_atlas/`

## Documentation

- English and Chinese document index: [docs/README.md](./docs/README.md)
- Chinese quick overview: [README.zh-CN.md](./README.zh-CN.md)

## Legacy tools note

The following are legacy or compatibility concepts and are no longer the primary naming used in current documentation:

- `Stage4A` -> `Stage4`
- `stage55` -> `linking`
- `stage6c` -> `full pipeline`
- `scripts/dev/*`
- `scripts/run_research_figures.py`

See [docs/LEGACY_TOOLS.md](./docs/LEGACY_TOOLS.md) for details.

## What not to commit

Do not commit generated runtime outputs such as:

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## Repository status

- current maintained runtime package: `src/alumina_sol_extractor/`
- archived historical helpers: `archive/`
- regression protection: `tests/`

