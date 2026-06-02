# RUN_FIGURE_ATLAS

`figure_atlas` 是一个新的 Stage3 / Stage4 / Stage5 批量科研图谱模块。

它只读取已有结果：

- Stage3 analysis outputs
- Stage4 per-paper spectra outputs
- Stage5 batch final exports

它不会：

- 重跑 Stage3 / Stage4 / Stage5
- 调用 LLM / VLM
- 写入 `data/outputs` 下新的 per-paper 结果

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
