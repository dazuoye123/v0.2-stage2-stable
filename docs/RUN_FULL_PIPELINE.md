# Run Full Pipeline

## Environment

Prepare the project root:

```powershell
Set-Location "G:\paper\Al-gel-sol\alumina_sol_extractor"
```

Required environment variables for live stages:

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

No model calls. Completed stages are skipped, missing model-dependent stages stay pending, and link-aware exports can be refreshed from existing outputs.

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

Use this when we want one paper to run through resume, fusion, linking dry-run, and link-aware export. Existing valid stages are skipped automatically.

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

## Linking + export only

Use this when Stage 3 and Stage 4A are already valid and we only want to refresh Stage 5, Stage 5.5 dry-run, and link-aware exports.

```powershell
python .\scripts\run_full_pipeline.py `
  --outputs-dir ".\data\outputs" `
  --markdown-dir ".\data\markdown" `
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

If markdown is missing and PDF files are available, allow Stage 1:

```powershell
python .\scripts\run_full_pipeline.py `
  --pdf-dir ".\data\pdfs" `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "paper_name_here" `
  --allow-stage1 `
  --auto-complete `
  --live-stage3 `
  --live-stage4a `
  --export-link-aware `
  --no-showcase
```

## Rebuild link-aware export only

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

Treat these as the authoritative tables:

- `final_parameters_linked.csv`
- `process_steps_table.csv`
- `evidence_parameter_links.csv`
- `spectra_parameter_links.csv`
- `sample_parameter_matrix.csv`

`final_showcase_table.csv` is only a preview table when generated. It is not the primary source for statistics or database loading.

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

Check whether:

1. `process_steps.jsonl` exists and contains `evidence_text`
2. `links.jsonl` contains `process_step -> parameter` or `evidence_object -> parameter`
3. `run_full_pipeline.py` was executed with `--force-linking`

### `spectra_parameter_links.csv` is empty

Check whether:

1. `spectra.jsonl` contains parsed peaks
2. parameter canonical keys exist for the peak type, such as `ftir_peak_position_cm_1`, `xrd_peak_position_2theta_deg`, `nmr_27Al_peak_position_ppm`
3. peak values numerically match parameter values

### Stage 4A failed

Inspect:

- `data/outputs/{paper_id}/stage4_vision_spectra/raw_vlm_outputs.jsonl`
- `data/outputs/{paper_id}/stage4_vision_spectra/failed_records.jsonl`
- `data/outputs/{paper_id}/stage4_vision_spectra/stage4_quality_review.md`

### Windows `PermissionError` / file lock

Close Excel, WPS, VS Code preview, or any viewer that may have opened:

- `final_dataset.csv`
- `final_parameters_linked.csv`
- `sample_parameter_matrix.csv`

Then rerun the same command.

### How to confirm skip / run / pending

Check the latest batch report:

- `data/batch_validation/{timestamp}/full_pipeline_run/run_summary.json`
- `data/batch_validation/{timestamp}/full_pipeline_run/run_report.md`
- `data/batch_validation/{timestamp}/full_pipeline_run/stage6c_full_resume/full_resume_report.md`
