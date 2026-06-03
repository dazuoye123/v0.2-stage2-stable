# Run Stage5 Batch

## Purpose

Use `scripts/run_stage5_batch.py` to run Stage 5 fusion and optional linking/export across many papers.

## Default behavior

- reads existing Stage 3 and Stage 4 outputs
- does not call VLM
- uses deterministic linking when linking is enabled
- `--skip-existing` is effectively on unless `--force` is used

## Supported arguments

- `--outputs-dir`
- `--report-dir`
- `--categories`
- `--limit`
- `--paper-filter`
- `--force`
- `--skip-existing`
- `--only-incomplete`
- `--stage5-only`
- `--with-linking`
- `--no-linking`
- `--dry-run`
- `--continue-on-error`
- `--workers`

## Recommended commands

Dry-run:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --dry-run `
  --limit 10
```

Stage 5 only:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --stage5-only `
  --skip-existing `
  --workers 1
```

Stage 5 with linking:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --skip-existing `
  --continue-on-error `
  --workers 1
```

Only incomplete:

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --only-incomplete `
  --skip-existing
```

## Key behaviors

### `--dry-run`

- plans the run
- writes batch reports
- does not write per-paper Stage 5 outputs

### `--skip-existing`

- skips papers that already have complete Stage 5 outputs
- is the safe default when `--force` is not used

### `--only-incomplete`

- filters the discovered paper list to papers missing one or more required Stage 5 or linking/export outputs
- `--limit` is applied after this filter

### `--force`

- overwrites Stage 5 outputs
- should only be used for controlled repair or rerun work

## Report files

The batch runner writes:

- `stage5_batch_paper_summary.csv`
- `stage5_batch_failure_manifest.csv`
- `stage5_batch_quality_summary.csv`
- `stage5_batch_overall_summary.json`
- `stage5_batch_run_report.md`

## Common warnings

- `missing_stage4a_but_stage5_partial_ok`
- `dry_run_only_spectra`
- `no_stage4a_live_spectra`
- `empty_parameters`
- `zero_process_steps`
- `zero_evidence_links`
- `zero_spectra_links`
- `zero_process_step_links`
- `zero_sample_matrix`

