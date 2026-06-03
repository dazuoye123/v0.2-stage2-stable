# 输入输出规范

## 必需输入布局

当前维护中的标准目录结构是：

```text
data/outputs/{category}/{paper_id}/
```

当前 batch 工作流支持的分类：

- `mechanism`
- `fiber_process`
- `applications`
- `rheology`

部分 discovery 代码也兼容扁平结构 `data/outputs/{paper_id}/`，但主库推荐仍然是带 category 的结构。

## 单篇 Stage 3 输出

可能的 Stage 3 目录：

- `stage3_twopass/`
- `stage3/`
- `stage3_dspy_smoke/`

当前代码常引用的 Stage 3 文件包括：

- `stage3_summary.json`
- `paper_extraction.schema_v2.json`
- `parameters.jsonl`
- `samples.jsonl`
- `process_steps.jsonl`
- `evidence_objects.jsonl`
- `quality_summary.json`

## 单篇 Stage 4 输出

可能的 Stage 4 目录：

- `stage4_vision_spectra_universal/`
- `stage4_vision_spectra/`

常见文件：

- `stage4a_summary.json`（文件名保留了 legacy 形式）
- `spectra_extractions.jsonl`
- `raw_vlm_outputs.jsonl`
- `spectra_failed_records.jsonl`

如果有额外 review / reparse 文件，应视为辅助文件，而不是主成功输入。

## 单篇 Stage 5 输出

目录：

```text
data/outputs/{category}/{paper_id}/final_dataset/
```

期望文件：

- `stage5_summary.json`
- `paper.json`
- `samples.jsonl`
- `parameters.jsonl`
- `process_steps.jsonl`
- `evidence.jsonl`
- `figures.jsonl`
- `spectra.jsonl`
- `quality_summary.json`
- `fusion_report.md`

## 单篇 linking 输出

目录：

```text
final_dataset/linking/
```

常见文件：

- `link_candidates.jsonl`
- `links.jsonl`
- `unmatched_candidates.jsonl`
- `rejected_links.jsonl`
- `raw_llm_linking_outputs.jsonl`
- `linking_summary.json`
- `linking_report.md`

说明：

- 当前官方 Stage 5 batch 默认走确定性 linking
- live linking 辅助仍然存在，但不是主流程默认路径

## 单篇 link-aware export 输出

目录：

```text
final_dataset/link_aware_exports/
```

常见文件：

- `final_parameters_linked.csv`
- `sample_parameter_matrix.csv`
- `evidence_parameter_links.csv`
- `process_step_parameter_links.csv`
- `spectra_parameter_links.csv`
- `process_steps_table.csv`
- `final_showcase_table.csv`
- `link_aware_export_summary.json`
- `link_aware_export_readme.md`
- `link_aware_export_diagnosis.md`

后续实现如果扩展，可能会出现更多 optional 文件。

## 批量最终导出

目录：

```text
data/outputs/_batch_final_exports/
```

当前批量导出文件：

- `all_papers_final_parameters_linked.csv`
- `all_papers_evidence_parameter_links.csv`
- `all_papers_process_step_parameter_links.csv`
- `all_papers_spectra_parameter_links.csv`
- `all_papers_process_steps_table.csv`
- `all_papers_sample_parameter_matrix.csv`
- `all_papers_final_showcase_table.csv`
- `all_papers_link_aware_summary.json`
- `all_papers_export_report.md`

主要用途：

- `all_papers_final_parameters_linked.csv`：跨论文参数主表
- `all_papers_evidence_parameter_links.csv`：证据到参数的聚合链接表
- `all_papers_process_step_parameter_links.csv`：工艺步骤到参数的聚合链接表
- `all_papers_spectra_parameter_links.csv`：谱图到参数的聚合链接表
- `all_papers_process_steps_table.csv`：聚合后的工艺步骤表
- `all_papers_sample_parameter_matrix.csv`：sample-by-parameter 矩阵行表
- `all_papers_final_showcase_table.csv`：更适合下游展示和摘要整理的总表

## figure atlas 输出

目录：

```text
data/batch_validation/{timestamp}/figure_atlas/
```

重要文件：

- `audit/result_inventory.json`
- `audit/result_inventory.md`
- `audit/data_availability_matrix.csv`
- `audit/figure_feasibility_matrix.csv`
- `audit/input_table_schema_report.json`
- `audit/input_table_schema_report.md`
- `tables/normalized_parameters.csv`
- `tables/normalized_process_steps.csv`
- `tables/normalized_stage4_spectra.csv`
- `tables/normalized_stage4_peaks.csv`
- `tables/normalized_stage5_links.csv`
- `tables/normalized_sample_matrix.csv`
- `tables/{figure_id}_source.csv`
- `figure_data/{figure_id}.json`
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

## 可以安全重生成的内容

- `data/outputs/_batch_final_exports/` 可以根据 per-paper `link_aware_exports/` 重新生成
- `data/batch_validation/{timestamp}/figure_atlas/` 可以根据已有 Stage 3 / Stage 4 / Stage 5 结果和 batch export 重新生成

## 不建议随意删除的内容

- `data/outputs/{category}/{paper_id}/stage3_*`
- `data/outputs/{category}/{paper_id}/stage4_vision_spectra_universal/`
- `data/outputs/{category}/{paper_id}/final_dataset/`

