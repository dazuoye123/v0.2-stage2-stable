# Refactor Audit

This document records conservative cleanup decisions made during the
`feature/refactor-clean-pipeline` refactor. The goal is structural clarity
without changing stable stage-2 behavior.

## Removed or Replaced

### 1. Fat `main.py` inline pipeline logic
- **What changed**: `main.py` no longer contains MinerU conversion details,
  table extraction, figure extraction, CLIP/ResNet loops, fragment stitch
  control, JSONL writing, or summary construction inline.
- **Replacement**:
  - `src/alumina_sol_extractor/pipeline/stage1_pdf_to_markdown.py`
  - `src/alumina_sol_extractor/pipeline/stage2_figure_pipeline.py`
- **Why safe**: The new pipeline modules call the same underlying functions and
  models with the same defaults. `settings.yaml` remains the entry point.
- **Validation**: compileall + regression scripts + baseline summary comparison.

### 2. Monolithic taxonomy / selection / review logic
- **What changed**: `vision/figure_filter.py` is now a compatibility facade.
- **Replacement**:
  - `vision/taxonomy_config.py`
  - `vision/taxonomy_classifier.py`
  - `vision/vision_selector.py`
  - `vision/review_rules.py`
- **Why safe**: The public `FigureFilter` API did not change. The rule order was
  copied into the new modules rather than redesigned.
- **Validation**: existing figure taxonomy tests and real-paper regression run.

### 3. Repeated figure-ID regex definitions
- **What changed**: Figure-ID regexes and exact mention builders are now
  centralized.
- **Replacement**:
  - `figures/figure_id.py`
- **Call sites updated**:
  - `utils/figure_utils.py`
  - `linking/figure_context_matcher.py`
  - `vision/figure_fragment_merger.py`
- **Why safe**: The shared regex preserves the existing `图/Fig./Figure` forms
  and keeps the same "must include prefix" behavior.
- **Validation**: exact-reference tests and multi-caption tests.

### 4. Duplicate JSONL writing paths
- **What changed**: low-level JSONL writing is centralized.
- **Replacement**:
  - `utils/jsonl.py`
  - `figures/figure_writer.py`
- **Compatibility kept**:
  - `storage/save_figures.py` still exists and forwards to the shared writer.
- **Why safe**: output file names and JSON fields remain unchanged.
- **Validation**: figures JSONL + summary outputs regenerated successfully.

## Deprecated Patterns Intentionally Not Restored

### PDF recrop / PyMuPDF
- **Status**: not reintroduced.
- **Reason**: stable version uses MinerU bbox stitching only.
- **Risk if restored**: behavior drift in fragment reconstruction.

### `section_type`
- **Status**: not reintroduced.
- **Reason**: removed earlier by design; user explicitly asked not to bring it
  back.
- **Risk if restored**: unstable filtering behavior across thesis/article
  layouts.

### Markdown-order fragment merge
- **Status**: not restored.
- **Reason**: stable behavior uses bbox-based spatial stitching.
- **Risk if restored**: 2-column fragment groups collapse into wrong long-strip
  images.

## Remaining Low-Risk Compatibility Shims

These modules still exist primarily to avoid breaking imports while the code is
being cleaned up:
- `storage/save_figures.py`
- `vision/figure_filter.py`
- `linking/figure_context_matcher.py`
- `utils/figure_utils.py`

They now delegate more of their work to smaller modules, but were intentionally
left in place so old scripts keep running.
