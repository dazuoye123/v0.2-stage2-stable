# Glossary

| term | definition | where it appears |
|---|---|---|
| Stage3 | structured text extraction stage | `stage3_*`, Stage 3 outputs |
| Stage4 | figure and spectra extraction stage | `stage4/`, `stage4_vision_spectra_universal/` |
| Stage5 | fusion stage | `stage5/`, `final_dataset/` |
| batch runner | script or module that processes many papers | `run_stage4_batch.py`, `run_stage5_batch.py` |
| full pipeline | top-level orchestrated workflow | `scripts/run_full_pipeline.py` |
| figure atlas | downstream plotting and audit package from existing outputs | `scripts/run_figure_atlas.py`, `figure_atlas/` |
| link-aware export | per-paper tables enriched with linking context | `final_dataset/link_aware_exports/` |
| deterministic linking | rule-based linking between evidence, spectra, process steps, and parameters | `stage5/linking/` |
| evidence link | link from evidence object to parameter | `evidence_parameter_links.csv` |
| spectra link | link from spectra record to parameter | `spectra_parameter_links.csv` |
| process-step link | link from process step to parameter | `process_step_parameter_links.csv` |
| sample matrix | sample-by-parameter export table | `sample_parameter_matrix.csv` |
| final dataset | per-paper Stage 5 output package | `final_dataset/` |
| batch final export | cross-paper aggregated export package | `data/outputs/_batch_final_exports/` |
| legacy wrapper | compatibility script that forwards to a newer or archived implementation | `scripts/dev/*`, `scripts/run_research_figures.py` |
| archive | historical implementation storage | `archive/` |
| dry-run | planning or no-live-call mode | Stage 4 batch, Stage 5 batch, full pipeline |
| skip-existing | skip outputs already considered complete | Stage 5 batch |
| only-incomplete | run only papers with missing Stage 5/linking/export outputs | Stage 5 batch |
| force rerun | overwrite or rerun an existing output set | Stage 4/Stage 5 controlled rerun |
| partial success | output was produced with warnings or reduced coverage | `stage5_summary.json`, batch reports |
| QA figure | quality assurance figure in figure atlas | `figures/qa/` |
| source data | per-figure CSV or JSON used to build an atlas figure | `tables/{figure_id}_source.csv`, `figure_data/{figure_id}.json` |
| normalized table | atlas-ready normalized tabular layer | `tables/normalized_*.csv` |
| manifest | structured run summary listing generated artifacts | `figure_atlas_manifest.json` |
| figure_index | table indexing all generated atlas figures | `figure_index.csv` |

