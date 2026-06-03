# Input / Output Specification

## Required input layout

The maintained repository layout is:

```text
data/outputs/{category}/{paper_id}/
```

Supported categories in current batch workflows:

- `mechanism`
- `fiber_process`
- `applications`
- `rheology`

Some discovery code also supports flat `data/outputs/{paper_id}/` directories for compatibility.

## Per-paper Stage 3 outputs

Possible Stage 3 directories:

- `stage3_twopass/`
- `stage3/`
- `stage3_dspy_smoke/`

Common Stage 3 files referenced by current code:

- `stage3_summary.json`
- `paper_extraction.schema_v2.json`
- `parameters.jsonl`
- `samples.jsonl`
- `process_steps.jsonl`
- `evidence_objects.jsonl`
- `quality_summary.json`

## Per-paper Stage 4 outputs

Possible Stage 4 directories:

- `stage4_vision_spectra_universal/`
- `stage4_vision_spectra/`

Common files:

- `stage4a_summary.json` (legacy file name, still used)
- `spectra_extractions.jsonl`
- `raw_vlm_outputs.jsonl`
- `spectra_failed_records.jsonl`

Optional / helper files may exist, including review or reparse outputs.

## Per-paper Stage 5 outputs

Directory:

```text
data/outputs/{category}/{paper_id}/final_dataset/
```

Expected files:

- `stage5_summary.json`
- `paper.json`
- `samples.jsonl`
- `parameters.jsonl`
- `process_steps.jsonl`
- `evidence.jsonl`
- `figures.jsonl`
- `spectra.jsonl`
- `quality_summary.json`
- `fusion_report.md`

## Per-paper linking outputs

Directory:

```text
final_dataset/linking/
```

Common files:

- `link_candidates.jsonl`
- `links.jsonl`
- `unmatched_candidates.jsonl`
- `rejected_links.jsonl`
- `raw_llm_linking_outputs.jsonl`
- `linking_summary.json`
- `linking_report.md`

Note:
- current Stage 5 batch uses deterministic linking only
- live linking helpers still exist, but they are not the default path for the official batch runner

## Per-paper link-aware export outputs

Directory:

```text
final_dataset/link_aware_exports/
```

Common files:

- `final_parameters_linked.csv`
- `sample_parameter_matrix.csv`
- `evidence_parameter_links.csv`
- `process_step_parameter_links.csv`
- `spectra_parameter_links.csv`
- `process_steps_table.csv`
- `final_showcase_table.csv`
- `link_aware_export_summary.json`
- `link_aware_export_readme.md`
- `link_aware_export_diagnosis.md`

Optional files may appear if the export implementation grows.

## Batch final export outputs

Directory:

```text
data/outputs/_batch_final_exports/
```

Current batch export files:

- `all_papers_final_parameters_linked.csv`
- `all_papers_evidence_parameter_links.csv`
- `all_papers_process_step_parameter_links.csv`
- `all_papers_spectra_parameter_links.csv`
- `all_papers_process_steps_table.csv`
- `all_papers_sample_parameter_matrix.csv`
- `all_papers_final_showcase_table.csv`
- `all_papers_link_aware_summary.json`
- `all_papers_export_report.md`

Purpose of major files:

- `all_papers_final_parameters_linked.csv`: cross-paper parameter table after Stage 5 export
- `all_papers_evidence_parameter_links.csv`: aggregated evidence-to-parameter links
- `all_papers_process_step_parameter_links.csv`: aggregated process-step-to-parameter links
- `all_papers_spectra_parameter_links.csv`: aggregated spectra-to-parameter links
- `all_papers_process_steps_table.csv`: aggregated process-step table
- `all_papers_sample_parameter_matrix.csv`: sample-by-parameter matrix rows
- `all_papers_final_showcase_table.csv`: curated downstream-friendly display table

## Figure atlas outputs

Directory:

```text
data/batch_validation/{timestamp}/figure_atlas/
```

Important files:

- `audit/result_inventory.json`
- `audit/result_inventory.md`
- `audit/data_availability_matrix.csv`
- `audit/figure_feasibility_matrix.csv`
- `audit/input_table_schema_report.json`
- `audit/input_table_schema_report.md`
- `tables/normalized_parameters.csv`
- `tables/normalized_process_steps.csv`
- `tables/normalized_stage4_spectra.csv`
- `tables/normalized_stage4_peaks.csv`
- `tables/normalized_stage5_links.csv`
- `tables/normalized_sample_matrix.csv`
- `tables/{figure_id}_source.csv`
- `figure_data/{figure_id}.json`
- `figures/main/`
- `figures/stage3/`
- `figures/stage4/`
- `figures/stage5/`
- `figures/cross_stage/`
- `figures/qa/`
- `figures/auto/`
- `figure_atlas_manifest.json`
- `figure_index.csv`
- `figure_atlas_readme.md`

## Safe to regenerate

- `data/outputs/_batch_final_exports/` can be regenerated from per-paper `link_aware_exports/`
- `data/batch_validation/{timestamp}/figure_atlas/` can be regenerated from existing Stage 3 / Stage 4 / Stage 5 outputs plus batch export files

## Not safe to delete casually

- `data/outputs/{category}/{paper_id}/stage3_*`
- `data/outputs/{category}/{paper_id}/stage4_vision_spectra_universal/`
- `data/outputs/{category}/{paper_id}/final_dataset/`

