# alumina_sol_extractor

Alumina-sol and alumina-fiber literature extraction pipeline for building structured datasets from PDF / Markdown papers.

## Project Goal

The maintained pipeline turns literature into structured outputs for downstream analysis:

`PDF / Markdown -> Stage 3 / Stage 4 extraction -> Stage 5 fusion -> link-aware export`

Target objects include:
- samples
- parameters
- process steps
- evidence
- spectra
- figures
- parameter links
- sample parameter matrices

## Main Entry

The recommended runtime entry is:

```bash
python scripts/run_full_pipeline.py --outputs-dir .\data\outputs ...
```

`python main.py` remains in the repository as a legacy lightweight entry, but it is no longer the recommended full-pipeline command.

Other maintained entrypoints:

- `python scripts/run_stage4_batch.py ...`
- `python scripts/run_stage5_batch.py ...`
- `python scripts/export_link_aware_dataset.py ...`
- `python scripts/export_batch_link_aware_dataset.py ...`
- `python scripts/run_figure_atlas.py ...`

## Core Stages

### Stage 1: PDF -> Markdown
- MinerU-based PDF to Markdown conversion
- image path rewriting
- chemistry/symbol cleanup
- cleaned markdown output

### Stage 2: Figure / Table Preparation
- figure extraction
- vision input preparation
- figure metadata for downstream Stage 4

### Stage 3: Structured Text Extraction
- cleaned-body text preparation
- procedure section selection
- structured extraction for samples, parameters, evidence, process steps, and related fields

### Stage 4: Vision / Spectra Extraction
- figure-level structured extraction for XRD, FTIR/IR, Raman, NMR, TG/TGA, DSC/DTA, TG-DSC/TG-DTA, Ferron, SEM, TEM, and related figure types

Legacy note:
- the historical name `Stage4A` still appears in some compatibility wrappers, tests, and archived notes
- the maintained pipeline and current docs use `Stage4` as the official name

### Stage 5: Fusion + Linking + Link-Aware Export
- final dataset fusion
- deterministic / controlled linking
- link-aware export tables
- sample matrix outputs

## Important Directories

- `src/alumina_sol_extractor/`
  Core runtime package.
- `scripts/`
  Runtime and operational entry scripts.
- `scripts/dev/`
  Manual inspection, batch planning, manifest, and developer utilities. These are not the main pipeline.
- `archive/`
  Archived legacy tools retained for compatibility and historical traceability.
- `tests/`
  Regression tests. These protect runtime behavior and are not part of the main pipeline itself.
- `docs/`
  Design notes, operational docs, and cleanup planning.
- `data/outputs/`
  Generated paper outputs. Do not commit runtime result files from this directory.

## Setup

Install the project in your preferred environment. The repository currently includes both `pyproject.toml` and `requirements.txt`; `pyproject.toml` is the better long-term source of truth, while `requirements.txt` remains for compatibility.

Example:

```bash
pip install -e .
```

If you still use the compatibility path:

```bash
pip install -r requirements.txt
```

Some stages require local environment variables or API credentials, depending on which parts of the pipeline you run.

## Typical Usage

Full pipeline:

```bash
python scripts/run_full_pipeline.py ^
  --markdown-dir .\data\markdown ^
  --outputs-dir .\data\outputs ^
  --paper-ids "example_paper" ^
  --export-link-aware
```

Stage 5 only:

```bash
python scripts/run_stage5_dataset_fusion.py ...
```

Stage 5 batch:

```bash
python scripts/run_stage5_batch.py ...
```

Linking only:

```bash
python scripts/run_stage5_linking.py ...
```

Link-aware export only:

```bash
python scripts/export_link_aware_dataset.py ...
```

## Testing

Run the regression suite with:

```bash
pytest
```

Optional compile check:

```bash
python -m compileall .\src .\scripts .\tests
```

## Repository Notes

- `scripts/dev/` is intentionally separate from the core runtime flow.
- `scripts/run_research_figures.py` and `src/alumina_sol_extractor/research_figures/` are kept only for legacy compatibility. New batch-level figure work should use `scripts/run_figure_atlas.py`.
- Legacy tool guidance is summarized in `docs/LEGACY_TOOLS.md`.
- `tests/` should be kept as regression protection, especially for Stage 3, Stage 4, Stage 5, linking, and sample-matrix behavior.
- `data/outputs/`, `data/markdown/`, `data/pdfs/`, and other generated or local source data should not be committed.
