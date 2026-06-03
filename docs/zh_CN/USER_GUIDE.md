# 用户手册

## 项目概览

`alumina_sol_extractor` 用于从氧化铝溶胶与氧化铝纤维文献中抽取结构化研究数据。

当前维护中的主流程包括：

- Stage 3 文本抽取：样品、参数、证据、工艺步骤
- Stage 4 图像与谱图抽取
- Stage 5 融合、确定性链接（deterministic linking）与链接感知导出（link-aware export）
- 跨论文批量导出
- 基于已有结果生成 figure atlas（图谱集）

## 推荐流程

```text
PDF / Markdown
  -> Stage1 / Stage2 预处理
  -> Stage3 文本抽取
  -> Stage4 图像与谱图抽取
  -> Stage5 融合
  -> deterministic linking
  -> link-aware export
  -> batch final export
  -> figure_atlas
```

## 环境配置

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

兼容安装方式：

```powershell
pip install -r requirements.txt
```

如果在 Windows 下处理中文路径或长输出，建议先设置：

```powershell
$env:PYTHONIOENCODING='utf-8'
```

## 目录结构

```text
data/
  outputs/
  batch_validation/
  analysis_outputs_stage3_v2/
src/alumina_sol_extractor/
scripts/
docs/
tests/
archive/
```

- `src/`：维护中的运行时代码
- `scripts/`：官方 CLI 入口
- `archive/`：历史工具实现归档
- `data/`：本地输入与运行输出，不应提交

## 官方入口

### `scripts/run_full_pipeline.py`

- 用途：官方顶层编排入口
- 适用场景：全流程控制运行、dry-run 规划、小范围恢复执行
- 读取：PDF、Markdown、Stage 3/4 结果以及已有 per-paper 输出
- 输出：批量报告及后续阶段结果
- 是否调用模型：取决于是否开启 live Stage 3 / Stage 4 / linking
- 是否可能重跑上游：会，取决于参数

### `scripts/run_stage4_batch.py`

- 用途：只跑 Stage 4 批量
- 适用场景：已有 per-paper 输出，只想补或跑 Stage 4
- 读取：`data/outputs/{category}/{paper_id}`、Stage 3 上下文、Stage 2 已筛图
- 输出：`stage4_vision_spectra_universal/` 和批量报告
- 是否调用模型：`--live` 时会；默认 dry-run 不会

### `scripts/run_stage5_batch.py`

- 用途：批量执行 Stage 5 融合，以及可选的 linking/export
- 适用场景：Stage 3 和 Stage 4 已经存在
- 读取：per-paper Stage 3 / Stage 4 输出
- 输出：`final_dataset/`、`linking/`、`link_aware_exports/`、批量报告
- 是否调用模型：不会；当前官方 Stage 5 batch 走确定性 linking

### `scripts/export_link_aware_dataset.py`

- 用途：基于已有 `final_dataset/` 重新导出单篇 link-aware 表格

### `scripts/export_batch_link_aware_dataset.py`

- 用途：把很多论文的 `link_aware_exports/` 聚合成批量导出

### `scripts/run_figure_atlas.py`

- 用途：基于现有 Stage 3 / 4 / 5 结果生成 figure atlas
- 是否调用模型：不会
- 是否重跑上游：不会

## Full pipeline 用法

```powershell
python .\scripts\run_full_pipeline.py `
  --pdf-dir ".\data\pdfs" `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "example_paper" `
  --export-link-aware
```

重要参数：

- `--pdf-dir`
- `--markdown-dir`
- `--outputs-dir`
- `--paper-ids`
- `--max-papers`
- `--live-stage3`
- `--live-stage4`
- `--force-stage3`
- `--force-stage4`
- `--force-stage5`
- `--export-link-aware`
- `--dry-run`
- `--safe`

Legacy alias：

- `--live-stage4a` -> `--live-stage4`
- `--force-stage4a` -> `--force-stage4`
- `--max-stage4a-papers` -> `--max-stage4-papers`
- `--max-stage4a-figures-per-paper` -> `--max-stage4-figures-per-paper`
- `--stage4a-figure-types` -> `--stage4-figure-types`

## Stage 4 batch 用法

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs" `
  --continue-on-error
```

Stage 4 默认使用：

- `figures.jsonl` 中的 Stage 2 已筛图
- 缺失时 fallback 到 `figures_for_vision/`
- 默认从 `stage3_twopass/` 读取上下文

默认 per-paper 输出目录：

- `stage4_vision_spectra_universal/`

## Stage 5 batch 用法

带 linking 的 Stage 5 batch：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --skip-existing `
  --continue-on-error `
  --workers 1
```

Dry-run：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --dry-run `
  --limit 10
```

只处理不完整论文：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --only-incomplete `
  --skip-existing
```

## 批量 link-aware export 用法

```powershell
python .\scripts\export_batch_link_aware_dataset.py `
  --outputs-dir ".\data\outputs" `
  --output-dir ".\data\outputs\_batch_final_exports"
```

## figure atlas 用法

只做 audit：

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --audit-only
```

生成图：

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures `
  --max-auto-figures 50
```

## 如何理解输出状态

- `success`：该阶段已正常产出
- `partial_success`：有可用结果，但存在 warning 或覆盖不足
- `failed`：该阶段未形成有效结果
- `warning`：非阻断问题，需要后续检查
- `dry_run_spectra_excluded`：Stage 5 明确排除了 dry-run 谱图记录
- `zero_evidence_links` / `zero_spectra_links` / `zero_process_step_links`：某类链接为空
- `Unknown / Other`：无法进一步归一化或分类

## 常见使用场景

### 我已经有 Stage 3 和 Stage 4，只想跑 Stage 5

用 `scripts/run_stage5_batch.py`

### 我只想重新生成批量导出

用 `scripts/export_batch_link_aware_dataset.py`

### 我只想基于已有结果生成图

用 `scripts/run_figure_atlas.py`

### 我只想检查哪些 Stage 5 不完整

用 `scripts/run_stage5_batch.py --only-incomplete --dry-run`

### 我想强制重跑一个小批次

谨慎使用 `--force`。只有确定覆盖 `final_dataset/` 是安全的，才建议这样做。

### 我想在出图前先做 audit

用 `scripts/run_figure_atlas.py --audit-only`

## 不要提交的内容

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

