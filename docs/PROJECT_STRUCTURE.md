# Project Structure

## Canonical Stage-Oriented Packages

- `alumina_sol_extractor.stage1`: PDF -> MinerU -> markdown -> figures_all
- `alumina_sol_extractor.stage2`: layout, bbox, captions, tables, figure classification, vision inputs
- `alumina_sol_extractor.stage3`: body trim, sections, procedure detection, DSPy text extraction
- `alumina_sol_extractor.stage4`: VLM image/spectra extraction
- `alumina_sol_extractor.stage5`: fusion, linking, link-aware export
- `alumina_sol_extractor.batch`: category normalization and category-aware batch path helpers
- `alumina_sol_extractor.common`: neutral helper re-exports

## Formal Data Path Rules

- `data/markdown/<category>/<paper_id>.md`
- `data/mineru_raw/<category>/<paper_id>/`
- `data/outputs/<category>/<paper_id>/`
- `data/supplementary/<category>/<paper_id>/`

### Stage 1 outputs

- markdown -> `data/markdown/<category>/<paper_id>.md`
- MinerU raw -> `data/mineru_raw/<category>/<paper_id>/`
- figures_all -> `data/outputs/<category>/<paper_id>/figures_all/`

### Stage 2 outputs

- reads `data/markdown/<category>/<paper_id>.md`
- reads `data/mineru_raw/<category>/<paper_id>/`
- writes under `data/outputs/<category>/<paper_id>/`
- writes `figures.jsonl`, `vision_inputs.jsonl`, `figure_stage2_summary.json`

### Stage 3/4/5 outputs

- continue to build on `data/outputs/<category>/<paper_id>/`

## Legacy Modules

Old modules under `pipeline/`, `pdf/`, `utils/`, `figures/`, `vision/`, `vision_spectra/`, `dataset_fusion/`, and `linking/` are retained for backward compatibility.
New development should prefer the `stage1/` ... `stage5/` packages directly.

## Why Some Files Stayed In Place

Some low-level helpers remain in neutral namespaces because they are shared across multiple stages and moving them in the same pass would increase import churn:

- `figures/figure_id.py`
- `storage/save_figures.py`
- `linking/figure_context_matcher.py`
- `markdown_processing/*`
- `dspy_modules/*`
