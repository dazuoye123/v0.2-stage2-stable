# Run Full Pipeline

## Purpose

Use `scripts/run_full_pipeline.py` when you want the maintained top-level orchestration entrypoint.

## When to use

- controlled end-to-end runs
- dry-run planning
- selective rerun of upstream stages
- Stage 5-only orchestration from existing outputs when `--markdown-dir` is omitted

## Minimal command

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs"
```

## Common commands

Dry-run:

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --dry-run `
  --safe
```

Selective papers:

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "paper_a,paper_b"
```

## Important arguments

- `--pdf-dir`
- `--markdown-dir`
- `--outputs-dir`
- `--paper-ids`
- `--max-papers`
- `--auto-complete`
- `--allow-stage1`
- `--allow-stage2-refresh`
- `--live-stage3`
- `--live-stage4`
- `--live-linking`
- `--force-stage3`
- `--force-stage4`
- `--force-stage5`
- `--force-linking`
- `--export-link-aware`
- `--dry-run`
- `--safe`
- `--max-stage3-papers`
- `--max-stage4-papers`
- `--max-stage4-figures-per-paper`
- `--max-total-model-calls`
- `--stage4-figure-types`
- `--stage4-figure-ids`
- `--stage3-subdir`
- `--stage4-subdir`
- `--stage4-routing-mode`
- `--stage4-candidate-source`
- `--no-showcase`
- `--output-dir`

## Stage 4 alias explanation

Legacy aliases are still accepted:

- `--live-stage4a`
- `--force-stage4a`
- `--max-stage4a-papers`
- `--max-stage4a-figures-per-paper`
- `--stage4a-figure-types`

Current documentation recommends the Stage 4 names instead.

## Dry-run and safe behavior

- `--dry-run` prevents real execution and writes planning/report outputs only.
- `--safe` keeps the run in a no-live-calls mode.

## Output paths

If `--output-dir` is omitted, reports are written under:

```text
data/batch_validation/{timestamp}/full_pipeline_run/
```

Key outputs:

- `run_summary.json`
- `run_report.md`

## Troubleshooting

- If Windows console output breaks, set:

```powershell
$env:PYTHONIOENCODING='utf-8'
```

- If you do not intend to rerun Stage 3 or Stage 4, use `--dry-run` or the stage-specific official entrypoints instead.

