# 运行 Figure Atlas

## 用途

使用 `scripts/run_figure_atlas.py` 从已有 Stage 3 / Stage 4 / Stage 5 结果生成 figure atlas。

## 重要原则

figure atlas 是下游只读层。

它只读取已有结果，不会重跑：

- Stage 3
- Stage 4
- Stage 5

## 当前支持的参数

- `--outputs-dir`
- `--batch-final-export-dir`
- `--stage3-analysis-dir`
- `--stage3-publication-dir`
- `--batch-output-dir`
- `--audit-only`
- `--generate-figures`
- `--skip-auto-figures`
- `--max-auto-figures`
- `--continue-on-error`

## 只做 audit

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --audit-only
```

## 生成图

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures `
  --max-auto-figures 50
```

## 输出结构

```text
data/batch_validation/{timestamp}/figure_atlas/
  audit/
  tables/
  figure_data/
  figures/
  figure_atlas_manifest.json
  figure_index.csv
  figure_atlas_readme.md
```

### `audit/`

- `result_inventory.json`
- `result_inventory.md`
- `data_availability_matrix.csv`
- `figure_feasibility_matrix.csv`
- `input_table_schema_report.json`
- `input_table_schema_report.md`

### `tables/`

- normalized tables
- 每张图对应的 `{figure_id}_source.csv`

### `figure_data/`

- 每张图对应的 `{figure_id}.json`

### `figures/`

- `main/`
- `stage3/`
- `stage4/`
- `stage5/`
- `cross_stage/`
- `qa/`
- `auto/`

## Manifest 与 index

- `figure_atlas_manifest.json`：整体摘要、计数、图元数据和 provenance
- `figure_index.csv`：一张图一行的 atlas 索引

## empty-data figures

有些 atlas 图会显式生成“空数据说明”，而不是静默跳过。这是有意为之，方便 QA。

## Unknown / Other

如果 QA 中出现很多 `Unknown` 或 `Other`，建议检查：

- `normalized_stage4_spectra.csv`
- `normalized_stage5_links.csv`
- `figures/qa/` 下的 QA 图

