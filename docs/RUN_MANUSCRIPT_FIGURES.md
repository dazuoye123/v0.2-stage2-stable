# Run Manuscript Figures

## Dry run

```powershell
python .\scripts\run_manuscript_figures.py `
  --diagnosis-dir ".\data\batch_validation\20260602_212510\manuscript_figure_diagnosis" `
  --output-dir ".\data\batch_validation\20260602_212510\manuscript_figures_nature_v1" `
  --figures Fig1 Fig2 Fig4 `
  --dry-run
```

## Generate figures

```powershell
python .\scripts\run_manuscript_figures.py `
  --diagnosis-dir ".\data\batch_validation\20260602_212510\manuscript_figure_diagnosis" `
  --output-dir ".\data\batch_validation\20260602_212510\manuscript_figures_nature_v1" `
  --figures Fig1 Fig2 Fig4 `
  --continue-on-error
```
