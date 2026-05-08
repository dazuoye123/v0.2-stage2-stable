# Run Full Pipeline

## Environment

Set the project root first:

```powershell
Set-Location "G:\paper\Al-gel-sol\alumina_sol_extractor"
```

Live stages need these environment variables:

- `OPENAI_API_KEY` or `DASHSCOPE_API_KEY`
- `OPENAI_BASE_URL`
- `LLM_MODEL_NAME`
- `VLM_MODEL_NAME`

Typical DashScope-compatible setup:

```powershell
$env:DASHSCOPE_API_KEY="your-key"
$env:OPENAI_API_KEY=$env:DASHSCOPE_API_KEY
$env:OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_MODEL_NAME="qwen3.6-max-preview"
$env:VLM_MODEL_NAME="qwen-vl-max"
```

## Safe mode

Safe mode does not call any model. Completed stages are skipped, model-dependent missing stages stay pending, and existing Stage 5+ outputs can still be refreshed.

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "柔性α-Al_2O_3纳米结构纤维的制备与表征_贾玉娜" `
  --safe `
  --export-link-aware `
  --no-showcase
```

## Single paper full pipeline

Use this when we want a single paper to go through controlled auto completion. Existing valid stages are skipped automatically.

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "柔性α-Al_2O_3纳米结构纤维的制备与表征_贾玉娜" `
  --auto-complete `
  --live-stage3 `
  --live-stage4a `
  --force-stage5 `
  --force-linking `
  --export-link-aware `
  --no-showcase
```

## Stage 5 / Stage 5.5 / export only

Use this after Stage 4A is already valid and we only want to refresh:

- Stage 5 fusion
- Stage 5.5 deterministic dry-run linking
- link-aware export

No markdown directory is required for this path.

```powershell
python .\scripts\run_full_pipeline.py `
  --outputs-dir ".\data\outputs" `
  --paper-ids "柔性α-Al_2O_3纳米结构纤维的制备与表征_贾玉娜" `
  --force-stage5 `
  --force-linking `
  --export-link-aware `
  --no-showcase
```

## Current four-paper controlled batch

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --max-papers 4 `
  --auto-complete `
  --allow-stage2-refresh `
  --live-stage3 `
  --live-stage4a `
  --max-stage3-papers 4 `
  --max-stage4a-papers 4 `
  --max-stage4a-figures-per-paper 4 `
  --force-stage5 `
  --force-linking `
  --export-link-aware `
  --no-showcase
```

## Stage 1 support from PDF

If markdown is missing and PDFs are available, allow Stage 1:

```powershell
python .\scripts\run_full_pipeline.py `
  --pdf-dir ".\data\pdfs" `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "柔性α-Al_2O_3纳米结构纤维的制备与表征_贾玉娜" `
  --allow-stage1 `
  --auto-complete `
  --live-stage3 `
  --live-stage4a `
  --export-link-aware `
  --no-showcase
```

## Rebuild link-aware export only

Per paper:

```powershell
python .\scripts\export_link_aware_dataset.py `
  --final-dataset-dir ".\data\outputs\柔性α-Al_2O_3纳米结构纤维的制备与表征_贾玉娜\final_dataset" `
  --no-showcase
```

Batch merge:

```powershell
python .\scripts\export_batch_link_aware_dataset.py `
  --outputs-dir ".\data\outputs" `
  --output-dir ".\data\outputs\_batch_final_exports"
```

## Where results go

- Per-paper final dataset:
  - `data/outputs/{paper_id}/final_dataset/`
- Per-paper linking:
  - `data/outputs/{paper_id}/final_dataset/linking/`
- Per-paper link-aware exports:
  - `data/outputs/{paper_id}/final_dataset/link_aware_exports/`
- Batch merged exports:
  - `data/outputs/_batch_final_exports/`
- Pipeline run summaries:
  - `data/batch_validation/{timestamp}/full_pipeline_run/`

## Primary outputs

Use these as the authoritative, traceable tables:

- `final_parameters_linked.csv`
- `process_steps_table.csv`
- `evidence_parameter_links.csv`
- `spectra_parameter_links.csv`
- `sample_parameter_matrix.csv`

`final_showcase_table.csv` is only a quick preview when generated. It is not the primary source for database loading or final statistics.

## Files not to commit

- `data/outputs/`
- `data/batch_validation/`
- `.env`
- PDFs
- model weights
- raw LLM/VLM outputs
- generated final dataset and export artifacts

## Troubleshooting

### `evidence_parameter_links.csv` is empty

Check:

1. `process_steps.jsonl` exists and contains `evidence_text`
2. `links.jsonl` contains `process_step -> parameter` or `evidence_object -> parameter`
3. `link_candidates.jsonl` contains the expected candidate family
4. `run_full_pipeline.py` was executed with `--force-linking`
5. the export step is reading the generated `source_type`

### `spectra_parameter_links.csv` is empty

Check:

1. `spectra.jsonl` contains parsed peaks or quantitative values
2. `parameters.jsonl` contains compatible canonical keys such as:
   - `ftir_peak_position_cm_1`
   - `xrd_peak_position_2theta_deg`
   - `nmr_27Al_peak_position_ppm`
   - `raman_peak_position_cm_1`
3. peak or observed values numerically match parameter values
4. `links.jsonl` contains `spectra_peak`, `spectra_record`, or `visual_extraction` links
5. if only `figure_id` matches but no value matches, deterministic spectra links should stay empty by design

### How to inspect linking quickly

Useful files:

- `final_dataset/linking/linking_summary.json`
- `final_dataset/linking/link_candidates.jsonl`
- `final_dataset/linking/links.jsonl`
- `final_dataset/link_aware_exports/evidence_parameter_links.csv`
- `final_dataset/link_aware_exports/spectra_parameter_links.csv`

### Stage 4A failed

Inspect:

- `data/outputs/{paper_id}/stage4_vision_spectra/raw_vlm_outputs.jsonl`
- `data/outputs/{paper_id}/stage4_vision_spectra/failed_records.jsonl`
- `data/outputs/{paper_id}/stage4_vision_spectra/stage4_quality_review.md`

### Windows `PermissionError` / file lock

Close Excel, WPS, VS Code preview, or any viewer that may still have open:

- `final_dataset.csv`
- `final_parameters_linked.csv`
- `sample_parameter_matrix.csv`
- `process_steps_table.csv`

Then rerun the same command.

### How to confirm skip / run / pending

Check the latest run outputs:

- `data/batch_validation/{timestamp}/full_pipeline_run/run_summary.json`
- `data/batch_validation/{timestamp}/full_pipeline_run/run_report.md`
- `data/batch_validation/{timestamp}/full_pipeline_run/stage6c_full_resume/full_resume_report.md`

### Why preview/showcase is not the core output

Preview/showcase rows are intentionally incomplete when:

- links are still missing
- evidence coverage is partial
- spectra have no deterministic parameter match

That is why the recommended primary tables are the linked parameter, process step, evidence link, spectra link, and sample matrix exports rather than the preview table.
