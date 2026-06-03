# 故障排查

## 环境或依赖问题

### `ModuleNotFoundError` 或缺依赖

- 确认激活了正确环境
- 运行：

```powershell
pip install -e .
```

兼容方式：

```powershell
pip install -r requirements.txt
```

## Windows 下 Unicode / GBK 问题

常见症状：

- 中文路径输出报错
- `OSError: [Errno 22] Invalid argument`
- 控制台乱码

建议先执行：

```powershell
$env:PYTHONIOENCODING='utf-8'
```

## VPN / 网络 / timeout

主要影响会调用模型或远程服务的阶段。

- Stage 5 batch 不需要 VLM
- figure atlas 不需要 VLM
- Stage 4 live 需要模型访问

## 缺少模型凭据

如果你开启了 Stage 4 live 且凭据缺失：

- 检查 `.env`
- 检查 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY`、`OPENAI_BASE_URL`、`VLM_MODEL_NAME`

## Stage 3 缺失

如果 Stage 5 报 `failed_missing_stage3`：

- 检查 `stage3_twopass/`、`stage3/` 或 `stage3_dspy_smoke/`
- 检查是否有 `stage3_summary.json`
- 确认论文目录是否位于 `data/outputs/{category}/{paper_id}/`

## Stage 4 缺图

如果 Stage 4 出现 `missing_image_path`：

- 检查 `figures.jsonl`
- 检查 `figures_for_vision/`
- 确认 `vision_image_path` 或 `image_path` 能正确解析到本地文件

## Stage 4 谱图结果过少

可能原因：

- Stage 2 本来就没选中很多图
- 很多图本身不可抽取
- 图片路径缺失或不可读
- 只跑过 dry-run，没有实际 live

重点看：

- `stage4a_summary.json`
- `spectra_extractions.jsonl`
- `spectra_failed_records.jsonl`

## Stage 5 `failed_missing_stage3`

- 表示缺少上游 Stage 3
- 在 Stage 3 补齐前不要强行跑 Stage 5

## Stage 5 `failed_missing_stage4`

Stage 5 并不总是因为缺 Stage 4 就硬失败。

- 可能仍然会产出 `partial_success`
- 文本参数和工艺步骤仍可融合

## `failed_linking_exception`

请检查：

- `final_dataset/linking/linking_summary.json`
- `final_dataset/linking/linking_report.md`
- linking candidate 的字段值类型是否异常

当前版本中，`source_value / target_value` 的 dict 标量化问题已经修过。

## `zero_evidence_links`

含义：

- 有 evidence objects
- 但没有 materialize 出 evidence-to-parameter links

通常这是 coverage 问题，不一定是崩溃。

## `zero_spectra_links`

含义：

- 有 spectra
- 但没有生成 spectra-to-parameter links

建议检查：

- `spectra_parameter_links.csv`
- per-paper `linking/links.jsonl`

## `zero_process_step_links`

含义：

- 有 process steps
- 但没有生成 process-step-to-parameter links

这往往是 deterministic linking coverage 偏弱，而不是执行失败。

## `dry_run_only_spectra`

含义：

- Stage 4 曾经有 dry-run 谱图记录
- 但没有可用于 Stage 5 的 live / fallback 成功谱图

这种情况下 Stage 5 仍可能产出文本融合结果，但状态往往是 `partial_success`。

## figure_atlas 中 Unknown / Other 太多

含义：

- 归一化无法把足够多的记录归到更具体的 family
- 可能是输入质量问题，也可能是 taxonomy 覆盖不足

建议看：

- `tables/normalized_stage4_spectra.csv`
- `tables/normalized_stage5_links.csv`
- `figures/qa/` 下的 QA 图

## figure_atlas 的 empty-data note 图

这通常是预期行为。

atlas 可以明确生成一个“空数据说明图”，而不是静默跳过。这样更利于 QA。

## `git status` 里出现大量 data 输出

不要提交：

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## 安全补跑策略

- 先用 `--dry-run`
- 尽量先用 `--skip-existing`
- 支持时优先用 `--only-incomplete`
- 只有在明确需要覆盖时再用 `--force`

## 如何检查 report CSV

Stage 5 batch 常看：

- `stage5_batch_paper_summary.csv`
- `stage5_batch_failure_manifest.csv`
- `stage5_batch_quality_summary.csv`
- `stage5_batch_overall_summary.json`

figure atlas 常看：

- `audit/result_inventory.md`
- `audit/data_availability_matrix.csv`
- `audit/figure_feasibility_matrix.csv`
- `figure_index.csv`

