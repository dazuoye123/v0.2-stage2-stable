# 流程详解

## 端到端数据流

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

## Stage 3

- 读取：论文 Markdown、清洗后的正文、procedure sections 等
- 输出：参数、样品、工艺步骤、证据对象以及 Stage 3 summary
- 成功标志：`stage3_summary.json` 存在且 JSONL 输出非空
- 常见 warning：证据稀疏、procedure section 缺失、参数抽取不完整
- 何时重跑：Stage 3 缺失或明显失真
- 不该重跑的情况：只是想做 Stage 5、batch export 或 figure atlas

## Stage 4

- 读取：
  - `figures.jsonl` 中的 Stage 2 已筛图
  - 缺失时 fallback `figures_for_vision/`
  - Stage 3 文本上下文
- 输出：
  - `spectra_extractions.jsonl`
  - `raw_vlm_outputs.jsonl`
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json`
- 成功标志：
  - 预期图已经处理或有明确 skip 原因
  - summary 存在
- 常见 warning：
  - `missing_image_path`
  - fallback reuse
  - dry-run summary
- 何时重跑：
  - 实际没跑 live
  - 仍有 retryable failures
- 不该重跑的情况：
  - 你只想基于现有结果继续做 Stage 5 或出图

## Stage 5

- 读取：
  - Stage 3 输出
  - Stage 4 的有效谱图结果
- 明确排除：
  - dry-run spectra
  - failed records
  - raw-only records
- 输出：
  - `final_dataset/`
  - `stage5_summary.json`
  - linking 结果
  - per-paper link-aware 导出
- 成功标志：
  - `final_dataset/` 完整
  - 如果开启 linking，则 `linking/` 和 `link_aware_exports/` 存在
- 常见 warning：
  - `dry_run_only_spectra`
  - `zero_evidence_links`
  - `zero_spectra_links`
  - `zero_process_step_links`

## deterministic linking

- 读取：
  - Stage 5 融合后的参数
  - evidence
  - spectra
  - samples
  - process steps
- 输出：
  - linking candidates
  - accepted links
  - linking summary
- 某一类 link 为空，不应直接让整篇失败

## link-aware export

- 读取：
  - `final_dataset/`
  - `final_dataset/linking/`
- 输出：
  - `final_dataset/link_aware_exports/`
- 用途：
  - 单篇下游分析
  - 后续 batch 聚合

## batch final export

- 读取：
  - 各篇论文的 `final_dataset/link_aware_exports/`
- 输出：
  - `data/outputs/_batch_final_exports/`
- 成功标志：
  - 聚合 CSV 和 summary JSON 存在

## figure atlas

- 只读取已有结果：
  - batch final exports
  - Stage 4 per-paper spectra outputs
  - 可选的 Stage 3 analysis 目录
- 输出：
  - audit
  - normalized tables
  - per-figure source CSV / JSON
  - 成图
- 不会重跑 Stage 3 / 4 / 5

## 验收检查点

### Stage 3 检查点

- 读取：Markdown
- 输出：Stage 3 JSON / JSONL
- 关键文件：`stage3_summary.json`、`parameters.jsonl`、`process_steps.jsonl`
- 成功标志：结构化输出非空

### Stage 4 检查点

- 读取：Stage 2 已筛图和 Stage 3 上下文
- 输出：Stage 4 谱图结果
- 关键文件：`spectra_extractions.jsonl`、`stage4a_summary.json`
- 成功标志：有 live/fallback 成功记录，且 summary 合理

### Stage 5 检查点

- 读取：Stage 3 + Stage 4
- 输出：`final_dataset/`
- 关键文件：`stage5_summary.json`、`parameters.jsonl`、`process_steps.jsonl`、`spectra.jsonl`
- 成功标志：Stage 5 输出存在，状态不是 failed

### Linking 检查点

- 读取：`final_dataset/`
- 输出：`final_dataset/linking/`
- 关键文件：`links.jsonl`、`linking_summary.json`
- 成功标志：输出存在；即使某些 link family 为空，也不应直接崩

### figure atlas 检查点

- 读取：batch final export 和已有阶段输出
- 输出：audit、normalized tables、figure bundles
- 关键文件：`figure_atlas_manifest.json`、`figure_index.csv`
- 成功标志：audit-only 模式能给出有效 inventory，生成模式能写出 manifest 和图索引

