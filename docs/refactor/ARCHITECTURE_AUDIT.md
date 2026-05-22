# Architecture Audit

## Current Package Tree

Top-level runtime packages under `src/alumina_sol_extractor/` after this refactor:

- `stage1/`: PDF, MinerU, markdown generation, Stage 1 batch/rebuild entrypoints
- `stage2/`: figure/table discovery, caption extraction, layout parsing, vision preprocessing
- `stage3/`: body trim, section/procedure parsing, DSPy text extraction pipeline
- `stage4/`: VLM figure/spectra extraction modules migrated from `vision_spectra/`
- `stage5/`: fusion/linking/export subpackages migrated from `dataset_fusion/` and `linking/`
- `batch/`: category normalization and category-aware path helpers
- `common/`: cross-stage helper exports (`jsonl`, chemistry text)
- legacy-compatible packages still present: `pipeline/`, `pdf/`, `figures/`, `vision/`, `vision_spectra/`, `dataset_fusion/`, `linking/`, `utils/`

## Module Responsibility and Suggested Stage Ownership

- `pipeline/stage1_pdf_to_markdown.py`, `pdf/mineru_pdf_to_markdown.py`: Stage 1
- `pipeline/stage2_figure_pipeline.py`, `pdf/mineru_layout_parser.py`, `utils/figure_utils.py`, `utils/table_utils.py`, `figures/*`, `vision/*`, `stage2_summary.py`: Stage 2
- `pipeline/stage3_dspy_pipeline.py`, `stage3/*`, `markdown_processing/*`, `dspy_modules/*`: Stage 3
- `vision_spectra/*`: Stage 4
- `dataset_fusion/*`, `linking/*`: Stage 5
- `utils/batch_categories.py`, category-aware path/report/manifest helpers: Batch
- `models/*`, `ontology/*`, `config/*`: stable shared support packages
- `storage/save_figures.py`, `figures/figure_id.py`, `linking/figure_context_matcher.py`: ambiguous shared utilities kept in place this round

## Key Dependency Edges

- Stage 1 depends on `config`, `batch.categories`, `stage2.figure_discovery` image rewrite helper, and shared chemistry normalization
- Stage 2 depends on `config`, `figures.figure_id`, `linking.figure_context_matcher`, `models.figure`, `storage.save_figures`, `vision`/`stage2` classifiers
- Stage 3 depends on `config`, `dspy_modules`, `models`, `markdown_processing`
- Stage 4 depends on `vision_spectra` logic now mirrored in `stage4/`
- Stage 5 depends heavily on `dataset_fusion` + `linking` internals; both are mirrored into `stage5/` subpackages

## Files Kept in Place and Why

- `figures/figure_id.py`: shared by Stage 2 caption/grouping logic; left in place to avoid cascading import churn
- `storage/save_figures.py`: used by figure writers without stage-specific behavior; left in place as neutral storage helper
- `linking/figure_context_matcher.py`: referenced by Stage 2 and Stage 5, so still ambiguous between stage-specific and shared logic
- `markdown_processing/*`: already stable Stage 3-adjacent package with clear semantics, left as-is
- `dspy_modules/*`: tightly coupled Stage 3 DSPy implementation; left as-is while `stage3/pipeline.py` becomes the clearer stage entrypoint

## Potential Circular Import Risks

- Stage 2 wrappers around `pipeline`, `figures`, `vision`, and `utils.figure_utils`
- Stage 5 mirrored `dataset_fusion` and `linking` packages, which reference each other
- Stage 4 mirrored `vision_spectra` package, which imports sibling modules transitively

These risks are controlled by making new stage packages the preferred import targets while old modules remain thin star-import wrappers.

## Stable Stage 2 Logic Protected in This Refactor

The following behavior must not regress and was kept untouched:

- `extract_caption_record(...)`
- `_group_consecutive_images(...)`
- `match_figure_contexts(...)`
- `FigureFilter`
- `CLIPPrefilter`
- `FigureClassifier` / ResNet classifier

In particular, no `mineru_layout_caption` source was reintroduced into formal logic.

## Modules Automatically Assigned by Codex

- `figures/*` -> Stage 2 because they are exclusively about figure captions/writers/description helpers
- `vision/*` -> Stage 2 because they are pre-VLM local figure classifiers and filters
- `vision_spectra/*` -> Stage 4 because they are VLM spectra/image extraction paths
- `dataset_fusion/*` and `linking/*` -> Stage 5 because they back fusion/link-aware export and parameter linking
- `utils/batch_categories.py` -> Batch because it only normalizes category-aware batch paths

## Ambiguous Files

- `linking/figure_context_matcher.py`: Stage 2 figure context helper living under Stage 5-ish linking namespace
- `storage/save_figures.py`: generic persistence utility, not stage-specific enough to move aggressively this round
- `figures/figure_id.py`: small figure-ID parser shared by Stage 2 utilities and tests

## This Refactor Did Not Change Algorithms

- No caption extraction rules were widened beyond restoring the old markdown-context behavior
- No FigureFilter / ResNet / CLIP logic changed
- No Stage 3 / 4 / 5 extraction algorithms changed
- No output file schema semantics changed
