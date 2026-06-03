# Run Stage4 Batch

## Purpose

Use `scripts/run_stage4_batch.py` to run the maintained Stage 4 batch workflow.

## Input layout

Stage 4 expects per-paper directories under:

```text
data/outputs/{category}/{paper_id}/
```

It uses:

- Stage 3 context from `stage3_twopass/` by default
- Stage 2-selected figures from `figures.jsonl`
- fallback `figures_for_vision/` if needed

## Minimal command

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs"
```

## Supported arguments

- `--outputs-dir`
- `--manifest`
- `--paper-ids`
- `--category`
- `--limit`
- `--live`
- `--force-stage4`
- `--stage4-figure-ids`
- `--continue-on-error`
- `--output-dir`
- `--stage3-subdir`
- `--stage4-subdir`
- `--stage4-routing-mode`
- `--candidate-source`
- `--max-figures-per-paper`

## Behavior

- default mode is dry-run
- `--live` enables real Stage 4 extraction
- `--force-stage4` removes the existing Stage 4 output directory before rerun
- if `--force-stage4` is not used, the runner may skip papers with a live-successful `stage4a_summary.json`
- `--stage4-figure-ids` limits work to selected figures

## Output location

Per-paper Stage 4 output:

```text
data/outputs/{category}/{paper_id}/stage4_vision_spectra_universal/
```

Batch report output:

```text
data/batch_validation/{timestamp}/stage4_batch/
```

Batch report files:

- `stage4_batch_rows.jsonl`
- `stage4_batch_summary.json`
- `stage4_batch_report.md`

## Warnings

- `stage4a_summary.json` is still the real summary filename for compatibility
- `Stage4A` is a legacy name only; current docs use `Stage4`

