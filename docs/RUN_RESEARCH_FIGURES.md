# RUN_RESEARCH_FIGURES (Legacy)

`scripts/run_research_figures.py` and `alumina_sol_extractor.research_figures`
are retained only for backward compatibility.

## Use this instead

For maintained batch-level figure generation, use:

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures
```

## Why this file still exists

- older notes and scripts may still reference `run_research_figures.py`
- older tests still verify the compatibility layer
- removing it immediately would create avoidable churn

This path should not be treated as the primary documented entrypoint anymore.
