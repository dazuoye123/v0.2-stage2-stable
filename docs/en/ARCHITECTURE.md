# Architecture

## Official entrypoints

Maintained entrypoints live in `scripts/`:

- `run_full_pipeline.py`
- `run_stage4_batch.py`
- `run_stage5_batch.py`
- `export_link_aware_dataset.py`
- `export_batch_link_aware_dataset.py`
- `run_figure_atlas.py`

## Runtime layers

### CLI layer

- Thin wrappers under `scripts/`
- Parse arguments
- Resolve relative paths
- Delegate to `src/alumina_sol_extractor/*`

### Orchestration layer

- `src/alumina_sol_extractor/pipeline/orchestrator.py`
- `src/alumina_sol_extractor/pipeline/full_pipeline_runner.py`
- `src/alumina_sol_extractor/pipeline/resume_status.py`

### Stage modules

- `stage1/`
- `stage2/`
- `stage3/`
- `stage4/`
- `stage5/`

### Analysis / plotting layer

- `figure_atlas/`

## Pipeline orchestration

`orchestrator.py` is now the preferred maintained orchestration layer.

It coordinates:

- Stage 1 recovery for missing Markdown when enabled
- full pipeline resume execution
- Stage 5-only reuse path
- link-aware export summary writing

`full_pipeline_runner.py` still contains older compatibility logic and legacy naming.

## Stage 3 module responsibilities

Stage 3 owns:

- document trimming
- section selection
- process step extraction
- parameter and evidence extraction
- validation and quality grading

## Stage 4 module responsibilities

Stage 4 owns:

- Stage 2-selected figure loading
- per-figure routing
- VLM interaction in live mode
- normalization and validation
- processed-index dedup
- fallback / replay-aware compatibility

## Stage 5 module responsibilities

Stage 5 owns:

- dataset fusion
- deterministic linking
- per-paper link-aware export
- batch aggregation

## Linking and export modules

The codebase keeps both:

- `src/alumina_sol_extractor/linking/`
- `src/alumina_sol_extractor/stage5/linking/`

and both:

- `src/alumina_sol_extractor/dataset_fusion/`
- `src/alumina_sol_extractor/stage5/dataset_fusion/`

Current maintained batch entrypoints use the Stage 5 namespaced modules, while compatibility imports remain available.

## Figure atlas modules

`figure_atlas/` is a read-only downstream analysis layer.

It uses:

- audit and discovery helpers
- normalized tables
- tiered figure generators
- per-figure source CSV / JSON bundles

## Compatibility namespaces

Compatibility namespaces still exist for historical reasons:

- `vision_spectra`
- `dataset_fusion`
- `linking`
- `research_figures`
- `batch_validation`

These should not be treated as the primary user-facing architecture if a dedicated official entrypoint already exists.

## Legacy wrappers

Many scripts in `scripts/dev/` are now wrappers that execute archived implementations from `archive/`.

Purpose:

- preserve old commands
- avoid breaking local notes or historical tooling
- keep official entrypoints cleaner

## Archive policy

`archive/` stores historical implementations that are no longer recommended as primary runtime paths.

Archive content is still useful when:

- reading old reports
- understanding previous repair/replay workflows
- tracing migrations from older command names

## Test strategy

The repository relies on broad regression coverage:

- Stage 3 tests
- Stage 4 tests
- Stage 5 tests
- linking tests
- batch export tests
- figure atlas tests
- full pipeline tests
- compatibility tests

## Data safety policy

The repository source should not commit runtime outputs such as:

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## Future extension points

- better deterministic linking coverage
- richer figure atlas source normalization
- eventual deeper retirement of legacy wrappers

