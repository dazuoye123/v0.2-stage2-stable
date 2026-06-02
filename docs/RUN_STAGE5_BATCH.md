# Run Stage 5 Batch

## Purpose

Use this command when Stage 3 and Stage 4 outputs already exist and you want to
batch-run:

- Stage 5 fusion
- deterministic linking
- link-aware exports

It does not call VLMs or rerun Stage 1-4.

## Official command

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --skip-existing `
  --continue-on-error `
  --workers 1
```

## Dry run

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --dry-run `
  --limit 10 `
  --continue-on-error `
  --workers 1
```

## Incomplete-only rerun planning

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --only-incomplete `
  --limit 20 `
  --skip-existing `
  --continue-on-error `
  --workers 1
```

`--only-incomplete` filters papers before `--limit` is applied, so the limit is
spent on papers that still need missing Stage 5/link-aware files.

## Key safety rules

- `--skip-existing` avoids overwriting complete `final_dataset` outputs.
- `--force` should only be used for controlled reruns.
- `--workers 1` is the recommended default until you intentionally validate
  concurrent behavior in your environment.

## Outputs

Per paper:

- `final_dataset/stage5_summary.json`
- `final_dataset/parameters.jsonl`
- `final_dataset/samples.jsonl`
- `final_dataset/process_steps.jsonl`
- `final_dataset/evidence.jsonl`
- `final_dataset/spectra.jsonl`
- `final_dataset/linking/`
- `final_dataset/link_aware_exports/`

Batch report directory:

- `stage5_batch_paper_summary.csv`
- `stage5_batch_failure_manifest.csv`
- `stage5_batch_quality_summary.csv`
- `stage5_batch_overall_summary.json`
- `stage5_batch_run_report.md`

## Legacy note

`scripts/dev/run_stage5_batch.py` is now only a compatibility wrapper around
this official entrypoint.
