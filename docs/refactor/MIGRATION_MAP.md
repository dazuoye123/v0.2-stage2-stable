# Migration Map

| Old path | New path | Stage | Migration mode | Wrapper kept | Notes |
|---|---|---|---|---|---|
| `pipeline/stage1_pdf_to_markdown.py` | `stage1/pdf_to_markdown.py` | Stage 1 | copied to canonical stage package | yes | old pipeline path now re-exports new module |
| `pdf/mineru_pdf_to_markdown.py` | `stage1/mineru_pdf_to_markdown.py` | Stage 1 | copied | yes | keeps MinerU conversion logic intact |
| `scripts/dev/run_stage1_markdown_batch.py` | `stage1/batch_runner.py` | Stage 1 | copied core entrypoint | script kept | script remains runnable |
| `scripts/dev/rebuild_stage1_from_mineru_raw.py` | `stage1/rebuild_from_mineru_raw.py` | Stage 1 | copied core entrypoint | script kept | script remains runnable |
| `pipeline/stage2_figure_pipeline.py` | `stage2/pipeline.py` | Stage 2 | copied | yes | old import stays valid |
| `pdf/mineru_layout_parser.py` | `stage2/mineru_layout_parser.py` | Stage 2 | copied | yes | layout parsing now stage-scoped |
| `utils/figure_utils.py` | `stage2/figure_discovery.py` | Stage 2 | copied | yes | stable caption logic preserved |
| `utils/table_utils.py` | `stage2/table_extractor.py` | Stage 2 | copied | yes | category-aware tables path behavior preserved |
| `figures/caption_extractor.py` | `stage2/caption_extractor.py` | Stage 2 | copied | yes | compatibility export retained |
| `figures/caption_assignment.py` | `stage2/caption_assignment.py` | Stage 2 | copied | yes | compatibility export retained |
| `figures/figure_writer.py` | `stage2/figure_writer.py` | Stage 2 | copied | yes | figures/vision outputs unchanged |
| `vision/figure_filter.py` | `stage2/figure_filter.py` | Stage 2 | copied | yes | no filter logic change |
| `vision/vision_selector.py` | `stage2/vision_selector.py` | Stage 2 | copied | yes | |
| `vision/taxonomy_classifier.py` | `stage2/taxonomy_classifier.py` | Stage 2 | copied | yes | |
| `vision/taxonomy_config.py` | `stage2/taxonomy_config.py` | Stage 2 | copied | yes | |
| `vision/resnet_classifier.py` | `stage2/resnet_classifier.py` | Stage 2 | copied | yes | |
| `vision/clip_prefilter.py` | `stage2/clip_prefilter.py` | Stage 2 | copied | yes | |
| `vision/figure_fragment_merger.py` | `stage2/fragment_merger.py` | Stage 2 | copied | yes | |
| `stage2_summary.py` | `stage2/summary.py` | Stage 2 | copied | yes | |
| `scripts/dev/run_stage2_preprocess_batch.py` | `stage2/batch_runner.py` | Stage 2 | copied core entrypoint | script kept | |
| `pipeline/stage3_dspy_pipeline.py` | `stage3/pipeline.py` | Stage 3 | copied | yes | existing `stage3/` package retained |
| `vision_spectra/*` | `stage4/*` | Stage 4 | copied package modules | yes | old package remains wrapper |
| `dataset_fusion/*` | `stage5/dataset_fusion/*` | Stage 5 | copied package modules | partially | old package modules re-export new stage5 copies |
| `linking/*` | `stage5/linking/*` | Stage 5 | copied package modules | partially | old package modules re-export new stage5 copies |
| `utils/batch_categories.py` | `batch/categories.py` | Batch | copied | yes | |
| `batch path helpers` | `batch/paths.py` | Batch | newly introduced | n/a | category-aware path helpers only |
