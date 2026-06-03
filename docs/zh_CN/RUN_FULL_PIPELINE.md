# 运行 Full Pipeline

## 用途

当你需要使用当前维护中的顶层官方编排入口时，使用 `scripts/run_full_pipeline.py`。

## 适用场景

- 受控的全流程运行
- dry-run 规划
- 选择性补跑上游阶段
- 在省略 `--markdown-dir` 时，走已有结果的 Stage 5-only 编排路径

## 最小命令

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs"
```

## 常见命令

Dry-run：

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --dry-run `
  --safe
```

指定论文：

```powershell
python .\scripts\run_full_pipeline.py `
  --markdown-dir ".\data\markdown" `
  --outputs-dir ".\data\outputs" `
  --paper-ids "paper_a,paper_b"
```

## 重要参数

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

## Stage 4 alias 说明

当前仍接受以下 legacy alias：

- `--live-stage4a`
- `--force-stage4a`
- `--max-stage4a-papers`
- `--max-stage4a-figures-per-paper`
- `--stage4a-figure-types`

但新文档统一推荐使用 Stage 4 命名。

## dry-run 与 safe 行为

- `--dry-run`：只输出计划和报告，不进行真实执行
- `--safe`：保持在不触发 live 调用的模式下运行

## 输出路径

如果不显式传 `--output-dir`，报告默认写到：

```text
data/batch_validation/{timestamp}/full_pipeline_run/
```

关键输出：

- `run_summary.json`
- `run_report.md`

## 排查建议

- Windows 控制台编码有问题时，先执行：

```powershell
$env:PYTHONIOENCODING='utf-8'
```

- 如果你本轮并不想真正补跑 Stage 3 或 Stage 4，优先用 `--dry-run` 或改用更具体的官方单阶段入口。

