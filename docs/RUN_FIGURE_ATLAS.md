# Run Figure Atlas

`figure_atlas` is the maintained batch-level figure generation path for Stage 3,
Stage 4, and Stage 5 analysis outputs.

It only reads existing results from:

- Stage 3 analysis outputs
- Stage 4 per-paper spectra outputs
- Stage 5 batch final exports

It does not:

- rerun Stage 3 / Stage 4 / Stage 5
- call LLM / VLM models
- overwrite per-paper outputs under `data/outputs`
- archive or delete legacy code as part of runtime execution

`scripts/run_research_figures.py` remains in the repository only for legacy
compatibility. New batch-level figure work should use `scripts/run_figure_atlas.py`.

## Audit only

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --audit-only
```

## Full atlas

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures `
  --max-auto-figures 50 `
  --continue-on-error
```

## Output layout

`data/batch_validation/{timestamp}/figure_atlas/`

- `audit/`
- `tables/`
- `figure_data/`
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
