# Architecture

## Official entrypoints

The maintained user-facing commands are:

- `scripts/run_full_pipeline.py`
- `scripts/run_stage4_batch.py`
- `scripts/run_stage5_batch.py`
- `scripts/export_link_aware_dataset.py`
- `scripts/export_batch_link_aware_dataset.py`
- `scripts/run_figure_atlas.py`

## Stage-oriented runtime packages

- `alumina_sol_extractor.stage1`
- `alumina_sol_extractor.stage2`
- `alumina_sol_extractor.stage3`
- `alumina_sol_extractor.stage4`
- `alumina_sol_extractor.stage5`

New development should prefer these namespaces directly.

## Compatibility namespaces

The following packages are still present for backward compatibility and import
stability:

- `alumina_sol_extractor.dataset_fusion`
- `alumina_sol_extractor.linking`
- `alumina_sol_extractor.vision_spectra`
- `alumina_sol_extractor.research_figures`

They should not be the primary design target for new runtime features.

## Stage 4

Stage 4 official execution should flow through:

- `alumina_sol_extractor.stage4.batch_runner`
- `alumina_sol_extractor.stage4.extractor.Stage4VisionSpectraExtractor`

Default maintained configuration:

- `stage3_subdir = stage3_twopass`
- `stage4_subdir = stage4_vision_spectra_universal`
- `routing_mode = universal_compact`
- `candidate_source = stage2-selected`

## Stage 5

Stage 5 official batch execution should flow through:

- `alumina_sol_extractor.stage5.batch_runner`
- `scripts/run_stage5_batch.py`

Per-paper fusion, linking, and export remain in:

- `alumina_sol_extractor.stage5.dataset_fusion`
- `alumina_sol_extractor.stage5.linking`

## Figure outputs

Batch-level research figure generation should use:

- `scripts/run_figure_atlas.py`
- `alumina_sol_extractor.figure_atlas`

`research_figures` remains only as a legacy compatibility tool and should not
be used as the primary documented path.
