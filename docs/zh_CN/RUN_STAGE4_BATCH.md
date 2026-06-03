# 运行 Stage 4 Batch

## 用途

使用 `scripts/run_stage4_batch.py` 运行当前维护中的 Stage 4 批量流程。

## 输入布局

Stage 4 期望 per-paper 目录位于：

```text
data/outputs/{category}/{paper_id}/
```

它会使用：

- 默认来自 `stage3_twopass/` 的 Stage 3 上下文
- `figures.jsonl` 中的 Stage 2 已筛图
- 必要时 fallback 到 `figures_for_vision/`

## 最小命令

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs"
```

## 当前支持的参数

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

## 行为说明

- 默认是 dry-run
- `--live` 会开启真实 Stage 4 提取
- `--force-stage4` 会在重跑前删除该论文已有的 Stage 4 输出目录
- 不加 `--force-stage4` 时，如果 `stage4a_summary.json` 已经是 live-success 状态，runner 可能直接 skip
- `--stage4-figure-ids` 可以只针对指定 figure 运行

## 输出位置

单篇 Stage 4 输出默认写到：

```text
data/outputs/{category}/{paper_id}/stage4_vision_spectra_universal/
```

Batch 报告默认写到：

```text
data/batch_validation/{timestamp}/stage4_batch/
```

Batch 报告文件：

- `stage4_batch_rows.jsonl`
- `stage4_batch_summary.json`
- `stage4_batch_report.md`

## 备注

- `stage4a_summary.json` 这个文件名仍然保留，是兼容历史结果格式
- `Stage4A` 只是旧名；当前文档主流程统一写 `Stage 4`

