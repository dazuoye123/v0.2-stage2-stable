# 运行 Stage 5 Batch

## 用途

使用 `scripts/run_stage5_batch.py` 批量运行 Stage 5 融合，以及可选的 linking/export。

## 默认行为

- 读取已有 Stage 3 和 Stage 4 输出
- 不调用 VLM
- linking 默认走 deterministic linking
- 如果没有 `--force`，则等效会启用 `--skip-existing`

## 当前支持的参数

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

## 推荐命令

Dry-run：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --dry-run `
  --limit 10
```

只跑 Stage 5：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --stage5-only `
  --skip-existing `
  --workers 1
```

Stage 5 + linking：

```powershell
python .\scripts\run_stage5_batch.py `
  --outputs-dir ".\data\outputs" `
  --report-dir ".\data\analysis_outputs_stage5_batch" `
  --with-linking `
  --skip-existing `
  --continue-on-error `
  --workers 1
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

## 关键行为说明

### `--dry-run`

- 只规划运行
- 仍会写 batch 报告
- 不写 per-paper Stage 5 结果

### `--skip-existing`

- 会跳过已经完整的 Stage 5 输出
- 这是默认更安全的行为

### `--only-incomplete`

- 会先筛出缺少 Stage 5 / linking/export 必需文件的论文
- 再应用 `--limit`

### `--force`

- 会覆盖 Stage 5 结果
- 只建议在受控修复或补跑场景下使用

## 报告文件

batch runner 会写：

- `stage5_batch_paper_summary.csv`
- `stage5_batch_failure_manifest.csv`
- `stage5_batch_quality_summary.csv`
- `stage5_batch_overall_summary.json`
- `stage5_batch_run_report.md`

## 常见 warning

- `missing_stage4a_but_stage5_partial_ok`
- `dry_run_only_spectra`
- `no_stage4a_live_spectra`
- `empty_parameters`
- `zero_process_steps`
- `zero_evidence_links`
- `zero_spectra_links`
- `zero_process_step_links`
- `zero_sample_matrix`

